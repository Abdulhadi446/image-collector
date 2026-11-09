"""Vista Cars — a local Flask gallery for the car collector output.

Reads every shoot under ./imgs/<date>/ (img-*.png + car.md) and every GIF under
./assets/, then serves an editorial photo archive.

Run:
    .venv/bin/python app.py
    .venv/bin/python app.py --port 8000 --host 0.0.0.0
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
from functools import lru_cache
from pathlib import Path

from flask import Flask, Response, abort, jsonify, redirect, render_template, request, send_from_directory, url_for
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
IMG_ROOT = BASE_DIR / "imgs"
ASSET_ROOT = BASE_DIR / "assets"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif"}
GIF_EXTS = {".gif"}

SPEC_LABELS = {
    "name": "Model",
    "company": "Make",
    "version": "Generation",
    "variant": "Variant",
    "color": "Finish",
    "year": "Year",
    "engine": "Engine",
    "power": "Power",
    "drivetrain": "Drivetrain",
}
SPEC_ORDER = ["name", "company", "version", "variant", "color", "year", "engine",
              "power", "drivetrain"]

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


@app.context_processor
def inject_globals():
    return {"now_year": dt.date.today().year}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def natural_key(value: str) -> list:
    """Sort img-2 before img-10."""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", value)]


def parse_car_md(path: Path) -> dict:
    """Parse the collector's ``key: value`` car.md into a dict."""
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    car: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip().lstrip("-* ").strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key = key.strip().lower().replace(" ", "_")
        value = value.strip()
        if key and value:
            car[key] = value
    return car


@lru_cache(maxsize=2048)
def _dims(path_str: str, mtime_ns: int) -> tuple[int, int]:
    try:
        with Image.open(path_str) as im:
            return int(im.width), int(im.height)
    except Exception:
        return 0, 0


def image_dims(path: Path) -> tuple[int, int]:
    try:
        return _dims(str(path), path.stat().st_mtime_ns)
    except OSError:
        return 0, 0


def date_label(value: str) -> str:
    # "2026-11-09" -> "09 NOV 2026"; "2026-11-09-14" -> "09 NOV 2026 · 14:00"
    for fmt, out in (("%Y-%m-%d-%H", "%d %b %Y · %H:00"),
                     ("%Y-%m-%d", "%d %b %Y")):
        try:
            return dt.datetime.strptime(value, fmt).strftime(out).upper()
        except ValueError:
            continue
    return value


def alt_text(car: dict, index: int) -> str:
    make = car.get("company", "")
    name = car.get("name", "car")
    return f"{make} {name} — frame {index}".strip()


def spec_rows(car: dict) -> list[dict]:
    rows = []
    for key in SPEC_ORDER:
        value = car.get(key)
        if value:
            rows.append({"key": key, "label": SPEC_LABELS.get(key, key.title()),
                         "value": value})
    for key, value in car.items():
        if key in SPEC_ORDER or key in {"description", "queries"} or not value:
            continue
        rows.append({"key": key, "label": key.replace("_", " ").title(), "value": value})
    return rows


def build_shoot(folder: Path) -> dict:
    car = parse_car_md(folder / "car.md")
    files = sorted(
        (p for p in folder.iterdir()
         if p.is_file() and p.suffix.lower() in IMAGE_EXTS and not p.name.startswith(".")),
        key=lambda p: natural_key(p.name),
    )
    gallery = []
    for index, path in enumerate(files, 1):
        width, height = image_dims(path)
        gallery.append({
            "filename": path.name,
            "url": url_for("media_shoot", date=folder.name, filename=path.name),
            "width": width,
            "height": height,
            "index": index,
            "bytes": path.stat().st_size,
            "alt": alt_text(car, index),
        })

    name = car.get("name") or folder.name
    company = car.get("company", "")
    subline = " · ".join(v for v in (car.get("version"), car.get("color"),
                                    car.get("year")) if v)
    chips = []
    if car.get("year"):
        chips.append({"label": "Year", "value": car["year"]})
    if car.get("power"):
        chips.append({"label": "Power", "value": car["power"]})
    if car.get("drivetrain"):
        chips.append({"label": "Drive", "value": car["drivetrain"].split(",")[0].strip()})
    mini = [{"label": SPEC_LABELS[key], "value": car[key]}
            for key in ("engine", "power", "drivetrain") if car.get(key)]
    gallery_bytes = sum(item["bytes"] for item in gallery)

    # Prefer a static frame as the hero: heroDrift animation on an animated GIF
    # makes the composition flicker, so keep car.gif in the contact sheet but
    # out of the hero when a still image is available.
    static_frames = [item for item in gallery
                     if item["filename"].lower().endswith(
                         (".png", ".jpg", ".jpeg", ".webp", ".avif"))]
    cover = (static_frames[0] if static_frames else (gallery[0] if gallery else None))
    cover_name = cover["filename"] if cover else None
    thumbs = [item for item in gallery if item["filename"] != cover_name][:3]
    cover_index = next((i for i, item in enumerate(gallery)
                       if cover and item["filename"] == cover["filename"]), 0)

    return {
        "date": folder.name,
        "date_label": date_label(folder.name),
        "car": car,
        "name": name,
        "company": company,
        "title": f"{company} {name}".strip(),
        "subline": subline,
        "description": car.get("description", ""),
        "chips": chips,
        "mini": mini,
        "specs": spec_rows(car),
        "images": gallery,
        "cover": cover,
        "cover_index": cover_index,
        "thumbs": thumbs,
        "count": len(gallery),
        "bytes": gallery_bytes,
    }


