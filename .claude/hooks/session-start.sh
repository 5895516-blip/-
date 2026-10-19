#!/bin/bash
# Готовит облачный контейнер Claude Code к скиллу motion-3d-montage (моушн, 3D и монтаж кодом):
# Chromium для рендера без окна с WebGL2, опциональные пакеты, проверка окружения.
# Запускается в начале каждой облачной сессии; повторный запуск ничего не ломает.
set -uo pipefail

# Только в облаке: на Mac всё ставит motion-3d-setup-mac.sh.
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
export PYTHONDONTWRITEBYTECODE=1   # не оставлять __pycache__ внутри скилла

# 1. Chromium. Под root он не стартует без --no-sandbox, а видеокарты в контейнере нет —
#    WebGL2 считает SwiftShader. Обёртка лежит в PATH под именем chromium, поэтому скрипты
#    скилла находят её сами; CHROME_PATH — на всякий случай.
real=""
for c in "${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}/chromium" \
         "${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}"/chromium-*/chrome-linux*/chrome \
         /usr/bin/google-chrome-stable /usr/bin/google-chrome; do
  if [ -x "$c" ]; then real="$c"; break; fi
done
if [ -n "$real" ]; then
  wrapper=/usr/local/bin/chromium
  if [ -e "$wrapper" ] && ! grep -q "motion-3d-montage" "$wrapper" 2>/dev/null; then
    wrapper=/usr/local/bin/motion-chrome   # чужой chromium не трогаем
  fi
  cat > "$wrapper" <<EOF
#!/bin/sh
# Chromium for headless rendering (motion-3d-montage) in a cloud container:
# running as root needs --no-sandbox; there is no GPU, so WebGL2 runs on SwiftShader;
# no background calls to Google update services while rendering.
exec "$real" --no-sandbox --enable-unsafe-swiftshader --disable-background-networking --disable-component-update "\$@"
EOF
  chmod +x "$wrapper"
  if [ -n "${CLAUDE_ENV_FILE:-}" ] && ! grep -qx "export CHROME_PATH=$wrapper" "$CLAUDE_ENV_FILE" 2>/dev/null; then
    echo "export CHROME_PATH=$wrapper" >> "$CLAUDE_ENV_FILE"
  fi
else
  echo "motion-3d-montage: Chromium не найден — рендер кадров работать не будет."
fi

# 2. Опциональное: OpenCV (монтаж поверх видео — стереть субтитры, трекинг) и faster-whisper
#    (слова озвучки с таймкодами). Ставятся, только если сетевая политика окружения пускает
#    на PyPI; без них рендер, звук и сборка видео работают.
missing=()
python3 -c "import cv2" 2>/dev/null || missing+=(opencv-python-headless)
python3 -c "import faster_whisper" 2>/dev/null || missing+=(faster-whisper)
if [ ${#missing[@]} -gt 0 ]; then
  probe=$(mktemp -d)
  if python3 -m pip download pip --no-deps --timeout 5 --retries 0 -q -d "$probe" >/dev/null 2>&1; then
    python3 -m pip install -q --disable-pip-version-check "${missing[@]}" >/dev/null 2>&1 \
      || echo "motion-3d-montage: не удалось поставить ${missing[*]}"
  else
    echo "motion-3d-montage: PyPI закрыт сетевой политикой окружения — не поставлены: ${missing[*]}"
  fi
  rm -rf "$probe"
fi

# 3. Проверка скриптом самого скилла: стартует Chrome и проверяет WebGL2 и float-текстуры.
skill=""
for d in "$PROJECT_DIR/.claude/skills/motion-3d-montage" "$HOME/.claude/skills/motion-3d-montage"; do
  if [ -f "$d/template/scripts/check_env.py" ]; then skill="$d"; break; fi
done
if [ -n "$skill" ]; then
  if report=$(timeout 120 python3 "$skill/template/scripts/check_env.py" 2>&1); then
    echo "motion-3d-montage: окружение готово к рендеру"
  else
    echo "motion-3d-montage: check_env.py нашёл проблемы"
  fi
  echo "$report" | sed -e '1d' -e '/^$/d' -e '/^• ready/d'
else
  echo "motion-3d-montage: скилла нет ни в .claude/skills репозитория, ни в ~/.claude/skills — пришли архив скилла"
fi
exit 0
