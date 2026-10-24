# Сцены 1+2 одним видео — пакет для генерации

> ## ✅ ЗАПУЩЕНО (24.10, вариант пользователя)
> По решению пользователя **стартовый кадр НЕ прикреплён** («сгенерированные кадры убивают картинку, пусть Seedance дорисует сам»): спальня описана текстом.
> Job: `9fa85e45-4bd6-478c-b1cd-78217298b839` — Seedance 2.5, omni_reference, 720p, 9:16, 10 сек, со звуком, **70 кредитов**.
>
> | Тег | Что | ID |
> |---|---|---|
> | `@image_1` | лицо героя v2 | `7550d525-9728-4d53-ba85-3cce6e54c172` |
> | `@image_2` | разворот героя v2 | `5a0a9e98-7ded-4167-844f-0000549655b1` |
> | `@image_3` | салон Mercedes-AMG GT | `87291df2-f1a8-433d-8ad8-94553e99803a` |
> | `@video_1` | превиз сцен 1+2 | `eee1dbad-4b7f-425a-99fd-43545b06ce85` |
>
> Отличия запущенного промпта от варианта ниже:
> - убрано предложение про `@image_3`-стартовый кадр;
> - салон стал `@image_3`;
> - в BEAT 1 добавлено словесное описание первого кадра (общий план из угла у изножья, на высоте груди);
> - `@video_1` теперь задаёт ещё и расстановку окна, кровати и сиденья.
>
> Предложение Higgsfield заменить промпт пресетом «IN THE DARK» отклонено: пресет не использует ни превиз, ни героя.

**Модель:** Seedance 2.5, режим `omni_reference`, **9:16**, **720p**, **10 сек**, со звуком.
**Почему одним видео:** склейка по глазам (спальня → машина) происходит внутри одной генерации, и шва нет вообще.
**«Киношность» как в Cinema Studio** заложена в текст промпта: камера, анаморфная оптика, диафрагма, плёнка, световая схема.

## Превиз (референс камеры)

`previs_scene01-02_combined.mp4`, 10 сек, 240 кадров:

| Время | Что происходит |
|---|---|
| 0.0–0.4 с | статичный общий план спальни |
| 0.4–4.8 с | наезд сцены 1, камера встаёт на глаза в 4.8 с |
| 5.0 с | тот же кадр глаз, мир вокруг уже машина |
| 5.6 с | глаза открываются |
| 5.8–8.5 с | отъезд с дугой к пассажирскому месту |
| 8.5–9.3 с | средний план 3/4, улыбка |
| 9.3–10 с | полоса блика фонаря, пик в 9.8 с (точка склейки со сценой 3) |

## Вложения и теги (проверено)

| Тег | Что | Higgsfield ID | Роль в API | За что отвечает |
|---|---|---|---|---|
| `@image_1` | эталон лица героя v2 | `7550d525-9728-4d53-ba85-3cce6e54c172` | image_references #1 | лицо |
| `@image_2` | разворот героя v2 | `5a0a9e98-7ded-4167-844f-0000549655b1` | image_references #2 | все ракурсы + серая футболка |
| `@image_3` | стартовый кадр (спальня, фотореал) | `35a30a50-c6b4-4cbf-a2a0-b9471a6ab989` | image_references #3 | первый кадр, свет спальни |
| `@image_4` | салон Mercedes-AMG GT | `87291df2-f1a8-433d-8ad8-94553e99803a` | image_references #4 | салон машины во 2-й части |
| `@video_1` | `previs_scene01-02_combined.mp4` | `eee1dbad-4b7f-425a-99fd-43545b06ce85` | video_references #1 | только камера и тайминг |

## Промпт

