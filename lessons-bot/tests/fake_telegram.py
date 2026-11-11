"""Имитация сервера Telegram Bot API для тестов: принимает те же HTTP-запросы, что и настоящий."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BOT = {"id": 999, "is_bot": True, "first_name": "Уроки", "username": "lessons_test_bot"}


class FakeTelegram:
    def __init__(self):
        self.calls: list = []          # [(метод, параметры)]
        self.members: dict = {}        # {(chat_id, user_id): статус}
        self.chats: dict = {}          # {chat_id или "@username": описание чата}
        self.fail: dict = {}           # {(метод, chat_id): (код, описание)}
        self.updates: list = []        # очередь для getUpdates
        self._mid = 1000
        self._lock = threading.Lock()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                method = self.path.rsplit("/", 1)[-1]
                params = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                status, payload = fake.handle(method, params)
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def handle(self, method: str, p: dict):
        with self._lock:
            self.calls.append((method, p))
            chat_id = p.get("chat_id")
            if (method, chat_id) in self.fail:
                code, desc = self.fail[(method, chat_id)]
                return code, {"ok": False, "error_code": code, "description": desc}

            if method == "getMe":
                return 200, {"ok": True, "result": BOT}
            if method == "getUpdates":
                updates, self.updates = self.updates, []
                return 200, {"ok": True, "result": updates}
            if method == "getChat":
                chat = self.chats.get(chat_id)
                if not chat:
                    return 400, {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}
                return 200, {"ok": True, "result": chat}
            if method == "getChatMember":
                status = self.members.get((chat_id, p.get("user_id")), "left")
                return 200, {"ok": True, "result": {"status": status, "user": {"id": p.get("user_id")}}}
            if method == "createChatInviteLink":
                return 200, {"ok": True, "result": {"invite_link": "https://t.me/+secretinvite"}}
            if method in ("answerCallbackQuery", "deleteMessage", "setMyCommands"):
                return 200, {"ok": True, "result": True}
            if method == "copyMessage":
                self._mid += 1
                return 200, {"ok": True, "result": {"message_id": self._mid}}
            # sendMessage, sendPhoto, editMessageText и т.п.
            self._mid += 1
            return 200, {"ok": True, "result": {"message_id": self._mid, "chat": {"id": chat_id}}}

    # ---- удобства для проверок ----

    def reset(self):
        with self._lock:
            self.calls.clear()

    def sent(self, method: str | None = None, chat_id: int | None = None) -> list:
        with self._lock:
            return [
                p
                for m, p in self.calls
                if (method is None or m == method) and (chat_id is None or p.get("chat_id") == chat_id)
            ]

    def texts(self, chat_id: int) -> str:
        """Весь текст, показанный пользователю (сообщения, правки, подписи)."""
        return "\n".join(str(p.get("text") or p.get("caption") or "") for p in self.sent(chat_id=chat_id))

    def buttons(self, chat_id: int) -> list:
        out = []
        for p in self.sent(chat_id=chat_id):
            for row in (p.get("reply_markup") or {}).get("inline_keyboard", []):
                out.extend(row)
        return out
