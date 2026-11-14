"""LangGraph: plan one car -> harvest -> rater (gemma4) -> save hero + sides + car.md."""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import TypedDict

from PIL import Image, ImageDraw, ImageFont
from langgraph.graph import END, START, StateGraph

import image_search as ims
import rater
import planner


class State(TypedDict):
    date: str
    target: int
    car: dict
    i: int
    query: str
    found: list[dict]  # {raw: bytes, url: str, portrait: bool}
    seen: list[int]  # perceptual hashes
    rated: list[dict]  # found + aura/side/match/watermark/real
    saved: list[str]


def _real(c: dict) -> bool:
    return bool(c.get("real", True))


def make_gif(files: list[str], path: str, w: int = 520, h: int = 650,
             ms: int = 900) -> int:
    frames = []
    for f in files:
        im = Image.open(f)
        if im.mode != "RGB":
            im = im.convert("RGB")
        im.thumbnail((w, h))
        c = Image.new("RGB", (w, h), (0, 0, 0))
        c.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
        frames.append(c)
    if not frames:
        return 0
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=ms, loop=0)
    return len(frames)


# Deliberately list a few distros' paths: tests2 is Ubuntu (DejaVu), the
# dev box ships Noto.  Anything missing falls back to PIL's built-in font.
FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
)


def _caption_font(size: int):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap(text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if not cur or font.getlength(trial) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def caption(path: str, text: str, max_lines: int = 3) -> bool:
    """Burn a semi-transparent bar with ``text`` into the bottom of ``path``.

    Rewrites the file in place as JPEG.  Returns False (leaving the photo
    untouched) when there is nothing to write or the bar would eat the shot.
    """
    if not text:
        return False
    try:
        im = Image.open(path).convert("RGB")
    except OSError:
        return False
    w, h = im.size
    size = max(12, int(w * 0.034))
    font = _caption_font(size)
    pad = max(8, int(w * 0.024))
    lines = _wrap(text, font, w - 2 * pad)[:max_lines]
    if not lines:
        return False
    lh = int(size * 1.34)
    bar_h = lh * len(lines) + 2 * pad
    if bar_h > h * 0.45:  # never let the caption swallow the photo
        return False
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rectangle([0, h - bar_h, w, h], fill=(0, 0, 0, 170))
    y = h - bar_h + pad
    for ln in lines:
        d.text((pad, y), ln, font=font, fill=(255, 255, 255, 245))
        y += lh
    Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB").save(
        path, "JPEG", quality=92)
    return True


def plan(state: State) -> dict:
    if not state["car"]:
        car = planner.plan_car()
        print(f"shoot: {car.get('company')} {car.get('name')} "
              f"({car.get('version')} {car.get('variant')}, {car.get('color')})")
        return {"car": car, "query": car["queries"][0], "i": 0}
    return {"query": state["car"]["queries"][state["i"]]}


def advance(state: State) -> dict:
    return {"i": state["i"] + 1}


def harvest(state: State) -> dict:
    time.sleep(2.0)  # ddgs rate limit
    urls = ims.search_images(state["query"])
    print(f"[{state['i'] + 1}/{len(state['car']['queries'])}] "
          f"{state['query']!r}: {len(urls)} urls")
    with ThreadPoolExecutor(max_workers=8) as ex:
        raws = list(ex.map(ims.download, urls))
    found, seen = list(state["found"]), list(state["seen"])
    for url, raw in zip(urls, raws):
        if not raw:
            continue
        got = ims.assess(raw)
        if not got:
            continue
        ph, portrait = got
        if ims.is_dup(ph, seen):
            continue
        found.append({"raw": raw, "url": url, "portrait": portrait})
        seen.append(ph)
    print(f"  accepted {len(found)} candidates (target {state['target']})")
    return {"found": found, "seen": seen}


