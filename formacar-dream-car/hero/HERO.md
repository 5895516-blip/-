# Герой — эталон внешности (Formacar «Машина твоей мечты»)

Один и тот же герой во всех 16 сценах. Эти два изображения — референс лица и костюма для каждой генерации.

| № | Что | Модель | Higgsfield job ID | Seed |
|---|---|---|---|---|
| 1 | Эталон лица (face lock): анфас крупно, чёрная майка, серый фон, плоский свет | Seedream 5.0 Pro, 3:4, 2K | `decbdf26-e9ce-4fd9-b672-c8a63936c6d3` | 153673 |
| 2 | Разворот: анфас / 3/4 / профиль / затылок, серая домашняя футболка | Seedream 5.0 Pro (референс = №1), 16:9, 2K | `89e24cd6-f3d4-46ff-bd7f-a9921ef7f212` | 153913 |

Ссылки: в галерее Higgsfield по job ID (в медиа-полях генераций передавать job ID, роль `image_references`).

## Описание (утверждено)
Около 25 лет, обычный симпатичный парень (не модель), славянская внешность, худощаво-спортивный.
Светлая кожа с тёплым подтоном, тёмно-каштановые короткие волосы, сверху чуть длиннее и слегка взъерошены.
Карие глаза, прямые брови, лёгкая щетина. Без тату, пирсинга, украшений.
**Костюм на весь ролик:** серая (меланж) домашняя хлопковая футболка, мягкая, чуть растянутый ворот.

## Промпт №1 (Seedream 5.0 Pro, text-to-image)
```text
Studio identity reference photograph of a man in his mid-twenties with a lean athletic build and Eastern European features, framed from just above the top of his head down to the upper chest, his face filling most of the frame. He has fair skin with a warm undertone, short dark brown hair cut a little longer and slightly messy on top with a few loose strands falling toward the forehead, straight dark brows, brown eyes, a straight nose, and light even stubble along the jaw and upper lip. An ordinary, likeable face rather than a model's, with the natural slight asymmetry of a real person. He wears a plain black ribbed cotton tank top. Body squared to the camera, head level, neutral relaxed expression, lips closed, eyes looking straight into the lens.

The background is an even 18% neutral grey seamless studio paper, one flat value from corner to corner with no gradient or vignette. Lighting is completely flat and shadowless: a huge soft frontal source at camera position with matched fill from both sides, above and below, so both halves of the face read at the same brightness and nothing is cast onto the backdrop; the skin keeps its true warm natural tone against the grey.

Shot on a full-frame camera with a 50mm prime at a wide aperture, the eyes tack sharp and the ears falling slightly softer. Real skin texture: fine even pores across the nose and cheeks, faint peach fuzz along the jaw and hairline, individual stubble hairs, natural moisture in the eyes with a small catchlight, individual hair strands and flyaways at the hairline, visible cotton rib texture on the tank top. Fine natural film grain over the whole frame. Matte skin with no retouching and no plastic smoothness.
```

## Промпт №2 (Seedream 5.0 Pro, edit, референс = №1)
```text
Use the man in the reference photo as the only identity source and keep his face, bone structure, warm fair skin tone, brown eyes, short slightly messy dark brown hair and light stubble exactly as they are. Create a four-panel studio turnaround sheet of this same man: one horizontal frame divided into four equal vertical panels with thin clean gaps between them, every panel framed from just above the top of his head down to the waist, the figure at the same scale in each panel. Panel one, far left: standing facing the camera straight on, eyes to the lens. Panel two: three-quarter view, body and head turned 45 degrees toward frame-left. Panel three: clean side profile facing frame-left, showing the nose, jaw line and ear. Panel four, far right: seen from directly behind, showing the back of his head, the hair at the nape and the back of the T-shirt.

In all four panels he wears the same plain heather-grey crew-neck cotton T-shirt, soft and slightly worn, a little loose on the body, with a relaxed slightly stretched collar - the shirt he sleeps in at home. Arms hang relaxed at his sides, neutral calm expression, lips closed.

Every panel has the identical flat 18% neutral grey seamless backdrop, one even value with no gradient. Lighting is flat and shadowless in every panel: a huge soft frontal source with matched fill from both sides, above and below, nothing cast onto the backdrop, and his skin renders at the same true warm tone in all four panels.

Shot on a 50mm prime, sharp throughout. Real skin with fine even pores, faint peach fuzz, individual stubble hairs and hair strands with flyaways; real cotton jersey with soft creases at the armpits and a few tiny pills on the fabric. Fine natural film grain across the whole frame. The same real face in every panel, with no retouching.
```
