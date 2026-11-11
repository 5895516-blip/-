"""Логика бота: выдача уроков, проверка подписки, админ-панель, рассылки."""
from __future__ import annotations

import html
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from config import Config
from db import DB
from tg import Telegram, TgError, TgNetworkError

log = logging.getLogger("bot")

PAGE_SIZE = 8
MAX_TITLE = 100
MAX_DESCRIPTION = 800
MAX_TEXT_LESSON = 3000
MAX_SETTING_TEXT = 1500

DEFAULT_WELCOME = "Привет! 👋\nЗдесь собраны мои уроки. Выбери нужный:"
DEFAULT_SUB_TEXT = (
    "Уроки доступны только подписчикам 🙌\n\n"
    "Подпишись, а потом нажми «Я подписался» — и я сразу пришлю материалы."
)

# Вид материала -> (метод Bot API, подпись для админа)
MEDIA = {
    "photo": ("sendPhoto", "фото"),
    "video": ("sendVideo", "видео"),
    "animation": ("sendAnimation", "GIF"),
    "document": ("sendDocument", "файл"),
    "audio": ("sendAudio", "аудио"),
    "voice": ("sendVoice", "голосовое"),
    "video_note": ("sendVideoNote", "кружок"),
}
CODE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
URL_RE = re.compile(r"^(https?://\S+|[\w-]+(\.[\w-]+)+([/?#]\S*)?)$")


def esc(text) -> str:
    return html.escape(str(text or ""), quote=False)


def btn(text: str, data: str | None = None, url: str | None = None) -> dict:
    return {"text": text, "url": url} if url else {"text": text, "callback_data": data}


def ikb(rows: list) -> dict:
    return {"inline_keyboard": [r for r in rows if r]}


def extract_content(m: dict):
    """Достаёт из сообщения админа материал урока: (вид, содержимое) или None."""
    if m.get("photo"):
        return "photo", m["photo"][-1]["file_id"]
    for kind in ("video", "animation", "document", "audio", "voice", "video_note"):
        if m.get(kind):
            return kind, m[kind]["file_id"]
    text = (m.get("text") or "").strip()
    if not text:
        return None
    if URL_RE.match(text):
        return "url", text if text.lower().startswith(("http://", "https://")) else "https://" + text
    return "text", text


