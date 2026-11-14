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
# Stock / watermarked / AI-rendered domains to drop.
WATERMARKED = ("freepik", "vecteezy", "shutterstock", "istockphoto",
               "gettyimages", "alamy", "dreamstime", "123rf", "depositphotos",
               "wixmp", "stablediffusionweb", "midjourney", "civitai")
# Known-good car photography domains — prefer these.
CAR_DOMAINS = (
    "bringatrailer.com", "cars.com", "car.info", "supercars.net",
    "ultimatecarpage.com", "autoblog.com", "motor1.com", "caranddriver.com",
    "roadandtrack.com", "topgear.com", "evo.co.uk", "carbuzz.com",
    "motorauthority.com", "thedrive.com", "jalopnik.com", "carscoops.com",
    "autoevolution.com", "gomotors.net", "carpix.nu", "autowp.ru",
    "wheelwell.com", "cardesignnews.com", "drive-mag.com", "petrolicious.com",
    "curbsideclassic.com", "barnfinds.com", "hemmings.com", "classic.com",
    "mecum.com", "bonhams.com", "rmsothebys.com", "goodwood.com",
    "petersen.org", "revsinstitute.org", "simeonefoundation.org",
    "ferrari.com", "lamborghini.com", "porsche.com", "mclaren.com",
    "astonmartin.com", "bugatti.com", "koenigsegg.com", "pagani.com",
    "bentley.com", "rolls-royce.com", "bmw.com", "mercedes-benz.com",
    "audi.com", "nissan.com", "toyota.com", "honda.com", "ford.com",
    "chevrolet.com", "dodge.com", "jeep.com", "ram.com", "subaru.com",
    "mazda.com", "mitsubishi.com", "lexus.com", "acura.com", "infiniti.com",
)

# Query suffixes that bias DDG toward real car photos, not renders/wallpapers.
CAR_QUERY_SUFFIXES = (
    "car photography",
    "automobile photoshoot",
    "real car photo",
    "vehicle exterior",
    "car side profile",
    "on the road",
    "street photography",
)


def search_images(query: str, max_results: int = 25) -> list[str]:
    """Direct image URLs for a query, retrying on DDG rate limits.

    Biases results toward real car photography by:
    - appending car-photography suffixes to the query
    - preferring known car domains
    - filtering out watermarked/AI domains
    """
    # Augment query with car-photography terms if not already present.
    q = query.strip()
    if not any(s in q.lower() for s in ("car", "auto", "vehicle", "photography", "photoshoot", "photo")):
        q = f"{q} car photography"

    last: Exception | None = None
    for attempt, pause in enumerate((5, 15)):
        try:
            results = DDGS().images(q, max_results=max_results)
            urls = []
            for r in results:
                url = r.get("image")
                if not url:
                    continue
                if any(w in url for w in WATERMARKED):
                    continue
                # Prioritize known car domains.
                urls.append(url)
            # Stable sort: car domains first.
            urls.sort(key=lambda u: 0 if any(d in u for d in CAR_DOMAINS) else 1)
            return urls
        except Exception as e:
            last = e
            time.sleep(pause)
    print(f"  search failed for {q!r}: {last}")
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
    # Social-media friendly frame: between 4:5 portrait and 1.91:1 landscape.
    ratio = w / h
    if ratio < 4 / 5 or ratio > 1.91:
        return None
    return _phash(img), h / w >= 1.25  # portrait if taller than 1.25:1
