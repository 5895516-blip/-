#!/usr/bin/env bash
# Рендер HTML-вёрстки КП в PDF через headless Chrome/Chromium.
# Использование: render_pdf.sh kp.html "КП_....pdf"
# logo.png должен лежать рядом с kp.html.
set -euo pipefail
HTML="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUT="$2"

CH=""
for c in google-chrome google-chrome-stable chromium chromium-browser \
         /opt/pw-browsers/chromium-*/chrome-linux/chrome \
         "$HOME"/.cache/ms-playwright/chromium-*/chrome-linux/chrome \
         "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; do
  if command -v "$c" >/dev/null 2>&1 || [ -x "$c" ]; then CH="$c"; break; fi
done
if [ -z "$CH" ]; then
  echo "Chrome/Chromium не найден. Поставь: pip install playwright && playwright install chromium" >&2
  exit 1
fi

"$CH" --headless --no-sandbox --disable-gpu --no-pdf-header-footer \
      --print-to-pdf="$OUT" "file://$HTML" 2>/dev/null
pdfinfo "$OUT" | grep Pages || true
