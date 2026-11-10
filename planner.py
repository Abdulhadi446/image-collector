"""Plan one car per day from the 5-car fallback pool via Ollama beam.

The previous sodeom.com/ai proxy was too flaky (empty/truncated JSON) and is
no longer used.  We instead ask Ollama model ``beam`` for one index only.
"""
from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path

import requests

URL = "https://ollama.com/v1/chat/completions"
MODEL = "beam"

# Keys tried in order: primary first, then fallback.  Each is tried until one
# returns a usable response, so a revoked primary key does not kill the run.
KEY_ORDER = ("OLLAMA_API_KEY", "OLLAMA_API_KEY_FALLBACK")


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


def _ask(prompt: str, max_tokens: int = 50) -> str:
    if not KEYS:
        raise RuntimeError("no OLLAMA_API_KEY (or fallback) configured")
    last_err: Exception | None = None
    for key in KEYS:
        try:
            r = requests.post(
                URL,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json={"model": MODEL,
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.9, "max_tokens": max_tokens},
                timeout=30,
            )
            r.raise_for_status()
            return str(r.json()["choices"][0]["message"]["content"]).strip()
        except Exception as e:  # noqa: BLE001 - try next key
            last_err = e
            print(f"  ollama key failed ({type(e).__name__}: {e}); "
                  f"trying fallback ({len(KEYS) - KEYS.index(key) - 1} left)")
    raise last_err if last_err else RuntimeError("no usable OLLAMA key")
FALLBACK_CARS = [
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
        "name": "GT-R Nismo", "company": "Nissan", "version": "R35", "variant": "Nismo",
        "color": "black", "year": "2024", "engine": "3.8L twin-turbo V6",
        "power": "600 hp", "drivetrain": "AWD, 6-speed DCT",
        "description": "Godzilla in Nismo trim — the ultimate street fighter.",
        "queries": [
            "Nissan GT-R Nismo black photoshoot", "GT-R R35 night photography",
            "black GT-R Nismo side profile", "R35 GT-R dark studio",
            "GT-R Nismo moody wallpaper", "GT-R black rear night",
            "GT-R R35 street night", "GT-R Nismo underground parking",
            "GT-R Nismo vertical wallpaper", "R35 GT-R phone wallpaper portrait",
            "black GT-R Nismo 9:16 wallpaper",
        ],
    },
    {
        "name": "M4 Competition", "company": "BMW", "version": "G82", "variant": "Competition",
        "color": "black", "year": "2023", "engine": "3.0L twin-turbo inline-six",
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
        "name": "Huracán EVO", "company": "Lamborghini", "version": "LB724", "variant": "EVO",
        "color": "black", "year": "2022", "engine": "5.2L naturally aspirated V10",
        "power": "631 hp", "drivetrain": "AWD, 7-speed LDF",
        "description": "Raw V10 Lamborghini with fighter-jet cockpit.",
        "queries": [
            "Lamborghini Huracan EVO black photoshoot", "Huracan EVO night photography",
            "black Huracan side profile", "Lamborghini Huracan dark studio",
            "Huracan EVO moody wallpaper", "Huracan black rear night",
            "Lamborghini Huracan street night", "Huracan underground parking",
            "Huracan EVO vertical wallpaper", "Lamborghini phone wallpaper portrait",
            "black Huracan 9:16 wallpaper",
        ],
    },
    {
        "name": "Supra GR", "company": "Toyota", "version": "A90", "variant": "GR",
        "color": "black", "year": "2023", "engine": "3.0L turbo inline-six",
        "power": "382 hp", "drivetrain": "RWD, 8-speed automatic",
        "description": "Long-hood sports coupe, legendary 2JZ lineage.",
        "queries": [
            "Toyota Supra A90 black photoshoot", "GR Supra night photography",
            "black Supra side profile", "Toyota Supra dark studio",
            "Supra GR moody wallpaper", "Supra black rear night",
            "Toyota Supra street night", "Supra underground parking",
            "GR Supra vertical wallpaper", "Toyota Supra phone wallpaper portrait",
            "black A90 Supra 9:16 wallpaper",
        ],
    },
]

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
    raise ValueError("invalid JSON from sodeom")


_CATALOG_LABELS = (
    "1=Porsche 911 GT3 RS  2=Nissan GT-R Nismo  3=BMW M4 Competition  "
    "4=Lamborghini Huracan EVO  5=Toyota Supra GR"
)


def plan_car() -> dict:
    """Ask Ollama beam for ONE car index 1-5; queries come from our pool."""
    prompt = (
        "Pick ONE number 1-5 for a moody night-street car aura photoshoot. "
        "Reply ONLY JSON, no prose: {\"i\": int}. Cars: "
        + _CATALOG_LABELS
    )
    try:
        raw = _parse_json(_ask(prompt, max_tokens=50))
        assert isinstance(raw, dict) and isinstance(raw.get("i"), int)
        i = raw.get("i")
        assert 1 <= i <= len(FALLBACK_CARS)
        return dict(FALLBACK_CARS[i - 1])
    except Exception as e:
        car = random.choice(FALLBACK_CARS)
        print(f"  ollama /ai car planning failed ({e}); using fallback: "
              f"{car['company']} {car['name']}")
        return dict(car)
