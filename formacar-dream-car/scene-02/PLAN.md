# Formacar «Машина твоей мечты» — Сцена 2 «Глаза открываются в машине»

Вертикаль 9:16. Генерация 5 сек → в монтаж ~4 сек (0:03–0:07 по сценарию).
Сцена 2 зеркалит сцену 1: там камера прилетела к глазам (уснул), здесь отлетает от глаз (проснулся во сне).

---

## 1. Бесшовная склейка со сценой 1 — цепочка «последний кадр → первый кадр»

1. Генерируем сцену 1.
2. Из готового видео сцены 1 вырезаем **последний кадр**. Камера там стоит намертво: кадр чёткий, без смаза.
3. Этот кадр загружаем в сцену 2 как `@image_1`, это первый кадр.

На стыке стоят два одинаковых кадра, поэтому шва нет. Скорость камеры на стыке тоже совпадает: в обеих сценах в этот момент ноль.
На крупном плане глаз не видно, лежит человек или сидит, поэтому кадр с подушки подходит и для водительского кресла.

**Монтаж:** сцена 1 — с ~1.0 до ~4.6 сек (камера уже стоит), сразу за ней сцена 2 с первого кадра.

## 2. Что в кадре

- **Салон:** низкое спортивное купе Mercedes-AMG GT, ночь, едем по пустому проспекту. Чёрная кожа, тёмный пластик, приборная подсветка холодно-белая. **Без красного**: красный цвет появится только в сцене 8, и тогда он будет заметен.
- **Герой:** тот же парень в той же серой домашней футболке, что и в кровати. Руки на руле «на десять и два». Смотрит вперёд на дорогу, **не в камеру**.
- **Телефон:** в держателе на центральном воздуховоде, справа от героя. В кадр сцены 2 не попадает, его покажем в сцене 4. Держатель стоит там всегда.
- **За стеклом** (справа в кадре, за его головой, через водительское окно): огни домов и неон проплывают назад.

## 3. Камера

| Время | Кадры (24 fps) | Что делает камера |
|---|---|---|
| 0.0–0.8 с | 1–20 | **стоит**, кадр = последний кадр сцены 1. На ~0.5 с по лицу проходит тёплый фонарь, на ~0.7 с глаза открываются |
| 0.8–3.6 с | 20–86 | плавный отъезд от глаз с лёгкой дугой вправо от героя (со стороны пассажира), объектив расширяется. Открываются лицо, плечи, руки на руле, окно с городом |
| 3.6–4.3 с | 86–104 | стоит на среднем плане 3/4, лёгкая дорожная вибрация. Он понимает, где он, и улыбается |
| 4.3–5.0 с | 104–120 | машина проходит под ярким фонарём: горизонтальная полоса анаморфного блика проходит по кадру, пик на 4.8 с (кадр 116) — **точка склейки** со сценой 3 |

- Оптика: начинаем ~40° по диагонали (≈58 мм, ровно как конец сцены 1), заканчиваем ~68° (≈32 мм).
- Финальный ракурс 3/4 из салона с пассажирской стороны **становится эталоном для сцен 5 и 6**. Там ракурс не меняется, а машина вокруг становится **BMW M5 (4-дверный седан)**, потом **Lamborghini Revuelto** (правка клиента, см. `../CLIENT_BRIEF.md`).
- ⚠️ По утверждённой механике свайпа (палец листает машину на экране телефона, и в тот же момент меняется машина вокруг) в сценах 5–6 желательно, чтобы **рука героя на телефоне была видна в кадре**. До рендера сцен 5–6 решаем: чуть расширить финальный ракурс сцены 2 вниз-влево, чтобы в кадр попадал держатель с телефоном и его правая рука.

## 4. Свет — «СОН»

- **Первые 0.5 с:** свет как в конце сцены 1, холодный ровный, слева в кадре. Без этого склейка не будет бесшовной.
- **Дальше:** уличные фонари и неон вывесок пробегают по лицу спереди назад, примерно каждые 0.75 с. Цвета по очереди: тёплый натриевый, пурпурный неон, циан.
- **Снизу** лицо мягко подсвечивает приборная панель, холодно-белая.

## 5. Звук (живой, без музыки)

Ровное урчание мотора V8, шорох шин по асфальту, ветер. Музыку сна кладём на монтаже.

## 6. Связка со сценой 3

Сцена 2 кончается полосой блика фонаря (пик на 4.8 с). **Сцена 3** начинается с яркого отражения того же фонаря, скользящего по капоту.
**Белая вспышка делается в монтаже**, не в генерации: на стык кладём белую вспышку 4–6 кадров + оверлей блика (CapCut / Premiere / DaVinci). Так надёжно на 100% и не нужно перегенерировать из-за неточного тайминга.
**Направление езды в сцене 3:** машина едет слева направо по кадру.

## 7. Производство

