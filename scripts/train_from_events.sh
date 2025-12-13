#!/usr/bin/env bash
set -euo pipefail
./scripts/events_to_training.py data/training/events.jsonl data/training/training.jsonl
# ensure model dir exists
sudo mkdir -p /opt/models
sudo chown -R ubuntu:ubuntu /opt/models || true
# train all cats present in training.jsonl
./scripts/train_ridge.py data/training/training.jsonl
