#!/usr/bin/env bash
# CollectAI EC2 deploy — rsync server/ → /opt/collectors/server/ + restart bake.
#
# WHY THIS EXISTS (incident, 2026-05-02):
#   The bake's systemd unit has `WorkingDirectory=/opt/collectors/server`,
#   so Python imports `app.*` resolve to `/opt/collectors/server/app/*`.
#   A full day of "successful" deploys went to `/opt/collectors/` (one
#   level too high). Preflight gates passed, postflight smoke passed,
#   bake restarted cleanly — but the BAKE WAS RUNNING OLD CODE because
#   it was importing from the canonical path while the new files sat in
#   a parallel `/opt/collectors/app/` tree it never looked at. Surfaced
#   only by a live E2E that exercised a freshly-added paywall gate and
#   got HTTP 200 instead of 403. See docs/DEPLOYMENT.md for the full
#   incident write-up.
#
#   tl;dr: source = local `server/`, dest = EC2 `/opt/collectors/server/`.
#   NEVER deploy to `/opt/collectors/` directly.
#
# USAGE
#   scripts/deploy_to_ec2.sh                # diff vs HEAD~1, rsync, no restart
#   scripts/deploy_to_ec2.sh --restart      # rsync + restart bake
#   scripts/deploy_to_ec2.sh --files paths.txt --restart
#       (paths.txt = newline-separated paths relative to `server/`,
#        e.g. `app/agents/foo.py`.)
#
# SAFETY
#   - Dry-run preview before every push, requires interactive confirm.
#   - --restart waits for `systemctl is-active` and dumps the first
#     30 seconds of journalctl warnings so a broken deploy is caught
#     before this script returns.
#   - Refuses to run if the local working tree has uncommitted changes
#     under server/ UNLESS --dirty is passed.
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
SERVER_DIR="$REPO_ROOT/server"
EC2_HOST="collectai"
EC2_DEST="/opt/collectors/server/"

# Parse args
RESTART=0
DIRTY=0
FILES_LIST=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --restart) RESTART=1; shift ;;
    --dirty)   DIRTY=1; shift ;;
    --files)   FILES_LIST="$2"; shift 2 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
done

if [[ ! -d "$SERVER_DIR" ]]; then
  echo "FATAL: $SERVER_DIR not found — run from repo root or symlink correctly" >&2
  exit 2
fi

if [[ $DIRTY -eq 0 ]]; then
  if git -C "$REPO_ROOT" status --porcelain server/ | grep -q .; then
    echo "FATAL: uncommitted changes under server/ — pass --dirty to override" >&2
    git -C "$REPO_ROOT" status --short server/ | head -10 >&2
    exit 2
  fi
fi

TMP_LIST=$(mktemp)
trap "rm -f $TMP_LIST" EXIT
if [[ -n "$FILES_LIST" ]]; then
  cp "$FILES_LIST" "$TMP_LIST"
else
  git -C "$REPO_ROOT" diff --name-only HEAD~1 HEAD -- server/ \
    | sed 's|^server/||' \
    | grep -v '^$' > "$TMP_LIST" || true
  if [[ ! -s "$TMP_LIST" ]]; then
    echo "no files to deploy (no server/* changes since HEAD~1)" >&2
    exit 0
  fi
fi

echo "Deploying $(wc -l < "$TMP_LIST") files to $EC2_HOST:$EC2_DEST"
echo "Files:"; sed 's/^/  /' "$TMP_LIST"; echo

echo "== DRY-RUN PREVIEW =="
rsync -nav --files-from="$TMP_LIST" "$SERVER_DIR/" "$EC2_HOST:$EC2_DEST" \
  | grep -v '^sending\|^sent\|^total ' | tail -30

read -r -p "Proceed with rsync? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "aborted"; exit 0
fi
rsync -av --files-from="$TMP_LIST" "$SERVER_DIR/" "$EC2_HOST:$EC2_DEST" | tail -20

if [[ $RESTART -eq 1 ]]; then
  echo
  echo "== restarting collectai-bake.service =="
  ssh "$EC2_HOST" "sudo systemctl restart collectai-bake.service"
  for i in {1..20}; do
    state=$(ssh "$EC2_HOST" "sudo systemctl is-active collectai-bake.service" 2>&1 || true)
    if [[ "$state" == "active" ]]; then
      echo "bake active after ${i}s"
      break
    fi
    sleep 1
  done
  if [[ "$state" != "active" ]]; then
    echo "FATAL: bake did not reach active state — check journalctl" >&2
    ssh "$EC2_HOST" "sudo journalctl -u collectai-bake.service --since '1 minute ago' --no-pager | tail -30" >&2
    exit 1
  fi
  ssh "$EC2_HOST" "sudo journalctl -u collectai-bake.service --since '30 seconds ago' --no-pager | grep -iE 'WARN|ERROR|FAIL' | head -10" || true
fi

echo "deploy ok"
