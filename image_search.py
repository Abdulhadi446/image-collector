"""Search and download car images. Dark no longer required; gemma4 rates aura."""
from __future__ import annotations

import time
from io import BytesIO

import requests
from ddgs import DDGS
from PIL import Image

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
MAX_BYTES = 25_000_000
# stock sites serve watermarked previews (wixmp = deviantart CDN); the second
# group is AI-art generators — real-photo rule rejects those too, but skip early
WATERMARKED = ("freepik", "vecteezy", "shutterstock", "istockphoto",
               "gettyimages", "alamy", "dreamstime", "123rf", "depositphotos",
               "wixmp", "stablediffusionweb", "civitai", "midjourney",
               "leonardo.ai", "openart", "nightcafe", "lexica", "artbreeder",
               "playgroundai", "dezgo")


def search_images(query: str, max_results: int = 25) -> list[str]:
    """Direct image URLs for a query, retrying on DDG rate limits."""
    last: Exception | None = None
    for attempt, pause in enumerate((5, 15)):
        try:
            results = DDGS().images(query, max_results=max_results)
            return [r["image"] for r in results
                    if r.get("image") and not any(w in r["image"] for w in WATERMARKED)]
        except Exception as e:
            last = e
            time.sleep(pause)
    print(f"  search failed for {query!r}: {last}")
    return []


def download(url: str) -> bytes | None:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
        if r.status_code != 200 or len(r.content) > MAX_BYTES:
            return None
        return r.content
    except requests.RequestException:
        return None


def _phash(img: Image.Image) -> int:
    px = img.convert("L").resize((8, 8)).tobytes()
    avg = sum(px) / 64
    bits = 0
    for p in px:
        bits = (bits << 1) | (p > avg)
    return bits


def is_dup(ph: int, seen: list[int]) -> bool:
    return any(bin(ph ^ s).count("1") <= 4 for s in seen)


def assess(raw: bytes) -> tuple[int, bool] | None:
    """(phash, is_portrait) if it decodes at a sane size, else None.

    No darkness gate — aura is Gemini's call now.
    """
    try:
        img = Image.open(BytesIO(raw))
        img.load()
    except Exception:
        return None
    w, h = img.size
    if w < 640 or h < 400:
        return None
    if w / h > 3 or h / w > 2.2:  # reject extreme panoramas / strips
        return None
    return _phash(img), h / w >= 1.25  # mobile-ratio (4:5 or taller)
