#!/usr/bin/env bash
# Install Crawl4AI on EC2 (or any Linux host).
# Crawl4AI is a Playwright-based web crawler — requires a real browser binary.
#
# Usage:
#   ./scripts/install_crawl4ai.sh
#
# After install, set CRAWL4AI_ENABLED=true in .env and restart the bake.

set -euo pipefail

echo "── installing crawl4ai Python package ──"
pip install --quiet crawl4ai

echo "── installing Playwright + Chromium browser ──"
playwright install chromium
playwright install-deps chromium

echo "── verify ──"
python3 -c "from crawl4ai import AsyncWebCrawler; print('crawl4ai OK')"
python3 -c "from playwright.sync_api import sync_playwright; print('playwright OK')"

echo ""
echo "Done. Now:"
echo "  1. Edit .env: set CRAWL4AI_ENABLED=true"
echo "  2. Restart bake: ./scripts/bake_stop.sh && ./scripts/bake_start.sh"
echo "  3. Verify: grep 'Crawl4AI' bake.log (should show successful scrapes, not ModuleNotFoundError)"
