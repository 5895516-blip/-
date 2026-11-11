"""Проверка бота от начала до конца на имитации Telegram.

Запуск:  python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import App, extract_content, render_text  # noqa: E402
from config import Config  # noqa: E402
from db import DB  # noqa: E402
from fake_telegram import FakeTelegram  # noqa: E402
from tg import Telegram, TgError, TgNetworkError  # noqa: E402

ADMIN = 1
USER = 50
CHANNEL = -1001234


class BotTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeTelegram()
        config = Config(token="TEST", admin_ids={ADMIN}, db_path=":memory:", api_url=self.fake.url)
        self.app = App(config, db=DB(":memory:"))
        self.app.broadcast_delay = 0
        self.app.setup()
        self.db = self.app.db
        self._update_id = 0
        self._message_id = 0
        self.fake.reset()

    def tearDown(self):
        self.app.stop.set()
        self.app.pool.shutdown(wait=True)
        self.fake.close()
        self.db.close()

    # ---- помощники: действия пользователя ----

    def message(self, uid: int, text: str | None = None, **extra) -> int:
        self._update_id += 1
        self._message_id += 1
        m = {
            "message_id": self._message_id,
            "from": {"id": uid, "first_name": f"User{uid}", "username": f"user{uid}"},
            "chat": {"id": uid, "type": "private"},
            **extra,
        }
        if text is not None:
            m["text"] = text
        self.app.handle_update({"update_id": self._update_id, "message": m})
        return self._message_id

    def click(self, uid: int, data: str, mid: int = 500) -> None:
        self._update_id += 1
        self.app.handle_update(
            {
                "update_id": self._update_id,
                "callback_query": {
                    "id": f"cq{self._update_id}",
                    "from": {"id": uid, "first_name": f"User{uid}"},
                    "data": data,
                    "message": {"message_id": mid, "chat": {"id": uid, "type": "private"}},
                },
            }
        )

    def add_lesson(self, title="Урок 1", description="Описание", kind="url", content="https://example.com/1") -> int:
        return self.db.add_lesson(title, description, kind, content)

    def add_channel(self):
        self.db.add_channel(CHANNEL, "Мой канал", "https://t.me/my_channel")

    def wait_broadcast(self):
        """Выполняет всё, что стоит в очереди (в работающем боте это делает планировщик)."""
        self.app.run_due_jobs()

    # ---- ученик ----

    def test_start_shows_welcome_and_lessons(self):
        self.add_lesson("Монтаж за 5 минут")
        self.add_lesson("Свет и кадр")
        self.db.update_lesson(self.add_lesson("Черновик"), hidden=1)

        self.message(USER, "/start")

        self.assertIn("Привет", self.fake.texts(USER))
        titles = [b["text"] for b in self.fake.buttons(USER)]
        self.assertEqual(titles, ["Монтаж за 5 минут", "Свет и кадр"])

    def test_start_without_lessons(self):
        self.message(USER, "/start")
        self.assertIn("Уроки скоро появятся", self.fake.texts(USER))

    def test_deep_link_opens_that_lesson(self):
        lesson_id = self.add_lesson("Монтаж", "Как монтировать", "url", "https://example.com/montage")
        self.add_lesson("Другой урок")

        self.message(USER, f"/start lesson{lesson_id}")

        sent = self.fake.sent("sendMessage", USER)
        self.assertEqual(len(sent), 1)
        self.assertIn("<b>Монтаж</b>", sent[0]["text"])
        self.assertIn("Как монтировать", sent[0]["text"])
        urls = [b.get("url") for b in self.fake.buttons(USER)]
        self.assertIn("https://example.com/montage", urls)
        self.assertEqual(self.db.lesson_views(lesson_id), {"total": 1, "people": 1})
        self.assertEqual(self.db.top_sources()[0]["source"], f"lesson{lesson_id}")

    def test_subscription_gate(self):
        lesson_id = self.add_lesson("Монтаж", content="https://example.com/montage")
        self.add_channel()

        # Не подписан: уроков нет, есть просьба подписаться и кнопка на канал.
        self.message(USER, f"/start lesson{lesson_id}")
        self.assertIn("только подписчикам", self.fake.texts(USER))
        self.assertNotIn("Монтаж", self.fake.texts(USER))
        buttons = self.fake.buttons(USER)
        self.assertEqual(buttons[0]["url"], "https://t.me/my_channel")
        self.assertEqual(buttons[-1]["callback_data"], "checksub")

        # Нажал «Я подписался», не подписавшись: получает предупреждение, урока нет.
        self.fake.reset()
        self.click(USER, "checksub")
        alerts = self.fake.sent("answerCallbackQuery")
        self.assertTrue(alerts[0]["show_alert"])
        self.assertIn("не вижу подписки", alerts[0]["text"])
        self.assertEqual(self.fake.sent("sendMessage", USER), [])

        # Подписался и нажал: получает именно тот урок, за которым пришёл.
        self.fake.reset()
        self.fake.members[(CHANNEL, USER)] = "member"
        self.click(USER, "checksub")
        self.assertIn("<b>Монтаж</b>", self.fake.texts(USER))
        self.assertEqual(self.db.lesson_views(lesson_id)["total"], 1)

    def test_lesson_button_is_gated_after_unsubscribe(self):
        lesson_id = self.add_lesson("Монтаж")
        self.add_channel()
        self.fake.members[(CHANNEL, USER)] = "member"
        self.message(USER, "/start")
        self.assertIn("Монтаж", [b["text"] for b in self.fake.buttons(USER)])

        self.fake.reset()
        self.fake.members[(CHANNEL, USER)] = "left"
        self.click(USER, f"l:{lesson_id}")
        self.assertIn("только подписчикам", self.fake.texts(USER))
        self.assertEqual(self.db.lesson_views(lesson_id)["total"], 0)

        # После повторной подписки бот помнит, какой урок человек хотел.
        self.fake.reset()
        self.fake.members[(CHANNEL, USER)] = "member"
        self.click(USER, "checksub")
        self.assertIn("<b>Монтаж</b>", self.fake.texts(USER))

    def test_broken_channel_does_not_lock_users_out(self):
        self.add_lesson("Монтаж")
        self.add_channel()
        self.fake.fail[("getChatMember", CHANNEL)] = (400, "Bad Request: member list is inaccessible")

        self.message(USER, "/start")

        self.assertIn("Монтаж", [b["text"] for b in self.fake.buttons(USER)])
        self.assertIn("Не могу проверить подписку", self.fake.texts(ADMIN))

    def test_file_lesson_and_protection(self):
        lesson_id = self.add_lesson("Презентация", "Слайды", "document", "FILE123")
        self.db.set_setting("protect", "1")

        self.click(USER, f"l:{lesson_id}")

        doc = self.fake.sent("sendDocument", USER)[0]
        self.assertEqual(doc["document"], "FILE123")
        self.assertIn("<b>Презентация</b>", doc["caption"])
        self.assertTrue(doc["protect_content"])

    def test_html_in_titles_is_escaped(self):
        lesson_id = self.add_lesson("Теги <b> & co", "5 < 6", "text", "a <i>b</i>")
        self.click(USER, f"l:{lesson_id}")
        text = self.fake.sent("sendMessage", USER)[0]["text"]
        self.assertIn("Теги &lt;b&gt; &amp; co", text)
        self.assertIn("a &lt;i&gt;b&lt;/i&gt;", text)

    def test_pagination(self):
        for i in range(1, 12):
            self.add_lesson(f"Урок {i}")
        self.message(USER, "/start")
        labels = [b["text"] for b in self.fake.buttons(USER)]
        self.assertEqual(labels[:8], [f"Урок {i}" for i in range(1, 9)])
        self.assertIn("1/2", labels)

        self.fake.reset()
        self.click(USER, "p:1")
        edit = self.fake.sent("editMessageText", USER)[0]
        labels = [b["text"] for row in edit["reply_markup"]["inline_keyboard"] for b in row]
        self.assertEqual(labels[:3], ["Урок 9", "Урок 10", "Урок 11"])

    def test_unknown_text_gets_hint(self):
        self.message(USER, "а где уроки?")
        self.assertIn("/start", self.fake.texts(USER))

    def test_id_command(self):
        self.message(USER, "/id")
        self.assertIn(f"<code>{USER}</code>", self.fake.texts(USER))

    # ---- админ ----

    def test_admin_panel_is_closed_for_others(self):
        self.message(USER, "/admin")
        self.assertNotIn("Панель управления", self.fake.texts(USER))
        self.click(USER, "a:ls")
        self.click(USER, "a:add")
        self.assertNotIn(USER, self.app.states)
        self.assertEqual(self.fake.sent("editMessageText", USER), [])

    def test_admin_adds_lesson(self):
        self.message(ADMIN, "/admin")
        self.assertIn("Панель управления", self.fake.texts(ADMIN))

        self.click(ADMIN, "a:add")
        self.message(ADMIN, "Монтаж за 5 минут")
        self.message(ADMIN, "Быстрый монтаж в телефоне")
        self.fake.reset()
        self.message(ADMIN, "youtu.be/abc123")

        lesson = self.db.lessons()[0]
        self.assertEqual(lesson["title"], "Монтаж за 5 минут")
        self.assertEqual(lesson["description"], "Быстрый монтаж в телефоне")
        self.assertEqual((lesson["kind"], lesson["content"]), ("url", "https://youtu.be/abc123"))
        text = self.fake.texts(ADMIN)
        self.assertIn("Вот так урок увидят ученики", text)
        self.assertIn(f"https://t.me/lessons_test_bot?start={lesson['code']}", text)
        self.assertNotIn(ADMIN, self.app.states)

    def test_admin_adds_file_lesson_without_description(self):
        self.click(ADMIN, "a:add")
        self.message(ADMIN, "Презентация")
        self.click(ADMIN, "a:skip")
        self.message(ADMIN, document={"file_id": "DOC1", "file_name": "slides.pdf"})

        lesson = self.db.lessons()[0]
        self.assertEqual((lesson["kind"], lesson["content"], lesson["description"]), ("document", "DOC1", ""))

    def test_bad_material_is_not_saved(self):
        self.fake.fail[("sendMessage", ADMIN)] = (400, "Bad Request: BUTTON_URL_INVALID")
        self.click(ADMIN, "a:add")
        self.app.states[ADMIN] = {"s": "add_content", "title": "Урок", "description": ""}
        self.message(ADMIN, "https://bad")
        self.assertEqual(self.db.lessons(include_hidden=True), [])
        self.assertEqual(self.app.states[ADMIN]["s"], "add_content")

    def test_admin_edits_hides_moves_deletes(self):
        first = self.add_lesson("Первый")
        second = self.add_lesson("Второй")

        self.click(ADMIN, f"a:e:{first}:title")
        self.message(ADMIN, "Первый (новый)")
        self.assertEqual(self.db.lesson(first)["title"], "Первый (новый)")

        self.click(ADMIN, f"a:e:{first}:code")
        self.message(ADMIN, "плохой код")
        self.assertEqual(self.db.lesson(first)["code"], f"lesson{first}")
        self.message(ADMIN, f"lesson{second}")  # занят другим уроком
        self.assertEqual(self.db.lesson(first)["code"], f"lesson{first}")
        self.message(ADMIN, "reels5")
        self.assertEqual(self.db.lesson(first)["code"], "reels5")
        self.assertEqual(self.db.lesson_by_code("REELS5")["id"], first)

        self.click(ADMIN, f"a:e:{first}:description")
        self.message(ADMIN, "-")
        self.assertEqual(self.db.lesson(first)["description"], "")

        self.click(ADMIN, f"a:dn:{first}")
        self.assertEqual([l["id"] for l in self.db.lessons()], [second, first])

        self.click(ADMIN, f"a:hide:{first}")
        self.assertEqual([l["id"] for l in self.db.lessons()], [second])
        self.fake.reset()
        self.message(USER, "/start reels5")  # скрытый урок по ссылке не выдаётся
        self.assertNotIn("Первый", self.fake.texts(USER))

        self.click(ADMIN, f"a:del:{second}")
        self.assertIsNotNone(self.db.lesson(second))  # сначала только вопрос
        self.click(ADMIN, f"a:delok:{second}")
        self.assertIsNone(self.db.lesson(second))

    def test_admin_adds_channel(self):
        self.fake.chats["@my_channel"] = {"id": CHANNEL, "type": "channel", "title": "Мой канал", "username": "my_channel"}
        self.fake.chats[CHANNEL] = self.fake.chats["@my_channel"]

        # Бот ещё не админ канала — канал не добавляется.
        self.click(ADMIN, "a:chadd")
        self.message(ADMIN, "https://t.me/my_channel")
        self.assertEqual(self.db.channels(), [])
        self.assertIn("не администратор", self.fake.texts(ADMIN))

        self.fake.members[(CHANNEL, 999)] = "administrator"
        self.message(ADMIN, "@my_channel")
        channel = self.db.channels()[0]
        self.assertEqual((channel["chat_id"], channel["link"]), (CHANNEL, "https://t.me/my_channel"))

        self.click(ADMIN, f"a:chdel:{CHANNEL}")
        self.assertEqual(self.db.channels(), [])

    def test_admin_adds_private_channel_by_forward(self):
        self.fake.chats[CHANNEL] = {"id": CHANNEL, "type": "channel", "title": "Закрытый"}
        self.fake.members[(CHANNEL, 999)] = "administrator"

        self.click(ADMIN, "a:chadd")
        self.message(ADMIN, "пост", forward_origin={"type": "channel", "chat": {"id": CHANNEL, "type": "channel"}})

        self.assertEqual(self.db.channels()[0]["link"], "https://t.me/+secretinvite")

    def test_broadcast(self):
        for uid in (50, 51, 52):
            self.message(uid, "/start")
        self.fake.fail[("copyMessage", 51)] = (403, "Forbidden: bot was blocked by the user")

        self.click(ADMIN, "a:bc")
        source_mid = self.message(ADMIN, "Завтра выйдет новый урок!")
        preview = self.fake.sent("copyMessage", ADMIN)
        self.assertEqual(preview[-1]["message_id"], source_mid)
        self.assertEqual(self.fake.sent("copyMessage", 50), [])  # до подтверждения никому не уходит

        self.fake.reset()
        self.click(ADMIN, "a:bcok")
        self.wait_broadcast()

        for uid in (50, 52, ADMIN):
            copies = self.fake.sent("copyMessage", uid)
            self.assertEqual(len(copies), 1, uid)
            self.assertEqual((copies[0]["from_chat_id"], copies[0]["message_id"]), (ADMIN, source_mid))
        report = self.fake.texts(ADMIN)
        self.assertIn("Доставлено: 3", report)
        self.assertIn("Заблокировали бота: 1", report)
        self.assertNotIn(51, self.db.active_user_ids())

    def test_broadcast_cancel(self):
        self.message(USER, "/start")
        self.click(ADMIN, "a:bc")
        self.message(ADMIN, "Черновик")
        self.click(ADMIN, "a:cancel")
        self.click(ADMIN, "a:bcok")
        self.wait_broadcast()
        self.assertEqual(self.db.broadcasts(), [])
        self.assertEqual(self.fake.sent("copyMessage", USER), [])

    def test_notify_about_lesson(self):
        lesson_id = self.add_lesson("Свет и кадр", "Про свет")
        self.message(USER, "/start")
        self.fake.reset()

        self.click(ADMIN, f"a:nt:{lesson_id}")
        self.assertEqual(self.fake.sent("sendMessage", USER), [])
        self.click(ADMIN, f"a:ntok:{lesson_id}")
        self.wait_broadcast()

        note = self.fake.sent("sendMessage", USER)[0]
        self.assertIn("Новый урок: Свет и кадр", note["text"])
        self.assertEqual(note["reply_markup"]["inline_keyboard"][0][0]["callback_data"], f"l:{lesson_id}")

    # ---- очередь рассылок, отложенная отправка, аудитории ----

    def queue(self, text="Привет", segment=None, scheduled_at=None, **payload) -> int:
        return self.app.queue_broadcast(ADMIN, "text", {"text": text, **payload}, segment, scheduled_at)

    def test_scheduled_broadcast_waits_for_its_time(self):
        self.message(USER, "/start")
        self.fake.reset()
        bid = self.queue("Завтра эфир", scheduled_at=int(time.time()) + 3600)

        self.wait_broadcast()
        self.assertEqual(self.fake.sent("sendMessage", USER), [])
        self.assertEqual(self.db.broadcast(bid)["status"], "scheduled")

        self.db._run("UPDATE broadcasts SET scheduled_at = ? WHERE id = ?", (int(time.time()) - 1, bid))
        self.wait_broadcast()
        self.assertEqual(self.fake.sent("sendMessage", USER)[0]["text"], "Завтра эфир")
        row = self.db.broadcast(bid)
        self.assertEqual((row["status"], row["total"], row["delivered"]), ("done", 1, 1))

        self.fake.reset()
        self.wait_broadcast()  # повторно не уходит
        self.assertEqual(self.fake.sent("sendMessage", USER), [])

    def test_cancelled_broadcast_is_not_sent(self):
        self.message(USER, "/start")
        self.fake.reset()
        bid = self.queue("Не отправлять")
        self.assertTrue(self.db.cancel_broadcast(bid))
        self.wait_broadcast()
        self.assertEqual(self.fake.sent("sendMessage", USER), [])
        self.assertFalse(self.db.cancel_broadcast(bid))

    def test_broadcast_segments(self):
        first = self.add_lesson("Первый")
        second = self.add_lesson("Второй")
        self.message(50, f"/start lesson{first}")   # открыл первый урок, пришёл по его ссылке
        self.message(51, "/start reels_7")          # ничего не открывал
        self.message(52, "/start")
        self.click(52, f"l:{second}")               # открыл второй урок
        self.db._run("UPDATE users SET created_at = created_at - 20 * 86400 WHERE id = 52")

        def audience(segment):
            return [u["id"] for u in self.db.segment_users(segment)]

        self.assertEqual(audience({"type": "all"}), [50, 51, 52])
        self.assertEqual(audience({"type": "lesson", "id": first}), [50])
        self.assertEqual(audience({"type": "not_lesson", "id": first}), [51, 52])
        self.assertEqual(audience({"type": "no_views"}), [51])
        self.assertEqual(audience({"type": "source", "value": "reels_7"}), [51])
        self.assertEqual(audience({"type": "new", "days": 7}), [50, 51])
        self.assertEqual(self.db.segment_count({"type": "not_lesson", "id": first}), 2)

        self.fake.reset()
        self.queue("Только тем, кто не открыл", segment={"type": "no_views"})
        self.wait_broadcast()
        self.assertEqual([p["chat_id"] for p in self.fake.sent("sendMessage") if p["text"].startswith("Только")], [51])

    def test_broadcast_formatting_name_button_and_photo(self):
        lesson_id = self.add_lesson("Монтаж")
        self.message(USER, "/start")
        self.fake.reset()
        self.queue("**Привет**, {имя}! <3", button_text="Открыть", button_target=f"lesson:{lesson_id}", photo="PHOTO_ID")
        self.queue("Ссылка", button_text="Сайт", button_target="https://example.com")
        self.wait_broadcast()

        photo = self.fake.sent("sendPhoto", USER)[0]
        self.assertEqual(photo["photo"], "PHOTO_ID")
        self.assertEqual(photo["caption"], f"<b>Привет</b>, User{USER}! &lt;3")
        self.assertEqual(photo["reply_markup"]["inline_keyboard"][0][0]["callback_data"], f"l:{lesson_id}")
        link = self.fake.sent("sendMessage", USER)[0]
        self.assertEqual(link["reply_markup"]["inline_keyboard"][0][0]["url"], "https://example.com")

    def test_interrupted_broadcast_resumes_without_duplicates(self):
        for uid in (50, 51, 52):
            self.message(uid, "/start")
        self.fake.reset()
        bid = self.queue("Важное")
        # Бот «упал» посреди рассылки: первому получателю уже отправлено.
        self.db.update_broadcast(bid, status="sending", total=3, delivered=1, last_user_id=50)

        self.wait_broadcast()

        self.assertEqual(sorted(p["chat_id"] for p in self.fake.sent("sendMessage") if p["text"] == "Важное"), [51, 52])
        row = self.db.broadcast(bid)
        self.assertEqual((row["status"], row["delivered"]), ("done", 3))

    def test_auto_messages(self):
        self.message(50, "/start")  # пришёл до создания автосообщения — ему оно не уходит
        self.db._run("UPDATE users SET created_at = created_at - 7200 WHERE id = 50")
        auto_id = self.db.save_auto(None, 60, "Как тебе урок, {имя}?", "", "", True)
        self.db._run("UPDATE autos SET created_at = created_at - 7000 WHERE id = ?", (auto_id,))
        self.message(51, "/start")
        self.message(52, "/start")
        self.db._run("UPDATE users SET created_at = created_at - 3601 WHERE id = 51")  # прошёл час
        self.fake.reset()

        self.wait_broadcast()
        sent = [p for p in self.fake.sent("sendMessage") if "Как тебе урок" in p["text"]]
        self.assertEqual([(p["chat_id"], p["text"]) for p in sent], [(51, "Как тебе урок, User51?")])

        self.fake.reset()
        self.wait_broadcast()  # второй раз тому же человеку не приходит
        self.assertEqual(self.fake.sent("sendMessage"), [])

        self.db.save_auto(auto_id, 60, "Как тебе урок?", "", "", False)  # выключено
        self.db._run("UPDATE users SET created_at = created_at - 3601 WHERE id = 52")
        self.wait_broadcast()
        self.assertEqual(self.fake.sent("sendMessage"), [])

    def test_panel_link_only_for_admins(self):
        self.message(ADMIN, "/panel")
        self.assertIn("выключена", self.fake.texts(ADMIN))
        self.message(USER, "/panel")
        self.assertNotIn("анел", self.fake.texts(USER))

    def test_stats_and_texts(self):
        lesson_id = self.add_lesson("Монтаж")
        self.message(USER, f"/start lesson{lesson_id}")
        self.message(51, "/start reels_7")
        self.fake.reset()

        self.click(ADMIN, "a:st")
        stats = self.fake.texts(ADMIN)
        self.assertIn("Всего пользователей: 3", stats)
        self.assertIn("Монтаж — 1 / 1", stats)
        self.assertIn("reels_7", stats)

        self.click(ADMIN, "a:txe:welcome")
        self.message(ADMIN, "Добро пожаловать в школу!")
        self.fake.reset()
        self.message(USER, "/start")
        self.assertIn("Добро пожаловать в школу!", self.fake.texts(USER))

    def test_user_blocking_bot_is_tracked(self):
        self.message(USER, "/start")
        self.app.handle_update(
            {
                "update_id": 1,
                "my_chat_member": {
                    "chat": {"id": USER, "type": "private"},
                    "from": {"id": USER},
                    "new_chat_member": {"status": "kicked"},
                },
            }
        )
        self.assertNotIn(USER, self.db.active_user_ids())
        self.message(USER, "/start")
        self.assertIn(USER, self.db.active_user_ids())

    def test_group_messages_are_ignored(self):
        self.app.handle_update(
            {
                "update_id": 1,
                "message": {"message_id": 1, "from": {"id": USER}, "chat": {"id": -5, "type": "group"}, "text": "/start"},
            }
        )
        self.assertEqual(self.fake.calls, [])

    # ---- работа через настоящий цикл получения сообщений ----

    def test_polling_loop(self):
        self.add_lesson("Монтаж")
        self.app.poll_timeout = 0
        self.fake.updates.append(
            {
                "update_id": 7,
                "message": {
                    "message_id": 1,
                    "from": {"id": USER, "first_name": "U"},
                    "chat": {"id": USER, "type": "private"},
                    "text": "/start",
                },
            }
        )
        runner = threading.Thread(target=self.app.run, daemon=True)
        runner.start()
        deadline = time.time() + 5
        while time.time() < deadline and not self.fake.sent("sendMessage", USER):
            time.sleep(0.02)
        self.app.stop.set()
        runner.join(timeout=5)

        self.assertIn("Монтаж", [b["text"] for b in self.fake.buttons(USER)])
        offsets = [p.get("offset") for p in self.fake.sent("getUpdates")]
        self.assertIn(8, offsets)  # обработанное сообщение не запрашивается повторно


class ClientTest(unittest.TestCase):
    def test_errors(self):
        fake = FakeTelegram()
        try:
            tg = Telegram("TEST", fake.url)
            fake.fail[("sendMessage", 5)] = (403, "Forbidden: bot was blocked by the user")
            with self.assertRaises(TgError) as ctx:
                tg.call("sendMessage", chat_id=5, text="hi")
            self.assertEqual(ctx.exception.code, 403)
            self.assertNotIn("reply_markup", fake.sent("sendMessage")[0])  # пустые параметры не отправляются
        finally:
            fake.close()
        with self.assertRaises(TgNetworkError) as ctx:
            Telegram("SECRET", fake.url, timeout=2).call("getMe")
        self.assertNotIn("SECRET", str(ctx.exception))


class ContentTest(unittest.TestCase):
    def test_extract_content(self):
        self.assertEqual(extract_content({"text": "https://youtu.be/x?t=1"}), ("url", "https://youtu.be/x?t=1"))
        self.assertEqual(extract_content({"text": "drive.google.com/file/d/1"}), ("url", "https://drive.google.com/file/d/1"))
        self.assertEqual(extract_content({"text": "Шаг 1. Открой приложение."}), ("text", "Шаг 1. Открой приложение."))
        self.assertEqual(extract_content({"photo": [{"file_id": "s"}, {"file_id": "big"}]}), ("photo", "big"))
        self.assertEqual(
            extract_content({"animation": {"file_id": "gif"}, "document": {"file_id": "doc"}}), ("animation", "gif")
        )
        self.assertIsNone(extract_content({"sticker": {"file_id": "x"}}))

    def test_render_text(self):
        self.assertEqual(render_text("**Жирный** и __курсив__", "Аня"), "<b>Жирный</b> и <i>курсив</i>")
        self.assertEqual(render_text("{имя}, привет", None), "друг, привет")
        self.assertEqual(render_text("{имя}", "<b>x</b>"), "&lt;b&gt;x&lt;/b&gt;")
        # Пересекающиеся выделения Telegram не примет — отправляем как обычный текст.
        self.assertEqual(render_text("**a __b** c__"), "**a __b** c__")


if __name__ == "__main__":
    unittest.main()
