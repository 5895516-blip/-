"""Хранилище бота: SQLite (один файл, ничего устанавливать не нужно)."""
from __future__ import annotations

import json
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
CREATE TABLE IF NOT EXISTS broadcasts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT NOT NULL,              -- text (собрана в панели) | copy (копия сообщения админа)
    payload      TEXT NOT NULL,              -- JSON: текст, кнопка, картинка и т.п.
    segment      TEXT NOT NULL,              -- JSON: кому отправлять
    status       TEXT NOT NULL,              -- scheduled | sending | done | cancelled
    scheduled_at INTEGER NOT NULL,
    created_by   INTEGER NOT NULL,
    created_at   INTEGER NOT NULL,
    started_at   INTEGER,
    finished_at  INTEGER,
    last_user_id INTEGER NOT NULL DEFAULT 0, -- до кого дошли: чтобы продолжить после перезапуска
    total        INTEGER NOT NULL DEFAULT 0,
    delivered    INTEGER NOT NULL DEFAULT 0,
    blocked      INTEGER NOT NULL DEFAULT 0,
    failed       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS autos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    delay_minutes INTEGER NOT NULL,          -- через сколько минут после первого /start
    text          TEXT NOT NULL,
    button_text   TEXT NOT NULL DEFAULT '',
    button_target TEXT NOT NULL DEFAULT '',  -- ссылка или lesson:ID
    enabled       INTEGER NOT NULL DEFAULT 1,
    created_at    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS auto_sent (
    auto_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    sent_at     INTEGER NOT NULL,
    PRIMARY KEY (auto_id, user_id)
);
CREATE TABLE IF NOT EXISTS sessions (
    sid_hash    TEXT PRIMARY KEY,
    admin_id    INTEGER NOT NULL,
    expires_at  INTEGER NOT NULL
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

    def user(self, uid: int):
        return self._one("SELECT * FROM users WHERE id = ?", (uid,))

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

    # ---------- аудитория рассылок ----------

    @staticmethod
    def _segment_where(segment: dict):
        """Условие SQL для сегмента аудитории: (текст условия, параметры)."""
        kind = (segment or {}).get("type", "all")
        if kind == "source":
            return "u.source = ? COLLATE NOCASE", [str(segment.get("value") or "")]
        if kind == "lesson":
            return "EXISTS (SELECT 1 FROM views v WHERE v.user_id = u.id AND v.lesson_id = ?)", [int(segment["id"])]
        if kind == "not_lesson":
            return "NOT EXISTS (SELECT 1 FROM views v WHERE v.user_id = u.id AND v.lesson_id = ?)", [int(segment["id"])]
        if kind == "no_views":
            return "NOT EXISTS (SELECT 1 FROM views v WHERE v.user_id = u.id)", []
        if kind == "new":
            return "u.created_at >= ?", [int(time.time()) - int(segment.get("days") or 7) * 86400]
        return "1 = 1", []

    def segment_count(self, segment: dict) -> int:
        where, args = self._segment_where(segment)
        return self._one(f"SELECT COUNT(*) AS n FROM users u WHERE u.blocked = 0 AND {where}", args)["n"]

    def segment_users(self, segment: dict, after_id: int = 0, limit: int = 200):
        """Следующая порция получателей (по возрастанию id), начиная после after_id."""
        where, args = self._segment_where(segment)
        return self._all(
            f"SELECT u.id, u.first_name FROM users u WHERE u.blocked = 0 AND u.id > ? AND {where}"
            " ORDER BY u.id LIMIT ?",
            [after_id] + args + [limit],
        )

    # ---------- рассылки ----------

    def add_broadcast(self, kind: str, payload: dict, segment: dict, scheduled_at: int, created_by: int) -> int:
        cur = self._run(
            "INSERT INTO broadcasts (kind, payload, segment, status, scheduled_at, created_by, created_at)"
            " VALUES (?, ?, ?, 'scheduled', ?, ?, ?)",
            (
                kind,
                json.dumps(payload, ensure_ascii=False),
                json.dumps(segment or {"type": "all"}, ensure_ascii=False),
                scheduled_at,
                created_by,
                int(time.time()),
            ),
        )
        return cur.lastrowid

    def broadcast(self, broadcast_id: int):
        return self._one("SELECT * FROM broadcasts WHERE id = ?", (broadcast_id,))

    def broadcasts(self, limit: int = 50):
        return self._all("SELECT * FROM broadcasts ORDER BY id DESC LIMIT ?", (limit,))

    def next_due_broadcast(self):
        """Прерванная перезапуском рассылка или первая, чьё время пришло."""
        return self._one(
            "SELECT * FROM broadcasts WHERE status = 'sending' OR (status = 'scheduled' AND scheduled_at <= ?)"
            " ORDER BY (status = 'sending') DESC, scheduled_at, id LIMIT 1",
            (int(time.time()),),
        )

    def update_broadcast(self, broadcast_id: int, **fields) -> None:
        allowed = {"status", "started_at", "finished_at", "last_user_id", "total", "delivered", "blocked", "failed"}
        sets = [k for k in fields if k in allowed]
        if sets:
            sql = "UPDATE broadcasts SET " + ", ".join(f"{k} = ?" for k in sets) + " WHERE id = ?"
            self._run(sql, [fields[k] for k in sets] + [broadcast_id])

    def cancel_broadcast(self, broadcast_id: int) -> bool:
        cur = self._run(
            "UPDATE broadcasts SET status = 'cancelled', finished_at = ?"
            " WHERE id = ? AND status IN ('scheduled', 'sending')",
            (int(time.time()), broadcast_id),
        )
        return cur.rowcount > 0

    # ---------- автосообщения ----------

    def autos(self):
        return self._all(
            "SELECT a.*, (SELECT COUNT(*) FROM auto_sent s WHERE s.auto_id = a.id) AS sent"
            " FROM autos a ORDER BY a.delay_minutes, a.id"
        )

    def auto(self, auto_id: int):
        return self._one("SELECT * FROM autos WHERE id = ?", (auto_id,))

    def save_auto(self, auto_id, delay_minutes: int, text: str, button_text: str, button_target: str, enabled: bool) -> int:
        if auto_id:
            self._run(
                "UPDATE autos SET delay_minutes = ?, text = ?, button_text = ?, button_target = ?, enabled = ?"
                " WHERE id = ?",
                (delay_minutes, text, button_text, button_target, 1 if enabled else 0, auto_id),
            )
            return auto_id
        cur = self._run(
            "INSERT INTO autos (delay_minutes, text, button_text, button_target, enabled, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (delay_minutes, text, button_text, button_target, 1 if enabled else 0, int(time.time())),
        )
        return cur.lastrowid

    def delete_auto(self, auto_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM autos WHERE id = ?", (auto_id,))
            self._conn.execute("DELETE FROM auto_sent WHERE auto_id = ?", (auto_id,))

    def auto_due_users(self, auto, limit: int = 100):
        """Кому пора отправить автосообщение. Тем, кто пришёл до его создания, оно не уходит."""
        now = int(time.time())
        return self._all(
            "SELECT u.id, u.first_name FROM users u"
            " WHERE u.blocked = 0 AND u.created_at >= ? AND u.created_at <= ?"
            " AND NOT EXISTS (SELECT 1 FROM auto_sent s WHERE s.auto_id = ? AND s.user_id = u.id)"
            " ORDER BY u.id LIMIT ?",
            (auto["created_at"], now - auto["delay_minutes"] * 60, auto["id"], limit),
        )

    def mark_auto_sent(self, auto_id: int, uid: int) -> None:
        self._run(
            "INSERT OR IGNORE INTO auto_sent (auto_id, user_id, sent_at) VALUES (?, ?, ?)",
            (auto_id, uid, int(time.time())),
        )

    # ---------- данные для панели ----------

    def daily_new_users(self, days: int, tz_offset_sec: int):
        """Сколько людей пришло в каждый из последних дней: {номер_дня: количество}."""
        since = int(time.time()) - days * 86400
        rows = self._all(
            "SELECT (created_at + ?) / 86400 AS d, COUNT(*) AS n FROM users WHERE created_at >= ? GROUP BY d",
            (tz_offset_sec, since),
        )
        return {r["d"]: r["n"] for r in rows}

    def find_users(self, query: str = "", limit: int = 50, offset: int = 0):
        where, args = "1 = 1", []
        query = (query or "").strip().lstrip("@")
        if query:
            like = f"%{query}%"
            where = "(u.username LIKE ? OR u.first_name LIKE ? OR u.source LIKE ? OR CAST(u.id AS TEXT) = ?)"
            args = [like, like, like, query]
        total = self._one(f"SELECT COUNT(*) AS n FROM users u WHERE {where}", args)["n"]
        rows = self._all(
            "SELECT u.id, u.username, u.first_name, u.source, u.blocked, u.created_at, u.last_seen,"
            " (SELECT COUNT(DISTINCT v.lesson_id) FROM views v WHERE v.user_id = u.id) AS lessons"
            f" FROM users u WHERE {where} ORDER BY u.created_at DESC, u.id DESC LIMIT ? OFFSET ?",
            args + [limit, offset],
        )
        return total, rows

    # ---------- вход в панель ----------

    def add_session(self, sid_hash: str, admin_id: int, expires_at: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))
            self._conn.execute(
                "INSERT INTO sessions (sid_hash, admin_id, expires_at) VALUES (?, ?, ?)",
                (sid_hash, admin_id, expires_at),
            )

    def session_admin(self, sid_hash: str):
        row = self._one(
            "SELECT admin_id FROM sessions WHERE sid_hash = ? AND expires_at >= ?", (sid_hash, int(time.time()))
        )
        return row["admin_id"] if row else None

    def delete_session(self, sid_hash: str) -> None:
        self._run("DELETE FROM sessions WHERE sid_hash = ?", (sid_hash,))
