"""Image rating via Jev (TypeSafe System One, typed decisions through DefAPI)."""
from __future__ import annotations

import base64
import json
import os
import re
from io import BytesIO

import requests
from PIL import Image

URL = "https://api.defapi.org/v1/chat/completions"
MODEL = "typesafe/jev-1.14.0"


def _load_key() -> str:
    for env in ("JEV_API_KEY", "TYPE_SAFE_API_KEY", "OLLAMA_API_KEY"):
        if v := os.environ.get(env):
            return v
    try:
        with open(os.path.join(os.path.dirname(__file__), ".env")) as f:
            for line in f:
                for name in ("JEV_API_KEY", "TYPE_SAFE_API_KEY", "OLLAMA_API_KEY"):
                    if line.startswith(name + "="):
                        return line.split("=", 1)[1].strip().strip("'\"")
    except OSError:
        pass
    print("warning: JEV_API_KEY not set (env or .env); ratings will fail")
    return ""


KEY = _load_key()


def _b64img(b: bytes) -> str:
    # full-res originals time out the API; a 768px jpeg keeps batches fast
    im = Image.open(BytesIO(b))
    im.thumbnail((768, 768))
    if im.mode != "RGB":
        im = im.convert("RGB")
    buf = BytesIO()
    im.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _ask(car: dict, images: list[bytes]) -> list[dict] | None:
    content: list[dict] = [
        {"type": "image_url", "image_url": {"url": _b64img(b)}}
        for b in images
    ]
    content.append({"type": "text", "text": (
        f"These are candidates for a photoshoot of a car: "
        f"{car.get('color', '')} {car.get('company', '')} {car.get('name', '')} "
        f"({car.get('version', '')} {car.get('variant', '')}). "
        "For EACH image in the order given, rate: "
        '"aura" = 0-10 how moody / aura-farming a hero shot it is, '
        '"side" = true if the image clearly shows the car from the side/profile '
        "or a clear exterior angle, false otherwise. "
        '"match" = true only if the image shows that EXACT car: same company, '
        "same model AND variant (a Turbo is not a GT3 RS), and same color "
        "when visible (a silver car is NOT a black car); false otherwise. "
        '"watermark" = true if a watermark, artist signature, site logo, or '
        "text overlay is burned into the picture (ignore car badges/decals "
        "and signage that is part of the scene); false otherwise. "
        '"real" = true only if this is a photograph of a real physical car '
        "(not AI-generated, not a 3D render, not a video-game screenshot, "
        "not a toy or scale model); false otherwise. "
        "Reply with ONLY a JSON array, one object per image, same order, no prose: "
        '[{"aura": 0, "side": false, "match": false, "watermark": false, "real": false}]')})
    r = requests.post(URL, headers={"Authorization": f"Bearer {KEY}",
                                   "TypeSafe-Danger-Zone-Images": "true"},
                      json={"model": MODEL, "max_tokens": 2048,
                            "messages": [{"role": "user", "content": content}]},
                      timeout=120)
    if r.status_code != 200:
        print(f"  rater error {r.status_code}: {r.text[:200]}")
        return None
    txt = r.json()["choices"][0]["message"]["content"].strip()
    if txt.startswith("```"):
        txt = txt.split("\n", 1)[1].rsplit("```", 1)[0]
    txt = txt.strip()
    try:
        got = json.loads(txt)
    except json.JSONDecodeError:
        m = re.search(r"[\[{].*[\]}]", txt, re.S)
        if not m:
            return None
        try:
            got = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if isinstance(got, dict):  # single-image replies come back as an object
        got = [got]
    if not isinstance(got, list) or len(got) != len(images):
        return None
    return [{"aura": int(g.get("aura", 0)), "side": bool(g.get("side", False)),
             "match": bool(g.get("match", False)),
             "watermark": bool(g.get("watermark", False)),
             "real": bool(g.get("real", False))}
            for g in got]


def rate(car: dict, images: list[bytes], batch: int = 6) -> list[dict]:
    """[{"aura": 0-10, "side": bool, "match": bool, "watermark": bool,
    "real": bool}, ...] aligned with images."""
    out: list[dict] = []
    for i in range(0, len(images), batch):
        chunk = images[i:i + batch]
        got = None
        for _ in range(2):  # one retry on malformed output
            try:
                got = _ask(car, chunk)
            except Exception as e:
                print(f"  rater call failed: {e}")
                got = None
            if got:
                break
        if not got:  # never crash the graph over a rating; treat as unusable
            got = [{"aura": 0, "side": False, "match": False,
                    "watermark": False, "real": False}] * len(chunk)
        out.extend(got)
    return out
