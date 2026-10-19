#!/bin/bash
# Ставит на Mac всё для скилла motion-3d-montage (моушн, 3D и монтаж кодом в Claude Code):
# Homebrew, ffmpeg, Python с numpy/Pillow (+ OpenCV и faster-whisper), poppler для PDF,
# Google Chrome — и кладёт сам скилл в ~/.claude/skills. В конце проверяет окружение.
#
#   bash motion-3d-setup-mac.sh                                  # архив ищется в «Загрузках»
#   bash motion-3d-setup-mac.sh ~/Downloads/motion-3d-montage.zip
set -euo pipefail

if [ "$(uname)" != "Darwin" ]; then
  echo "Этот скрипт — для macOS."
  exit 1
fi

NAME=motion-3d-montage
DEST="$HOME/.claude/skills/$NAME"
HERE="$(cd "$(dirname "$0")" && pwd)"

# 1. Скилл: архив или папка из аргумента, иначе архив в «Загрузках» (или папка — Safari сам
#    распаковывает скачанные zip), иначе копия рядом со скриптом.
SRC="${1:-}"
if [ -z "$SRC" ]; then
  for c in "$HOME/Downloads/$NAME.zip" "$HOME/Downloads"/*"$NAME"*.zip "$HOME/Downloads/$NAME" \
           "$HERE/.claude/skills/$NAME"; do
    if [ -e "$c" ]; then SRC="$c"; break; fi
  done
fi
if [ -z "$SRC" ] || [ ! -e "$SRC" ]; then
  echo "Не нашёл скилл. Укажи архив: bash $0 ~/Downloads/$NAME.zip"
  exit 1
fi
echo "Скилл: $SRC"

# 2. Homebrew — установщик программ для Mac. Если его нет, попросит пароль от Mac — это нормально.
find_brew() {
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [ -x "$b" ]; then eval "$("$b" shellenv)"; return 0; fi
  done
  return 1
}
if ! find_brew; then
  echo "Ставлю Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  find_brew
fi
# чтобы ffmpeg и python3 из Homebrew видели новые окна Терминала и Claude Code
if ! grep -qs "brew shellenv" "$HOME/.zprofile"; then
  echo "eval \"\$($(command -v brew) shellenv)\"" >> "$HOME/.zprofile"
fi

# 3. Программы: ffmpeg (сборка видео), Python, poppler (PDF → картинки), Google Chrome (рендер кадров).
echo "Ставлю ffmpeg, Python и poppler..."
brew install ffmpeg python poppler
if [ ! -d "/Applications/Google Chrome.app" ] && [ ! -d "$HOME/Applications/Google Chrome.app" ]; then
  echo "Ставлю Google Chrome..."
  brew install --cask google-chrome
fi

# 4. Пакеты Python. Python из Homebrew защищён от pip (PEP 668), поэтому ставим в папку
#    пользователя. OpenCV и faster-whisper не обязательны: если для этой версии Python
#    ещё нет готовых сборок, рендер всё равно работает.
PY="$(brew --prefix)/bin/python3"
PIP=("$PY" -m pip install --user --disable-pip-version-check --no-warn-script-location --quiet)
if "$PY" -c "import os, sysconfig; exit(not os.path.exists(os.path.join(sysconfig.get_path('stdlib'), 'EXTERNALLY-MANAGED')))"; then
  PIP+=(--break-system-packages)
fi
echo "Ставлю numpy и Pillow..."
"${PIP[@]}" numpy pillow
for pkg in opencv-python faster-whisper; do
  echo "Ставлю $pkg..."
  "${PIP[@]}" --only-binary=:all: "$pkg" || echo "  $pkg не встал — это необязательно, рендер работает и без него"
done

# 5. Кладём скилл в ~/.claude/skills. Старая версия уезжает в ~/.claude/skills-backup
#    (не внутрь skills, иначе Claude увидит два одинаковых скилла).
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
if [ -d "$SRC" ]; then
  cp -R "$SRC" "$TMP/$NAME"
else
  unzip -q "$SRC" -d "$TMP"
fi
SKILL_MD="$(find "$TMP" -maxdepth 3 -name SKILL.md -not -path "*/__MACOSX/*" | head -1)"
if [ -z "$SKILL_MD" ]; then
  echo "В $SRC нет SKILL.md — это не тот архив."
  exit 1
fi
NEW="$(dirname "$SKILL_MD")"
mkdir -p "$HOME/.claude/skills"
if [ -d "$DEST" ]; then
  if [ -d "$DEST/bin" ]; then mv "$DEST/bin" "$NEW/bin"; fi   # своя сборка ffmpeg переживает переустановку
  mkdir -p "$HOME/.claude/skills-backup"
  mv "$DEST" "$HOME/.claude/skills-backup/$NAME-$(date +%Y%m%d-%H%M%S)"
fi
mv "$NEW" "$DEST"
# скрипты скилла ищут ffmpeg и в своей папке bin — так он найдётся, даже если PATH без Homebrew
mkdir -p "$DEST/bin"
[ -e "$DEST/bin/ffmpeg" ] || ln -s "$(brew --prefix)/bin/ffmpeg" "$DEST/bin/ffmpeg"
echo "Скилл установлен: $DEST"

# 6. Проверка: Chrome без окна, WebGL2, ffmpeg с libx264, пакеты Python, место на диске.
echo
PYTHONDONTWRITEBYTECODE=1 "$PY" "$DEST/template/scripts/check_env.py" || true
echo
if ! command -v claude >/dev/null 2>&1; then
  echo "Скилл работает в Claude Code: приложение Claude → вкладка Code."
fi
echo "Готово. Перезапусти Claude Code и напиши: «проверь окружение для моушн-скилла»."
