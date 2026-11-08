#!/usr/bin/env python3
"""create.py — single entrypoint for the whole car aura pipeline.

Runs the LangGraph workflow (plan -> harvest -> rate -> save) for one date and
writes `./imgs/{date}/img-{n}.png`, `car.md` and `car.gif`, prints a short
summary, and exits 0 only if the full target count was saved.

Usage:
    .venv/bin/python create.py                      # today, 10 images
    .venv/bin/python create.py --date 2026-11-07
    .venv/bin/python create.py --target 8 --skip-if-exists
    .venv/bin/python create.py --date 2026-11-07 --quiet

For cron, point at this file (paths resolve regardless of the working dir):
    0 3 * * * cd /home/abdulhadi/learnings/image-collector && .venv/bin/python create.py >> /var/log/car-aura.log 2>&1
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def _date(s: str) -> str:
    dt.date.fromisoformat(s)
    return s


def main() -> int:
    ap = argparse.ArgumentParser(prog="create.py")
    ap.add_argument("--date", type=_date, default=dt.date.today().isoformat(),
                    metavar="YYYY-MM-DD", help="shoot date (default: today)")
    ap.add_argument("--target", type=int, default=10,
                    help="number of images to save (default: 10)")
    ap.add_argument("--quiet", action="store_true", help="print only the final line")
    ap.add_argument("--skip-if-exists", action="store_true",
                    help="do nothing if img-1.png already exists for that date")
    ap.add_argument("--no-checks", action="store_true",
                    help="exit 0 even if fewer than TARGET images were saved")
    ap.add_argument("--no-demo", action="store_true",
                    help="skip refreshing assets/demo.gif from this shoot")
    args = ap.parse_args()

    if args.target < 1:
        print("[error] --target must be >= 1", file=sys.stderr)
        return 2

    date = args.date
    out = BASE / "imgs" / date

    if args.skip_if_exists and (out / "img-1.png").exists():
        if not args.quiet:
            print(f"[skip] {out} already has images")
        return 0

    if not (BASE / ".env").exists():
        print(f"[warn] {BASE/'.env'} missing - running with no OLLAMA key "
              "(ratings/planning will degrade; expect fallback car)", file=sys.stderr)

    os.chdir(BASE)

    try:
        import workflow
    except Exception as e:
        print(f"[error] cannot import workflow: {e}", file=sys.stderr)
        return 2

    initial = {
        "date": date, "target": args.target, "car": {}, "i": 0, "query": "",
        "found": [], "seen": [], "rated": [], "saved": [],
    }

    if not args.quiet:
        print(f"[start] {date} target={args.target} -> {out}")
    start = time.monotonic()
    try:
        result = workflow.build_graph().invoke(
            initial, {"recursion_limit": 200})
    except KeyboardInterrupt:
        elapsed = time.monotonic() - start
        print(f"\n[abort] interrupted after {elapsed:.1f}s", file=sys.stderr)
        return 130
    except Exception as e:
        elapsed = time.monotonic() - start
        print(f"[error] workflow failed after {elapsed:.1f}s: {e}", file=sys.stderr)
        return 1

    elapsed = time.monotonic() - start
    saved = result.get("saved") or []
    n = len(saved)
    print(f"[done] date={date} saved={n}/{args.target} in {elapsed:.1f}s -> {out}")

    # regenerate the repo's hero demo.gif from this shoot so the README's
    # top-of-page GIF always tracks the latest output (2026-11-07, 2026-11-08, ...)
    if (not args.no_demo) and saved:
        try:
            demo_paths = sorted(saved,
                                 key=lambda p: int(Path(p).stem.split("-")[1]))
            demo_out = BASE / "assets" / "demo.gif"
            gif_n = workflow.make_gif(demo_paths, str(demo_out), 520, 720, 900)
            if gif_n:
                print(f"[done] refreshed {demo_out.relative_to(BASE)} "
                      f"({gif_n} frames) from this shoot")
        except Exception as e:  # noqa: BLE001 - gif refresh is nice-to-have
            print(f"[warn] could not refresh demo.gif: {e}", file=sys.stderr)

    if not args.no_checks and n < args.target:
        print(f"[fail] only {n} images reached the target of {args.target}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
