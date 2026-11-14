"""Plan one car per day from the 5-car fallback pool via OpenRouter.

The previous sodeom.com/ai proxy and the Ollama key both stopped working
(flat/no credits), so we now ask OpenRouter's ``openrouter/free`` model for
one index only.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import requests
from ddgs import DDGS

URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/free"

# Keys tried in order: primary first, then fallback.  Each is tried until one
# returns a usable response, so a revoked primary key does not kill the run.
KEY_ORDER = ("OPENROUTER_API_KEY", "OPENROUTER_API_KEY_FALLBACK")


def _load_env() -> dict:
    """Process env merged with `KEY=value` lines from .env next to this file."""
    env = dict(os.environ)
    try:
        with open(Path(__file__).resolve().parent / ".env") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                env.setdefault(k.strip(), v.strip().strip("'\""))
    except OSError:
        pass
    return env


def _load_keys() -> list[str]:
    env = _load_env()
    keys = []
    for name in KEY_ORDER:
        if v := (env.get(name) or "").strip().strip("'\""):
            if v not in keys:
                keys.append(v)
    return keys


KEYS = _load_keys()
KEY = KEYS[0] if KEYS else None


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo instant answer / web search for factual grounding.

    Returns a list of dicts with keys: title, href, body.
    """
    try:
        return list(DDGS().text(query, max_results=max_results))
    except Exception as e:  # noqa: BLE001
        print(f"  web search failed for {query!r}: {e}")
        return []


def _ask(prompt: str, max_tokens: int = 300, tries: int = 4) -> str:
    """One completion, retried.

    The free ``openrouter/free`` route hands back ``content: null`` whenever
    the routed model spends its whole token budget on reasoning.  ``str(None)``
    used to become the literal text ``"None"``, which then failed JSON parsing
    and silently dropped us onto a random car.  Treat empty/null content as a
    failure so it is retried instead of being forwarded as an answer.
    """
    if not KEYS:
        raise RuntimeError("no OPENROUTER_API_KEY (or fallback) configured")
    last_err: Exception | None = None
    for attempt in range(tries):
        for key in KEYS:
            try:
                r = requests.post(
                    URL,
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json",
                             "HTTP-Referer": "https://vistacars.thetrillioniar.me",
                             "X-Title": "Vista Cars planner"},
                    json={"model": MODEL,
                          "messages": [{"role": "user", "content": prompt}],
                          "temperature": 0.9, "max_tokens": max_tokens},
                    timeout=45,
                )
                r.raise_for_status()
                choices = r.json().get("choices") or [{}]
                content = (choices[0].get("message") or {}).get("content")
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("null/empty content from model")
                return content.strip()
            except Exception as e:  # noqa: BLE001 - try next key / retry
                last_err = e
                print(f"  openrouter attempt {attempt + 1}/{tries} failed "
                      f"({type(e).__name__}: {e})")
        time.sleep(1.5)
    raise last_err if last_err else RuntimeError("no usable OPENROUTER key")
