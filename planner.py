"""Plan one car per day from the 5-car fallback pool via OpenRouter.

The previous sodeom.com/ai proxy and the Ollama key both stopped working
(flat/no credits), so we now ask OpenRouter's ``openrouter/free`` model for
one index only.
"""
from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path

import requests

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


def _ask(prompt: str, max_tokens: int = 50) -> str:
    if not KEYS:
        raise RuntimeError("no OPENROUTER_API_KEY (or fallback) configured")
    last_err: Exception | None = None
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
                timeout=30,
            )
            r.raise_for_status()
            return str(r.json()["choices"][0]["message"]["content"]).strip()
        except Exception as e:  # noqa: BLE001 - try next key
            last_err = e
            print(f"  openrouter key failed ({type(e).__name__}: {e}); "
                  f"trying fallback ({len(KEYS) - KEYS.index(key) - 1} left)")
    raise last_err if last_err else RuntimeError("no usable OPENROUTER key")
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
    {
        "name": "R8 V10 Performance", "company": "Audi", "version": "4S", "variant": "Performance",
        "color": "black", "year": "2023", "engine": "5.2L naturally aspirated V10",
        "power": "602 hp", "drivetrain": "AWD, 7-speed S tronic",
        "description": "Mid-engine V10 supercar with a razor edge at night.",
        "queries": [
            "Audi R8 V10 black photoshoot", "R8 Performance night photography",
            "black Audi R8 side profile", "Audi R8 dark studio",
            "R8 V10 moody wallpaper", "Audi R8 black rear night",
            "Audi R8 street night", "R8 underground parking",
            "Audi R8 V10 vertical wallpaper", "R8 phone wallpaper portrait",
            "black Audi R8 9:16 wallpaper",
        ],
    },
    {
        "name": "Corvette C8 Stingray", "company": "Chevrolet", "version": "C8", "variant": "Stingray",
        "color": "black", "year": "2023", "engine": "6.2L naturally aspirated V8",
        "power": "490 hp", "drivetrain": "RWD, 8-speed DCT",
        "description": "Mid-engine American V8 with exotic proportions.",
        "queries": [
            "Corvette C8 black photoshoot", "C8 Stingray night photography",
            "black Corvette side profile", "Chevrolet Corvette dark studio",
            "Corvette C8 moody wallpaper", "Corvette black rear night",
            "Corvette C8 street night", "C8 underground parking",
            "Corvette C8 vertical wallpaper", "Corvette phone wallpaper portrait",
            "black C8 Corvette 9:16 wallpaper",
        ],
    },
    {
        "name": "AMG GT Black Series", "company": "Mercedes-AMG", "version": "C190", "variant": "Black Series",
        "color": "black", "year": "2021", "engine": "4.0L twin-turbo flat-plane V8",
        "power": "720 hp", "drivetrain": "RWD, 7-speed DCT",
        "description": "Long-bonnet aero monster built for the track.",
        "queries": [
            "Mercedes AMG GT Black Series black photoshoot", "AMG GT Black Series night photography",
            "black AMG GT side profile", "Mercedes AMG GT dark studio",
            "AMG GT Black Series moody wallpaper", "AMG GT black rear night",
            "Mercedes AMG GT street night", "AMG GT underground parking",
            "AMG GT Black Series vertical wallpaper", "AMG GT phone wallpaper portrait",
            "black AMG GT 9:16 wallpaper",
        ],
    },
    {
        "name": "RX-7 FD3S", "company": "Mazda", "version": "FD", "variant": "Type-R",
        "color": "black", "year": "1999", "engine": "1.3L twin-rotor 13B-REW",
        "power": "276 hp", "drivetrain": "RWD, 5-speed manual",
        "description": "Pop-up-headlight rotary icon of the JDM golden era.",
        "queries": [
            "Mazda RX-7 FD black photoshoot", "RX-7 FD night photography",
            "black RX-7 side profile", "Mazda RX-7 dark studio",
            "RX-7 FD moody wallpaper", "RX-7 black rear night",
            "Mazda RX-7 street night", "RX-7 underground parking",
            "RX-7 FD vertical wallpaper", "Mazda RX-7 phone wallpaper portrait",
            "black RX-7 FD 9:16 wallpaper",
        ],
    },
    {
        "name": "720S", "company": "McLaren", "version": "720S", "variant": "Coupe",
        "color": "black", "year": "2021", "engine": "4.0L twin-turbo V8",
        "power": "710 hp", "drivetrain": "RWD, 7-speed SSG",
        "description": "Dihedral-door British supercar with alien lighting.",
        "queries": [
            "McLaren 720S black photoshoot", "720S night photography",
            "black McLaren side profile", "McLaren 720S dark studio",
            "720S moody wallpaper", "McLaren black rear night",
            "McLaren 720S street night", "720S underground parking",
            "McLaren 720S vertical wallpaper", "720S phone wallpaper portrait",
            "black McLaren 720S 9:16 wallpaper",
        ],
    },
    {
        "name": "LFA", "company": "Lexus", "version": "LFA10", "variant": "Nurburgring",
        "color": "black", "year": "2012", "engine": "4.8L naturally aspirated V10",
        "power": "552 hp", "drivetrain": "RWD, 6-speed ASG",
        "description": "V10 that screams to 9,000 rpm; a modern collectible.",
        "queries": [
            "Lexus LFA black photoshoot", "Lexus LFA night photography",
            "black LFA side profile", "Lexus LFA dark studio",
            "LFA Nurburgring moody wallpaper", "Lexus LFA black rear night",
            "Lexus LFA street night", "LFA underground parking",
            "Lexus LFA vertical wallpaper", "LFA phone wallpaper portrait",
            "black Lexus LFA 9:16 wallpaper",
        ],
    },
    {
        "name": "Shelby GT500", "company": "Ford", "version": "S650", "variant": "Shelby",
        "color": "black", "year": "2022", "engine": "5.2L supercharged V8",
        "power": "760 hp", "drivetrain": "RWD, 7-speed dual-clutch",
        "description": "Supercharged muscle car with track aero.",
        "queries": [
            "Ford Shelby GT500 black photoshoot", "GT500 night photography",
            "black Mustang Shelby side profile", "Ford Mustang dark studio",
            "GT500 moody wallpaper", "Mustang black rear night",
            "Ford Mustang street night", "GT500 underground parking",
            "Shelby GT500 vertical wallpaper", "GT500 phone wallpaper portrait",
            "black Mustang GT500 9:16 wallpaper",
        ],
    },
    {
        "name": "Silvia S15 Spec-R", "company": "Nissan", "version": "S15", "variant": "Spec-R",
        "color": "black", "year": "2002", "engine": "2.0L turbo inline-four SR20DET",
        "power": "247 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "Drift-culture hero with a sharp notchback stance.",
        "queries": [
            "Nissan Silvia S15 black photoshoot", "S15 Silvia night photography",
            "black S15 side profile", "Nissan Silvia dark studio",
            "Silvia S15 moody wallpaper", "S15 black rear night",
            "Nissan Silvia street night", "S15 underground parking",
            "Silvia S15 vertical wallpaper", "S15 phone wallpaper portrait",
            "black Nissan Silvia 9:16 wallpaper",
        ],
    },
]


