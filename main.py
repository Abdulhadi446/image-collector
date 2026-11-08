"""Collect one car's shoot into ./imgs/{date}/img-{n}.png + car.md."""
import argparse
import datetime

from workflow import build_graph


def main() -> None:
    p = argparse.ArgumentParser(description="Aura car photoshoot collector (LangGraph + Gemini)")
    p.add_argument("--date", default=datetime.date.today().isoformat(),
                   help="output folder, YYYY-MM-DD (default: today)")
    p.add_argument("--target", type=int, default=10, help="images to keep (default: 10)")
    a = p.parse_args()

    print(f"Collecting {a.target} images of one car into ./imgs/{a.date}/ ...")
    final = build_graph().invoke(
        {"date": a.date, "target": a.target, "car": {}, "i": 0, "query": "",
         "found": [], "seen": [], "rated": [], "saved": []},
        {"recursion_limit": 200})
    n = len(final["saved"])
    suffix = "" if n >= a.target else "  (fewer than requested)"
    print(f"\nDone: {n}/{a.target} images in ./imgs/{a.date}/{suffix}")


if __name__ == "__main__":
    main()
