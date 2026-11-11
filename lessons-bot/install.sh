#!/usr/bin/env bash
# Установка (и обновление) бота на сервере с Ubuntu или Debian.
#
#   bash install.sh              — адрес сервера определится сам
#   bash install.sh 203.0.113.10 — если нужно указать адрес сервера вручную
#
# Запускать от имени root из папки lessons-bot. Повторный запуск обновляет код,
# а настройки (.env) и данные (data/) не трогает.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${LESSONS_BOT_DIR:-/opt/lessons-bot}"
UNIT_DIR="${LESSONS_BOT_UNIT_DIR:-/etc/systemd/system}"
SERVICE=lessons-bot
RUN_USER=lessonsbot

fail() { echo "ОШИБКА: $*" >&2; exit 1; }

[ "$(id -u)" = 0 ] || fail "нужны права администратора. Запусти так: sudo bash install.sh"
command -v systemctl >/dev/null || fail "на этом сервере нет systemd. Нужен обычный сервер с Ubuntu или Debian."
[ -f "$SRC/.env" ] || [ -f "$DEST/.env" ] || fail "нет файла .env с токеном бота рядом с install.sh."

if ! command -v python3 >/dev/null; then
  echo "Ставлю Python…"
  apt-get update -qq && apt-get install -y -qq python3
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
  || fail "нужен Python 3.9 или новее. Возьми сервер с Ubuntu 22.04 или 24.04."

# ---- адрес сервера для ссылки на панель ----
IP="${1:-}"
FORCE_URL=no
[ -n "$IP" ] && FORCE_URL=yes   # адрес указан вручную — он важнее того, что записано в настройках
if [ -z "$IP" ]; then
  IP="$( (ip -4 route get 1.1.1.1 2>/dev/null || true) | awk '{for (i = 1; i <= NF; i++) if ($i == "src") print $(i + 1)}' | head -n 1)"
fi
if [ -z "$IP" ]; then
  IP="$( (hostname -I 2>/dev/null || true) | awk '{print $1}')"
fi
[ -n "$IP" ] || fail "не удалось определить адрес сервера. Запусти так: bash install.sh АДРЕС_СЕРВЕРА"
case "$IP" in
  10.*|192.168.*|172.1[6-9].*|172.2[0-9].*|172.3[01].*|127.*)
    fail "определился внутренний адрес ($IP). Запусти так: bash install.sh ВНЕШНИЙ_АДРЕС_СЕРВЕРА (он указан в письме от хостинга)" ;;
esac

# ---- файлы ----
echo "Копирую бота в $DEST…"
mkdir -p "$DEST/panel" "$DEST/data"
cp "$SRC"/*.py "$DEST/"
cp "$SRC"/panel/* "$DEST/panel/"
[ -f "$DEST/.env" ] || cp "$SRC/.env" "$DEST/.env"

# Панель должна открываться по адресу сервера, а не только с самого сервера.
python3 - "$DEST/.env" "$IP" "$FORCE_URL" <<'PY'
import sys

path, ip, force = sys.argv[1], sys.argv[2], sys.argv[3] == "yes"
lines = open(path, encoding="utf-8").read().splitlines()
values = {l.split("=", 1)[0].strip(): l.split("=", 1)[1].strip() for l in lines if "=" in l and not l.lstrip().startswith("#")}
port = values.get("PANEL_PORT") or "8080"
wanted = {"PANEL_HOST": "0.0.0.0"}
current = values.get("PANEL_URL", "")
if force or not current or "localhost" in current or "127.0.0.1" in current:
    wanted["PANEL_URL"] = f"http://{ip}:{port}"
out, done = [], set()
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
    if key in wanted:
        out.append(f"{key}={wanted[key]}")
        done.add(key)
    else:
        out.append(line)
out += [f"{k}={v}" for k, v in wanted.items() if k not in done]
open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
PY

# ---- отдельный пользователь: бот не работает с правами администратора ----
id -u "$RUN_USER" >/dev/null 2>&1 || useradd --system --home-dir "$DEST" --shell /usr/sbin/nologin "$RUN_USER"
chown -R "$RUN_USER":"$RUN_USER" "$DEST"
chmod 600 "$DEST/.env"

# ---- автозапуск ----
cat > "$UNIT_DIR/$SERVICE.service" <<EOF
[Unit]
Description=Telegram lessons bot
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$DEST
Environment=PYTHONUNBUFFERED=1
ExecStart=$(command -v python3) $DEST/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null 2>&1
systemctl restart "$SERVICE"

# ---- открыть порт панели, если включён файрвол ----
PORT="$(grep -E '^PANEL_PORT=' "$DEST/.env" | tail -n 1 | cut -d= -f2)"
PORT="${PORT:-8080}"
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
  ufw allow "$PORT"/tcp >/dev/null
fi

sleep 3
if systemctl is-active --quiet "$SERVICE"; then
  echo
  echo "ГОТОВО. Бот работает и будет сам запускаться после перезагрузки сервера."
  echo "Панель управления: отправь боту в Telegram команду /panel"
  echo
  echo "Полезные команды:"
  echo "  journalctl -u $SERVICE -n 50     — что бот пишет в журнал"
  echo "  systemctl restart $SERVICE       — перезапустить"
  echo "  systemctl stop $SERVICE          — остановить"
else
  echo
  echo "Бот не запустился. Вот что он написал:"
  journalctl -u "$SERVICE" -n 30 --no-pager || true
  exit 1
fi