def _car_key(car: dict) -> tuple[str, str]:
    """Identity of a car for duplicate detection (company + name)."""
    return (str(car.get("company", "")).strip().lower(),
            str(car.get("name", "")).strip().lower())


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


def _used_keys() -> set[tuple[str, str]]:
    """Cars already shot, read from every ``imgs/<slot>/car.md`` on disk."""
    used: set[tuple[str, str]] = set()
    for md in sorted((Path(__file__).resolve().parent / "imgs").glob("*/car.md")):
        name = company = ""
        try:
            for line in md.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("company:"):
                    company = line.split(":", 1)[1].strip()
        except OSError:
            continue
        if name:
            used.add((company.lower(), name.lower()))
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
    raise ValueError("invalid JSON from sodeom")


def plan_car() -> dict:
    """Pick a car, never repeating one that already exists in ``imgs/``.

    The model is shown the whole pool.  If it returns an index for a car we
    have already shot (or an out-of-range/invalid index), we force a random
    car from the not-yet-shot remainder instead.
    """
    pool = _dedupe_pool(FALLBACK_CARS)
    used = _used_keys()
    available = [c for c in pool if _car_key(c) not in used] or pool

    prompt = (
        "Pick ONE number 1-%d for a moody night-street car aura photoshoot. "
        "Reply ONLY JSON, no prose: {\"i\": int}. Cars: %s"
        % (len(pool), _labels(pool))
    )
    try:
        raw = _parse_json(_ask(prompt, max_tokens=300))
        assert isinstance(raw, dict) and isinstance(raw.get("i"), int)
        i = raw.get("i")
        assert 1 <= i <= len(pool)
        car = pool[i - 1]
        if _car_key(car) in used:
            raise ValueError(f"already shot: {car['company']} {car['name']}")
    except Exception as e:
        car = random.choice(available)
        print(f"  car pick rejected ({e}); forcing a different car: "
              f"{car['company']} {car['name']}")
        return dict(car)
    return dict(car)