| Шаг | Что | Кредиты |
|---|---|---|
| 1 | Последний кадр сцены 1 → `@image_1` (вырезаем из готового видео) | 0 |
| 2 | Финальный кадр 3/4 в салоне в фотореал: кадр превиза №100 + лицо героя | 1 картинка |
| 3 | Seedance 2.5 omni_reference: тест 480p | 1 генерация |
| 4 | Финал 1080p | 1 генерация |
| 5 | Монтаж: белая вспышка 4–6 кадров на стыке сцен 2→3 | 0 |

---

## 8. Промпт видео — Seedance 2.5 (omni_reference)

Загрузка: `@image_1` = последний кадр сцены 1, `@image_2` = фотореал финального кадра (шаг 2), `@video_1` = превиз `previs_scene02.mp4`.

```text
GENERATION. One continuous shot that seamlessly continues the previous clip. @image_1 is the first-frame anchor: the film opens on exactly this extreme close-up of the young man's closed eyes, identical framing, light and skin. @image_2 is the final-frame anchor: it defines the car interior, his face, grey T-shirt and the landing composition. @video_1 is a grey-box camera blockout: copy only its camera path, speed curve and timing; ignore its grey shapes and flat materials.

LOCATION MAP: the driver's seat of a low black sports coupe driving at night along an empty city avenue. Black leather bucket seats, dark dashboard with cool white instrument glow, a round sports steering wheel. The driver's side window is behind him on the right of the frame; city buildings with lit windows and neon signs slide past outside it.

CONTINUITY LOCK: exactly one person in the car — the same young man in the same plain grey home T-shirt. His hands stay on the steering wheel at ten and two. He looks forward at the road, never into the lens.

FIRST FRAME: identical to @image_1 — his closed eyes and eyebrows fill the frame, eye line horizontal, eyes slightly above the centre, soft cool light from frame-left.

CAMERA: for the first 0.8 seconds the camera holds perfectly still on the close-up. Then one smooth continuous pull-back with a gentle arc toward the passenger side, the lens widening as it goes, revealing his face, shoulders, hands on the wheel and the driver's window with the city behind him; it lands at 3.6 seconds in a three-quarter medium shot from the passenger side of the windshield at eye level, matching @image_2, and holds there with only a faint road vibration. No handheld shake, no cuts.

ACTION: at 0.5 seconds a warm streetlight band slides across his closed eyes; at 0.7 seconds his eyes open slowly, pupils catching the passing lights. During the pull-back he takes in where he is; by 3.6 seconds a slow, disbelieving smile spreads across his face and grows into a wide grin. Small natural micro-movements from the car's motion, his body settled in the seat.

LIGHT: the opening holds the cool frame-left light of @image_1. Then the light of the moving city takes over: streetlights and neon signs sweep across his face from front to back roughly every 0.75 seconds, alternating warm sodium amber, magenta neon and cyan. A soft cool white glow from the instrument cluster lights his chin and hands from below. The cabin stays dark between the light sweeps.

END (4.3–5.0 s): the car passes under a bright streetlight; a thin horizontal blue-white anamorphic streak flare sweeps across the frame at his eye level and peaks at 4.8 seconds, then begins to fade. The frame never goes fully white.

AUDIO: smooth deep V8 engine purr, tyres hissing on asphalt, faint wind. No music, no voice.

STYLE: photorealistic cinema, large-format digital cinema camera with anamorphic lens character — horizontal streak flares, oval bokeh of city lights. Low-key night exposure with readable face and eyes, rich neon palette of amber, magenta and cyan against deep blacks, fine 35mm film grain, natural skin with visible pores and stubble, real leather texture. Natural 180-degree shutter motion blur on the passing lights only; the face stays sharp.
```

## 9. Промпт финального кадра — Nano Banana Pro (редактирование)

Загрузка: `@image_1` = `previs_scene02_land.png` (кадр превиза №100), `@image_2` = эталон лица героя (`../hero/HERO.md`, job `decbdf26-…`).

```text
Rebuild @image_1 (a grey 3D blockout) as a photorealistic cinematic film still. Keep its exact camera position, angle and framing and the position of the man, his arms, the steering wheel and the window; ignore the grey materials. @image_2 defines his face, 100% as in the reference.

Vertical 9:16. Night, inside a black Mercedes-AMG GT coupe driving through an empty city. A 25-year-old man with short dark hair and light stubble, in a plain grey home T-shirt, sits in a black leather bucket seat, hands on a round sports steering wheel at ten and two, looking forward at the road with a stunned, starting smile. Three-quarter view from the passenger side of the windshield at eye level. Behind him, through the driver's window, out-of-focus city buildings with warm lit windows and magenta and cyan neon signs.

Light: a magenta neon sweep falls across his face from frame-left, a cool white instrument glow from below lights his chin and hands, deep black cabin around him. Large-format cinema camera with anamorphic lens character, horizontal streak flares, oval bokeh, fine 35mm film grain, real leather and skin texture.
```
