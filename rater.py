"""Neutral rating fallback — no external AI image classification.

Historically this module called Ollama Gemma-4 or Jev/DefAPI to score
candidate images (`aura`, `side`, `match`, `watermark`, `real`).  That
classification has been removed entirely per the user's request, so this
module no longer makes any network call.  Every candidate is treated as
usable; only local harvest metadata (portrait orientation) is retained.
"""
from __future__ import annotations


def rate(car: dict, images: list[bytes], batch: int = 6) -> list[dict]:
    """Neutral ratings for ``images`` — no external classification."""
    return [{"aura": 0, "side": False, "match": True,
             "watermark": False, "real": True}
            for _ in images]