FALLBACK_CARS = [
    # ==================== BMW ====================
    {
        "name": "M2 Competition", "company": "BMW", "version": "F87", "variant": "Competition",
        "color": "black", "year": "2020", "engine": "3.0L twin-turbo inline-six S55",
        "power": "405 hp", "drivetrain": "RWD, 7-speed DCT",
        "description": "Short-wheelbase coupe that loves to be sideways.",
        "queries": [
            "BMW M2 Competition black photoshoot", "F87 M2 night photography",
            "black BMW M2 side profile", "BMW M2 dark studio",
            "M2 Competition moody wallpaper", "M2 black rear night",
            "BMW M2 street night", "M2 underground parking",
            "BMW M2 vertical wallpaper", "M2 Competition phone wallpaper portrait",
            "black BMW M2 9:16 wallpaper",
        ],
    },
    {
        "name": "M2", "company": "BMW", "version": "G87", "variant": "Base",
        "color": "zandvoort blue", "year": "2023", "engine": "3.0L twin-turbo inline-six S58",
        "power": "453 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "New generation with manual transmission and aggressive stance.",
        "queries": [
            "BMW M2 G87 blue photoshoot", "G87 M2 night photography",
            "blue BMW M2 side profile", "BMW M2 G87 dark studio",
            "M2 moody wallpaper", "M2 blue rear night",
            "BMW M2 street night", "M2 underground parking",
            "BMW M2 vertical wallpaper", "M2 phone wallpaper portrait",
            "blue BMW M2 9:16 wallpaper",
        ],
    },
    {
        "name": "M3 Competition", "company": "BMW", "version": "G80", "variant": "Competition",
        "color": "isle of man green", "year": "2022", "engine": "3.0L twin-turbo inline-six S58",
        "power": "503 hp", "drivetrain": "AWD, 8-speed automatic",
        "description": "First-ever all-wheel-drive M3 with track-ready composure.",
        "queries": [
            "BMW M3 Competition green photoshoot", "G80 M3 night photography",
            "green BMW M3 side profile", "BMW M3 dark studio",
            "M3 Competition moody wallpaper", "M3 green rear night",
            "BMW M3 street night", "M3 underground parking",
            "BMW M3 vertical wallpaper", "M3 Competition phone wallpaper portrait",
            "green BMW M3 9:16 wallpaper",
        ],
    },
    {
        "name": "M3 CS", "company": "BMW", "version": "G80", "variant": "CS",
        "color": "signal green", "year": "2024", "engine": "3.0L twin-turbo inline-six S58",
        "power": "543 hp", "drivetrain": "AWD, 8-speed automatic",
        "description": "Lightweight special with carbon bucket seats and track focus.",
        "queries": [
            "BMW M3 CS green photoshoot", "G80 M3 CS night photography",
            "green BMW M3 CS side profile", "BMW M3 CS dark studio",
            "M3 CS moody wallpaper", "M3 CS green rear night",
            "BMW M3 CS street night", "M3 CS underground parking",
            "BMW M3 CS vertical wallpaper", "M3 CS phone wallpaper portrait",
            "green BMW M3 CS 9:16 wallpaper",
        ],
    },
    {
        "name": "M4 Competition", "company": "BMW", "version": "G82", "variant": "Competition",
        "color": "black", "year": "2023", "engine": "3.0L twin-turbo inline-six S58",
        "power": "503 hp", "drivetrain": "RWD, 8-speed automatic",
        "description": "Big-grille coupe with brutal straight-line pace.",
        "queries": [
            "BMW M4 Competition black photoshoot", "G82 M4 night photography",
            "black M4 side profile", "BMW M4 dark studio",
            "M4 Competition moody wallpaper", "M4 black rear night",
            "BMW M4 street night", "M4 underground parking",
            "BMW M4 vertical wallpaper", "M4 Competition phone wallpaper portrait",
            "black BMW M4 9:16 wallpaper",
        ],
    },
    {
        "name": "M4 CSL", "company": "BMW", "version": "G82", "variant": "CSL",
        "color": "frozen black", "year": "2023", "engine": "3.0L twin-turbo inline-six S58",
        "power": "543 hp", "drivetrain": "RWD, 8-speed automatic",
        "description": "Lightweight homologation special, 1000 units only.",
        "queries": [
            "BMW M4 CSL black photoshoot", "G82 M4 CSL night photography",
            "black M4 CSL side profile", "BMW M4 CSL dark studio",
            "M4 CSL moody wallpaper", "M4 CSL black rear night",
            "BMW M4 CSL street night", "M4 CSL underground parking",
            "BMW M4 CSL vertical wallpaper", "M4 CSL phone wallpaper portrait",
            "black BMW M4 CSL 9:16 wallpaper",
        ],
    },
    {
        "name": "M5 Competition", "company": "BMW", "version": "F90", "variant": "Competition",
        "color": "dravit grey", "year": "2022", "engine": "4.4L twin-turbo V8 S63",
        "power": "617 hp", "drivetrain": "AWD, 8-speed automatic",
        "description": "Executive sedan that doubles as a track weapon.",
        "queries": [
            "BMW M5 Competition grey photoshoot", "F90 M5 night photography",
            "grey BMW M5 side profile", "BMW M5 dark studio",
            "M5 Competition moody wallpaper", "M5 grey rear night",
            "BMW M5 street night", "M5 underground parking",
            "BMW M5 vertical wallpaper", "M5 Competition phone wallpaper portrait",
            "grey BMW M5 9:16 wallpaper",
        ],
    },
    {
        "name": "M5 CS", "company": "BMW", "version": "F90", "variant": "CS",
        "color": "frozen deep green", "year": "2022", "engine": "4.4L twin-turbo V8 S63",
        "power": "627 hp", "drivetrain": "AWD, 8-speed automatic",
        "description": "Most powerful BMW production car ever at launch.",
        "queries": [
            "BMW M5 CS green photoshoot", "F90 M5 CS night photography",
            "green BMW M5 CS side profile", "BMW M5 CS dark studio",
            "M5 CS moody wallpaper", "M5 CS green rear night",
            "BMW M5 CS street night", "M5 CS underground parking",
            "BMW M5 CS vertical wallpaper", "M5 CS phone wallpaper portrait",
            "green BMW M5 CS 9:16 wallpaper",
        ],
    },
    {
        "name": "M8 Competition", "company": "BMW", "version": "F92", "variant": "Competition",
        "color": "tanzanite blue", "year": "2021", "engine": "4.4L twin-turbo V8 S63",
        "power": "617 hp", "drivetrain": "AWD, 8-speed automatic",
        "description": "Grand tourer with supercar performance and presence.",
        "queries": [
            "BMW M8 Competition blue photoshoot", "F92 M8 night photography",
            "blue BMW M8 side profile", "BMW M8 dark studio",
            "M8 Competition moody wallpaper", "M8 blue rear night",
            "BMW M8 street night", "M8 underground parking",
            "BMW M8 vertical wallpaper", "M8 Competition phone wallpaper portrait",
            "blue BMW M8 9:16 wallpaper",
        ],
    },
    {
        "name": "X3 M Competition", "company": "BMW", "version": "G01", "variant": "Competition",
        "color": "toronto red", "year": "2023", "engine": "3.0L twin-turbo inline-six S58",
        "power": "503 hp", "drivetrain": "AWD, 8-speed automatic",
        "description": "Compact SUV with M-division firepower.",
        "queries": [
            "BMW X3 M Competition red photoshoot", "G01 X3 M night photography",
            "red BMW X3 M side profile", "BMW X3 M dark studio",
            "X3 M Competition moody wallpaper", "X3 M red rear night",
            "BMW X3 M street night", "X3 M underground parking",
            "BMW X3 M vertical wallpaper", "X3 M Competition phone wallpaper portrait",
            "red BMW X3 M 9:16 wallpaper",
        ],
    },
    {
        "name": "X4 M Competition", "company": "BMW", "version": "G02", "variant": "Competition",
        "color": "frozen grey", "year": "2022", "engine": "3.0L twin-turbo inline-six S58",
        "power": "503 hp", "drivetrain": "AWD, 8-speed automatic",
        "description": "Coupe-SUV silhouette with track-ready dynamics.",
        "queries": [
            "BMW X4 M Competition grey photoshoot", "G02 X4 M night photography",
            "grey BMW X4 M side profile", "BMW X4 M dark studio",
            "X4 M Competition moody wallpaper", "X4 M grey rear night",
            "BMW X4 M street night", "X4 M underground parking",
            "BMW X4 M vertical wallpaper", "X4 M Competition phone wallpaper portrait",
            "grey BMW X4 M 9:16 wallpaper",
        ],
    },
    {
        "name": "X5 M Competition", "company": "BMW", "version": "F95", "variant": "Competition",
        "color": "carbon black", "year": "2023", "engine": "4.4L twin-turbo V8 S63",
        "power": "617 hp", "drivetrain": "AWD, 8-speed automatic",
        "description": "Family hauler that embarrasses sports cars.",
        "queries": [
            "BMW X5 M Competition black photoshoot", "F95 X5 M night photography",
            "black BMW X5 M side profile", "BMW X5 M dark studio",
            "X5 M Competition moody wallpaper", "X5 M black rear night",
            "BMW X5 M street night", "X5 M underground parking",
            "BMW X5 M vertical wallpaper", "X5 M Competition phone wallpaper portrait",
            "black BMW X5 M 9:16 wallpaper",
        ],
    },
    {
        "name": "X6 M Competition", "company": "BMW", "version": "F96", "variant": "Competition",
        "color": "amarone", "year": "2022", "engine": "4.4L twin-turbo V8 S63",
        "power": "617 hp", "drivetrain": "AWD, 8-speed automatic",
        "description": "Coupe-SUV with V8 thunder and rear-wheel steer.",
        "queries": [
            "BMW X6 M Competition amarone photoshoot", "F96 X6 M night photography",
            "amarone BMW X6 M side profile", "BMW X6 M dark studio",
            "X6 M Competition moody wallpaper", "X6 M amarone rear night",
            "BMW X6 M street night", "X6 M underground parking",
            "BMW X6 M vertical wallpaper", "X6 M Competition phone wallpaper portrait",
            "amarone BMW X6 M 9:16 wallpaper",
        ],
    },
    {
        "name": "Z4 M40i", "company": "BMW", "version": "G29", "variant": "M40i",
        "color": "san francisco red", "year": "2021", "engine": "3.0L turbo inline-six B58",
        "power": "382 hp", "drivetrain": "RWD, 8-speed automatic",
        "description": "Roadster with turbo straight-six and perfect balance.",
        "queries": [
            "BMW Z4 M40i red photoshoot", "G29 Z4 night photography",
            "red BMW Z4 side profile", "BMW Z4 dark studio",
            "Z4 M40i moody wallpaper", "Z4 red rear night",
            "BMW Z4 street night", "Z4 underground parking",
            "BMW Z4 vertical wallpaper", "Z4 M40i phone wallpaper portrait",
            "red BMW Z4 9:16 wallpaper",
        ],
    },
    {
        "name": "1M Coupe", "company": "BMW", "version": "E82", "variant": "1M",
        "color": "valencia orange", "year": "2011", "engine": "3.0L twin-turbo inline-six N54",
        "power": "335 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "Future classic that started the turbo M-coupe legacy.",
        "queries": [
            "BMW 1M Coupe orange photoshoot", "E82 1M night photography",
            "orange BMW 1M side profile", "BMW 1M dark studio",
            "1M Coupe moody wallpaper", "1M orange rear night",
            "BMW 1M street night", "1M underground parking",
            "BMW 1M vertical wallpaper", "1M phone wallpaper portrait",
            "orange BMW 1M 9:16 wallpaper",
        ],
    },
    {
        "name": "M3 CSL", "company": "BMW", "version": "E46", "variant": "CSL",
        "color": "silver grey", "year": "2003", "engine": "3.2L inline-six S54",
        "power": "355 hp", "drivetrain": "RWD, 6-speed SMG",
        "description": "Lightweight icon with carbon roof and legendary balance.",
        "queries": [
            "BMW E46 M3 CSL silver photoshoot", "E46 M3 night photography",
            "silver BMW M3 side profile", "BMW M3 CSL dark studio",
            "E46 M3 CSL moody wallpaper", "M3 CSL silver rear night",
            "BMW E46 M3 street night", "E46 M3 underground parking",
            "BMW E46 M3 vertical wallpaper", "E46 M3 CSL phone wallpaper portrait",
            "silver BMW E46 M3 9:16 wallpaper",
        ],
    },
    {
        "name": "M3", "company": "BMW", "version": "E92", "variant": "Base",
        "color": "interlagos blue", "year": "2010", "engine": "4.0L naturally aspirated V8 S65",
        "power": "414 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "Last naturally aspirated M3 V8 — a high-rev masterpiece.",
        "queries": [
            "BMW E92 M3 blue photoshoot", "E92 M3 night photography",
            "blue BMW M3 side profile", "BMW E92 M3 dark studio",
            "E92 M3 moody wallpaper", "M3 blue rear night",
            "BMW E92 M3 street night", "E92 M3 underground parking",
            "BMW E92 M3 vertical wallpaper", "E92 M3 phone wallpaper portrait",
            "blue BMW E92 M3 9:16 wallpaper",
        ],
    },
    {
        "name": "M6", "company": "BMW", "version": "F12", "variant": "Base",
        "color": "frozen silver", "year": "2013", "engine": "4.4L twin-turbo V8 S63",
        "power": "552 hp", "drivetrain": "RWD, 7-speed DCT",
        "description": "Grand coupe with twin-turbo V8 and carbon-ceramic brakes.",
        "queries": [
            "BMW M6 F12 silver photoshoot", "F12 M6 night photography",
            "silver BMW M6 side profile", "BMW M6 dark studio",
            "M6 moody wallpaper", "M6 silver rear night",
            "BMW M6 street night", "M6 underground parking",
            "BMW M6 vertical wallpaper", "M6 phone wallpaper portrait",
            "silver BMW M6 9:16 wallpaper",
        ],
    },
    {
        "name": "M1", "company": "BMW", "version": "E26", "variant": "Base",
        "color": "orange", "year": "1979", "engine": "3.5L inline-six M88",
        "power": "273 hp", "drivetrain": "RWD, 5-speed manual",
        "description": "Mid-engine supercar that launched M Division.",
        "queries": [
            "BMW M1 orange photoshoot", "E26 M1 night photography",
            "orange BMW M1 side profile", "BMW M1 dark studio",
            "M1 moody wallpaper", "M1 orange rear night",
            "BMW M1 street night", "M1 underground parking",
            "BMW M1 vertical wallpaper", "M1 phone wallpaper portrait",
            "orange BMW M1 9:16 wallpaper",
        ],
    },

    # ==================== PORSCHE ====================
    {
        "name": "911 GT3 RS", "company": "Porsche", "version": "992.1", "variant": "RS",
        "color": "black", "year": "2023", "engine": "4.0L naturally aspirated flat-six",
        "power": "518 hp", "drivetrain": "RWD, 7-speed PDK",
        "description": "Track-focused 911 with a huge swan-neck rear wing.",
        "queries": [
            "Porsche 911 GT3 RS black photoshoot", "911 GT3 RS night photography",
            "black 911 GT3 RS side profile", "992 GT3 RS dark studio",
            "911 GT3 RS moody wallpaper", "GT3 RS black rear wing night",
            "911 GT3 RS street night", "GT3 RS underground parking",
            "911 GT3 RS vertical wallpaper", "GT3 RS phone wallpaper portrait",
            "black 911 GT3 RS 9:16 wallpaper",
        ],
    },
    {
        "name": "911 GT3", "company": "Porsche", "version": "992.1", "variant": "GT3",
        "color": "shark blue", "year": "2022", "engine": "4.0L naturally aspirated flat-six",
        "power": "502 hp", "drivetrain": "RWD, 7-speed PDK",
        "description": "Naturally aspirated track scalpel with optional manual.",
        "queries": [
            "Porsche 911 GT3 blue photoshoot", "992 GT3 night photography",
            "blue 911 GT3 side profile", "Porsche 911 GT3 dark studio",
            "911 GT3 moody wallpaper", "GT3 blue rear night",
            "Porsche 911 GT3 street night", "911 GT3 underground parking",
            "911 GT3 vertical wallpaper", "GT3 phone wallpaper portrait",
            "blue 911 GT3 9:16 wallpaper",
        ],
    },
    {
        "name": "911 GT3 RS", "company": "Porsche", "version": "991.2", "variant": "RS",
        "color": "lizard green", "year": "2018", "engine": "4.0L naturally aspirated flat-six",
        "power": "520 hp", "drivetrain": "RWD, 7-speed PDK",
        "description": "Previous-gen RS with a massive rear wing and raw feel.",
        "queries": [
            "Porsche 911 GT3 RS green photoshoot", "991 GT3 RS night photography",
            "green 911 GT3 RS side profile", "Porsche 911 GT3 RS dark studio",
            "991 GT3 RS moody wallpaper", "GT3 RS green rear wing night",
            "Porsche 911 GT3 RS street night", "GT3 RS underground parking",
            "911 GT3 RS vertical wallpaper", "GT3 RS phone wallpaper portrait",
            "green 911 GT3 RS 9:16 wallpaper",
        ],
    },
    {
        "name": "911 GT3", "company": "Porsche", "version": "991.2", "variant": "GT3",
        "color": "racing yellow", "year": "2017", "engine": "4.0L naturally aspirated flat-six",
        "power": "500 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "The return of the manual GT3 with 9,000 rpm redline.",
        "queries": [
            "Porsche 911 GT3 yellow photoshoot", "991 GT3 night photography",
            "yellow 911 GT3 side profile", "Porsche 911 GT3 dark studio",
            "991 GT3 moody wallpaper", "GT3 yellow rear night",
            "Porsche 911 GT3 street night", "911 GT3 underground parking",
            "911 GT3 vertical wallpaper", "GT3 phone wallpaper portrait",
            "yellow 911 GT3 9:16 wallpaper",
        ],
    },
    {
        "name": "911 GT2 RS", "company": "Porsche", "version": "991.2", "variant": "GT2 RS",
        "color": "weissach package", "year": "2018", "engine": "3.8L twin-turbo flat-six",
        "power": "700 hp", "drivetrain": "RWD, 7-speed PDK",
        "description": "Most powerful 911 ever — twin-turbo rear-engine rocket.",
        "queries": [
            "Porsche 911 GT2 RS weissach photoshoot", "991 GT2 RS night photography",
            "weissach 911 GT2 RS side profile", "Porsche 911 GT2 RS dark studio",
            "911 GT2 RS moody wallpaper", "GT2 RS rear night",
            "Porsche 911 GT2 RS street night", "GT2 RS underground parking",
            "911 GT2 RS vertical wallpaper", "GT2 RS phone wallpaper portrait",
            "weissach 911 GT2 RS 9:16 wallpaper",
        ],
    },
    {
        "name": "911 Turbo S", "company": "Porsche", "version": "992", "variant": "Turbo S",
        "color": "gentian blue", "year": "2024", "engine": "3.8L twin-turbo flat-six",
        "power": "640 hp", "drivetrain": "AWD, 8-speed PDK",
        "description": "All-weather missile that defies physics out of corners.",
        "queries": [
            "Porsche 911 Turbo S blue photoshoot", "992 Turbo S night photography",
            "blue 911 Turbo side profile", "Porsche 911 dark studio",
            "911 Turbo S moody wallpaper", "Turbo S blue rear night",
            "Porsche 911 street night", "911 Turbo underground parking",
            "911 Turbo S vertical wallpaper", "911 phone wallpaper portrait",
            "blue Porsche 911 Turbo 9:16 wallpaper",
        ],
    },
    {
        "name": "911 Turbo S", "company": "Porsche", "version": "991.2", "variant": "Turbo S",
        "color": "chalk", "year": "2020", "engine": "3.8L twin-turbo flat-six",
        "power": "640 hp", "drivetrain": "AWD, 8-speed PDK",
        "description": "Previous-gen Turbo S with insane launch and daily usability.",
        "queries": [
            "Porsche 911 Turbo S chalk photoshoot", "991 Turbo S night photography",
            "chalk 911 Turbo side profile", "Porsche 911 Turbo S dark studio",
            "991 Turbo S moody wallpaper", "Turbo S chalk rear night",
            "Porsche 911 Turbo S street night", "Turbo S underground parking",
            "911 Turbo S vertical wallpaper", "Turbo S phone wallpaper portrait",
            "chalk 911 Turbo S 9:16 wallpaper",
        ],
    },
    {
        "name": "911 Turbo", "company": "Porsche", "version": "992", "variant": "Turbo",
        "color": "ice grey metallic", "year": "2023", "engine": "3.7L twin-turbo flat-six",
        "power": "572 hp", "drivetrain": "AWD, 8-speed PDK",
        "description": "Slightly softer Turbo with the same everyday supercar DNA.",
        "queries": [
            "Porsche 911 Turbo grey photoshoot", "992 Turbo night photography",
            "grey 911 Turbo side profile", "Porsche 911 Turbo dark studio",
            "911 Turbo moody wallpaper", "Turbo grey rear night",
            "Porsche 911 Turbo street night", "911 Turbo underground parking",
            "911 Turbo vertical wallpaper", "Turbo phone wallpaper portrait",
            "grey Porsche 911 Turbo 9:16 wallpaper",
        ],
    },
    {
        "name": "911 Carrera 4S", "company": "Porsche", "version": "992", "variant": "Carrera 4S",
        "color": "carmine red", "year": "2022", "engine": "3.0L twin-turbo flat-six",
        "power": "443 hp", "drivetrain": "AWD, 8-speed PDK",
        "description": "Sweet spot of daily driver and track capability.",
        "queries": [
            "Porsche 911 Carrera 4S red photoshoot", "992 Carrera 4S night photography",
            "red 911 Carrera side profile", "Porsche 911 Carrera dark studio",
            "Carrera 4S moody wallpaper", "911 Carrera red rear night",
            "Porsche 911 street night", "Carrera 4S underground parking",
            "911 Carrera 4S vertical wallpaper", "Carrera 4S phone wallpaper portrait",
            "red Porsche 911 9:16 wallpaper",
        ],
    },
    {
        "name": "911 Carrera GTS", "company": "Porsche", "version": "992", "variant": "GTS",
        "color": "python green", "year": "2024", "engine": "3.0L twin-turbo flat-six hybrid",
        "power": "473 hp", "drivetrain": "RWD, 8-speed PDK",
        "description": "First hybrid GTS with T-Hybrid electric assist.",
        "queries": [
            "Porsche 911 GTS green photoshoot", "992 GTS night photography",
            "green 911 GTS side profile", "Porsche 911 GTS dark studio",
            "911 GTS moody wallpaper", "GTS green rear night",
            "Porsche 911 GTS street night", "911 GTS underground parking",
            "911 GTS vertical wallpaper", "GTS phone wallpaper portrait",
            "green Porsche 911 GTS 9:16 wallpaper",
        ],
    },
    {
        "name": "718 Cayman GT4 RS", "company": "Porsche", "version": "982", "variant": "GT4 RS",
        "color": "ruby star neo", "year": "2022", "engine": "4.0L naturally aspirated flat-six",
        "power": "493 hp", "drivetrain": "RWD, 7-speed PDK",
        "description": "Mid-engine GT3 engine in a Cayman — track perfection.",
        "queries": [
            "Porsche 718 Cayman GT4 RS red photoshoot", "GT4 RS night photography",
            "red Cayman GT4 side profile", "Porsche GT4 RS dark studio",
            "Cayman GT4 RS moody wallpaper", "GT4 RS red rear night",
            "Porsche Cayman street night", "GT4 RS underground parking",
            "Cayman GT4 RS vertical wallpaper", "GT4 RS phone wallpaper portrait",
            "red Porsche Cayman GT4 9:16 wallpaper",
        ],
    },
    {
        "name": "718 Cayman GT4", "company": "Porsche", "version": "982", "variant": "GT4",
        "color": "racing yellow", "year": "2020", "engine": "4.0L naturally aspirated flat-six",
        "power": "414 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "Manual mid-engine track weapon with GT3 DNA.",
        "queries": [
            "Porsche 718 Cayman GT4 yellow photoshoot", "GT4 night photography",
            "yellow Cayman GT4 side profile", "Porsche Cayman GT4 dark studio",
            "Cayman GT4 moody wallpaper", "GT4 yellow rear night",
            "Porsche Cayman GT4 street night", "GT4 underground parking",
            "Cayman GT4 vertical wallpaper", "GT4 phone wallpaper portrait",
            "yellow Porsche Cayman 9:16 wallpaper",
        ],
    },
    {
        "name": "718 Boxster Spyder", "company": "Porsche", "version": "982", "variant": "Spyder",
        "color": "gt silver metallic", "year": "2020", "engine": "4.0L naturally aspirated flat-six",
        "power": "414 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "Open-top mid-engine with the same GT4 heart.",
        "queries": [
            "Porsche 718 Boxster Spyder silver photoshoot", "Boxster Spyder night photography",
            "silver Boxster Spyder side profile", "Porsche Boxster Spyder dark studio",
            "Boxster Spyder moody wallpaper", "Spyder silver rear night",
            "Porsche Boxster Spyder street night", "Spyder underground parking",
            "Boxster Spyder vertical wallpaper", "Spyder phone wallpaper portrait",
            "silver Porsche Boxster 9:16 wallpaper",
        ],
    },
    {
        "name": "911 GT3 RS 4.0", "company": "Porsche", "version": "997.2", "variant": "RS 4.0",
        "color": "peridot metallic", "year": "2011", "engine": "4.0L naturally aspirated flat-six",
        "power": "500 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "Last Mezger-engined GT3 RS — a modern air-cooled legend.",
        "queries": [
            "Porsche 911 GT3 RS 4.0 green photoshoot", "997 GT3 RS night photography",
            "green 997 GT3 RS side profile", "Porsche 997 GT3 RS dark studio",
            "997 GT3 RS moody wallpaper", "GT3 RS 4.0 green rear night",
            "Porsche 997 GT3 RS street night", "997 GT3 RS underground parking",
            "997 GT3 RS vertical wallpaper", "GT3 RS phone wallpaper portrait",
            "green Porsche 997 GT3 9:16 wallpaper",
        ],
    },
    {
        "name": "911 GT2", "company": "Porsche", "version": "997", "variant": "GT2",
        "color": "black", "year": "2010", "engine": "3.6L twin-turbo flat-six",
        "power": "620 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "Widow-maker turbo with raw rear-engine character.",
        "queries": [
            "Porsche 911 GT2 black photoshoot", "997 GT2 night photography",
            "black 911 GT2 side profile", "Porsche 911 GT2 dark studio",
            "997 GT2 moody wallpaper", "GT2 black rear night",
            "Porsche 911 GT2 street night", "GT2 underground parking",
            "911 GT2 vertical wallpaper", "GT2 phone wallpaper portrait",
            "black Porsche 997 GT2 9:16 wallpaper",
        ],
    },
    {
        "name": "911 GT3", "company": "Porsche", "version": "997.1", "variant": "GT3",
        "color": "signal green", "year": "2006", "engine": "3.6L naturally aspirated flat-six",
        "power": "409 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "First GT3 with Mezger engine — pure analog precision.",
        "queries": [
            "Porsche 997 GT3 green photoshoot", "997 GT3 night photography",
            "green 997 GT3 side profile", "Porsche 997 GT3 dark studio",
            "997 GT3 moody wallpaper", "GT3 green rear night",
            "Porsche 997 GT3 street night", "997 GT3 underground parking",
            "997 GT3 vertical wallpaper", "GT3 phone wallpaper portrait",
            "green Porsche 997 GT3 9:16 wallpaper",
        ],
    },
    {
        "name": "Taycan Turbo S", "company": "Porsche", "version": "J1", "variant": "Turbo S",
        "color": "acid green", "year": "2024", "engine": "dual-motor electric",
        "power": "750 hp", "drivetrain": "AWD, 2-speed transmission",
        "description": "First electric Porsche with 911-beating acceleration.",
        "queries": [
            "Porsche Taycan Turbo S green photoshoot", "Taycan night photography",
            "green Taycan side profile", "Porsche Taycan dark studio",
            "Taycan Turbo S moody wallpaper", "Taycan green rear night",
            "Porsche Taycan street night", "Taycan underground parking",
            "Taycan Turbo S vertical wallpaper", "Taycan phone wallpaper portrait",
            "green Porsche Taycan 9:16 wallpaper",
        ],
    },
    {
        "name": "918 Spyder", "company": "Porsche", "version": "918", "variant": "Base",
        "color": "liquid metal chrome blue", "year": "2015", "engine": "4.6L V8 + dual electric motors",
        "power": "887 hp", "drivetrain": "AWD, 7-speed PDK",
        "description": "Hybrid hypercar with V8 scream and electric torque.",
        "queries": [
            "Porsche 918 Spyder blue photoshoot", "918 Spyder night photography",
            "blue 918 Spyder side profile", "Porsche 918 dark studio",
            "918 Spyder moody wallpaper", "918 Spyder blue rear night",
            "Porsche 918 street night", "918 Spyder underground parking",
            "918 Spyder vertical wallpaper", "918 Spyder phone wallpaper portrait",
            "blue Porsche 918 9:16 wallpaper",
        ],
    },
    {
        "name": "Carrera GT", "company": "Porsche", "version": "980", "variant": "Base",
        "color": "guards red", "year": "2005", "engine": "5.7L naturally aspirated V10",
        "power": "605 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "V10 analog hypercar with ceramic clutch and no aids.",
        "queries": [
            "Porsche Carrera GT red photoshoot", "Carrera GT night photography",
            "red Carrera GT side profile", "Porsche Carrera GT dark studio",
            "Carrera GT moody wallpaper", "Carrera GT red rear night",
            "Porsche Carrera GT street night", "Carrera GT underground parking",
            "Carrera GT vertical wallpaper", "Carrera GT phone wallpaper portrait",
            "red Porsche Carrera GT 9:16 wallpaper",
        ],
    },
    {
        "name": "911 GT3 RS", "company": "Porsche", "version": "996", "variant": "RS",
        "color": "gt silver", "year": "2003", "engine": "3.6L naturally aspirated flat-six",
        "power": "381 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "First water-cooled GT3 RS — a homologation special.",
        "queries": [
            "Porsche 996 GT3 RS silver photoshoot", "996 GT3 RS night photography",
            "silver 996 GT3 RS side profile", "Porsche 996 GT3 RS dark studio",
            "996 GT3 RS moody wallpaper", "GT3 RS silver rear night",
            "Porsche 996 GT3 RS street night", "996 GT3 RS underground parking",
            "996 GT3 RS vertical wallpaper", "GT3 RS phone wallpaper portrait",
            "silver Porsche 996 GT3 9:16 wallpaper",
        ],
    },
]


