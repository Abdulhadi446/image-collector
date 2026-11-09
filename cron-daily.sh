#!/usr/bin/env bash
# cron-daily.sh - generate today's car photos and push them to origin.
set -u
REPO=$(cd "$(dirname "$0")" && pwd)
cd "$REPO"
LOG="${REPO}/cron-daily.log"
DATE=$(date '+%Y-%m-%d-%H')
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

# Ship the new shoot + hero GIF to the live gallery host. When this script
# runs ON tests2 (the server serving vistacars.thetrillioniar.me) there is
# nothing to sync - the gallery reads ./imgs right here.
if [ "$REPO" != "/home/ubuntu/image-collector" ]; then
    if command -v rsync >/dev/null 2>&1 && ssh -o BatchMode=yes -o ConnectTimeout=8 tests2 true >/dev/null 2>&1; then
        rsync -a "$REPO/imgs/$DATE" tests2:/home/ubuntu/image-collector/imgs/ && \
        rsync -a "$REPO/assets/demo.gif" tests2:/home/ubuntu/image-collector/assets/ && \
        echo "synced $DATE + demo.gif to tests2" || echo "WARN: tests2 sync failed"
    else
        echo "WARN: tests2 unreachable; images only on local + github"
    fi
else
    echo "running on gallery host; no remote sync needed"
fi
echo "===== $(date) done $DATE ====="
