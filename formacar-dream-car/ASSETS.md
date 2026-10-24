# Реестр референсов (Higgsfield)

В генерациях передавать **job ID** (или media ID для загруженных файлов) в поле `medias`.
Картинки — роль `image_references`, видео — роль `video_references`.

| Что | Тип | ID | Где используется |
|---|---|---|---|
| **Герой — эталон лица v2** | картинка | `7550d525-9728-4d53-ba85-3cce6e54c172` | все сцены с героем |
| **Герой — разворот со всех сторон v2** (серая футболка) | картинка | `5a0a9e98-7ded-4167-844f-0000549655b1` | все сцены с героем |
| **Mercedes-AMG GT — экстерьер, ЭТАЛОН** (3/4 спереди, нос вправо) | картинка | `5c3f7d60-463c-4abc-9b7e-8c18286befac` | сцены 3, 7 |
| Mercedes — профиль слева (нос вправо) | картинка | `86b90f69-5dbf-45a7-9f85-a18b23f19652` | сцены 3, 7 (камера едет сбоку) |
| Mercedes — низко и близко у переднего колеса (вертикаль) | картинка | `0d764619-6555-497f-9226-23f2d661dbc6` | сцена 3 (старт у колеса) |
| Mercedes — 3/4 сзади слева | картинка | `9a2d99e3-9cd9-4598-9346-3cf962e2f195` | сцена 7 |
| Mercedes — крупно колесо и фара (вертикаль) | картинка | `00efecc3-a93a-4189-b5c8-21a214042808` | сцена 3 |
| Mercedes — общий план сверху издалека | картинка | `ab6bb30b-d40f-47d7-b6d5-dfe3057ac6da` | форма крыши и кузова сверху |
| **Mercedes-AMG GT — салон** (с пассажирского места, телефон в держателе) | картинка | `87291df2-f1a8-433d-8ad8-94553e99803a` | сцены 2, 4, 5 |
| BMW M5 (4-дверный) — экстерьер / салон | картинка | — сделать перед сценой 5 | сцены 5, 7 |
| Lamborghini Revuelto — экстерьер / салон | картинка | — сделать перед сценой 6 | сцены 6, 7, 8, 14 |
| Превиз сцены 1 (`scene-01/previs/previs_scene01.mp4`) | видео | — загрузить | сцена 1 |
| Превиз сцены 1, кадр 1 (`scene-01/previs/previs_first.png`) | картинка | — загрузить | первый кадр сцены 1 |
| Превиз сцены 2 (`scene-02/previs/previs_scene02.mp4`) | видео | — загрузить | сцена 2 |
| Превиз сцены 2, кадр 100 (`scene-02/previs/previs_scene02_land.png`) | картинка | — загрузить | финальный кадр сцены 2 |

Архив (не использовать): герой v1 — `decbdf26-…`, `89e24cd6-…`.

Набор ракурсов сделан **от эталона** `5c3f7d60` (Seedream edit: «Keep the car from the reference image exactly as it is … Change only the camera: …»), поэтому машина на всех фото одна и та же.

## Промпты машин (Seedream 5.0 Pro, 16:9, 2K)

**Экстерьер `5c3f7d60-…`**
```text
Automotive studio photograph of a black Mercedes-AMG GT 63 coupé of the current second generation, shot in a three-quarter front view from the car's left side so the nose points toward frame-right. Obsidian black metallic paint, the AMG Panamericana grille with vertical chrome slats, slim angular LED headlights, a long bonnet with twin power domes, frameless side windows, a sweeping fastback roofline, multi-spoke AMG forged wheels in matte titanium grey with black brake calipers, and plain blank number-plate mounts. The whole car sits on a dark charcoal seamless studio cyclorama that curves from floor to wall with no visible edge. One very large soft overhead light panel draws long smooth reflections along the shoulder line, bonnet and roof so every body line reads against the black paint, with a soft dark contact shadow under the tyres. Shot from about eight metres away on a full-frame camera with a 70mm lens at f/8, the entire car sharp. Real paint with faint orange-peel texture, a little road dust in the tyre sidewalls, true black glass, fine natural film grain. No text and no logos other than the car's own badges.
```

**Салон `87291df2-…`**
```text
Interior photograph of the cabin of a black Mercedes-AMG GT 63 coupé of the current second generation, taken from the passenger seat and looking across toward the empty driver's seat and the dashboard. An AMG Performance steering wheel with a flat-bottom rim in black Nappa leather, a free-standing digital instrument display behind it, a portrait-oriented central touchscreen flowing down into the centre console, round turbine-style air vents with thin chrome rings, black Nappa leather AMG Performance bucket seats with fine diamond quilting and integrated headrests, carbon-fibre trim and thin strips of cool white ambient lighting along the doors and the dashboard. A black smartphone sits in a slim holder clipped to the central air vent just to the right of the steering wheel, its screen dark. Soft even daylight fills the cabin through the windows from every side with no harsh hotspots, so every material reads clearly: the grain of the leather, the weave of the carbon fibre, the brushed metal of the shift paddles. Shot on a full-frame camera with a 24mm lens at f/8, everything sharp. Fine natural film grain, a trace of dust on the dashboard top and faint fingerprints on the touchscreen.
```
