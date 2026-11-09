#!/usr/bin/env bash
# cron-daily.sh - generate this scheduled shoot and push it to origin.
# Slot is UTC-referenced because the meridian/four-slot schedule is wallclock
# in UTC (00/06/12/18). A delayed or caught-up run still lands in the
# correct YYYY-MM-DD-HH folder.
set -u
REPO=$(cd "$(dirname "$0")" && pwd)
cd "$REPO"
LOG="${REPO}/cron-daily.log"
SLOT=$(date -u '+%Y-%m-%d-%H')
exec >>"$LOG" 2>&1
echo "===== $(date -u) start $SLOT ====="

if ! "$REPO/.venv/bin/python" "$REPO/create.py" --date "$SLOT" --target 10 --skip-if-exists; then
    echo "collect failed; aborting before push"
    exit 1
fi

# Only push if there is something new. On a completed/re-run slot this is a
# graceful no-op.
git add -A
git add -f "imgs/$SLOT" "assets/demo.gif" >/dev/null 2>&1 || true
if git diff --cached --quiet; then
    echo "no new images to commit; skipping push"
    echo "$SLOT" >> "$REPO/cron-daily.last"
    echo "===== $(date -u) done $SLOT (nothing new) ====="
    exit 0
fi
if git commit -m "Addimages for $SLOT"; then
    git push origin master
    echo "push completed"
else
    echo "commit failed"
    exit 1
fi
echo "$SLOT" > "$REPO/cron-daily.last"
echo "===== $(date -u) done $SLOT ====="
