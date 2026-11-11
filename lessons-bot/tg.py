"""Минимальный клиент Telegram Bot API на стандартной библиотеке Python."""
from __future__ import annotations

import json
import socket
import time
import uuid
import urllib.error
import urllib.request


class TgError(Exception):
    """Telegram ответил ошибкой (например, 403 — пользователь заблокировал бота)."""

    def __init__(self, code: int, description: str, retry_after: int | None = None):
        super().__init__(f"{code}: {description}")
        self.code = code
        self.description = description
        self.retry_after = retry_after


class TgNetworkError(Exception):
    """До Telegram не удалось достучаться (нет сети, таймаут)."""


class Telegram:
    def __init__(self, token: str, api_url: str = "https://api.telegram.org", timeout: float = 30):
        self._base = f"{api_url.rstrip('/')}/bot{token}/"
        self._timeout = timeout

    def call(self, method: str, _timeout: float | None = None, **params):
        """Вызов метода Bot API. Параметры со значением None не отправляются."""
        body = json.dumps({k: v for k, v in params.items() if v is not None}).encode("utf-8")
        attempts = 0
        while True:
            attempts += 1
            try:
                return self._request(method, body, _timeout or self._timeout)
            except TgError as e:
                # Короткий «подожди» от Telegram — ждём и повторяем один раз.
                if e.code == 429 and e.retry_after is not None and e.retry_after <= 5 and attempts < 2:
                    time.sleep(e.retry_after + 0.5)
                    continue
                raise

    def upload(self, method: str, field: str, filename: str, data: bytes, mime: str, **params):
        """Вызов метода с загрузкой файла (например, sendPhoto с картинкой с компьютера)."""
        boundary = uuid.uuid4().hex
        chunks = []
        for key, value in params.items():
            if value is None:
                continue
            text = value if isinstance(value, str) else json.dumps(value)
            chunks.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{text}\r\n'.encode("utf-8")
            )
        safe_name = "".join(c for c in filename if c.isascii() and (c.isalnum() or c in "._-")) or "file"
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{safe_name}"\r\n'
            f"Content-Type: {mime}\r\n\r\n".encode("utf-8")
            + data
            + b"\r\n"
        )
        chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
        return self._request(method, b"".join(chunks), 120, f"multipart/form-data; boundary={boundary}")

    def _request(self, method: str, body: bytes, timeout: float, content_type: str = "application/json"):
        req = urllib.request.Request(self._base + method, data=body, headers={"Content-Type": content_type})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                payload = json.loads(e.read().decode("utf-8"))
            except Exception:
                raise TgError(e.code, e.reason or "HTTP error") from None
        except (urllib.error.URLError, socket.timeout, ConnectionError, TimeoutError, OSError) as e:
            # В текст ошибки не включаем URL: в нём токен бота.
            raise TgNetworkError(type(e).__name__) from None
        except ValueError:
            raise TgNetworkError("bad response") from None

        if payload.get("ok"):
            return payload.get("result")
        raise TgError(
            int(payload.get("error_code") or 0),
            str(payload.get("description") or "unknown error"),
            (payload.get("parameters") or {}).get("retry_after"),
        )