def _car_key(car: dict) -> tuple[str, str]:
    """Identity of a car for duplicate detection (company + name + version + variant).

    This treats different generations/variants of the same model as distinct cars
    (e.g., 911 GT3 RS 992.1 ≠ 911 GT3 RS 991.2), while still catching exact
    duplicate entries in the pool or re-shoots of the same spec.
    """
    return (str(car.get("company", "")).strip().lower(),
            str(car.get("name", "")).strip().lower(),
            str(car.get("version", "")).strip().lower(),
            str(car.get("variant", "")).strip().lower())


def _dedupe_pool(cars: list[dict]) -> list[dict]:
    """Drop duplicate car entries, keeping the first occurrence."""
    seen: set[tuple[str, str]] = set()
    out = []
    for c in cars:
        k = _car_key(c)
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


def _used_keys() -> set[tuple[str, str, str, str]]:
    """Cars already shot, read from every ``imgs/<slot>/car.md`` on disk."""
    used: set[tuple[str, str, str, str]] = set()
    for md in sorted((Path(__file__).resolve().parent / "imgs").glob("*/car.md")):
        name = company = version = variant = ""
        try:
            for line in md.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("company:"):
                    company = line.split(":", 1)[1].strip()
                elif line.startswith("version:"):
                    version = line.split(":", 1)[1].strip()
                elif line.startswith("variant:"):
                    variant = line.split(":", 1)[1].strip()
        except OSError:
            continue
        if name:
            used.add((company.lower(), name.lower(), version.lower(), variant.lower()))
    return used


