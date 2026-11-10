#!/usr/bin/env bash
# cron-daily.sh - generate this scheduled shoot and push it to origin.
# Slot is UTC-referenced because the four-slot schedule is wallclock in UTC
# (00/06/12/18). A delayed or caught-up run still lands in the correct
# YYYY-MM-DD-HH folder.
set -u
REPO=$(cd "$(dirname "$0")" && pwd)
cd "$REPO"
LOG="${REPO}/cron-daily.log"
SLOT=$(date -u '+%Y-%m-%d-%H')
exec >>"$LOG" 2>&1
echo "===== $(date -u) start $SLOT ====="

# Sync with origin BEFORE shooting. This box and a laptop both push to master,
# so without this the local branch drifts and every later push gets rejected.
git fetch origin master >/dev/null 2>&1 || echo "warning: git fetch failed"
if ! git merge --ff-only origin/master >/dev/null 2>&1; then
    echo "fast-forward not possible; rebasing local history onto origin"
    if ! git pull --rebase origin master; then
        echo "warning: rebase onto origin failed; continuing with local history"
        git rebase --abort >/dev/null 2>&1 || true
    fi
fi

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
if ! git commit -m "Addimages for $SLOT"; then
    echo "commit failed"
    exit 1
fi

# Push and actually check the exit status (the old script ignored it, so a
# rejected push was reported as success and the branch silently drifted).
if git push origin master; then
    echo "push completed"
else
    echo "push rejected; rebasing onto origin and retrying once"
    if git pull --rebase origin master && git push origin master; then
        echo "push completed after rebase"
    else
        echo "push FAILED - images stay local and will ride along next slot"
        exit 1
    fi
fi
echo "$SLOT" > "$REPO/cron-daily.last"
echo "===== $(date -u) done $SLOT ====="
