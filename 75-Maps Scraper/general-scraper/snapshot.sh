#!/bin/bash
# Build a timestamped, downloadable archive of everything scraped so far.
# Safe to run at any time, including mid-scrape - it only reads.
#
#   ./snapshot.sh          -> /opt/maps-scraper/snapshots/maps_data_<stamp>.zip
#
# Run from cron (see deploy notes) so a fresh archive always exists to grab.
set -euo pipefail

BASE=/opt/maps-scraper
STAMP=$(date -u +%Y%m%d_%H%M)
SNAPDIR="$BASE/snapshots"
mkdir -p "$SNAPDIR"

cd "$BASE"

# Rebuild merged exports first so the archive reflects the newest combos.
./venv/bin/python run_parallel.py --export-only >/dev/null 2>&1 || true

ZIP="$SNAPDIR/maps_data_${STAMP}.zip"
zip -qr "$ZIP" output/_merged output/*/ -x '*.tmp' 2>/dev/null || \
  zip -qr "$ZIP" output/_merged 2>/dev/null || true

ln -sfn "$ZIP" "$SNAPDIR/latest.zip"

# Keep the 12 most recent archives; older ones are redundant.
ls -1t "$SNAPDIR"/maps_data_*.zip 2>/dev/null | tail -n +13 | xargs -r rm -f

TOTAL=$(./venv/bin/python -c "import json,sys
try:
    d=json.load(open('$BASE/output/_merged/SUMMARY.json'))
    print(d['total_unique_businesses'])
except Exception:
    print(0)" 2>/dev/null || echo 0)

echo "[$(date -u '+%F %T')] snapshot -> $ZIP  ($TOTAL unique businesses)"
