"""Car planner using Ollama cloud model "beam" (text-only planner, no vision)."""
from __future__ import annotations

import json
import os
import random
from typing import Any

import requests

OLLAMA_URL = "https://ollama.com/v1/chat/completions"
MODEL = "beam"


def _load_key() -> str:
    key = os.environ.get("OLLAMA_API_KEY", "").strip()
    if key:
        return key
    here = os.path.dirname(os.path.abspath(__file__))
    for name in (".env", os.path.join(here, ".env")):
        path = name if os.path.isabs(name) else os.path.join(here, name)
        try:
            for line in open(path):
                line = line.strip()
                if line.startswith("OLLAMA_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val
        except FileNotFoundError:
            continue
    print("WARNING: OLLAMA_API_KEY not found in env or .env; planner will not work")
    return ""


KEY = _load_key()

# Fallback cars used if beam fails or returns unusable JSON.
FALLBACK_CARS: list[dict[str, Any]] = [
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


def _ask(prompt: str, max_tokens: int = 1500) -> str:
    if not KEY:
        raise RuntimeError("no OLLAMA_API_KEY")
    r = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
        "max_tokens": max_tokens,
    }, headers={"Authorization": f"Bearer {KEY}"}, timeout=90)
    r.raise_for_status()
    data = r.json()
    return str(data["choices"][0]["message"].get("content", "")).strip()


def _parse_json(txt: str) -> dict:
    if txt.startswith("```"):
        txt = txt.split("\n", 1)[1].rsplit("```", 1)[0]
    txt = txt.strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        pass
    # balance braces
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
    # last resort for unterminated strings: append closers
    for n in range(1, 7):
        try:
            return json.loads(txt + ("}" * n))
        except json.JSONDecodeError:
            continue
    raise ValueError("invalid JSON from beam")


def plan_car() -> dict:
    """Pick ONE real car + its shoot queries using Ollama model 'beam'."""
    prompt = (
        "Pick ONE real iconic sports/supercar (any brand — vary the choice "
        "between calls) for a moody night-street aura photoshoot. Reply ONLY with "
        "compact single-line JSON, no markdown fences, no prose before/after it. "
        "Object keys: name (str), company (str), version (str), variant (str), "
        "color (str), year (str), engine (str), power (str), drivetrain (str), "
        "description (str), queries (array of 4 short web image-search queries "
        "naming that EXACT car, at least 2 must ask for portrait/vertical "
        "framing like 'X phone wallpaper 9:16')."
    )
    try:
        car = _parse_json(_ask(prompt, max_tokens=1500))
        assert isinstance(car, dict) and car.get("name") and car.get("company")
        qs = car.get("queries")
        assert isinstance(qs, list) and len(qs) >= 3
        return car
    except Exception as e:
        car = random.choice(FALLBACK_CARS)
        print(f"  beam planner failed ({e}); using fallback: "
              f"{car['company']} {car['name']}")
        return dict(car)