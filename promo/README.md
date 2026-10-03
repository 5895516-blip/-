# Промо PRO NEURO (60 с)

ТЗ — `BRIEF.md`, сверка фактов с сайтом — `SITE_FACTS.md`.
Две версии: v1 — по ТЗ (`src/`), v2 — продающая (`src/v2/`, обоснование и сценарий — `CONCEPT_V2.md`).

## Сборка

```bash
cd promo
npm ci                                # если npm-реестр недоступен — можно пропустить
./scripts/fetch_vendor.sh             # three.js r186 (из node_modules или GitHub), шрифты, логотип с сайта → vendor/
python3 scripts/prepare_works.py      # работы с Яндекс Диска → works/src, works/frames, works/manifest.json
node render.mjs keys 2.5 10.5 17.5    # пробные кадры → out/keys/
node render.mjs full 4                # полный ролик → out/neuroprovideo_promo_60s.mp4 + out/poster.jpg

# v2
python3 music/make_sfx.py             # звуковой слой → music/mix_v2.wav (трек + эффекты)
PROMO=v2 node render.mjs keys 6.4 16.5
PROMO=v2 node render.mjs full 4       # → out/neuroprovideo_promo_60s_v2.mp4 + out/poster_v2.jpg
```

- `src/scene.js` — сцена three.js + UnrealBloomPass; `window.renderAt(t)` выставляет кадр строго по времени.
- `works/works.json` — какие работы и где стоят (карусель, четыре причины, стена 5×3), подписи с сайта.
- `prepare_works.py` нарезает видеофрагменты в JPG 30 fps, если файлы на Диске доступны для скачивания;
  иначе в экраны идёт превью-кадр с Диска с медленным наездом. После появления доступа достаточно
  перезапустить `prepare_works.py` и `render.mjs full` — сцена сама возьмёт видео.
- Музыка: `music/track.wav`, сетка ударов — `music/beats.json` (128 BPM, такт 1.875 с).