```text
GENERATION. One continuous 10-second shot in two beats with no visible cut: a man asleep in a dark bedroom, then the same man waking up inside his dream car. @image_3 is the first frame: the video opens on exactly this bedroom, man, window, phone and light. @image_1 is his face and @image_2 shows him from every angle in his grey home T-shirt; he is this exact person throughout and the only person in the video. @image_4 is the car interior of beat 2: a black Mercedes-AMG GT 63 cabin. @video_1 is a grey-box blockout of the whole shot: copy only its camera path, speed and timing; ignore its grey shapes and lighting.

CAMERA PACKAGE: ARRI Alexa 35 with Cooke anamorphic lenses at T2.3: oval bokeh, horizontal blue streak flares on point lights, gentle edge falloff, shallow depth of field. The lens tightens during the push-in and widens again during the pull-back, as in @video_1.

BEAT 1, BEDROOM (0-5 s): the dark bedroom from @image_3: window in the left wall, narrow bed under it, a black phone screen-up and dark on the windowsill, a car poster above the headboard. He sleeps on his back, face up, blanket to his chest. Camera as in @video_1: a short still hold, then one smooth move gliding over the bed, rising and tilting down until it looks straight down at his face, then dropping straight down along one axis and landing at 4.8 s in an extreme close-up of both closed eyes and brows, forehead at the top of the frame, eye line horizontal, eyes slightly above centre; it stops dead with no settle or drift. Lighting: hard cold moonlight through the window from frame-left is the only key, throwing the cross-shaped shadow of the window frame across the blanket and his face; thin haze turns the moonbeam into soft shafts; a cool rim traces his hair and brow; warm sodium streetlight bounces faintly on the ceiling; the far side of the room falls into deep blacks that hold detail. At 1-2.5 s car headlights from the courtyard sweep across the ceiling. In the last second his eyes flick under the closed lids.

BEAT 2, DREAM CAR (5-10 s): the framing stays the same at 5.0 s, but a warm streetlight band slides across his closed eyes: he is now in the driver's seat of the moving car from @image_4 on an empty night avenue. At 5.6 s his eyes open, pupils catching the lights. From 5.8 s, as in @video_1, the camera pulls back in one smooth move with a gentle arc toward the passenger side, revealing his face, shoulders, hands on the wheel at ten and two and the driver's window behind him on the right; it lands at 8.5 s in a three-quarter medium shot from the passenger side of the windscreen at eye level and holds with a faint road vibration. A slow, disbelieving smile grows into a wide grin; he looks at the road, never into the lens. Lighting: the cabin is dark; streetlights and neon signs sweep across his face front to back about every 0.75 s in amber, magenta and cyan; neon through the window behind him paints a coloured rim on his hair and shoulder; the instrument display gives a soft cool underlight on his chin and hands; city bokeh glows behind him. At 9.3 s a bright streetlight throws a thin horizontal blue-white anamorphic streak across the frame at eye level, peaking at 9.8 s; the frame never goes fully white.

AUDIO: beat 1 quiet room tone, distant city hum, a car passing below, slow breathing; beat 2 a deep V8 purr rising at 5.0 s, tyres hissing, faint wind. No music, no voice.

STYLE: photorealistic theatrical cinema, Kodak Vision3 500T-like colour negative look with fine 35mm grain, deep contrast with detailed shadows and soft highlight roll-off, teal night with warm amber accents in the bedroom, saturated amber, magenta and cyan neon in the car, real skin pores, eyelashes and stubble, real leather and cotton. Motion blur only on passing lights; the face stays sharp; no flicker.
```

**Проверка тегов:**
- `@image_1`: 1 раз;
- `@image_2`: 1 раз;
- `@image_3`: 2 раза;
- `@image_4`: 2 раза;
- `@video_1`: 4 раза.

Все 5 вложений упомянуты, лишних тегов нет.

## Цена (проверено через Higgsfield, с прикреплённым превизом)

| Вариант | Кредиты |
|---|---|
| **720p, 10 сек, со звуком** | **70** |
| тест 480p, 10 сек, без звука | 30 |
| стартовый кадр (уже сделан) | 2.5 |

## Монтаж

- Если нужен хронометраж сценария (0:00–0:07), лишнее режем на неподвижных местах: в начале (0–0.4 с) и на зависании на глазах (4.8–5.6 с). Камера там стоит, поэтому склейки не видно.
- Последний кадр (пик блика) — стык со сценой 3 через белую вспышку 4–6 кадров.
