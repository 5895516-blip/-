#!/bin/bash
# Настраивает Google Chrome на Mac: файлы скачиваются сразу в «Загрузки», без вопроса «куда сохранить».
set -e

PREFS="$HOME/Library/Application Support/Google/Chrome/Default/Preferences"
DL="$HOME/Downloads"

if [ ! -f "$PREFS" ]; then
  echo "Не нашёл настройки Chrome. Откройте Chrome хотя бы один раз и запустите снова."
  exit 1
fi

echo "Закрываю Chrome..."
osascript -e 'quit app "Google Chrome"' || true
sleep 3

cp "$PREFS" "$PREFS.backup"

osascript -l JavaScript - "$PREFS" "$DL" <<'JS'
ObjC.import('Foundation');
function run(argv) {
  var path = argv[0], dir = argv[1];
  var text = $.NSString.stringWithContentsOfFileEncodingError(path, $.NSUTF8StringEncoding, null).js;
  var p = JSON.parse(text);
  p.download = p.download || {};
  p.download.default_directory = dir;
  p.download.prompt_for_download = false;
  p.savefile = p.savefile || {};
  p.savefile.default_directory = dir;
  $(JSON.stringify(p)).writeToFileAtomicallyEncodingError(path, true, $.NSUTF8StringEncoding, null);
}
JS

echo "Готово. Chrome будет сохранять файлы сразу в «Загрузки»."
open -a "Google Chrome"
open "$DL"