class App:
    def __init__(self, config: Config, tg: Telegram | None = None, db: DB | None = None):
        self.config = config
        self.tg = tg or Telegram(config.token, config.api_url)
        self.db = db or DB(config.db_path)
        self.me: dict = {}
        self.states: dict = {}  # шаги диалогов админа: {user_id: {"s": "...", ...}}
        self.stop = threading.Event()
        self.pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="upd")
        self.broadcast_delay = 0.05  # ~20 сообщений в секунду, с запасом от лимитов Telegram
        self.poll_timeout = 50
        self._broadcast_lock = threading.Lock()
        self._broadcast_thread: threading.Thread | None = None
        self._channel_warned: dict = {}

    # ================= запуск =================

    def setup(self) -> None:
        self.me = self.tg.call("getMe")
        log.info("Бот @%s запущен", self.me.get("username"))
        try:
            self.tg.call(
                "setMyCommands",
                commands=[
                    {"command": "start", "description": "Открыть уроки"},
                    {"command": "lessons", "description": "Список уроков"},
                ],
            )
        except (TgError, TgNetworkError) as e:
            log.warning("Не удалось задать меню команд: %s", e)
        if not self.config.admin_ids:
            log.warning("ADMIN_IDS пуст: админ-панель недоступна. Узнай свой ID командой /id и впиши в .env")

    def run(self) -> None:
        self.setup()
        offset = None
        backoff = 1
        while not self.stop.is_set():
            try:
                updates = self.tg.call(
                    "getUpdates",
                    _timeout=self.poll_timeout + 15,
                    offset=offset,
                    timeout=self.poll_timeout,
                    allowed_updates=["message", "callback_query", "my_chat_member"],
                )
                backoff = 1
            except TgNetworkError as e:
                log.warning("Нет связи с Telegram (%s), повтор через %s с", e, backoff)
                self.stop.wait(backoff)
                backoff = min(backoff * 2, 30)
                continue
            except TgError as e:
                if e.code == 401:
                    raise SystemExit("Telegram не принял BOT_TOKEN (401). Проверь токен в .env.")
                if e.code == 409:
                    log.error("Бот уже запущен где-то ещё с этим же токеном. Останови вторую копию.")
                else:
                    log.error("Ошибка getUpdates: %s", e)
                self.stop.wait(5)
                continue
            for update in updates or []:
                offset = update["update_id"] + 1
                self.pool.submit(self.handle_update, update)
        self.pool.shutdown(wait=True)

    def handle_update(self, update: dict) -> None:
        try:
            if "message" in update:
                self.on_message(update["message"])
            elif "callback_query" in update:
                self.on_callback(update["callback_query"])
            elif "my_chat_member" in update:
                self.on_my_chat_member(update["my_chat_member"])
        except TgError as e:
            if e.code == 403:  # пользователь заблокировал бота, пока мы отвечали
                uid = self._update_user_id(update)
                if uid:
                    self.db.set_blocked(uid, True)
            else:
                log.exception("Ошибка Telegram при обработке сообщения")
        except Exception:
            log.exception("Ошибка при обработке сообщения")

    @staticmethod
    def _update_user_id(update: dict):
        for key in ("message", "callback_query", "my_chat_member"):
            if key in update:
                return (update[key].get("from") or {}).get("id")
        return None

    # ================= помощники =================

    def is_admin(self, uid: int) -> bool:
        return uid in self.config.admin_ids

    def send(self, chat_id: int, text: str, kb: dict | None = None, **extra):
        return self.tg.call(
            "sendMessage",
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=kb,
            link_preview_options={"is_disabled": True},
            **extra,
        )

    def show(self, chat_id: int, text: str, kb: dict | None = None, mid: int | None = None):
        """Обновляет сообщение с меню на месте, а если нельзя — присылает новое."""
        if mid:
            try:
                return self.tg.call(
                    "editMessageText",
                    chat_id=chat_id,
                    message_id=mid,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=kb,
                    link_preview_options={"is_disabled": True},
                )
            except TgError as e:
                if "not modified" in e.description:
                    return None
        return self.send(chat_id, text, kb)

    def answer(self, cq: dict, text: str | None = None, alert: bool = False) -> None:
        cq["_answered"] = True
        try:
            self.tg.call("answerCallbackQuery", callback_query_id=cq["id"], text=text, show_alert=alert or None)
        except (TgError, TgNetworkError):
            pass

    @property
    def protect(self) -> bool:
        return self.db.get_setting("protect", "0") == "1"

    def lesson_link(self, lesson) -> str:
        return f"https://t.me/{self.me.get('username', 'бот')}?start={lesson['code']}"

    # ================= входящие сообщения =================

    def on_message(self, m: dict) -> None:
        if (m.get("chat") or {}).get("type") != "private" or not m.get("from"):
            return
        user = m["from"]
        uid = user["id"]
        text = (m.get("text") or "").strip()

        if text.startswith("/"):
            cmd, _, arg = text.partition(" ")
            cmd = cmd.split("@")[0].lower()
            arg = arg.strip()
            if cmd == "/start":
                self.states.pop(uid, None)
                return self.cmd_start(user, arg)
            self.db.upsert_user(uid, user.get("username"), user.get("first_name"))
            if cmd in ("/lessons", "/menu"):
                self.states.pop(uid, None)
                if self.gate(uid):
                    self.send_menu(uid)
                return
            if cmd == "/id":
                self.send(uid, f"Твой Telegram ID: <code>{uid}</code>")
                return
            if cmd == "/help":
                extra = "\n/admin — панель управления" if self.is_admin(uid) else ""
                self.send(uid, "/start — открыть уроки\n/lessons — список уроков" + extra)
                return
            if self.is_admin(uid) and cmd in ("/admin", "/cancel"):
                self.states.pop(uid, None)
                return self.admin_home(uid)
        else:
            self.db.upsert_user(uid, user.get("username"), user.get("first_name"))

        if self.is_admin(uid) and uid in self.states:
            return self.admin_input(uid, m)
        self.send(uid, "Чтобы открыть уроки, нажми /start")

    def cmd_start(self, user: dict, payload: str) -> None:
        uid = user["id"]
        payload = payload if CODE_RE.match(payload or "") else ""
        self.db.upsert_user(uid, user.get("username"), user.get("first_name"), payload or None)
        if payload:
            self.db.set_pending(uid, payload)
        if self.gate(uid):
            self.deliver(uid)

    def on_my_chat_member(self, upd: dict) -> None:
        if (upd.get("chat") or {}).get("type") != "private":
            return
        status = (upd.get("new_chat_member") or {}).get("status")
        uid = upd["chat"]["id"]
        if status == "kicked":
            self.db.set_blocked(uid, True)
        elif status == "member":
            self.db.set_blocked(uid, False)

    # ================= проверка подписки =================

    def missing_channels(self, uid: int) -> list:
        """Каналы, на которые человек ещё не подписан."""
        missing = []
        for ch in self.db.channels():
            try:
                member = self.tg.call("getChatMember", chat_id=ch["chat_id"], user_id=uid)
            except TgNetworkError:
                continue  # сбой сети — не наказываем пользователя
            except TgError as e:
                # Обычно это значит, что бота убрали из админов канала. Пропускаем людей и зовём админа.
                self._warn_channel(ch, e)
                continue
            status = member.get("status")
            subscribed = status in ("creator", "administrator", "member") or (
                status == "restricted" and member.get("is_member")
            )
            if not subscribed:
                missing.append(ch)
        return missing

    def _warn_channel(self, ch, error: TgError) -> None:
        log.warning("Не могу проверить подписку на %s: %s", ch["title"], error)
        now = time.time()
        if now - self._channel_warned.get(ch["chat_id"], 0) < 3600:
            return
        self._channel_warned[ch["chat_id"]] = now
        for admin_id in self.config.admin_ids:
            try:
                self.send(
                    admin_id,
                    f"⚠️ Не могу проверить подписку на «{esc(ch['title'])}» — пока пропускаю всех без проверки.\n"
                    "Убедись, что я добавлен в этот канал администратором.",
                )
            except (TgError, TgNetworkError):
                pass

    def gate(self, uid: int) -> bool:
        """True — можно выдавать уроки. Иначе присылает просьбу подписаться."""
        missing = self.missing_channels(uid)
        if not missing:
            return True
        rows = [[btn(f"📢 {ch['title']}", url=ch["link"])] for ch in missing]
        rows.append([btn("✅ Я подписался", "checksub")])
        self.send(uid, esc(self.db.get_setting("sub_text", DEFAULT_SUB_TEXT)), ikb(rows))
        return False

    # ================= уроки для учеников =================

    def deliver(self, uid: int) -> None:
        """Выдаёт то, за чем человек пришёл: конкретный урок по ссылке или весь список."""
        code = self.db.pop_pending(uid)
        lesson = self.db.lesson_by_code(code) if code else None
        if lesson and not lesson["hidden"]:
            self.open_lesson(uid, lesson)
        else:
            self.send_menu(uid)

    def menu_content(self, page: int = 0):
        lessons = self.db.lessons()
        text = esc(self.db.get_setting("welcome", DEFAULT_WELCOME))
        if not lessons:
            return text + "\n\n<i>Уроки скоро появятся — я пришлю уведомление.</i>", None
        pages = (len(lessons) - 1) // PAGE_SIZE + 1
        page = max(0, min(page, pages - 1))
        rows = [
            [btn(l["title"], f"l:{l['id']}")] for l in lessons[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
        ]
        if pages > 1:
            nav = []
            if page > 0:
                nav.append(btn("⬅️", f"p:{page - 1}"))
            nav.append(btn(f"{page + 1}/{pages}", "noop"))
            if page < pages - 1:
                nav.append(btn("➡️", f"p:{page + 1}"))
            rows.append(nav)
        return text, ikb(rows)

    def send_menu(self, uid: int, page: int = 0, mid: int | None = None) -> None:
        text, kb = self.menu_content(page)
        self.show(uid, text, kb, mid)

    def lesson_text(self, lesson) -> str:
        text = f"<b>{esc(lesson['title'])}</b>"
        if lesson["description"]:
            text += "\n\n" + esc(lesson["description"])
        if lesson["kind"] == "text":
            text += "\n\n" + esc(lesson["content"])
        return text

    def send_lesson(self, uid: int, lesson) -> None:
        kind, content = lesson["kind"], lesson["content"]
        rows = []
        if kind == "url":
            rows.append([btn("▶️ Открыть урок", url=content)])
        rows.append([btn("📚 Все уроки", "menu")])
        kb = ikb(rows)
        text = self.lesson_text(lesson)
        protect = True if self.protect else None
        if kind in ("url", "text"):
            self.send(uid, text, kb, protect_content=protect)
        elif kind == "video_note":  # у кружков не бывает подписи
            self.tg.call("sendVideoNote", chat_id=uid, video_note=content, protect_content=protect)
            self.send(uid, text, kb)
        else:
            self.tg.call(
                MEDIA[kind][0],
                chat_id=uid,
                caption=text,
                parse_mode="HTML",
                reply_markup=kb,
                protect_content=protect,
                **{kind: content},
            )

    def open_lesson(self, uid: int, lesson) -> None:
        try:
            self.send_lesson(uid, lesson)
        except TgError as e:
            if e.code == 403:
                raise
            log.error("Урок %s не отправился: %s", lesson["id"], e)
            self.send(uid, "Не получилось открыть этот урок 😔 Попробуй чуть позже.")
            return
        self.db.add_view(uid, lesson["id"])

    # ================= нажатия на кнопки =================

    def on_callback(self, cq: dict) -> None:
        user = cq["from"]
        uid = user["id"]
        data = cq.get("data") or ""
        msg = cq.get("message") or {}
        mid = msg.get("message_id")
        try:
            if (msg.get("chat") or {}).get("type") != "private":
                return
            self.db.upsert_user(uid, user.get("username"), user.get("first_name"))
            if data.startswith("a:"):
                if self.is_admin(uid):
                    self.admin_callback(cq, uid, data, mid)
                return

            if data == "checksub":
                if self.missing_channels(uid):
                    self.answer(cq, "Пока не вижу подписки 🙈 Подпишись и нажми кнопку ещё раз.", alert=True)
                    return
                self.answer(cq, "Спасибо за подписку! 🎉")
                try:
                    self.tg.call("deleteMessage", chat_id=uid, message_id=mid)
                except (TgError, TgNetworkError):
                    pass
                self.deliver(uid)
            elif data.startswith("l:"):
                lesson = self.db.lesson(int(data[2:]))
                if not lesson or lesson["hidden"]:
                    self.answer(cq, "Этот урок больше недоступен.", alert=True)
                    self.send_menu(uid, mid=mid)
                    return
                self.db.set_pending(uid, lesson["code"])
                if self.gate(uid):
                    self.db.pop_pending(uid)
                    self.open_lesson(uid, lesson)
            elif data.startswith("p:"):
                self.send_menu(uid, int(data[2:]), mid)
            elif data == "menu":
                if self.gate(uid):
                    self.send_menu(uid)
        finally:
            if not cq.get("_answered"):
                self.answer(cq)

    # ================= админ-панель =================

    def admin_home(self, uid: int, mid: int | None = None) -> None:
        stats = self.db.user_stats()
        text = (
            "<b>Панель управления</b>\n\n"
            f"Пользователей: {stats['total']}\n"
            f"Уроков: {len(self.db.lessons(include_hidden=True))}\n"
            f"Каналов для обязательной подписки: {len(self.db.channels())}"
        )
        kb = ikb(
            [
                [btn("📚 Уроки", "a:ls"), btn("➕ Добавить урок", "a:add")],
                [btn("📢 Рассылка", "a:bc"), btn("📊 Статистика", "a:st")],
                [btn("🔔 Обязательная подписка", "a:ch")],
                [btn("✏️ Тексты", "a:tx"), btn("⚙️ Настройки", "a:set")],
            ]
        )
        self.show(uid, text, kb, mid)

    def admin_callback(self, cq: dict, uid: int, data: str, mid: int | None) -> None:
        parts = data.split(":")
        action = parts[1]
        arg = parts[2] if len(parts) > 2 else ""

        # Любая кнопка, кроме подтверждений и «пропустить», сбрасывает незаконченный диалог.
        if action not in ("skip", "bcok"):
            self.states.pop(uid, None)

        if action in ("home", "cancel"):
            self.admin_home(uid, mid)
        elif action == "ls":
            self.admin_lessons(uid, mid)
        elif action == "add":
            self.states[uid] = {"s": "add_title"}
            self.show(uid, "<b>Новый урок · шаг 1 из 3</b>\n\nПришли название урока.", self.cancel_kb(), mid)
        elif action == "skip":
            st = self.states.get(uid)
            if st and st["s"] == "add_desc":
                st["description"] = ""
                self.ask_content(uid, st, mid)
        elif action == "l":
            self.admin_lesson(uid, int(arg), mid)
        elif action == "e":
            self.admin_edit_start(uid, int(arg), parts[3], mid)
        elif action == "hide":
            lesson = self.db.lesson(int(arg))
            if lesson:
                self.db.update_lesson(lesson["id"], hidden=0 if lesson["hidden"] else 1)
            self.admin_lesson(uid, int(arg), mid)
        elif action in ("up", "dn"):
            self.db.move_lesson(int(arg), -1 if action == "up" else 1)
            self.answer(cq, "Передвинул")
            self.admin_lessons(uid, mid)
        elif action == "view":
            lesson = self.db.lesson(int(arg))
            if lesson:
                self.send_lesson(uid, lesson)
        elif action == "del":
            lesson = self.db.lesson(int(arg))
            if lesson:
                self.show(
                    uid,
                    f"Удалить урок «{esc(lesson['title'])}»? Это нельзя отменить.",
                    ikb([[btn("🗑 Да, удалить", f"a:delok:{arg}"), btn("⬅️ Нет", f"a:l:{arg}")]]),
                    mid,
                )
        elif action == "delok":
            self.db.delete_lesson(int(arg))
            self.answer(cq, "Урок удалён")
            self.admin_lessons(uid, mid)
        elif action == "nt":
            lesson = self.db.lesson(int(arg))
            if lesson:
                count = len(self.db.active_user_ids())
                self.show(
                    uid,
                    f"Отправить всем ({count}) уведомление об уроке «{esc(lesson['title'])}»?",
                    ikb([[btn("📢 Да, отправить", f"a:ntok:{arg}"), btn("⬅️ Нет", f"a:l:{arg}")]]),
                    mid,
                )
        elif action == "ntok":
            self.notify_lesson(uid, int(arg), mid)
        elif action == "bc":
            self.states[uid] = {"s": "bc_wait"}
            self.show(
                uid,
                "<b>Рассылка</b>\n\nПришли сообщение, которое нужно разослать всем: текст, фото, видео, файл — "
                "что угодно. Сначала покажу, как оно будет выглядеть.",
                self.cancel_kb(),
                mid,
            )
        elif action == "bcok":
            st = self.states.pop(uid, None)
            if st and st["s"] == "bc_confirm":
                self.start_copy_broadcast(uid, st["mid"], mid)
        elif action == "st":
            self.admin_stats(uid, mid)
        elif action == "ch":
            self.admin_channels(uid, mid)
        elif action == "chadd":
            self.states[uid] = {"s": "ch_add"}
            self.show(
                uid,
                "<b>Добавить канал или группу</b>\n\n"
                f"1. Добавь меня (@{esc(self.me.get('username'))}) в канал <b>администратором</b>.\n"
                "2. Пришли сюда @username канала, ссылку на него или просто перешли любой пост из канала.",
                self.cancel_kb("a:ch"),
                mid,
            )
        elif action == "chdel":
            self.db.delete_channel(int(arg))
            self.answer(cq, "Убрал")
            self.admin_channels(uid, mid)
        elif action == "tx":
            self.show(
                uid,
                "<b>Тексты бота</b>\n\n"
                f"<b>Приветствие</b> (над списком уроков):\n{esc(self.db.get_setting('welcome', DEFAULT_WELCOME))}\n\n"
                f"<b>Просьба подписаться:</b>\n{esc(self.db.get_setting('sub_text', DEFAULT_SUB_TEXT))}",
                ikb(
                    [
                        [btn("✏️ Изменить приветствие", "a:txe:welcome")],
                        [btn("✏️ Изменить просьбу подписаться", "a:txe:sub_text")],
                        [btn("⬅️ Назад", "a:home")],
                    ]
                ),
                mid,
            )
        elif action == "txe" and arg in ("welcome", "sub_text"):
            self.states[uid] = {"s": "text", "key": arg}
            self.show(uid, "Пришли новый текст одним сообщением.", self.cancel_kb("a:tx"), mid)
        elif action == "set":
            self.admin_settings(uid, mid)
        elif action == "prot":
            self.db.set_setting("protect", "0" if self.protect else "1")
            self.admin_settings(uid, mid)

    @staticmethod
    def cancel_kb(back: str = "a:cancel") -> dict:
        return ikb([[btn("❌ Отмена", back)]])

    # ---------- уроки ----------

    def admin_lessons(self, uid: int, mid: int | None = None) -> None:
        lessons = self.db.lessons(include_hidden=True)
        rows = [[btn(("🙈 " if l["hidden"] else "") + l["title"], f"a:l:{l['id']}")] for l in lessons]
        rows.append([btn("➕ Добавить урок", "a:add")])
        rows.append([btn("⬅️ Назад", "a:home")])
        text = "<b>Уроки</b>\n\nНажми на урок, чтобы изменить его или получить ссылку."
        if not lessons:
            text = "<b>Уроки</b>\n\nПока нет ни одного урока. Добавь первый 👇"
        self.show(uid, text, ikb(rows), mid)

    def admin_lesson(self, uid: int, lesson_id: int, mid: int | None = None) -> None:
        lesson = self.db.lesson(lesson_id)
        if not lesson:
            return self.admin_lessons(uid, mid)
        views = self.db.lesson_views(lesson_id)
        kind = lesson["kind"]
        if kind == "url":
            material = f"ссылка — {esc(lesson['content'])}"
        elif kind == "text":
            material = "текст"
        else:
            material = MEDIA[kind][1]
        text = (
            f"<b>{esc(lesson['title'])}</b>\n"
            f"{esc(lesson['description']) or '<i>без описания</i>'}\n\n"
            f"Материал: {material}\n"
            f"Статус: {'🙈 скрыт от учеников' if lesson['hidden'] else '👁 виден ученикам'}\n"
            f"Открытий: {views['total']} (человек: {views['people']})\n\n"
            "Ссылка на этот урок для Instagram / ChatPlace:\n"
            f"<code>{esc(self.lesson_link(lesson))}</code>"
        )
        i = lesson_id
        kb = ikb(
            [
                [btn("👀 Посмотреть как ученик", f"a:view:{i}")],
                [btn("✏️ Название", f"a:e:{i}:title"), btn("✏️ Описание", f"a:e:{i}:description")],
                [btn("✏️ Материал", f"a:e:{i}:content"), btn("🔗 Код ссылки", f"a:e:{i}:code")],
                [
                    btn("⬆️ Выше", f"a:up:{i}"),
                    btn("⬇️ Ниже", f"a:dn:{i}"),
                    btn("👁 Показать" if lesson["hidden"] else "🙈 Скрыть", f"a:hide:{i}"),
                ],
                [btn("📢 Уведомить всех об уроке", f"a:nt:{i}")],
                [btn("🗑 Удалить", f"a:del:{i}"), btn("⬅️ К урокам", "a:ls")],
            ]
        )
        self.show(uid, text, kb, mid)

    def ask_content(self, uid: int, st: dict, mid: int | None = None) -> None:
        st["s"] = "add_content"
        self.show(
            uid,
            "<b>Новый урок · шаг 3 из 3</b>\n\n"
            "Пришли сам материал: ссылку (на видео, презентацию, Google-диск…), файл, видео, фото или просто текст.",
            self.cancel_kb(),
            mid,
        )

    def admin_edit_start(self, uid: int, lesson_id: int, field: str, mid: int | None) -> None:
        prompts = {
            "title": "Пришли новое название урока.",
            "description": "Пришли новое описание урока. Чтобы убрать описание, пришли минус: -",
            "content": "Пришли новый материал: ссылку, файл, видео, фото или текст.",
            "code": (
                "Пришли новый код для ссылки — латинские буквы, цифры, «_» и «-», например <code>reels5</code>.\n\n"
                "Внимание: старая ссылка на этот урок перестанет вести на него."
            ),
        }
        if field not in prompts or not self.db.lesson(lesson_id):
            return
        self.states[uid] = {"s": "edit", "id": lesson_id, "f": field}
        self.show(uid, prompts[field], self.cancel_kb(f"a:l:{lesson_id}"), mid)

    def try_preview(self, uid: int, lesson: dict) -> bool:
        """Показывает админу урок глазами ученика; заодно проверяет, что Telegram его принимает."""
        try:
            self.send(uid, "Вот так урок увидят ученики 👇")
            self.send_lesson(uid, lesson)
            return True
        except TgError as e:
            self.send(
                uid,
                "Telegram не принял этот материал (скорее всего, ссылка написана с ошибкой).\n"
                f"<i>{esc(e.description)}</i>\n\nПришли материал ещё раз.",
                self.cancel_kb(),
            )
            return False

    # ---------- ввод админа по шагам ----------

    def admin_input(self, uid: int, m: dict) -> None:
        st = self.states[uid]
        step = st["s"]
        text = (m.get("text") or "").strip()

        if step == "add_title":
            if not self.valid_text(uid, text, MAX_TITLE):
                return
            st.update(s="add_desc", title=text)
            self.send(
                uid,
                "<b>Новый урок · шаг 2 из 3</b>\n\nПришли короткое описание: о чём урок, что человек получит.",
                ikb([[btn("⏭ Без описания", "a:skip")], [btn("❌ Отмена", "a:cancel")]]),
            )
        elif step == "add_desc":
            if not self.valid_text(uid, text, MAX_DESCRIPTION):
                return
            st["description"] = text
            self.ask_content(uid, st)
        elif step == "add_content":
            content = self.valid_content(uid, m)
            if not content:
                return
            draft = {"title": st["title"], "description": st["description"], "kind": content[0], "content": content[1]}
            if not self.try_preview(uid, draft):
                return
            lesson_id = self.db.add_lesson(**draft)
            self.states.pop(uid, None)
            self.send(uid, "✅ Урок добавлен!")
            self.admin_lesson(uid, lesson_id)
        elif step == "edit":
            self.admin_edit_input(uid, st, m, text)
        elif step == "bc_wait":
            try:
                self.send(uid, "Вот так сообщение увидят получатели 👇")
                self.tg.call("copyMessage", chat_id=uid, from_chat_id=uid, message_id=m["message_id"])
            except TgError as e:
                self.send(uid, f"Такое сообщение разослать не получится: <i>{esc(e.description)}</i>\nПришли другое.")
                return
            self.states[uid] = {"s": "bc_confirm", "mid": m["message_id"]}
            count = len(self.db.active_user_ids())
            self.send(
                uid,
                f"Отправить это сообщение всем пользователям ({count})?",
                ikb([[btn("✅ Отправить", "a:bcok"), btn("❌ Отмена", "a:cancel")]]),
            )
        elif step == "bc_confirm":
            self.send(uid, "Нажми «Отправить» или «Отмена» под сообщением выше.")
        elif step == "ch_add":
            self.admin_channel_input(uid, m, text)
        elif step == "text":
            if not self.valid_text(uid, text, MAX_SETTING_TEXT):
                return
            self.db.set_setting(st["key"], text)
            self.states.pop(uid, None)
            self.send(uid, "✅ Текст обновлён.", ikb([[btn("⬅️ К текстам", "a:tx")]]))

    def valid_text(self, uid: int, text: str, limit: int) -> bool:
        if not text:
            self.send(uid, "Нужен обычный текст. Пришли его сообщением.")
            return False
        if len(text) > limit:
            self.send(uid, f"Слишком длинно: {len(text)} символов, а нужно не больше {limit}. Сократи и пришли ещё раз.")
            return False
        return True

    def valid_content(self, uid: int, m: dict):
        content = extract_content(m)
        if not content:
            self.send(uid, "Не понял, что это за материал. Пришли ссылку, файл, видео, фото или текст.")
            return None
        if content[0] == "text" and len(content[1]) > MAX_TEXT_LESSON:
            self.send(uid, f"Текст слишком длинный — максимум {MAX_TEXT_LESSON} символов. Сократи или пришли файлом.")
            return None
        return content

    def admin_edit_input(self, uid: int, st: dict, m: dict, text: str) -> None:
        lesson = self.db.lesson(st["id"])
        if not lesson:
            self.states.pop(uid, None)
            return self.admin_lessons(uid)
        field = st["f"]
        if field == "title":
            if not self.valid_text(uid, text, MAX_TITLE):
                return
            self.db.update_lesson(lesson["id"], title=text)
        elif field == "description":
            if text == "-":
                text = ""
            elif not self.valid_text(uid, text, MAX_DESCRIPTION):
                return
            self.db.update_lesson(lesson["id"], description=text)
        elif field == "content":
            content = self.valid_content(uid, m)
            if not content:
                return
            draft = dict(lesson)
            draft.update(kind=content[0], content=content[1])
            if not self.try_preview(uid, draft):
                return
            self.db.update_lesson(lesson["id"], kind=content[0], content=content[1])
        elif field == "code":
            if not CODE_RE.match(text):
                self.send(uid, "В коде могут быть только латинские буквы, цифры, «_» и «-» (до 64 символов).")
                return
            other = self.db.lesson_by_code(text)
            if other and other["id"] != lesson["id"]:
                self.send(uid, f"Этот код уже занят уроком «{esc(other['title'])}». Пришли другой.")
                return
            self.db.update_lesson(lesson["id"], code=text)
        self.states.pop(uid, None)
        self.send(uid, "✅ Сохранено.")
        self.admin_lesson(uid, lesson["id"])

    # ---------- обязательная подписка ----------

    def admin_channels(self, uid: int, mid: int | None = None) -> None:
        channels = self.db.channels()
        if channels:
            lines = "\n".join(f"• {esc(c['title'])} — {esc(c['link'])}" for c in channels)
            text = (
                "<b>Обязательная подписка</b>\n\n"
                f"Уроки получают только подписчики:\n{lines}\n\nНажми на канал, чтобы убрать его."
            )
        else:
            text = (
                "<b>Обязательная подписка</b>\n\n"
                "Сейчас уроки доступны всем. Добавь канал или группу — и бот будет выдавать уроки только подписчикам."
            )
        rows = [[btn(f"❌ {c['title']}", f"a:chdel:{c['chat_id']}")] for c in channels]
        rows.append([btn("➕ Добавить канал", "a:chadd")])
        rows.append([btn("⬅️ Назад", "a:home")])
        self.show(uid, text, ikb(rows), mid)

    def admin_channel_input(self, uid: int, m: dict, text: str) -> None:
        origin = m.get("forward_origin") or {}
        fwd_chat = origin.get("chat") or origin.get("sender_chat") or m.get("forward_from_chat")
        if fwd_chat:
            target = fwd_chat["id"]
        else:
            match = re.match(r"^(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z][\w]{3,})/?(?:\d+)?$", text)
            if match:
                target = "@" + match.group(1)
            elif re.match(r"^@[A-Za-z][\w]{3,}$", text):
                target = text
            elif re.match(r"^-?\d+$", text):
                target = int(text)
            else:
                self.send(
                    uid,
                    "Не понял, что это за канал. Пришли @username, ссылку вида t.me/название "
                    "или перешли сюда любой пост из канала (для закрытых каналов — только так).",
                    self.cancel_kb("a:ch"),
                )
                return

        not_admin = (
            "Я не вижу этот канал или я в нём не администратор.\n"
            "Добавь меня в канал администратором и пришли его ещё раз."
        )
        try:
            chat = self.tg.call("getChat", chat_id=target)
            me = self.tg.call("getChatMember", chat_id=chat["id"], user_id=self.me["id"])
        except TgError:
            self.send(uid, not_admin, self.cancel_kb("a:ch"))
            return
        if chat.get("type") not in ("channel", "supergroup", "group"):
            self.send(uid, "Это не канал и не группа. Пришли канал или группу.", self.cancel_kb("a:ch"))
            return
        if me.get("status") not in ("administrator", "creator"):
            self.send(uid, not_admin, self.cancel_kb("a:ch"))
            return

        if chat.get("username"):
            link = f"https://t.me/{chat['username']}"
        else:
            link = chat.get("invite_link")
            try:
                link = self.tg.call("createChatInviteLink", chat_id=chat["id"], name="Бот с уроками")["invite_link"]
            except TgError:
                pass
            if not link:
                self.send(
                    uid,
                    "Канал закрытый, а у меня нет права создавать ссылки-приглашения.\n"
                    "Включи мне в настройках администратора право «Пригласительные ссылки» и пришли канал ещё раз.",
                    self.cancel_kb("a:ch"),
                )
                return

        self.db.add_channel(chat["id"], chat.get("title") or str(chat["id"]), link)
        self.states.pop(uid, None)
        self.send(uid, f"✅ Готово! Теперь уроки получат только подписчики «{esc(chat.get('title'))}».")
        self.admin_channels(uid)

    # ---------- статистика и настройки ----------

    def admin_stats(self, uid: int, mid: int | None = None) -> None:
        s = self.db.user_stats()
        lines = [
            "<b>Статистика</b>\n",
            f"Всего пользователей: {s['total']}",
            f"Новых за сутки: {s['day']}",
            f"Новых за 7 дней: {s['week']}",
            f"Заблокировали бота: {s['blocked']}",
        ]
        lessons = self.db.lessons(include_hidden=True)
        if lessons:
            lines.append("\n<b>Открытия уроков</b> (всего / человек):")
            for l in lessons:
                v = self.db.lesson_views(l["id"])
                lines.append(f"• {esc(l['title'])} — {v['total']} / {v['people']}")
        sources = self.db.top_sources()
        if sources:
            lines.append("\n<b>По каким ссылкам приходят:</b>")
            for r in sources:
                lines.append(f"• <code>{esc(r['source'])}</code> — {r['n']}")
        self.show(uid, "\n".join(lines), ikb([[btn("🔄 Обновить", "a:st"), btn("⬅️ Назад", "a:home")]]), mid)

    def admin_settings(self, uid: int, mid: int | None = None) -> None:
        on = self.protect
        text = (
            "<b>Настройки</b>\n\n"
            f"Защита уроков от пересылки и сохранения: <b>{'включена' if on else 'выключена'}</b>\n"
            "Когда она включена, урок нельзя переслать другому человеку или сохранить файл."
        )
        kb = ikb(
            [
                [btn("🔓 Выключить защиту" if on else "🔒 Включить защиту", "a:prot")],
                [btn("⬅️ Назад", "a:home")],
            ]
        )
        self.show(uid, text, kb, mid)

    # ================= рассылки =================

    def start_copy_broadcast(self, admin_id: int, source_mid: int, mid: int | None) -> None:
        def send_one(target: int) -> None:
            self.tg.call("copyMessage", chat_id=target, from_chat_id=admin_id, message_id=source_mid)

        self.start_broadcast(admin_id, send_one, mid)

    def notify_lesson(self, admin_id: int, lesson_id: int, mid: int | None) -> None:
        lesson = self.db.lesson(lesson_id)
        if not lesson:
            return self.admin_lessons(admin_id, mid)
        text = f"🆕 <b>Новый урок: {esc(lesson['title'])}</b>"
        if lesson["description"]:
            text += "\n\n" + esc(lesson["description"])
        kb = ikb([[btn("▶️ Открыть урок", f"l:{lesson_id}")]])

        def send_one(target: int) -> None:
            self.send(target, text, kb)

        self.start_broadcast(admin_id, send_one, mid)

    def start_broadcast(self, admin_id: int, send_one, mid: int | None = None) -> None:
        if not self._broadcast_lock.acquire(blocking=False):
            self.show(admin_id, "Предыдущая рассылка ещё идёт. Дождись отчёта и попробуй снова.", None, mid)
            return
        targets = self.db.active_user_ids()
        self.show(admin_id, f"🚀 Рассылка началась: {len(targets)} получателей. Пришлю отчёт, когда закончу.", None, mid)
        self._broadcast_thread = threading.Thread(
            target=self._broadcast_worker, args=(admin_id, targets, send_one), name="broadcast", daemon=True
        )
        self._broadcast_thread.start()

    def _broadcast_worker(self, admin_id: int, targets: list, send_one) -> None:
        delivered = blocked = failed = 0
        try:
            for target in targets:
                if self.stop.is_set():
                    break
                result = self._send_with_retry(target, send_one)
                if result == "ok":
                    delivered += 1
                elif result == "blocked":
                    blocked += 1
                    self.db.set_blocked(target, True)
                else:
                    failed += 1
                time.sleep(self.broadcast_delay)
        finally:
            self._broadcast_lock.release()
        report = f"✅ Рассылка завершена.\n\nДоставлено: {delivered}\nЗаблокировали бота: {blocked}"
        if failed:
            report += f"\nНе доставлено из-за ошибок: {failed}"
        try:
            self.send(admin_id, report, ikb([[btn("⬅️ В панель", "a:home")]]))
        except (TgError, TgNetworkError):
            log.warning("Не удалось отправить отчёт о рассылке")

    def _send_with_retry(self, target: int, send_one) -> str:
        for _ in range(3):
            try:
                send_one(target)
                return "ok"
            except TgError as e:
                if e.code == 429:
                    time.sleep((e.retry_after or 1) + 0.5)
                    continue
                if e.code == 403 or "chat not found" in e.description or "deactivated" in e.description:
                    return "blocked"
                log.warning("Рассылка: ошибка для %s: %s", target, e)
                return "failed"
            except TgNetworkError:
                time.sleep(2)
        return "failed"
