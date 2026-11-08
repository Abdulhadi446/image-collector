#!/usr/bin/env bash
# cron-daily.sh - generate today's car photos and push them to origin.
set -u
REPO=$(cd "$(dirname "$0")" && pwd)
cd "$REPO"
LOG="${REPO}/cron-daily.log"
DATE=$(date '+%Y-%m-%d')
CACHE="$REPO/cron-daily.last"
exec >>"$LOG" 2>&1
echo "===== $(date) start $DATE ====="

# Run the whole image collector
if ! "$REPO/.venv/bin/python" "$REPO/create.py" --date "$DATE" --target 10; then
    echo "collect failed; aborting before push"
    exit 1
fi

# Stage everything, including the freshly generated (git-ignored-by-default)
# image folders via a force-add, then verify there is something to push.
git add -A
git add -f "imgs/$DATE" "assets/demo.gif" >/dev/null 2>&1 || true
if git diff --cached --quiet; then
    echo "no new images to commit; skipping push"
    echo "$DATE" > "$CACHE"
    exit 0
fi
if git commit -m "Addimages for $DATE"; then
    git push origin master
    echo "push completed"
else
    echo "commit failed"
    exit 1
fi
echo "$DATE" > "$CACHE"
echo "===== $(date) done $DATE ====="
