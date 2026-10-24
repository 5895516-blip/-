# Сцена 1 — пакет для генерации (Higgsfield)

Модель видео: **Seedance 2.5**, режим `omni_reference`, 9:16, **5 сек**.
Порядок вложений фиксированный. Номера тегов в тексте = порядок загрузки внутри своего типа (картинки отдельно, видео отдельно).

## Шаг 1. Стартовый кадр (фотореал) — Seedream 5.0 Pro, 9:16, 2K — 2.5 кредита

Вложения (по порядку):
1. `previs_first.png` — серый кадр №1 превиза (композиция) — *загрузить*
2. `7550d525-…` — эталон лица героя v2
3. `5a0a9e98-…` — разворот героя v2 (серая футболка)

```text
Turn image 1, a grey 3D blockout of a bedroom, into a photorealistic cinematic film still. Keep its exact camera position, angle and framing and the position of every object: the window in the left wall with its white windowsill, the narrow bed running under the window, the pillow, the blanket, the framed poster above the headboard and the nightstand on the right. Image 2 and image 3 define the man asleep in the bed: the same face, hair and stubble, wearing a heather-grey home T-shirt.

Night in a small bedroom of an old apartment block, no lamps on. He sleeps on his back, face up, head on the pillow, the blanket pulled up to his chest and one arm resting on top of it. A black smartphone lies screen-up and dark on the windowsill near the head of the bed. A framed poster of a black sports car hangs above the headboard. Cold blue moonlight and city skyglow come through the window from frame-left and fall across the pillow and his face; a faint warm sodium-orange glow from the streetlights below lies on the ceiling; out-of-focus city lights twinkle through the glass with soft horizontal streak flares.

Low-key night exposure with his face and closed eyes readable, teal night palette with warm amber accents, a large-format cinema camera with an anamorphic lens: oval bokeh, gentle edge falloff, fine 35mm film grain. Real textures: creased cotton bedding, matte wall paint, a worn windowsill, real skin with stubble. Photographed, not rendered, with no grey clay surfaces left from the blockout.
```

Этот кадр — ещё и **референс спальни** для сцен 11–15 (та же комната утром).

## Шаг 2. Видео — Seedance 2.5 omni_reference

### Вложения и теги (проверено)

| Тег в тексте | Что прикрепить | ID | Роль в API | За что отвечает |
|---|---|---|---|---|
| `@image_1` | эталон лица героя v2 | `7550d525-9728-4d53-ba85-3cce6e54c172` | image_references #1 | лицо |
| `@image_2` | разворот героя v2 | `5a0a9e98-7ded-4167-844f-0000549655b1` | image_references #2 | голова со всех сторон + серая футболка |
| `@image_3` | стартовый кадр из шага 1 | *job ID после шага 1* | image_references #3 | первый кадр: спальня, поза, свет |
| `@video_1` | `previs_scene01.mp4` | *media ID после загрузки* | video_references #1 | только движение камеры и тайминг |

Машины в сцене 1 нет — её референсы не прикрепляем.

### Промпт

```text
GENERATION. One continuous shot, the opening shot of a short film. @image_3 is the first-frame anchor: the video opens on exactly this frame — the dark bedroom, the sleeping man, the window, the phone on the windowsill and the night light — and keeps its look for the whole shot. @image_1 defines the man's face and @image_2 shows the same man from every angle in his grey home T-shirt; he is 100% this person throughout. @video_1 is a grey-box camera blockout: copy only its camera path, speed curve and timing; ignore its grey shapes, flat materials and lighting.

LOCATION MAP: a small dark bedroom in an old apartment block at night. The window is in the left wall; a narrow bed runs along that wall directly under the window, headboard against the back wall. A white windowsill sits just above the head of the bed. A framed poster of a black sports car hangs above the headboard. A nightstand with a switched-off lamp stands to the right of the bed head.

CONTINUITY LOCK: exactly one person in the room. Exactly one black smartphone lies screen-up and dark on the windowsill near the head of the bed and stays there for the whole shot.

FIRST FRAME: identical to @image_3 — a medium-wide view from the corner near the foot of the bed at standing chest height, looking toward the head of the bed and the window. He lies on his back, head on the pillow, face up, blanket pulled to his chest, one arm resting on the blanket.

CAMERA: one single continuous, perfectly smooth move exactly as in @video_1. It eases in, glides over the bed while gently rising and tilting down until it looks straight down at his face; from that moment the aim is locked and the camera only drops straight down toward his eyes along one axis, with no further rotation. It lands decisively in an extreme close-up of both closed eyes and eyebrows, his forehead toward the top of the frame and his nose toward the bottom: eye line perfectly horizontal, eyes centred slightly above the middle of the frame. On landing the camera stops dead and stays locked off for the last half second: no settle, no re-framing, no drift. Field of view starts around 70° diagonal and narrows to about 40° by the landing. No shake, no handheld, no cuts.

ACTION: he is deeply asleep; slow breathing gently lifts the blanket. In the final 1.5 seconds, as the camera arrives, REM sleep begins: his eyeballs flick side to side under the closed lids, the eyelids flutter, a faint twitch at the brow. His eyes stay closed until the last frame.

LIGHT: no lamps are on. Cold blue moonlight and city skyglow through the window are the key, falling from frame-left across the pillow and his face and leaving the right side of his face in soft shadow; his closed eyes stay readable. Faint warm sodium-orange streetlight bounce from the courtyard below glows on the ceiling. Between 1 and 2.5 seconds, the headlights of a car passing in the courtyard sweep slowly across the ceiling and wall from left to right. Out-of-focus city lights twinkle through the window glass.

AUDIO: quiet room tone, distant city hum, one car passing far below in sync with the headlight sweep, his soft slow breathing. No music, no voice.

STYLE: photorealistic cinema, large-format digital cinema camera with anamorphic lens character: soft horizontal blue streak flares from the city lights, oval bokeh, gentle edge falloff. Low-key night exposure, teal-blue night palette with warm amber accents, fine 35mm film grain, natural skin with visible pores, fine eyelashes and stubble. Stable picture, natural motion cadence, no flicker.
```

**Проверка тегов:** в тексте есть `@image_1` (лицо), `@image_2` (ракурсы и футболка), `@image_3` (первый кадр, 2 раза), `@video_1` (камера, 2 раза). Других тегов нет, лишних вложений нет.

### Настройки и цена (проверено через Higgsfield)

| Прогон | Настройки | Кредиты |
|---|---|---|
| Тест | 480p, без звука, 5 сек | **15** |
| Финал | 720p, со звуком (звук на 720p бесплатный), 5 сек | **35** |
| (не советую) | 1080p со звуком | 80 |

Цену с прикреплённым видео-превизом перепроверю после загрузки: видео-референс может её изменить.

## Шаг 3. Монтаж

Берём **1.0–4.6 сек**: убираем медленный разгон, конец уже на неподвижной камере.
**Последний кадр финального видео сохраняем как PNG.** Это первый кадр сцены 2 (см. `../PIPELINE.md`).
