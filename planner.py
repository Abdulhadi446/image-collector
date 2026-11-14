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
import time
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
    {
        "name": "Skyline GT-R R34", "company": "Nissan", "version": "BNR34", "variant": "V-Spec II",
        "color": "black", "year": "2002", "engine": "2.6L twin-turbo inline-six RB26DETT",
        "power": "280 hp", "drivetrain": "AWD, 6-speed manual",
        "description": "Godzilla's most iconic generation, gran turismo royalty.",
        "queries": [
            "Nissan Skyline GT-R R34 black photoshoot", "R34 GT-R night photography",
            "black R34 side profile", "BNR34 GT-R dark studio",
            "R34 GT-R moody wallpaper", "GT-R R34 black rear night",
            "Nissan Skyline R34 street night", "R34 underground parking",
            "Skyline GT-R R34 vertical wallpaper", "R34 phone wallpaper portrait",
            "black Nissan Skyline R34 9:16 wallpaper",
        ],
    },
    {
        "name": "NSX", "company": "Honda", "version": "NA2", "variant": "Type S",
        "color": "black", "year": "2002", "engine": "3.2L V6 C32B",
        "power": "290 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "Mid-engine Honda that redefined the supercar playbook.",
        "queries": [
            "Honda NSX black photoshoot", "Acura NSX night photography",
            "black NSX side profile", "Honda NSX dark studio",
            "NSX moody wallpaper", "NSX black rear night",
            "Honda NSX street night", "NSX underground parking",
            "NSX vertical wallpaper", "NSX phone wallpaper portrait",
            "black Honda NSX 9:16 wallpaper",
        ],
    },
    {
        "name": "WRX STI", "company": "Subaru", "version": "VA", "variant": "STI",
        "color": "black", "year": "2019", "engine": "2.5L turbo flat-four EJ257",
        "power": "310 hp", "drivetrain": "AWD, 6-speed manual",
        "description": "Rally-bred sedan with a hood scoop and a wing.",
        "queries": [
            "Subaru WRX STI black photoshoot", "WRX STI night photography",
            "black WRX side profile", "Subaru WRX dark studio",
            "WRX STI moody wallpaper", "WRX black rear night",
            "Subaru WRX street night", "WRX underground parking",
            "WRX STI vertical wallpaper", "WRX phone wallpaper portrait",
            "black Subaru WRX 9:16 wallpaper",
        ],
    },
    {
        "name": "Lancer Evo IX", "company": "Mitsubishi", "version": "CT9A", "variant": "MR",
        "color": "black", "year": "2006", "engine": "2.0L turbo inline-four 4G63",
        "power": "286 hp", "drivetrain": "AWD, 5-speed manual",
        "description": "Final evolution of the 4G63 rally weapon.",
        "queries": [
            "Mitsubishi Lancer Evo IX black photoshoot", "Lancer Evo night photography",
            "black Evo IX side profile", "Mitsubishi Lancer dark studio",
            "Lancer Evo IX moody wallpaper", "Evo black rear night",
            "Mitsubishi Evo street night", "Lancer underground parking",
            "Lancer Evo IX vertical wallpaper", "Evo phone wallpaper portrait",
            "black Mitsubishi Lancer 9:16 wallpaper",
        ],
    },
    {
        "name": "911 Turbo S", "company": "Porsche", "version": "992", "variant": "Turbo S",
        "color": "black", "year": "2024", "engine": "3.8L twin-turbo flat-six",
        "power": "640 hp", "drivetrain": "AWD, 8-speed PDK",
        "description": "All-weather missile that defies physics out of corners.",
        "queries": [
            "Porsche 911 Turbo S black photoshoot", "992 Turbo S night photography",
            "black 911 Turbo side profile", "Porsche 911 dark studio",
            "911 Turbo S moody wallpaper", "Turbo S black rear night",
            "Porsche 911 street night", "911 Turbo underground parking",
            "911 Turbo S vertical wallpaper", "911 phone wallpaper portrait",
            "black Porsche 911 Turbo 9:16 wallpaper",
        ],
    },
    {
        "name": "488 Pista", "company": "Ferrari", "version": "F142M", "variant": "Pista",
        "color": "black", "year": "2019", "engine": "3.9L twin-turbo V8",
        "power": "710 hp", "drivetrain": "RWD, 7-speed DCT",
        "description": "Track-focused Ferrari with razor aero and no compromise.",
        "queries": [
            "Ferrari 488 Pista black photoshoot", "488 Pista night photography",
            "black Ferrari 488 side profile", "Ferrari 488 dark studio",
            "488 Pista moody wallpaper", "Ferrari black rear night",
            "Ferrari 488 street night", "488 underground parking",
            "488 Pista vertical wallpaper", "Ferrari phone wallpaper portrait",
            "black Ferrari 488 9:16 wallpaper",
        ],
    },
    {
        "name": "Vantage", "company": "Aston Martin", "version": "V8", "variant": "AMR",
        "color": "black", "year": "2022", "engine": "4.0L twin-turbo V8",
        "power": "503 hp", "drivetrain": "RWD, 8-speed automatic",
        "description": "British grand tourer with a predator's stance.",
        "queries": [
            "Aston Martin Vantage black photoshoot", "Vantage night photography",
            "black Aston Martin side profile", "Aston Martin dark studio",
            "Vantage moody wallpaper", "Vantage black rear night",
            "Aston Martin street night", "Vantage underground parking",
            "Aston Martin Vantage vertical wallpaper", "Vantage phone wallpaper portrait",
            "black Aston Martin 9:16 wallpaper",
        ],
    },
    {
        "name": "RS 6 Avant", "company": "Audi", "version": "C8", "variant": "Performance",
        "color": "black", "year": "2023", "engine": "4.0L twin-turbo V8",
        "power": "621 hp", "drivetrain": "AWD, 8-speed automatic",
        "description": "Supercar speed hidden in a family wagon body.",
        "queries": [
            "Audi RS6 Avant black photoshoot", "RS6 night photography",
            "black Audi RS6 side profile", "Audi RS6 dark studio",
            "RS6 Avant moody wallpaper", "RS6 black rear night",
            "Audi RS6 street night", "RS6 underground parking",
            "RS6 Avant vertical wallpaper", "Audi RS6 phone wallpaper portrait",
            "black Audi RS6 9:16 wallpaper",
        ],
    },
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
        "name": "Camaro ZL1", "company": "Chevrolet", "version": "6th gen", "variant": "ZL1",
        "color": "black", "year": "2022", "engine": "6.2L supercharged V8 LT4",
        "power": "650 hp", "drivetrain": "RWD, 10-speed automatic",
        "description": "Muscle car with track-bred aero and brutal grip.",
        "queries": [
            "Chevrolet Camaro ZL1 black photoshoot", "Camaro ZL1 night photography",
            "black Camaro side profile", "Chevrolet Camaro dark studio",
            "Camaro ZL1 moody wallpaper", "Camaro black rear night",
            "Chevrolet Camaro street night", "Camaro underground parking",
            "Camaro ZL1 vertical wallpaper", "Camaro phone wallpaper portrait",
            "black Chevrolet Camaro 9:16 wallpaper",
        ],
    },
    {
        "name": "Challenger SRT Hellcat", "company": "Dodge", "version": "LD", "variant": "Hellcat",
        "color": "black", "year": "2023", "engine": "6.2L supercharged V8 HEMI",
        "power": "717 hp", "drivetrain": "RWD, 8-speed automatic",
        "description": "Heavyweight brute with a supercharger whine.",
        "queries": [
            "Dodge Challenger Hellcat black photoshoot", "Challenger Hellcat night photography",
            "black Challenger side profile", "Dodge Challenger dark studio",
            "Challenger Hellcat moody wallpaper", "Hellcat black rear night",
            "Dodge Challenger street night", "Challenger underground parking",
            "Challenger Hellcat vertical wallpaper", "Challenger phone wallpaper portrait",
            "black Dodge Challenger 9:16 wallpaper",
        ],
    },
    {
        "name": "F-Type SVR", "company": "Jaguar", "version": "X152", "variant": "SVR",
        "color": "black", "year": "2017", "engine": "5.0L supercharged V8",
        "power": "575 hp", "drivetrain": "AWD, 8-speed automatic",
        "description": "Last of the big supercharged Jaguar cats.",
        "queries": [
            "Jaguar F-Type SVR black photoshoot", "F-Type night photography",
            "black Jaguar F-Type side profile", "Jaguar F-Type dark studio",
            "F-Type SVR moody wallpaper", "F-Type black rear night",
            "Jaguar F-Type street night", "F-Type underground parking",
            "F-Type SVR vertical wallpaper", "F-Type phone wallpaper portrait",
            "black Jaguar F-Type 9:16 wallpaper",
        ],
    },
    {
        "name": "MX-5 Miata", "company": "Mazda", "version": "ND", "variant": "RF",
        "color": "black", "year": "2023", "engine": "2.0L Skyactiv-G inline-four",
        "power": "181 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "Lightweight targa roadster built for pure feel.",
        "queries": [
            "Mazda MX-5 Miata black photoshoot", "Miata ND night photography",
            "black Miata side profile", "Mazda MX-5 dark studio",
            "MX-5 Miata moody wallpaper", "Miata black rear night",
            "Mazda Miata street night", "Miata underground parking",
            "MX-5 Miata vertical wallpaper", "Miata phone wallpaper portrait",
            "black Mazda Miata 9:16 wallpaper",
        ],
    },
    {
        "name": "Mustang GT", "company": "Ford", "version": "S650", "variant": "GT",
        "color": "black", "year": "2024", "engine": "5.0L Coyote V8",
        "power": "480 hp", "drivetrain": "RWD, 10-speed automatic",
        "description": "The original pony car, still naturally aspirated.",
        "queries": [
            "Ford Mustang GT black photoshoot", "Mustang GT night photography",
            "black Mustang side profile", "Ford Mustang dark studio",
            "Mustang GT moody wallpaper", "Mustang black rear night",
            "Ford Mustang street night", "Mustang underground parking",
            "Mustang GT vertical wallpaper", "Mustang phone wallpaper portrait",
            "black Ford Mustang 9:16 wallpaper",
        ],
    },
    {
        "name": "370Z", "company": "Nissan", "version": "Z34", "variant": "Nismo",
        "color": "black", "year": "2020", "engine": "3.7L V6 VQ37VHR",
        "power": "350 hp", "drivetrain": "RWD, 7-speed automatic",
        "description": "Long-bonnet Z-car with a wide, planted stance.",
        "queries": [
            "Nissan 370Z black photoshoot", "370Z Nismo night photography",
            "black 370Z side profile", "Nissan 370Z dark studio",
            "370Z moody wallpaper", "370Z black rear night",
            "Nissan 370Z street night", "370Z underground parking",
            "370Z vertical wallpaper", "370Z phone wallpaper portrait",
            "black Nissan 370Z 9:16 wallpaper",
        ],
    },
    {
        "name": "BRZ", "company": "Subaru", "version": "ZD8", "variant": "tS",
        "color": "black", "year": "2023", "engine": "2.4L flat-four FA24",
        "power": "228 hp", "drivetrain": "RWD, 6-speed manual",
        "description": "Low, light rear-drive coupe with perfect balance.",
        "queries": [
            "Subaru BRZ black photoshoot", "BRZ night photography",
            "black BRZ side profile", "Subaru BRZ dark studio",
            "BRZ moody wallpaper", "BRZ black rear night",
            "Subaru BRZ street night", "BRZ underground parking",
            "BRZ vertical wallpaper", "BRZ phone wallpaper portrait",
            "black Subaru BRZ 9:16 wallpaper",
        ],
    },
    {
        "name": "GR Yaris", "company": "Toyota", "version": "GXPA16", "variant": "Circuit",
        "color": "black", "year": "2023", "engine": "1.6L turbo inline-three G16E-GTS",
        "power": "257 hp", "drivetrain": "AWD, 6-speed manual",
        "description": "Homologation special built for rally stages.",
        "queries": [
            "Toyota GR Yaris black photoshoot", "GR Yaris night photography",
            "black GR Yaris side profile", "Toyota GR Yaris dark studio",
            "GR Yaris moody wallpaper", "GR Yaris black rear night",
            "Toyota Yaris street night", "GR Yaris underground parking",
            "GR Yaris vertical wallpaper", "GR Yaris phone wallpaper portrait",
            "black Toyota GR Yaris 9:16 wallpaper",
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
                line = line.strip()
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
    raise ValueError("invalid JSON from model")


def plan_car() -> dict:
    """Pick a car, never repeating one that already exists in ``imgs/``.

    Hard guarantee: the model is only ever shown the *not-yet-shot* cars, and
    both the model path and the forced-random path draw from that same
    ``available`` list.  ``available`` is checked non-empty up front, so there
    is no code path that can return an already-shot car.  If the pool runs dry
    we raise instead of silently re-shooting.
    """
    pool = _dedupe_pool(FALLBACK_CARS)
    used = _used_keys()
    available = [c for c in pool if _car_key(c) not in used]
    if not available:
        raise RuntimeError(
            f"car pool exhausted: all {len(pool)} cars in FALLBACK_CARS already "
            f"exist under imgs/ - add new cars before the next run"
        )

    prompt = (
        "Pick ONE number 1-%d for a moody night-street car aura photoshoot. "
        "Reply ONLY JSON, no prose: {\"i\": int}. Cars: %s"
        % (len(available), _labels(available))
    )
    try:
        raw = _parse_json(_ask(prompt, max_tokens=300))
        assert isinstance(raw, dict) and isinstance(raw.get("i"), int)
        i = raw.get("i")
        assert 1 <= i <= len(available)
        car = available[i - 1]
        # Belt and braces: available holds no used cars, but never trust it.
        if _car_key(car) in used:
            raise ValueError(f"already shot: {car['company']} {car['name']}")
    except Exception as e:
        car = random.choice(available)
        print(f"  car pick rejected ({e}); forcing a different car: "
              f"{car['company']} {car['name']}")
        return dict(car)
    return dict(car)
