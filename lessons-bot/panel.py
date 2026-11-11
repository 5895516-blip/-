"""Веб-панель управления ботом: открывается в браузере, вход — по одноразовой ссылке из бота (/panel)."""
from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import html
import io
import json
import logging
import os
import re
import secrets
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from app import CODE_RE, MAX_DESCRIPTION, MAX_SETTING_TEXT, MAX_TEXT_LESSON, MAX_TITLE, MEDIA
from app import DEFAULT_SUB_TEXT, DEFAULT_WELCOME, normalize_url, parse_channel_ref
from tg import TgError, TgNetworkError

log = logging.getLogger("panel")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel")
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
}
TOKEN_TTL = 10 * 60
SESSION_TTL = 30 * 86400
MAX_BODY = 15 * 1024 * 1024
MAX_PHOTO = 10 * 1024 * 1024
MAX_AUTO_DELAY = 60 * 24 * 90  # автосообщение — не позже чем через 90 дней
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,100}$")

LOGIN_PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Вход в панель</title>
<link rel="stylesheet" href="/app.css"></head><body class="gate"><main class="gate-box">
<p class="gate-mark">Панель бота</p><h1>{title}</h1><p>{text}</p>{form}</main></body></html>"""


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def sid_hash(sid: str) -> str:
    return hashlib.sha256(sid.encode()).hexdigest()


class Panel:
    def __init__(self, app, host: str, port: int, public_url: str):
        self.app = app
        self.db = app.db
        self.public_url = public_url.rstrip("/")
        self.secure = self.public_url.startswith("https://")
        self._tokens: dict = {}  # одноразовые ссылки для входа: {токен: (id админа, срок)}
        self._lock = threading.Lock()
        panel = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "LessonsBotPanel"
            sys_version = ""

            def do_GET(self):
                panel.dispatch(self, "GET")

            def do_POST(self):
                panel.dispatch(self, "POST")

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]

    def start(self) -> None:
        threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.1}, name="panel", daemon=True
        ).start()
        log.info("Панель управления: %s (ссылку для входа даёт команда /panel в боте)", self.public_url)

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    # ================= вход =================

    def login_link(self, admin_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            self._tokens = {t: v for t, v in self._tokens.items() if v[1] > now}
            self._tokens[token] = (admin_id, now + TOKEN_TTL)
        return f"{self.public_url}/login?t={token}"

    def _use_token(self, token: str):
        with self._lock:
            admin_id, expires = self._tokens.pop(token, (None, 0))
        if admin_id is None or expires < time.time() or not self.app.is_admin(admin_id):
            return None
        return admin_id

    def _session_admin(self, handler):
        cookie = SimpleCookie(handler.headers.get("Cookie", ""))
        if "sid" not in cookie:
            return None, None
        hashed = sid_hash(cookie["sid"].value)
        admin_id = self.db.session_admin(hashed)
        if admin_id is None or not self.app.is_admin(admin_id):
            return None, None
        return admin_id, hashed

    # ================= HTTP =================

    def dispatch(self, handler, method: str) -> None:
        url = urlparse(handler.path)
        path = url.path
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if method == "GET" and path in STATIC:
                return self._static(handler, *STATIC[path])
            if path == "/login":
                return self._login(handler, method, query)
            if not path.startswith("/api/"):
                raise ApiError("Не найдено", 404)

            admin_id, session = self._session_admin(handler)
            if admin_id is None:
                raise ApiError("Нужно войти: отправь боту команду /panel и открой ссылку.", 401)
            body = {}
            if method == "POST":
                # Свой заголовок нельзя отправить с чужого сайта — защита от подделки запросов.
                if handler.headers.get("X-Panel") != "1":
                    raise ApiError("Запрос отклонён", 403)
                body = self._read_json(handler)
            result = self.api(method, path[5:], query, body, admin_id, session)
            if isinstance(result, tuple):  # (тип, имя файла, содержимое) — скачивание файла
                return self._send(
                    handler, 200, result[2], result[0], {"Content-Disposition": f'attachment; filename="{result[1]}"'}
                )
            self._json(handler, 200, result if result is not None else {"ok": True})
        except ApiError as e:
            self._json(handler, e.status, {"error": e.message})
        except TgError as e:
            self._json(handler, 400, {"error": f"Telegram не принял запрос: {e.description}"})
        except TgNetworkError:
            self._json(handler, 502, {"error": "Нет связи с Telegram. Попробуй ещё раз через минуту."})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            log.exception("Ошибка панели")
            self._json(handler, 500, {"error": "Что-то сломалось на сервере. Подробности — в журнале бота."})

    def _read_json(self, handler) -> dict:
        try:
            length = int(handler.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError("Неверный запрос")
        if length > MAX_BODY:
            raise ApiError("Файл слишком большой: максимум 10 МБ.", 413)
        raw = handler.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ApiError("Неверный запрос")
        if not isinstance(data, dict):
            raise ApiError("Неверный запрос")
        return data

    def _send(self, handler, status: int, body: bytes, content_type: str, headers: dict | None = None) -> None:
        handler.send_response(status)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("X-Frame-Options", "DENY")
        handler.send_header("Referrer-Policy", "no-referrer")
        handler.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; frame-ancestors 'none'; form-action 'self'",
        )
        for key, value in (headers or {}).items():
            handler.send_header(key, value)
        handler.end_headers()
        handler.wfile.write(body)

    def _json(self, handler, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(handler, status, body, "application/json; charset=utf-8")

    def _static(self, handler, filename: str, content_type: str) -> None:
        with open(os.path.join(STATIC_DIR, filename), "rb") as f:
            self._send(handler, 200, f.read(), content_type)

    def _page(self, handler, status: int, title: str, text: str, form: str = "", headers: dict | None = None) -> None:
        body = LOGIN_PAGE.format(title=html.escape(title), text=html.escape(text), form=form).encode("utf-8")
        self._send(handler, status, body, "text/html; charset=utf-8", headers)

    def _login(self, handler, method: str, query: dict) -> None:
        expired = ("Ссылка устарела", "Она одноразовая и живёт 10 минут. Отправь боту /panel — он пришлёт новую.")
        if method == "GET":
            token = query.get("t", "")
            if not TOKEN_RE.match(token):
                return self._page(handler, 400, *expired)
            # Сам вход — только по нажатию кнопки: так ссылку не «съест» предпросмотр в мессенджере.
            form = (
                '<form method="post" action="/login">'
                f'<input type="hidden" name="t" value="{html.escape(token)}">'
                '<button class="btn btn-primary" type="submit">Войти в панель</button></form>'
            )
            return self._page(handler, 200, "Вход по ссылке из бота", "Нажми кнопку, чтобы открыть панель управления.", form)

        length = min(int(handler.headers.get("Content-Length") or 0), 4096)
        fields = parse_qs(handler.rfile.read(length).decode("utf-8", "replace"))
        token = (fields.get("t") or [""])[0]
        admin_id = self._use_token(token) if TOKEN_RE.match(token) else None
        if admin_id is None:
            return self._page(handler, 400, *expired)
        sid = secrets.token_urlsafe(32)
        self.db.add_session(sid_hash(sid), admin_id, int(time.time()) + SESSION_TTL)
        cookie = f"sid={sid}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_TTL}" + ("; Secure" if self.secure else "")
        self._send(handler, 303, b"", "text/plain", {"Location": "/", "Set-Cookie": cookie})

    # ================= API =================

    def api(self, method: str, path: str, query: dict, body: dict, admin_id: int, session: str):
        parts = path.strip("/").split("/")
        name = parts[0]
        item = int(parts[1]) if len(parts) > 1 and parts[1].lstrip("-").isdigit() else None
        action = parts[2] if len(parts) > 2 else (parts[1] if len(parts) > 1 and item is None else "")
        get, post = method == "GET", method == "POST"

        if name == "overview" and get:
            return self.overview(query)
        if name == "status" and get:
            return self.status()
        if name == "logout" and post:
            self.db.delete_session(session)
            return None

        if name == "broadcasts":
            if get:
                return self.broadcasts()
            if item is None and action == "test":
                return self.broadcast_test(body, admin_id)
            if item is None and not action:
                return self.broadcast_create(body, admin_id)
            if action == "cancel":
                if not self.db.cancel_broadcast(item):
                    raise ApiError("Эту рассылку уже нельзя отменить.")
                return None
        if name == "audience" and post:
            error, segment = self.app.clean_segment(body.get("segment"))
            if error:
                raise ApiError(error)
            return {"count": self.db.segment_count(segment)}
        if name == "photo" and post:
            return self.photo_upload(body, admin_id)

        if name == "lessons":
            if get:
                return self.lessons()
            if item is None:
                return self.lesson_save(None, body)
            if not self.db.lesson(item):
                raise ApiError("Этого урока уже нет.", 404)
            if not action:
                return self.lesson_save(item, body)
            if action == "delete":
                self.db.delete_lesson(item)
                return None
            if action == "move":
                self.db.move_lesson(item, -1 if body.get("dir") == "up" else 1)
                return None
            if action == "notify":
                self.app.notify_lesson(admin_id, item, announce=False)
                return {"count": self.db.segment_count({"type": "all"})}

        if name == "autos":
            if get:
                return self.autos()
            if item is None:
                return self.auto_save(body)
            if action == "delete":
                self.db.delete_auto(item)
                return None

        if name == "users":
            if get and action == "export":
                return self.users_csv()
            if get:
                return self.users(query)

        if name == "settings":
            if get:
                return self.settings()
            return self.settings_save(body)
        if name == "channels" and post:
            if item is not None and action == "delete":
                self.db.delete_channel(item)
                return None
            target = parse_channel_ref(str(body.get("ref") or ""))
            if target is None:
                raise ApiError("Не понял, что это за канал. Впиши @username или ссылку вида t.me/название.")
            error, title = self.app.connect_channel(target)
            if error:
                raise ApiError(error)
            return {"title": title}

        raise ApiError("Не найдено", 404)

    # ---------- обзор ----------

    def overview(self, query: dict) -> dict:
        try:
            tz = max(-900, min(900, int(query.get("tz", 0))))
        except ValueError:
            tz = 0
        offset = -tz * 60  # в браузере смещение считается «наоборот»
        counts = self.db.daily_new_users(30, offset)
        today = (int(time.time()) + offset) // 86400
        daily = [{"day": d * 86400, "n": counts.get(d, 0)} for d in range(today - 29, today + 1)]
        lessons = []
        for lesson in self.db.lessons(include_hidden=True):
            views = self.db.lesson_views(lesson["id"])
            lessons.append({"id": lesson["id"], "title": lesson["title"], "hidden": bool(lesson["hidden"]), **views})
        stats = self.db.user_stats()
        return {
            "bot": self.app.me.get("username", ""),
            "users": stats,
            "active": stats["total"] - stats["blocked"],
            "daily": daily,
            "lessons": lessons,
            "sources": [{"source": r["source"], "n": r["n"]} for r in self.db.top_sources(8)],
            "channels": len(self.db.channels()),
            "queue": [self._broadcast_view(b) for b in self.db.broadcasts(50) if b["status"] in ("sending", "scheduled")],
        }

    def status(self) -> dict:
        """Короткая сводка для лампы «в эфире»: идёт ли рассылка и сколько ждёт в очереди."""
        sending, scheduled = None, 0
        for b in self.db.broadcasts(50):
            if b["status"] == "sending" and sending is None:
                sending = {"id": b["id"], "done": b["delivered"] + b["blocked"] + b["failed"], "total": b["total"]}
            elif b["status"] == "scheduled":
                scheduled += 1
        return {"bot": self.app.me.get("username", ""), "sending": sending, "scheduled": scheduled}

    # ---------- рассылки ----------

    def _broadcast_view(self, row) -> dict:
        payload = json.loads(row["payload"])
        if row["kind"] == "copy":
            text = "Сообщение, пересланное боту в Telegram"
        else:
            text = payload.get("text") or re.sub(r"<[^>]+>", "", payload.get("html") or "")
        return {
            "id": row["id"],
            "text": text,
            "button_text": payload.get("button_text") or "",
            "has_photo": bool(payload.get("photo")),
            "audience": self.app.segment_label(json.loads(row["segment"])),
            "status": row["status"],
            "scheduled_at": row["scheduled_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "total": row["total"],
            "delivered": row["delivered"],
            "blocked": row["blocked"],
            "failed": row["failed"],
        }

    def broadcasts(self) -> dict:
        return {
            "items": [self._broadcast_view(b) for b in self.db.broadcasts(50)],
            "lessons": [{"id": l["id"], "title": l["title"]} for l in self.db.lessons(include_hidden=True)],
            "sources": [r["source"] for r in self.db.top_sources(50)],
            "total": self.db.segment_count({"type": "all"}),
        }

    def broadcast_test(self, body: dict, admin_id: int):
        error, payload = self.app.clean_message(body)
        if error:
            raise ApiError(error)
        me = self.db.user(admin_id)
        first_name = me["first_name"] if me else None
        self.app.send_composed(admin_id, first_name, payload)
        return None

    def broadcast_create(self, body: dict, admin_id: int) -> dict:
        error, payload = self.app.clean_message(body)
        if error:
            raise ApiError(error)
        error, segment = self.app.clean_segment(body.get("segment"))
        if error:
            raise ApiError(error)
        scheduled_at = body.get("scheduled_at")
        if scheduled_at is not None:
            if not isinstance(scheduled_at, (int, float)) or scheduled_at < time.time() - 60:
                raise ApiError("Время отправки уже прошло. Выбери время в будущем.")
            if scheduled_at > time.time() + 366 * 86400:
                raise ApiError("Запланировать можно не дальше чем на год вперёд.")
        count = self.db.segment_count(segment)
        if scheduled_at is None and count == 0:
            raise ApiError("В этой аудитории сейчас никого нет — отправлять некому.")
        bid = self.app.queue_broadcast(admin_id, "text", payload, segment, int(scheduled_at) if scheduled_at else None)
        return {"id": bid, "count": count}

    def photo_upload(self, body: dict, admin_id: int) -> dict:
        try:
            data = base64.b64decode(str(body.get("data") or ""), validate=True)
        except (binascii.Error, ValueError):
            raise ApiError("Не получилось прочитать картинку.")
        if not data or len(data) > MAX_PHOTO:
            raise ApiError("Картинка должна быть не больше 10 МБ.")
        if data[:3] == b"\xff\xd8\xff":
            mime, name = "image/jpeg", "photo.jpg"
        elif data[:8] == b"\x89PNG\r\n\x1a\n":
            mime, name = "image/png", "photo.png"
        elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            mime, name = "image/webp", "photo.webp"
        else:
            raise ApiError("Подойдёт картинка JPG, PNG или WebP.")
        # Telegram отдаёт идентификатор файла только после отправки, поэтому шлём картинку самому админу.
        message = self.app.tg.upload(
            "sendPhoto", "photo", name, data, mime, chat_id=admin_id, caption="Картинка для рассылки загружена ✅"
        )
        return {"photo": message["photo"][-1]["file_id"]}

    # ---------- уроки ----------

    def lessons(self) -> dict:
        items = []
        for lesson in self.db.lessons(include_hidden=True):
            kind = lesson["kind"]
            items.append(
                {
                    "id": lesson["id"],
                    "code": lesson["code"],
                    "title": lesson["title"],
                    "description": lesson["description"],
                    "kind": kind,
                    "kind_label": {"url": "ссылка", "text": "текст"}.get(kind) or MEDIA[kind][1],
                    "content": lesson["content"] if kind in ("url", "text") else "",
                    "hidden": bool(lesson["hidden"]),
                    "link": self.app.lesson_link(lesson),
                    **self.db.lesson_views(lesson["id"]),
                }
            )
        return {"items": items}

    def lesson_save(self, lesson_id, body: dict) -> dict:
        current = self.db.lesson(lesson_id) if lesson_id else None
        title = str(body.get("title") or "").strip()
        description = str(body.get("description") or "").strip()
        if not title:
            raise ApiError("Напиши название урока.")
        if len(title) > MAX_TITLE:
            raise ApiError(f"Название длиннее {MAX_TITLE} символов.")
        if len(description) > MAX_DESCRIPTION:
            raise ApiError(f"Описание длиннее {MAX_DESCRIPTION} символов.")
        fields = {"title": title, "description": description}

        kind = str(body.get("kind") or "")
        content = str(body.get("content") or "").strip()
        is_file = bool(current) and current["kind"] not in ("url", "text")
        if kind in ("url", "text") and (content or not is_file):
            if kind == "url":
                content = normalize_url(content)
                if not content:
                    raise ApiError("Ссылка на урок выглядит неправильно. Пример: https://youtu.be/abc")
            elif not content:
                raise ApiError("Напиши текст урока.")
            elif len(content) > MAX_TEXT_LESSON:
                raise ApiError(f"Текст урока длиннее {MAX_TEXT_LESSON} символов. Сократи или пришли боту файлом.")
            fields.update(kind=kind, content=content)
        elif not current:
            raise ApiError("Выбери, что будет в уроке: ссылка или текст.")

        if current:
            code = str(body.get("code") or current["code"]).strip()
            if not CODE_RE.match(code):
                raise ApiError("В коде ссылки могут быть только латинские буквы, цифры, «_» и «-».")
            other = self.db.lesson_by_code(code)
            if other and other["id"] != lesson_id:
                raise ApiError(f"Этот код ссылки уже занят уроком «{other['title']}».")
            fields.update(code=code, hidden=1 if body.get("hidden") else 0)
            self.db.update_lesson(lesson_id, **fields)
            return {"id": lesson_id}
        return {"id": self.db.add_lesson(title, description, fields["kind"], fields["content"])}

    # ---------- автосообщения ----------

    def autos(self) -> dict:
        return {
            "items": [
                {
                    "id": a["id"],
                    "delay_minutes": a["delay_minutes"],
                    "text": a["text"],
                    "button_text": a["button_text"],
                    "button_target": a["button_target"],
                    "enabled": bool(a["enabled"]),
                    "sent": a["sent"],
                }
                for a in self.db.autos()
            ],
            "lessons": [{"id": l["id"], "title": l["title"]} for l in self.db.lessons(include_hidden=True)],
        }

    def auto_save(self, body: dict) -> dict:
        auto_id = body.get("id")
        if auto_id is not None and not self.db.auto(int(auto_id)):
            raise ApiError("Этого автосообщения уже нет.", 404)
        delay = body.get("delay_minutes")
        if not isinstance(delay, (int, float)) or not 1 <= delay <= MAX_AUTO_DELAY:
            raise ApiError("Укажи, через сколько отправлять: от 1 минуты до 90 дней.")
        error, payload = self.app.clean_message({**body, "photo": ""})
        if error:
            raise ApiError(error)
        saved = self.db.save_auto(
            int(auto_id) if auto_id is not None else None,
            int(delay),
            payload["text"],
            payload.get("button_text", ""),
            payload.get("button_target", ""),
            bool(body.get("enabled", True)),
        )
        return {"id": saved}

    # ---------- пользователи ----------

    def users(self, query: dict) -> dict:
        try:
            offset = max(0, int(query.get("offset", 0)))
        except ValueError:
            offset = 0
        total, rows = self.db.find_users(query.get("q", ""), 50, offset)
        return {"total": total, "items": [dict(r) for r in rows]}

    def users_csv(self):
        out = io.StringIO()
        writer = csv.writer(out, delimiter=";")
        writer.writerow(["ID", "Имя", "Username", "Пришёл по ссылке", "Дата", "Открыто уроков", "Заблокировал бота"])
        offset = 0
        while True:
            _, rows = self.db.find_users("", 1000, offset)
            if not rows:
                break
            for r in rows:
                writer.writerow(
                    [
                        r["id"],
                        self._csv_safe(r["first_name"]),
                        self._csv_safe(r["username"]),
                        self._csv_safe(r["source"]),
                        time.strftime("%Y-%m-%d %H:%M", time.localtime(r["created_at"])),
                        r["lessons"],
                        "да" if r["blocked"] else "",
                    ]
                )
            offset += len(rows)
        # BOM нужен, чтобы Excel правильно показал русские буквы.
        return "text/csv; charset=utf-8", "users.csv", ("﻿" + out.getvalue()).encode("utf-8")

    @staticmethod
    def _csv_safe(value) -> str:
        """Имена задают сами пользователи — не даём им превратиться в формулу в Excel."""
        text = str(value or "")
        return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text

    # ---------- настройки ----------

    def settings(self) -> dict:
        return {
            "welcome": self.db.get_setting("welcome", DEFAULT_WELCOME),
            "sub_text": self.db.get_setting("sub_text", DEFAULT_SUB_TEXT),
            "protect": self.app.protect,
            "channels": [dict(c) for c in self.db.channels()],
            "bot": self.app.me.get("username", ""),
        }

    def settings_save(self, body: dict):
        for key in ("welcome", "sub_text"):
            if key in body:
                text = str(body[key] or "").strip()
                if not text:
                    raise ApiError("Текст не может быть пустым.")
                if len(text) > MAX_SETTING_TEXT:
                    raise ApiError(f"Текст длиннее {MAX_SETTING_TEXT} символов.")
                self.db.set_setting(key, text)
        if "protect" in body:
            self.db.set_setting("protect", "1" if body["protect"] else "0")
        return None
