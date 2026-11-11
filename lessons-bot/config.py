"""Настройки бота: читаются из переменных окружения и файла .env рядом с ботом."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env_file(path: str) -> None:
    """Простой разбор .env: строки вида КЛЮЧ=значение. Уже заданные переменные не трогаем."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)


@dataclass
class Config:
    token: str
    admin_ids: set = field(default_factory=set)
    db_path: str = os.path.join(BASE_DIR, "data", "bot.db")
    api_url: str = "https://api.telegram.org"
    panel_port: int = 8080          # 0 — панель выключена
    panel_host: str = "0.0.0.0"
    panel_url: str = "http://localhost:8080"


def load_config() -> Config:
    load_env_file(os.path.join(BASE_DIR, ".env"))

    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token or token.startswith("123456:"):
        raise SystemExit(
            "Не задан BOT_TOKEN. Скопируй .env.example в .env и впиши токен от @BotFather."
        )

    admin_ids = set()
    for part in os.environ.get("ADMIN_IDS", "").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if not part.lstrip("-").isdigit():
            raise SystemExit(f"ADMIN_IDS: «{part}» — это не числовой ID. Узнать свой ID: команда /id в боте.")
        admin_ids.add(int(part))

    db_path = os.environ.get("DB_PATH", "").strip() or os.path.join(BASE_DIR, "data", "bot.db")
    if not os.path.isabs(db_path):
        db_path = os.path.join(BASE_DIR, db_path)

    api_url = os.environ.get("TELEGRAM_API_URL", "").strip() or "https://api.telegram.org"

    port_raw = os.environ.get("PANEL_PORT", "").strip() or "8080"
    if not port_raw.isdigit() or int(port_raw) > 65535:
        raise SystemExit(f"PANEL_PORT: «{port_raw}» — это не номер порта. Пример: 8080 (0 — выключить панель).")
    panel_port = int(port_raw)
    panel_url = os.environ.get("PANEL_URL", "").strip().rstrip("/") or f"http://localhost:{panel_port}"
    if not panel_url.startswith(("http://", "https://")):
        panel_url = "http://" + panel_url

    return Config(
        token=token,
        admin_ids=admin_ids,
        db_path=db_path,
        api_url=api_url.rstrip("/"),
        panel_port=panel_port,
        panel_host=os.environ.get("PANEL_HOST", "").strip() or "0.0.0.0",
        panel_url=panel_url,
    )
