#!/usr/bin/env bash
# Кладёт three.js и шрифты в promo/vendor/. Нужен, когда npm-реестр недоступен:
# берёт то же самое с GitHub (three.js r186 = npm three@0.186, шрифты из google/fonts).
set -euo pipefail
cd "$(dirname "$0")/.."
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p vendor/three vendor/fonts

if [ -d node_modules/three/build ]; then
  cp -r node_modules/three/build node_modules/three/examples vendor/three/
else
  git clone -q --depth 1 --branch r186 --filter=blob:none --sparse https://github.com/mrdoob/three.js "$TMP/three"
  git -C "$TMP/three" sparse-checkout set build examples/jsm/postprocessing examples/jsm/shaders
  cp -r "$TMP/three/build" "$TMP/three/examples" vendor/three/
fi

git clone -q --depth 1 --filter=blob:none --sparse https://github.com/google/fonts "$TMP/gfonts"
git -C "$TMP/gfonts" sparse-checkout set ofl/unbounded ofl/manrope
cp "$TMP/gfonts/ofl/unbounded/Unbounded[wght].ttf" vendor/fonts/Unbounded.ttf
cp "$TMP/gfonts/ofl/manrope/Manrope[wght].ttf" vendor/fonts/Manrope.ttf

curl -sSL -o vendor/logo.png https://neuroprovideo.ru/assets/logo.png
ls -R vendor | head -20