def _labels(cars: list[dict]) -> str:
    return "  ".join(f"{i}={c['company']} {c['name']}"
                     for i, c in enumerate(cars, start=1))

def _parse_json(txt: str):
    if txt.startswith("```"):
        txt = txt.split("\n", 1)[1].rsplit("```", 1)[0]
    txt = txt.strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        pass
    # repair truncated/unterminated answers: take the outermost balanced object
    start = txt.find("{")
    if start >= 0:
        depth = 0
        end = -1
        for i, ch in enumerate(txt[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end > start:
            try:
                return json.loads(txt[start:end + 1])
            except json.JSONDecodeError:
                pass
    # last resort: append closers (handles unterminated-string truncations)
    for n in range(1, 7):
        try:
            return json.loads(txt + ("}" * n))
        except json.JSONDecodeError:
            continue
    raise ValueError("invalid JSON from model")


def plan_car() -> dict:
    """Ask the model for a car; re-ask while it repeats one we already shot.

    There is **no random fallback**.  Only two outcomes:

    * the model returns a car that is not already in ``imgs/`` -> use it;
      if it returns a used car or nonsense, the model is asked again
      (up to 5 rounds) rather than quietly forcing a pick;
    * the API is unreachable / out of credit / returns nothing usable ->
      raise, so the run quits loudly instead of guessing.

    Before asking, we fetch fresh web snippets for the *available* cars so the
    model has current specs/pricing instead of relying on training memory.
    """
    pool = _dedupe_pool(FALLBACK_CARS)
    used = _used_keys()
    available = [c for c in pool if _car_key(c) not in used]
    if not available:
        raise RuntimeError(
            f"car pool exhausted: all {len(pool)} cars in FALLBACK_CARS already "
            f"exist under imgs/ - add new cars before the next run"
        )

    # Ground the model with live web context for each available car.
    snippets = []
    for c in available:
        label = " ".join(str(c.get(k) or "") for k in ("company", "name", "variant")).strip()
        year = str(c.get("year") or "").strip()
        q = f"{year} {label} specifications"
        hits = search_web(q, max_results=3)
        if hits:
            snippet = "; ".join(h.get("body", "")[:200] for h in hits if h.get("body"))
            if snippet:
                snippets.append(f"{label}: {snippet}")
    context = "\n".join(snippets) if snippets else ""

    prompt = (
        "Pick ONE number 1-%d for a moody night-street car aura photoshoot. "
        "Reply ONLY JSON, no prose: {\"i\": int}. Cars: %s\n\n"
        "Current web specs (for your reference):\n%s"
        % (len(available), _labels(available), context)
    )
    for round_no in range(1, 6):
        try:
            raw = _parse_json(_ask(prompt, max_tokens=300))
        except Exception as e:  # noqa: BLE001 - model/API is down: quit
            raise RuntimeError(
                f"openrouter unreachable after retries ({type(e).__name__}: "
                f"{e}); quitting instead of guessing a car"
            ) from e
        try:
            if not isinstance(raw, dict) or not isinstance(raw.get("i"), int):
                raise ValueError(f"model did not reply with an int: {raw!r}")
            i = raw["i"]
            if not 1 <= i <= len(available):
                raise ValueError(
                    f"index {i} out of range 1-{len(available)}")
            car = available[i - 1]
            # Belt and braces: available holds no used cars, but never trust it.
            if _car_key(car) in used:
                raise ValueError(
                    f"already shot: {car['company']} {car['name']}")
            return dict(car)
        except Exception as e:  # noqa: BLE001 - bad pick: ask the model again
            print(f"  car pick rejected (round {round_no}/5): {e}; "
                  f"re-asking the model")
    raise RuntimeError(
        "model failed to name an un-shot car in 5 rounds; quitting"
    )


def fun_fact(car: dict, tries: int = 5) -> str:
    """One surprising fact about ``car`` from the model, or ``''`` if it can't.

    Non-fatal by design: a missing fun fact must never abort a shoot that
    already has its images.

    We first search the web for a surprising fact, then ask the model to
    condense it into a single sentence.
    """
    label = " ".join(
        str(car.get(k) or "") for k in ("company", "name", "variant")
    ).strip()
    year = str(car.get("year") or "").strip()

    # Ground with a live web search for surprising/unique facts.
    q = f"{year} {label} interesting fact"
    hits = search_web(q, max_results=4)
    context = ""
    if hits:
        bodies = [h.get("body", "")[:300] for h in hits if h.get("body")]
        if bodies:
            context = "\n".join(bodies)

    prompt = (
        f'Write ONE surprising true fun fact about the {year} {label}. '
        f'Max 22 words. Reply ONLY JSON, no prose: {{"fact": "..."}}.'
    )
    if context:
        prompt = f"Web context:\n{context}\n\n{prompt}"
    try:
        # 900 is not padding: the routed free models burn several hundred
        # tokens reasoning before emitting, and below ~900 they return
        # content: null (the plan_car JSON prompt happens to fit in 300).
        # tries=5 because openrouter/free re-routes to a different model on
        # every request, so more attempts = more chances of a clean answer.
        txt = _ask(prompt, max_tokens=900, tries=tries)
    except Exception as e:  # noqa: BLE001 - decoration is optional
        print(f"  fun fact skipped ({type(e).__name__}: {e})")
        txt = ""
    txt = " ".join(txt.split()).strip().strip("\"'").strip()
    txt = re.sub(r"^(fun\s*fact\s*[:\-–—]\s*)", "", txt, flags=re.I).strip()
    if not txt:
        # The routed free models return content: null often enough that the
        # caption would be missing half the time. Fall back to the car's own
        # one-line description so img-1 always gets a bar.
        txt = str(car.get("description") or "").strip()
    if not txt:
        return ""
    if len(txt) > 220:
        txt = txt[:217].rsplit(" ", 1)[0] + "..."
    return txt
