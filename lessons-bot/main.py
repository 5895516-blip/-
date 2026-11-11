"""Запуск бота: python3 main.py"""
from __future__ import annotations

import logging
import signal
import sys

from app import App
from config import load_config


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    app = App(load_config())

    def shutdown(*_):
        # Прерываем ожидание новых сообщений, чтобы бот остановился сразу.
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        app.run()
    except KeyboardInterrupt:
        logging.getLogger("bot").info("Останавливаюсь…")
        app.stop.set()
        app.pool.shutdown(wait=True)


if __name__ == "__main__":
    main()
