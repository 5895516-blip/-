"""Хранилище бота: SQLite (один файл, ничего устанавливать не нужно)."""
from __future__ import annotations

import os
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    source      TEXT,              -- с какой ссылкой человек пришёл впервые
    pending     TEXT,              -- какой урок выдать после подписки
    blocked     INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL,
    last_seen   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS lessons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT UNIQUE,       -- хвост ссылки t.me/бот?start=КОД
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    kind        TEXT NOT NULL,     -- url | text | photo | video | document | ...
    content     TEXT NOT NULL,     -- ссылка, текст или file_id
    position    INTEGER NOT NULL DEFAULT 0,
    hidden      INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS views (
    user_id     INTEGER NOT NULL,
    lesson_id   INTEGER NOT NULL,
    created_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS views_lesson ON views (lesson_id);
CREATE TABLE IF NOT EXISTS channels (
    chat_id     INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    link        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);
"""


class DB:
    def __init__(self, path: str):
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _all(self, sql: str, args=()):
        with self._lock:
            return self._conn.execute(sql, args).fetchall()

    def _one(self, sql: str, args=()):
        with self._lock:
            return self._conn.execute(sql, args).fetchone()

    def _run(self, sql: str, args=()):
        with self._lock:
            return self._conn.execute(sql, args)

    # ---------- пользователи ----------

    def upsert_user(self, uid: int, username: str | None, first_name: str | None, source: str | None = None) -> bool:
        """Запоминает пользователя. Возвращает True, если он новый."""
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO users (id, username, first_name, source, created_at, last_seen)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (uid, username, first_name, source, now, now),
            )
            if cur.rowcount:
                return True
            self._conn.execute(
                "UPDATE users SET username = ?, first_name = ?, last_seen = ?, blocked = 0,"
                " source = COALESCE(source, ?) WHERE id = ?",
                (username, first_name, now, source, uid),
            )
            return False

    def set_pending(self, uid: int, code: str | None) -> None:
        self._run("UPDATE users SET pending = ? WHERE id = ?", (code, uid))

    def pop_pending(self, uid: int) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT pending FROM users WHERE id = ?", (uid,)).fetchone()
            self._conn.execute("UPDATE users SET pending = NULL WHERE id = ?", (uid,))
            return row["pending"] if row else None

    def set_blocked(self, uid: int, blocked: bool) -> None:
        self._run("UPDATE users SET blocked = ? WHERE id = ?", (1 if blocked else 0, uid))

    def active_user_ids(self) -> list:
        return [r["id"] for r in self._all("SELECT id FROM users WHERE blocked = 0 ORDER BY id")]

    def user_stats(self) -> dict:
        now = int(time.time())
        row = self._one(
            "SELECT COUNT(*) AS total,"
            " COALESCE(SUM(blocked), 0) AS blocked,"
            " COALESCE(SUM(created_at >= ?), 0) AS day,"
            " COALESCE(SUM(created_at >= ?), 0) AS week"
            " FROM users",
            (now - 86400, now - 7 * 86400),
        )
        return dict(row)

    def top_sources(self, limit: int = 10):
        return self._all(
            "SELECT source, COUNT(*) AS n FROM users WHERE source IS NOT NULL AND source != ''"
            " GROUP BY source ORDER BY n DESC, source LIMIT ?",
            (limit,),
        )

    # ---------- уроки ----------

    def add_lesson(self, title: str, description: str, kind: str, content: str) -> int:
        with self._lock:
            pos = self._conn.execute("SELECT COALESCE(MAX(position), 0) + 1 AS p FROM lessons").fetchone()["p"]
            cur = self._conn.execute(
                "INSERT INTO lessons (title, description, kind, content, position, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (title, description, kind, content, pos, int(time.time())),
            )
            lesson_id = cur.lastrowid
            code = f"lesson{lesson_id}"
            n = 0
            while self._conn.execute("SELECT 1 FROM lessons WHERE code = ?", (code,)).fetchone():
                n += 1
                code = f"lesson{lesson_id}_{n}"
            self._conn.execute("UPDATE lessons SET code = ? WHERE id = ?", (code, lesson_id))
            return lesson_id

    def lesson(self, lesson_id: int):
        return self._one("SELECT * FROM lessons WHERE id = ?", (lesson_id,))

    def lesson_by_code(self, code: str):
        return self._one("SELECT * FROM lessons WHERE code = ? COLLATE NOCASE", (code,))

    def lessons(self, include_hidden: bool = False):
        where = "" if include_hidden else "WHERE hidden = 0"
        return self._all(f"SELECT * FROM lessons {where} ORDER BY position, id")

    def update_lesson(self, lesson_id: int, **fields) -> None:
        allowed = {"title", "description", "kind", "content", "code", "hidden"}
        sets = [k for k in fields if k in allowed]
        if not sets:
            return
        sql = "UPDATE lessons SET " + ", ".join(f"{k} = ?" for k in sets) + " WHERE id = ?"
        self._run(sql, [fields[k] for k in sets] + [lesson_id])

    def delete_lesson(self, lesson_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
            self._conn.execute("DELETE FROM views WHERE lesson_id = ?", (lesson_id,))

    def move_lesson(self, lesson_id: int, direction: int) -> None:
        """Сдвигает урок в списке: direction = -1 вверх, +1 вниз."""
        with self._lock:
            ids = [r["id"] for r in self._conn.execute("SELECT id FROM lessons ORDER BY position, id")]
            if lesson_id not in ids:
                return
            i = ids.index(lesson_id)
            j = i + direction
            if j < 0 or j >= len(ids):
                return
            ids[i], ids[j] = ids[j], ids[i]
            for pos, lid in enumerate(ids, start=1):
                self._conn.execute("UPDATE lessons SET position = ? WHERE id = ?", (pos, lid))

    def add_view(self, uid: int, lesson_id: int) -> None:
        self._run(
            "INSERT INTO views (user_id, lesson_id, created_at) VALUES (?, ?, ?)",
            (uid, lesson_id, int(time.time())),
        )

    def lesson_views(self, lesson_id: int) -> dict:
        row = self._one(
            "SELECT COUNT(*) AS total, COUNT(DISTINCT user_id) AS people FROM views WHERE lesson_id = ?",
            (lesson_id,),
        )
        return dict(row)

    # ---------- каналы обязательной подписки ----------

    def channels(self):
        return self._all("SELECT * FROM channels ORDER BY rowid")

    def add_channel(self, chat_id: int, title: str, link: str) -> None:
        self._run(
            "INSERT INTO channels (chat_id, title, link) VALUES (?, ?, ?)"
            " ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title, link = excluded.link",
            (chat_id, title, link),
        )

    def delete_channel(self, chat_id: int) -> None:
        self._run("DELETE FROM channels WHERE chat_id = ?", (chat_id,))

    # ---------- настройки ----------

    def get_setting(self, key: str, default: str = "") -> str:
        row = self._one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self._run(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
