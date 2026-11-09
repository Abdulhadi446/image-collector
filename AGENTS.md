# AGENTS.md

Python LangGraph car-photo collector + a "Vista Cars" Flask gallery.

## Fast commands
- Full shoot: `.venv/bin/python create.py --date YYYY-MM-DD --target 10` (writes `./imgs/<date>/img-*.jpg`, `car.md`, `car.gif`; refreshes `assets/demo.gif`).
- Skip when already downloaded: `.venv/bin/python create.py --date YYYY-MM-DD --skip-if-exists --quiet`.
- Gallery server: `.venv/bin/python app.py --port 5000`.
- Setup: `.venv/bin/pip install -r requirements.txt`, with `OLLAMA_API_KEY` in `.env`.
- Cron (from script docstring): `0 3 * * * cd /path/to/image-collector && .venv/bin/python create.py >> /var/log/car-aura.log 2>&1`

## Tests
- `test_score.py` and `test_graph.py` — run with `python test_score.py && python test_graph.py` (offline; test_graph monkey-patches `planner.plan_car`, `image_search.search_images`, `rater.rate`).
- `test_graph.py` confirms hero/side/fill/watermark/real/car.md/car.gif rules on a `imgs/test-day` fixture.
- New non-trivial logic left under one self-check per ponytail style. Python 3.14; no JS.
- Before `git push`, run the two tests.

## Build / project map
- Production entrypoint: `create.py` (paths resolve relative to file location, chdir to base; do not use cwd assumptions).
- `main.py` is a thin alias to the same workflow and still supported.
- Graph in `workflow.py`: `plan` → `harvest` → `route` (portrait-aware, target based) → `rate` → `save` -> generates `car.md` and `car.gif`, and returns `saved` paths.
- `planner.py`: selects one car from the 5-key `FALLBACK_CARS` pool **without** sodeom.com's unreliable proxy — uses Ollama model `beam` with a minimal `{"i": int}` JSON prompt; falls back to `random.choice` on empty/truncated/timeout (2 retries, 10s each).
- `image_search.py`: DuckDuckGo search, download (UA, 15s, 25MB cap), min 640x400, extreme-ratio reject, `WATERMARKED` blocklist (watermark + selected AI-site domains), `is_dup` per phash hamming distance ≤ 4. No darkness gate; `assess` returns `(phash, is_portrait≥1.25)`.
- `rater.py`: Gemma-4 via Ollama (768px JPEG q=80) scoring `aura/side/match/watermark/real`, batches = 6, 2 retries; fallback dicts use aura=0/False all keys.
- `app.py`: Flask Vista gallery — reads `./imgs/<date>` and `./assets/*.gif` except `demo.gif` for the motion page.

## Guardrails / gotchas
- Use the `OLLAMA_API_KEY` from `.env`; don't leak it in code or logs. `planner` falls back to random pool if key missing or Ollama fails; `rater` degrades aura=0 + real=False.
- `.gitignore` ignores only `imgs/test-day/` (offline fixture) plus job logs; shoot folders like `imgs/2026-11-08-20/` are tracked and pushed.
- `assets/demo.gif` is rebuilt per `create.py`; pass `--no-demo` if you want the hero unchanged.
- The `Read` tool may not show images in some model sessions — treat rater flags + PIL dimensional checks as truth, re-eyeball manually when needed.
- Some test data files may be partial — use `test_graph.py` to validate behavior offline.
- No human-in-the-loop anymore; user asked to remove it and accept \"let it go\" false positives.

## Architecture notes
- One "car per day": every found image candidate must respect `match=True` for heroes/sides; fills shortfall from match False remain with note.
- `image_search` filters at 8-thread pool; harvest stops when portraits ≥ target, max(total = max(target*8, target+30)) or queries exhausted.
- Workflow uses `MemorySaver`? No — no interrupt checkpointer; graph's `compile()` is a single-edge run.
- `recursion_limit` is 200 on both `.invoke()` sites.

## Where to change
- Form of `car.md`: write `_md_lines` skip empty values (so partial planner supplies degrade gracefully).
- Filters/sort priority order: watermark < match < side < aura.
- `is_dup` hamming cutoff maybe tweak > 4 for aggressive dedupe.
- `make_gif` dims 520x720 @ 900ms.

## References
- See `README.md` (mermaid pipeline, output tree, run-output sample, Gallery web app documentation).
- Commit authored as Abdulhadi446/image-collector on GitHub.