def load_shoots() -> list[dict]:
    if not IMG_ROOT.is_dir():
        return []
    folders = sorted(
        (p for p in IMG_ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")),
        key=lambda p: p.name,
        reverse=True,
    )
    shoots = [build_shoot(folder) for folder in folders]
    return [shoot for shoot in shoots if shoot["images"]]


def load_shoot(date: str) -> dict | None:
    for shoot in load_shoots():
        if shoot["date"] == date:
            return shoot
    # legacy URL without the hour suffix: /shoot/2026-11-08 ->
    # the newest /shoot/2026-11-08-HH slot from that day
    for shoot in load_shoots():
        if shoot["date"].startswith(date + "-"):
            return shoot
    return None


@lru_cache(maxsize=512)
def _gif_meta(path_str: str, mtime_ns: int) -> tuple[int, int, int, int]:
    try:
        with Image.open(path_str) as im:
            width, height = im.size
            frames = int(getattr(im, "n_frames", 1))
            duration = int(im.info.get("duration") or 0)
        return width, height, frames, duration
    except Exception:
        return 0, 0, 0, 0


def build_gif(path: Path, source: str = "asset", shoot_date: str | None = None,
              shoot_title: str | None = None) -> dict:
    width, height, frames, duration = _gif_meta(str(path), path.stat().st_mtime_ns)
    seconds = (frames * duration) / 1000 if duration else 0.0
    if source == "shoot" and shoot_date:
        url = f"/media/shoot/{shoot_date}/{path.name}"
        stem = shoot_title or path.stem.replace("-", " ").replace("_", " ")
        alt = f"Animated showreel — {shoot_title or path.stem}"
    else:
        source = "asset"
        url = f"/media/assets/{path.name}"
        stem = path.stem.replace("-", " ").replace("_", " ")
        alt = f"Animated showreel {path.stem}"
    return {
        "filename": path.name,
        "stem": stem,
        "url": url,
        "width": width,
        "height": height,
        "frames": frames,
        "duration": duration,
        "seconds": seconds,
        "bytes": path.stat().st_size,
        "alt": alt,
        "source": source,
        "date": shoot_date or "",
        "shoot_title": shoot_title or "",
    }
 
 
def load_gifs() -> list[dict]:
    items: list[dict] = []
    # Route helpers such as url_for need an application context.
    with app.app_context():
        # Supplemental loops from assets/ (demo.gif, tests, etc.)
        if ASSET_ROOT.is_dir():
            asset_files = sorted(
                (p for p in ASSET_ROOT.iterdir()
                 if p.is_file() and p.suffix.lower() in GIF_EXTS
                 and not p.name.startswith(".")
                 and p.name != "demo.gif"),
                key=lambda p: natural_key(p.name),
            )
            items.extend(build_gif(path) for path in asset_files)

        # Per-shoot animation: imgs/<date>/car.gif. Collect newest shoots first.
        if IMG_ROOT.is_dir():
            shoot_folders = sorted(
                (p for p in IMG_ROOT.iterdir()
                 if p.is_dir() and not p.name.startswith(".")),
                key=lambda p: p.name,
                reverse=True,
            )
            for folder in shoot_folders:
                gif = folder / "car.gif"
                if not gif.is_file():
                    continue
                car = parse_car_md(folder / "car.md")
                title = f"{car.get('company', '')} {car.get('name', folder.name)}".strip()
                items.append(build_gif(gif, source="shoot",
                                       shoot_date=folder.name, shoot_title=title))
    return items


# --------------------------------------------------------------------------- #
# routes
# --------------------------------------------------------------------------- #
@app.get("/")
def index():
    shoots = load_shoots()
    gifs = load_gifs()
    featured = shoots[0] if shoots else None
    stats = {
        "shoots": len(shoots),
        "frames": sum(shoot["count"] for shoot in shoots),
        "cars": len({shoot["title"] for shoot in shoots}),
        "loops": len(gifs),
    }
    return render_template("index.html", active="archive", shoots=shoots,
                           featured=featured, gifs=gifs, gif=gifs[0] if gifs else None,
                           stats=stats)


@app.get("/shoot/<date>")
def shoot(date: str):
    found = load_shoot(date)
    if found is None:
        abort(404)
    if found["date"] != date:  # old bare-date link -> canonical hour URL
        return redirect(url_for("shoot", date=found["date"]), code=301)
    shoots = load_shoots()
    position = next(i for i, item in enumerate(shoots) if item["date"] == date)
    newer = shoots[position - 1] if position > 0 else None
    older = shoots[position + 1] if position + 1 < len(shoots) else None
    return render_template("shoot.html", active="archive", shoot=found,
                           newer=newer, older=older)


@app.get("/motion")
def motion():
    gifs = load_gifs()
    return render_template("motion.html", active="motion", gifs=gifs)


@app.get("/media/shoot/<date>/<path:filename>")
def media_shoot(date: str, filename: str):
    if not any(item["date"] == date for item in load_shoots()):
        abort(404)
    return send_from_directory(IMG_ROOT / date, filename, max_age=86400)


@app.get("/media/assets/<path:filename>")
def media_asset(filename: str):
    return send_from_directory(ASSET_ROOT, filename, max_age=3600)


@app.get("/api/shoots")
def api_shoots():
    shoots = load_shoots()
    return jsonify({
        "count": len(shoots),
        "shoots": [
            {
                "date": shoot["date"],
                "car": shoot["car"],
                "count": shoot["count"],
                "images": [{k: item[k] for k in ("filename", "url", "width", "height")}
                           for item in shoot["images"]],
            }
            for shoot in shoots
        ],
    })


@app.get("/api/shoots/<date>")
def api_shoot(date: str):
    found = load_shoot(date)
    if found is None:
        abort(404)
    return jsonify({k: v for k, v in found.items() if k != "car"} | {"car": found["car"]})


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html", active=""), 404


@app.get("/robots.txt")
def robots_txt():
    base = request.url_root.rstrip("/")
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /healthz\n"
        "Disallow: /api/\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")


