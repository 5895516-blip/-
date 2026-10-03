#!/usr/bin/env python3
"""Готовит исходники работ для рендера.

Для каждой работы из works/works.json:
  * превью-кадр с Яндекс Диска -> works/src/previews/<slug>.jpg (всегда);
  * если видео доступно -> файл в works/src/video/, фрагмент CLIP_SEC с clip_start, нарезанный в
    works/frames/<slug>/%04d.jpg (960x540, 30 fps, cover-crop).
Итог пишется в works/manifest.json, его читает сцена.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKS = os.path.join(ROOT, "works")
API = "https://cloud-api.yandex.net/v1/disk/public/resources"
CLIP_SEC = 8

os.environ.setdefault("SSL_CERT_FILE", "/root/.ccr/ca-bundle.crt")


def api(endpoint, **params):
    url = endpoint + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def main():
    cfg = json.load(open(os.path.join(WORKS, "works.json"), encoding="utf-8"))
    key = cfg["yandex_public_key"]
    listing = api(API, public_key=key, limit=500, preview_size="XXXL")
    items = {i["name"]: i for i in listing["_embedded"]["items"]}

    os.makedirs(os.path.join(WORKS, "src", "previews"), exist_ok=True)
    manifest = {}
    for w in cfg["works"]:
        slug, item = w["slug"], items.get(w["file"])
        if item is None:
            print(f"!! {slug}: файл {w['file']!r} не найден на Диске")
            continue
        entry = {"file": w["file"]}

        still = os.path.join(WORKS, "src", "previews", slug + ".jpg")
        if not os.path.exists(still):
            urllib.request.urlretrieve(re.sub(r"size=[^&]+", "size=XXXL", item["preview"]), still)
        entry["still"] = f"works/src/previews/{slug}.jpg"

        frames_dir = os.path.join(WORKS, "frames", slug)
        if not (os.path.isdir(frames_dir) and os.listdir(frames_dir)):
            try:
                href = api(API + "/download", public_key=key, path=item["path"])["href"]
                if not href:
                    raise RuntimeError("Диск не выдал ссылку на скачивание")
                # ffmpeg не умеет ходить через прокси окружения, поэтому файл качаем curl'ом
                src = os.path.join(WORKS, "src", "video", slug + os.path.splitext(w["file"])[1].lower())
                os.makedirs(os.path.dirname(src), exist_ok=True)
                if not os.path.exists(src):
                    subprocess.run(["curl", "-sS", "-L", "--fail", "-o", src + ".part", href], check=True, timeout=1800)
                    os.replace(src + ".part", src)
                os.makedirs(frames_dir, exist_ok=True)
                subprocess.run([
                    "ffmpeg", "-v", "error", "-y", "-ss", str(w.get("clip_start", 0)),
                    "-i", src, "-t", str(CLIP_SEC),
                    "-vf", "fps=30,scale=960:540:force_original_aspect_ratio=increase,crop=960:540",
                    "-q:v", "3", os.path.join(frames_dir, "%04d.jpg"),
                ], check=True, timeout=600)
            except Exception as e:  # noqa: BLE001 — сеть закрыта: остаёмся на превью
                shutil.rmtree(frames_dir, ignore_errors=True)
                print(f"-- {slug}: видео недоступно ({e.__class__.__name__}), берём превью")
        n = len(os.listdir(frames_dir)) if os.path.isdir(frames_dir) else 0
        if n:
            entry.update(frames=f"works/frames/{slug}", count=n)
        manifest[slug] = entry
        print(f"ok {slug}: {'кадров ' + str(n) if n else 'превью'}")

    json.dump(manifest, open(os.path.join(WORKS, "manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.exit(main())
