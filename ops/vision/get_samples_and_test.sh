#!/usr/bin/env bash
set -euo pipefail

# ---- config (EDIT BUCKET + optional REGION) ----
: "${BUCKET:?Set BUCKET env first, e.g., export BUCKET='my-bucket-name'}"
: "${AWS_DEFAULT_REGION:=eu-central-1}"

SAMPLES_DIR="/tmp/vision_samples"
mkdir -p "$SAMPLES_DIR"

echo "== Downloading a few real images =="
# LEGO box (Wikimedia)
curl -L -o "$SAMPLES_DIR/lego.jpg" \
  "https://upload.wikimedia.org/wikipedia/commons/thumb/6/64/Lego_Logo.svg/512px-Lego_Logo.svg.png"
# Hot Wheels car (Wikimedia)
curl -L -o "$SAMPLES_DIR/diecast.jpg" \
  "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7f/Hot_Wheels_logo.svg/512px-Hot_Wheels_logo.svg.png"
# Warhammer (Wikimedia)
curl -L -o "$SAMPLES_DIR/warhammer.jpg" \
  "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/Warhammer_logo.svg/512px-Warhammer_logo.svg.png"

echo "== Verifying mime + size =="
min=4096
for f in "$SAMPLES_DIR"/*.jpg; do
  size=$(stat -c%s "$f")
  mime=$(file --mime-type -b "$f" || true)
  echo " - $f  size=$size bytes  mime=$mime"
  if [ "$size" -lt "$min" ]; then echo "   -> too small; will still upload for demo"; fi
done

echo "== Uploading to S3 prefix: s3://$BUCKET/spool/vision/raw/ =="
for f in "$SAMPLES_DIR"/*.jpg; do
  aws s3 cp "$f" "s3://$BUCKET/spool/vision/raw/$(basename "$f")"
done

echo "== Rebuilding index =="
sudo systemctl start vision-index.service
sleep 1
journalctl -u vision-index.service -n 200 --no-pager || true

echo "== Artifacts =="
ls -lh ops/vision/faiss.index ops/vision/ids.jsonl || true
echo "ids.jsonl lines:"
[ -f ops/vision/ids.jsonl ] && wc -l ops/vision/ids.jsonl || true

echo "== Health & vision debug =="
curl -sS http://127.0.0.1:8081/healthz | jq .
curl -sS http://127.0.0.1:8081/ops/vision/debug | jq .

echo "== Text search smoke =="
curl -sS "http://127.0.0.1:8081/vision/search/text?q=lego%20logo" | jq .

echo "== Image predict smoke (local files) =="
for f in "$SAMPLES_DIR"/*.jpg; do
  echo "--- $f ---"
  curl -sS -F "file=@$f" http://127.0.0.1:8081/vision/predict | jq .
done

echo "✓ Done."
