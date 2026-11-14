#!/bin/bash
# Собирает «Суфлёр» и ставит его на подключённый кабелем iPhone.
#
#   bash Sufler/tools/install.sh
#
# Нужен Mac с Xcode, в котором выполнен вход в Apple ID (Xcode → Settings → Accounts).
# Если скрипт не угадал команду разработчика или телефон, их можно задать вручную:
#
#   TEAM_ID=ABCDE12345 DEVICE_ID=00008110-001234567890801E bash Sufler/tools/install.sh

set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT="Sufler.xcodeproj"
SCHEME="Sufler"
BUILD_DIR="build/install"

fail() {
  echo ""
  echo "✗ $1"
  exit 1
}

command -v xcodebuild >/dev/null 2>&1 || fail "Не найден Xcode. Установите его из App Store и откройте один раз."

# --- Команда разработчика (Team ID) -----------------------------------------
TEAM="${TEAM_ID:-}"
if [ -z "$TEAM" ]; then
  TEAM=$(security find-certificate -a -c "Apple Development" -p 2>/dev/null \
    | openssl x509 -noout -subject 2>/dev/null \
    | sed -nE 's/.*OU ?= ?([A-Z0-9]{10}).*/\1/p' | head -1 || true)
fi
[ -n "$TEAM" ] || fail "Не нашёл Apple ID для подписи. Откройте Sufler.xcodeproj в Xcode, на вкладке Signing & Capabilities выберите Team и нажмите ▶ — это тот же результат."
echo "• Команда разработчика: $TEAM"

# --- Телефон -----------------------------------------------------------------
DEVICE="${DEVICE_ID:-}"
if [ -z "$DEVICE" ]; then
  DEVICE=$(xcrun xctrace list devices 2>/dev/null \
    | awk '/^== Devices ==/{on=1; next} /^== /{on=0} on' \
    | sed -nE 's/.*\(([0-9A-Fa-f]{8}-[0-9A-Fa-f]{16}|[0-9A-Fa-f]{40})\)[[:space:]]*$/\1/p' | head -1 || true)
fi
[ -n "$DEVICE" ] || fail "Не вижу iPhone. Подключите его кабелем, разблокируйте и нажмите «Доверять этому компьютеру»."
echo "• iPhone: $DEVICE"

# --- Сборка ------------------------------------------------------------------
echo "• Собираю приложение (первый раз это занимает пару минут)…"
mkdir -p "$BUILD_DIR"
if ! xcodebuild \
  -project "$PROJECT" -scheme "$SCHEME" -configuration Release \
  -destination "id=$DEVICE" \
  -derivedDataPath "$BUILD_DIR" \
  -allowProvisioningUpdates \
  DEVELOPMENT_TEAM="$TEAM" \
  build > "$BUILD_DIR/build.log" 2>&1; then
  echo ""
  grep -E "error:|Maximum number|No profiles|requires a development team|not be installed" "$BUILD_DIR/build.log" | sort -u | head -15 || true
  fail "Сборка не удалась. Полный журнал: $(pwd)/$BUILD_DIR/build.log"
fi

APP="$BUILD_DIR/Build/Products/Release-iphoneos/Sufler.app"
[ -d "$APP" ] || fail "Сборка прошла, но приложение не найдено: $APP"

# --- Установка ---------------------------------------------------------------
echo "• Ставлю на телефон…"
if ! xcrun devicectl device install app --device "$DEVICE" "$APP" > "$BUILD_DIR/install.log" 2>&1; then
  tail -12 "$BUILD_DIR/install.log" || true
  echo ""
  echo "Частая причина: на телефоне уже стоят три приложения с бесплатного Apple ID."
  echo "Удалите одно из них с телефона и запустите скрипт ещё раз."
  fail "Установка не удалась. Журнал: $(pwd)/$BUILD_DIR/install.log"
fi

echo ""
echo "✓ Готово: «Суфлёр» на телефоне."
echo "  Если iPhone не даёт его открыть: Настройки → Основные → VPN и управление устройством → доверять разработчику."
