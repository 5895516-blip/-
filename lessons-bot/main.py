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
    config = load_config()
    app = App(config)
    if config.panel_port:
        from panel import Panel

        try:
            app.panel = Panel(app, config.panel_host, config.panel_port, config.panel_url)
        except OSError as e:
            raise SystemExit(
                f"Не удалось запустить панель на порту {config.panel_port}: {e.strerror}. "
                "Поменяй PANEL_PORT в .env или поставь PANEL_PORT=0, чтобы выключить панель."
            )
        app.panel.start()

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
