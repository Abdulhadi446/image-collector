"""Offline full-graph test: faked search/rater, real graph wiring."""
import io
import os
import shutil

from PIL import Image, ImageDraw

import image_search as ims
import rater
import planner
from workflow import build_graph

CAR = {"name": "911 GT3 RS", "company": "Porsche", "version": "992.1",
       "variant": "RS", "color": "black", "year": "2023", "engine": "flat-six",
       "power": "518 hp", "drivetrain": "RWD", "description": "test car",
       "queries": ["q1", "q2", "q3"]}


def img(w: int, h: int, seed: int) -> bytes:
    # big seed-placed bright block on a seed-varied base -> unique phash per fixture
    g = 15 + (seed * 37) % 60
    im = Image.new("RGB", (w, h), (g, g, g))
    d = ImageDraw.Draw(im)
    bx = (seed * 97) % (w // 2)
    by = (seed * 53) % (h // 2)
    d.rectangle([bx, by, bx + w // 3, by + h // 3], fill=(235, 235, 235))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


MAP = {f"u{i}": img(800, 600, i + 1) for i in range(4)}       # landscape heroes
MAP.update({f"u{4 + i}": img(768, 960, i + 10) for i in range(6)})  # portrait sides (4:5)

planner.plan_car = lambda: CAR
ims.search_images = lambda q, max_results=25: list(MAP)
ims.download = lambda url: MAP[url]
# wrong cars u3/u6/u9: u3 has the global top aura 10 but match=False;
# u0 (aura 9, match) is watermarked -> img-1 must be the best CLEAN match u7;
# u1 is an AI/render (real=False) and must be dropped everywhere
AURAS = [9, 5, 4, 10, 6, 3, 8, 7, 2, 1]
rater.rate = lambda car, images, batch=6: [
    {"aura": AURAS[i], "side": i % 2 == 0, "match": i not in (3, 6, 9),
     "watermark": i == 0, "real": i != 1}
    for i in range(len(images))
]

DATE = "test-day"
shutil.rmtree(os.path.join("imgs", DATE), ignore_errors=True)
final = build_graph().invoke(
    {"date": DATE, "target": 6, "car": {}, "i": 0, "query": "",
     "found": [], "seen": [], "rated": [], "saved": []},
    {"recursion_limit": 200})

assert len(final["saved"]) == 6, f"saved {len(final['saved'])}"
out = os.path.join("imgs", DATE)
for n in range(1, 7):
    assert os.path.exists(os.path.join(out, f"img-{n}.jpg")), f"img-{n} missing"
md = open(os.path.join(out, "car.md")).read()
assert "name: 911 GT3 RS" in md and "company: Porsche" in md
assert "queries" not in md, "queries must not leak into car.md"
# img-1 = best CLEAN match (u7); watermarked u0 (aura 9) and wrong car
# u3 (aura 10) must both lose
def source_jpeg(b: bytes) -> bytes:
    # normalize a source image (PNG) to the same quality-92 JPEG the workflow
    # writes, so the result compares byte-for-byte with a workflow output file
    im = Image.open(io.BytesIO(b)).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB").tobytes()


def actual_rgb(b: bytes) -> bytes:
    # a workflow output is already JPEG; do NOT re-compress it here
    return Image.open(io.BytesIO(b)).convert("RGB").tobytes()


with open(os.path.join(out, "img-1.jpg"), "rb") as f:
    assert actual_rgb(f.read()) == source_jpeg(MAP["u7"]), \
        "img-1 must be the best clean match, not watermarked or wrong car"
for n in range(1, 7):  # watermarked u0 / AI u1 appear nowhere in the output
    with open(os.path.join(out, f"img-{n}.jpg"), "rb") as f:
        b = f.read()
    assert actual_rgb(b) != source_jpeg(MAP["u0"]), f"img-{n} is watermarked"
    assert actual_rgb(b) != source_jpeg(MAP["u1"]), f"img-{n} is not a real photo"
side2 = Image.open(os.path.join(out, "img-2.jpg"))
assert side2.size[1] / side2.size[0] >= 1.25, "img-2+ are portrait sides"
with open(os.path.join(out, "img-2.jpg"), "rb") as f:
    assert actual_rgb(f.read()) == source_jpeg(MAP["u4"]), \
        "img-2 must be the first matching side angle"
# fill picks matching u2 (aura 4), never wrong-car u3 (aura 10)
with open(os.path.join(out, "img-5.jpg"), "rb") as f:
    assert actual_rgb(f.read()) == source_jpeg(MAP["u2"]), \
        "fill must prefer a matching car over the top-aura wrong car"
assert os.path.exists(os.path.join(out, "car.gif")), "car.gif missing"
shutil.rmtree(out, ignore_errors=True)
print("ok: plan->harvest->rate->save, real+watermark-free hero+sides+fill"
      "+car.md+car.gif")
