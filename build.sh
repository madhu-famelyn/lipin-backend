#!/usr/bin/env bash
# Render build script for Playwright

set -o errexit  # Exit on error

echo "=== Starting build script ==="

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browser (let Playwright manage its own path)
echo "=== Installing Playwright Chromium ==="
playwright install chromium

# Show where Playwright installed the browser
echo "=== Playwright browser location ==="
python -c "from playwright.sync_api import sync_playwright; print('Playwright ready')" || echo "Playwright check failed"

echo "=== Build completed ==="
