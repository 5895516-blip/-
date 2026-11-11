"""Проверка веб-панели: настоящие HTTP-запросы к панели, бот работает на имитации Telegram.

Запуск:  python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import App  # noqa: E402
from config import Config  # noqa: E402
from db import DB  # noqa: E402
from fake_telegram import FakeTelegram  # noqa: E402
from panel import Panel  # noqa: E402

ADMIN = 1
CHANNEL = -1001234
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class PanelTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeTelegram()
        config = Config(token="TEST", admin_ids={ADMIN}, db_path=":memory:", api_url=self.fake.url)
        self.app = App(config, db=DB(":memory:"))
        self.app.broadcast_delay = 0
        self.app.setup()
        self.db = self.app.db
        self.panel = Panel(self.app, "127.0.0.1", 0, "http://panel.test")
        self.panel.public_url = f"http://127.0.0.1:{self.panel.port}"
        self.app.panel = self.panel
        self.panel.start()
        self.opener = urllib.request.build_opener(NoRedirect)
        self.cookie = None
        self.db.upsert_user(ADMIN, "creator", "Автор")
        for uid in (50, 51, 52):
            self.db.upsert_user(uid, f"user{uid}", f"User{uid}", "reels_7" if uid == 51 else None)
        self.fake.reset()

    def tearDown(self):
        self.panel.stop()
        self.app.stop.set()
        self.app.pool.shutdown(wait=True)
        self.fake.close()
        self.db.close()

    # ---- помощники ----

    def http(self, method: str, path: str, body=None, headers=None, raw: bool = False):
        """Возвращает (код ответа, тело, заголовки)."""
        headers = dict(headers or {})
        data = None
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            headers.setdefault("Content-Type", "application/json")
            headers.setdefault("X-Panel", "1")
        if self.cookie:
            headers.setdefault("Cookie", self.cookie)
        request = urllib.request.Request(self.panel.public_url + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=10) as response:
                status, content, response_headers = response.status, response.read(), response.headers
        except urllib.error.HTTPError as e:
            status, content, response_headers = e.code, e.read(), e.headers
        if raw:
            return status, content, response_headers
        return status, json.loads(content or b"{}"), response_headers

    def login(self) -> None:
        token = self.panel.login_link(ADMIN).split("t=")[1]
        status, _, headers = self.http(
            "POST", "/login", f"t={token}".encode(), {"Content-Type": "application/x-www-form-urlencoded"}, raw=True
        )
        self.assertEqual(status, 303)
        self.cookie = headers["Set-Cookie"].split(";")[0]

    def get(self, path: str):
        status, data, _ = self.http("GET", "/api/" + path)
        self.assertEqual(status, 200, data)
        return data

    def post(self, path: str, body: dict | None = None, expect: int = 200):
        status, data, _ = self.http("POST", "/api/" + path, body or {})
        self.assertEqual(status, expect, data)
        return data

    # ---- вход и защита ----

    def test_api_requires_login(self):
        for path in ("overview", "users", "lessons", "settings", "users/export"):
            status, data, _ = self.http("GET", "/api/" + path)
            self.assertEqual(status, 401, path)
        status, _, _ = self.http("POST", "/api/broadcasts", {"text": "спам"})
        self.assertEqual(status, 401)
        self.assertEqual(self.db.broadcasts(), [])

    def test_login_link_is_one_time(self):
        link = self.panel.login_link(ADMIN)
        token = link.split("t=")[1]
        form = {"Content-Type": "application/x-www-form-urlencoded"}

        # Открытие ссылки (например, предпросмотром в мессенджере) не тратит её.
        status, page, headers = self.http("GET", "/login?t=" + token, raw=True)
        self.assertEqual(status, 200)
        self.assertIn("Войти в панель", page.decode())
        self.assertNotIn("Set-Cookie", headers)

        status, _, headers = self.http("POST", "/login", f"t={token}".encode(), form, raw=True)
        self.assertEqual(status, 303)
        cookie = headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

        status, page, headers = self.http("POST", "/login", f"t={token}".encode(), form, raw=True)
        self.assertEqual(status, 400)
        self.assertNotIn("Set-Cookie", headers)
        self.assertIn("Ссылка устарела", page.decode())

        status, _, _ = self.http("POST", "/login", b"t=" + b"x" * 43, form, raw=True)
        self.assertEqual(status, 400)

    def test_expired_token_and_removed_admin(self):
        token = self.panel.login_link(ADMIN).split("t=")[1]
        self.panel._tokens[token] = (ADMIN, time.time() - 1)
        status, _, _ = self.http(
            "POST", "/login", f"t={token}".encode(), {"Content-Type": "application/x-www-form-urlencoded"}, raw=True
        )
        self.assertEqual(status, 400)

        self.login()
        self.get("status")
        self.app.config.admin_ids.clear()  # человека убрали из админов — его вход перестаёт работать
        status, _, _ = self.http("GET", "/api/status")
        self.assertEqual(status, 401)

    def test_forged_request_is_rejected(self):
        self.login()
        status, _, _ = self.http("POST", "/api/broadcasts", {"text": "спам"}, {"X-Panel": ""})
        self.assertEqual(status, 403)
        self.assertEqual(self.db.broadcasts(), [])

    def test_logout(self):
        self.login()
        self.post("logout")
        status, _, _ = self.http("GET", "/api/status")
        self.assertEqual(status, 401)

    def test_pages_and_security_headers(self):
        for path, marker in (("/", "<title>Панель бота</title>"), ("/app.js", "use strict"), ("/app.css", "--ink")):
            status, body, headers = self.http("GET", path, raw=True)
            self.assertEqual(status, 200, path)
            self.assertIn(marker, body.decode())
            self.assertEqual(headers["X-Frame-Options"], "DENY")
            self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        for path in ("/panel.py", "/../config.py", "/.env"):
            status, _, _ = self.http("GET", path, raw=True)
            self.assertEqual(status, 404, path)

    # ---- рассылки ----

    def test_send_broadcast_now(self):
        self.login()
        result = self.post("broadcasts", {"text": "**Привет**, {имя}!", "button_text": "Сайт", "button_target": "example.com"})
        self.assertEqual(result["count"], 4)
        self.app.run_due_jobs()

        message = self.fake.sent("sendMessage", 50)[0]
        self.assertEqual(message["text"], "<b>Привет</b>, User50!")
        self.assertEqual(message["reply_markup"]["inline_keyboard"][0][0]["url"], "https://example.com")
        item = self.get("broadcasts")["items"][0]
        self.assertEqual((item["status"], item["delivered"], item["total"]), ("done", 4, 4))
        self.assertEqual(item["audience"], "Все пользователи")
        self.assertIn("Рассылка завершена", self.fake.texts(ADMIN))

    def test_schedule_and_cancel_broadcast(self):
        self.login()
        when = int(time.time()) + 3600
        bid = self.post("broadcasts", {"text": "Завтра эфир", "scheduled_at": when, "segment": {"type": "source", "value": "reels_7"}})["id"]
        self.app.run_due_jobs()
        self.assertEqual(self.fake.sent("sendMessage"), [])

        status = self.get("status")
        self.assertEqual((status["sending"], status["scheduled"]), (None, 1))
        queue = self.get("overview?tz=-180")["queue"]
        self.assertEqual((queue[0]["id"], queue[0]["audience"]), (bid, "Пришли по ссылке reels_7"))

        self.post(f"broadcasts/{bid}/cancel")
        self.assertEqual(self.db.broadcast(bid)["status"], "cancelled")
        self.post(f"broadcasts/{bid}/cancel", expect=400)

    def test_broadcast_validation(self):
        self.login()
        bad = [
            {"text": ""},
            {"text": "x" * 4001},
            {"text": "x" * 1001, "photo": "P"},
            {"text": "ok", "button_text": "Кнопка", "button_target": "не ссылка"},
            {"text": "ok", "button_text": "", "button_target": "https://example.com"},
            {"text": "ok", "button_text": "Урок", "button_target": "lesson:999"},
            {"text": "ok", "segment": {"type": "lesson", "id": 999}},
            {"text": "ok", "segment": {"type": "new", "days": 0}},
            {"text": "ok", "scheduled_at": int(time.time()) - 3600},
            {"text": "ok", "segment": {"type": "source", "value": "никто_так_не_приходил"}},
        ]
        for body in bad:
            data = self.post("broadcasts", body, expect=400)
            self.assertTrue(data["error"], body)
        self.assertEqual(self.db.broadcasts(), [])

    def test_test_message_goes_only_to_admin(self):
        self.login()
        self.post("broadcasts/test", {"text": "Проверка, {имя}"})
        sent = self.fake.sent("sendMessage")
        self.assertEqual([(p["chat_id"], p["text"]) for p in sent], [(ADMIN, "Проверка, Автор")])
        self.assertEqual(self.db.broadcasts(), [])

    def test_photo_upload(self):
        self.login()
        result = self.post("photo", {"data": base64.b64encode(PNG).decode()})
        upload = self.fake.sent("sendPhoto", ADMIN)[0]
        self.assertEqual(upload["photo"], PNG)
        self.assertTrue(result["photo"].startswith("PHOTO_"))

        self.post("broadcasts", {"text": "С картинкой", "photo": result["photo"], "segment": {"type": "source", "value": "reels_7"}})
        self.app.run_due_jobs()
        self.assertEqual(self.fake.sent("sendPhoto", 51)[0]["photo"], result["photo"])

        self.post("photo", {"data": base64.b64encode(b"<script>alert(1)</script>").decode()}, expect=400)
        self.post("photo", {"data": "не base64!"}, expect=400)

    def test_audience_count(self):
        self.login()
        self.assertEqual(self.post("audience", {"segment": {"type": "all"}})["count"], 4)
        self.assertEqual(self.post("audience", {"segment": {"type": "source", "value": "reels_7"}})["count"], 1)
        self.assertEqual(self.post("audience", {"segment": {"type": "no_views"}})["count"], 4)

    # ---- уроки ----

    def test_lessons(self):
        self.login()
        lesson_id = self.post("lessons", {"title": "Монтаж", "description": "Быстро", "kind": "url", "content": "youtu.be/abc"})["id"]
        item = self.get("lessons")["items"][0]
        self.assertEqual((item["content"], item["link"]), ("https://youtu.be/abc", f"https://t.me/lessons_test_bot?start=lesson{lesson_id}"))

        self.post(f"lessons/{lesson_id}", {"title": "Монтаж 2", "description": "", "kind": "text", "content": "Шаг 1", "code": "reels5", "hidden": True})
        lesson = self.db.lesson(lesson_id)
        self.assertEqual(
            (lesson["title"], lesson["kind"], lesson["content"], lesson["code"], lesson["hidden"]),
            ("Монтаж 2", "text", "Шаг 1", "reels5", 1),
        )

        second = self.post("lessons", {"title": "Свет", "kind": "text", "content": "Текст"})["id"]
        self.post(f"lessons/{second}/move", {"dir": "up"})
        self.assertEqual([l["id"] for l in self.get("lessons")["items"]], [second, lesson_id])

        for body in (
            {"title": "", "kind": "url", "content": "https://a.com"},
            {"title": "Урок", "kind": "url", "content": "просто слова"},
            {"title": "Урок", "kind": "text", "content": ""},
            {"title": "Урок"},
        ):
            self.post("lessons", body, expect=400)
        self.post(f"lessons/{second}", {"title": "Свет", "kind": "text", "content": "Текст", "code": "reels5"}, expect=400)  # код занят
        self.post(f"lessons/{second}", {"title": "Свет", "kind": "text", "content": "Текст", "code": "плохой код"}, expect=400)

        self.post(f"lessons/{second}/notify")
        self.app.run_due_jobs()
        self.assertIn("Новый урок: Свет", self.fake.sent("sendMessage", 50)[0]["text"])

        self.post(f"lessons/{second}/delete")
        self.assertIsNone(self.db.lesson(second))
        self.post(f"lessons/{second}/delete", expect=404)

    def test_file_lesson_keeps_its_file(self):
        self.login()
        lesson_id = self.db.add_lesson("Презентация", "", "document", "FILE1")
        item = self.get("lessons")["items"][0]
        self.assertEqual((item["kind_label"], item["content"]), ("файл", ""))
        self.post(f"lessons/{lesson_id}", {"title": "Презентация v2", "description": "PDF"})
        lesson = self.db.lesson(lesson_id)
        self.assertEqual((lesson["title"], lesson["kind"], lesson["content"]), ("Презентация v2", "document", "FILE1"))

    # ---- автосообщения ----

    def test_autos(self):
        self.login()
        auto_id = self.post("autos", {"delay_minutes": 60, "text": "Как урок?", "button_text": "Сайт", "button_target": "example.com"})["id"]
        item = self.get("autos")["items"][0]
        self.assertEqual((item["delay_minutes"], item["button_target"], item["enabled"], item["sent"]), (60, "https://example.com", True, 0))

        self.post("autos", {"id": auto_id, "delay_minutes": 1440, "text": "Новый текст", "enabled": False})
        item = self.get("autos")["items"][0]
        self.assertEqual((item["delay_minutes"], item["text"], item["enabled"], item["button_text"]), (1440, "Новый текст", False, ""))

        self.post("autos", {"delay_minutes": 0, "text": "x"}, expect=400)
        self.post("autos", {"delay_minutes": 60, "text": ""}, expect=400)
        self.post("autos", {"id": 999, "delay_minutes": 60, "text": "x"}, expect=404)
        self.post(f"autos/{auto_id}/delete")
        self.assertEqual(self.get("autos")["items"], [])

    # ---- люди ----

    def test_users_list_search_and_export(self):
        self.db.upsert_user(60, "evil", "=HYPERLINK(1)", "<script>")
        self.db.set_blocked(52, True)
        self.login()

        data = self.get("users")
        self.assertEqual(data["total"], 5)
        found = self.get("users?q=%40user51")
        self.assertEqual([u["id"] for u in found["items"]], [51])
        self.assertEqual(self.get("users?q=reels_7")["total"], 1)
        self.assertEqual(self.get("users?q=52")["items"][0]["blocked"], 1)

        status, body, headers = self.http("GET", "/api/users/export", raw=True)
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        text = body.decode("utf-8-sig")
        self.assertIn("ID;Имя;Username", text)
        self.assertIn("'=HYPERLINK(1)", text)  # имя не станет формулой в Excel
        self.assertEqual(len(text.strip().splitlines()), 6)

    def test_overview(self):
        lesson_id = self.db.add_lesson("Монтаж", "", "url", "https://a.com")
        self.db.add_view(50, lesson_id)
        self.login()
        data = self.get("overview?tz=-180")
        self.assertEqual(data["users"]["total"], 4)
        self.assertEqual(data["active"], 4)
        self.assertEqual(len(data["daily"]), 30)
        self.assertEqual(data["daily"][-1]["n"], 4)
        self.assertEqual(data["lessons"][0]["total"], 1)
        self.assertEqual(data["sources"], [{"source": "reels_7", "n": 1}])

    # ---- настройки ----

    def test_settings_and_channels(self):
        self.login()
        self.post("settings", {"welcome": "Добро пожаловать!", "protect": True})
        data = self.get("settings")
        self.assertEqual((data["welcome"], data["protect"]), ("Добро пожаловать!", True))
        self.post("settings", {"welcome": "  "}, expect=400)

        self.fake.chats["@my_channel"] = {"id": CHANNEL, "type": "channel", "title": "Мой канал", "username": "my_channel"}
        self.fake.chats[CHANNEL] = self.fake.chats["@my_channel"]
        error = self.post("channels", {"ref": "@my_channel"}, expect=400)["error"]  # бот ещё не админ канала
        self.assertIn("не администратор", error)
        self.post("channels", {"ref": "что-то непонятное"}, expect=400)

        self.fake.members[(CHANNEL, 999)] = "administrator"
        self.assertEqual(self.post("channels", {"ref": "https://t.me/my_channel"})["title"], "Мой канал")
        self.assertEqual(self.get("settings")["channels"][0]["link"], "https://t.me/my_channel")
        self.post(f"channels/{CHANNEL}/delete")
        self.assertEqual(self.get("settings")["channels"], [])


if __name__ == "__main__":
    unittest.main()