def route(state: State) -> str:
    # portrait sides are the scarce thing — stop on those, not total count
    portraits = sum(1 for c in state["found"] if c["portrait"])
    cap = max(state["target"] * 8, state["target"] + 30)
    if (portraits >= state["target"]
            or len(state["found"]) >= cap
            or state["i"] >= len(state["car"]["queries"]) - 1):
        return "rate"
    return "again"


def rate(state: State) -> dict:
    cands = state["found"]
    print(f"rating {len(cands)} candidates (neutral, no external classification)...")
    ratings = rater.rate(state["car"], [c["raw"] for c in cands])
    rated = [{**c, **r} for c, r in zip(cands, ratings)]
    return {"rated": rated}


def save(state: State) -> dict:
    out = os.path.join("imgs", state["date"])
    os.makedirs(out, exist_ok=True)
    # real photos only: AI/renders/CGI never make the cut
    pool = [c for c in state["rated"] if _real(c)]
    if len(pool) < len(state["rated"]):
        print(f"  dropped {len(state['rated']) - len(pool)} "
              "AI-generated / rendered / non-real candidates")
    # Sort pool: watermarked last, then by match/aura (legacy AI rating;
    # with neutral rater all aura=0/match=True so this falls back to pool order)
    pool.sort(key=lambda x: (bool(x.get("watermark")),
                             not x.get("match", True), -x.get("aura", 0)))
    keep: list[dict] = []
    if pool:
        hero = pool[0]  # img-1: best match, any ratio
        keep.append(hero)
        rest = pool[1:]
        # Prioritize portrait (side-angle) images for the remaining slots
        sides = [c for c in rest if c.get("portrait") and c.get("match", True)]
        sides.sort(key=lambda x: (bool(x.get("watermark")), -x.get("aura", 0)))
        keep += sides[: state["target"] - 1]
        if len(keep) < state["target"]:  # fill with best remaining
            used = {c["url"] for c in keep}
            fill = [c for c in rest if c["url"] not in used]
            fill.sort(key=lambda x: (bool(x.get("watermark")),
                                     not x.get("match", True),
                                     -x.get("aura", 0)))
            keep += fill[: state["target"] - len(keep)]
            print(f"  note: only {len(sides)} portrait sides, "
                  f"filled to {len(keep)} with best remaining angles")
    paths = []
    for n, item in enumerate(keep, 1):
        img = Image.open(BytesIO(item["raw"]))
        if img.mode != "RGB":
            img = img.convert("RGB")
        p = os.path.join(out, f"img-{n}.jpg")
        img.save(p, "JPEG", quality=92)
        paths.append(p)
        print(f"  saved {p}  aura={item['aura']} side={item['side']} "
              f"match={item.get('match', True)} real={item.get('real', True)} "
              f"watermark={item.get('watermark', False)} {item['url'][:80]}")
    car = state["car"]
    md_lines = [f"{k}: {v}" for k, v in car.items() if k != "queries" and v]
    md_path = os.path.join(out, "car.md")
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"  wrote {md_path}")
    # Fun fact burned into the hero shot (img-1) as a bottom caption bar.
    fact = planner.fun_fact(car) if paths else ""
    if fact and caption(paths[0], fact):
        print(f"  fun fact on {paths[0]}: {fact}")
    gif_path = os.path.join(out, "car.gif")
    n = make_gif(paths, gif_path)
    if n:
        print(f"  wrote {gif_path} ({n} frames)")
    if len(paths) < state["target"]:
        print(f"WARNING: only {len(paths)}/{state['target']} images "
              "(not enough portrait side angles?)")
    return {"saved": paths}


def build_graph():
    b = StateGraph(State)
    b.add_node("plan", plan)
    b.add_node("advance", advance)
    b.add_node("harvest", harvest)
    b.add_node("rate", rate)
    b.add_node("save", save)
    b.add_edge(START, "plan")
    b.add_edge("plan", "harvest")
    b.add_conditional_edges("harvest", route, {"again": "advance", "rate": "rate"})
    b.add_edge("advance", "plan")
    b.add_edge("rate", "save")
    b.add_edge("save", END)
    return b.compile()
