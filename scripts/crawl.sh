#!/bin/bash
set -e

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting weekly crawl"

house-crawler db init
house-crawler crawl all
house-crawler analyze snapshots
house-crawler analyze scores

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Weekly crawl completed"