@app.get("/sitemap.xml")
def sitemap_xml():
    import xml.etree.ElementTree as ET
    base = request.url_root.rstrip("/")
    urlset = ET.Element("urlset", {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"})
    for path in ("/", "/motion"):
        url = ET.SubElement(urlset, "url")
        ET.SubElement(url, "loc").text = base + path
        ET.SubElement(url, "priority").text = "1.0" if path == "/" else "0.7"
    for shoot in load_shoots():
        url = ET.SubElement(urlset, "url")
        ET.SubElement(url, "loc").text = f"{base}/shoot/{shoot['date']}"
        ET.SubElement(url, "lastmod").text = shoot["date"]
        ET.SubElement(url, "priority").text = "0.8"
    body = ET.tostring(urlset, encoding="unicode")
    return Response('<?xml version="1.0" encoding="UTF-8"?>\n' + body,
                    mimetype="application/xml")


@app.get("/llms.txt")
def llms_txt():
    base = request.url_root.rstrip("/")
    lines = [
        "# Vista Cars",
        "",
        "> A local-first archive of car photoshoots: ranked frames, spec sheets and looping GIFs.",
        "",
        "## Site",
        f"- URL: {base}/",
        "- Motion: " + base + "/motion",
        "- Sitemap: " + base + "/sitemap.xml",
        "",
        "## Shoots",
    ]
    for shoot in load_shoots():
        lines.append(f"- {shoot['title']} ({shoot['date']}): "
                     f"{shoot['count']} frames; {shoot['description']}")
    lines.extend([
        "",
        "## Data",
        "- Shoots include car.md metadata (make, model, generation, finish, year, engine, power, drivetrain).",
        "- Every still is a ranked frame in its shoot; animated loops come from assets/*.gif plus each shoot's imgs/<date>/car.gif.",
        "",
        "See /robots.txt and /sitemap.xml for crawlers.",
    ])
    body = "\n".join(lines) + "\n"
    return Response(body, mimetype="text/plain")


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="Vista Cars — local car gallery")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--no-debug", action="store_true")
    args = parser.parse_args()
    print(f"Vista Cars → http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=not args.no_debug)


if __name__ == "__main__":
    main()
