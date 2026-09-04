#!/bin/bash
# One-glance health + progress report. Run this when you come back to the box.
BASE=/opt/maps-scraper
cd "$BASE" || exit 1

echo "=================================================================="
echo " MAPS SCRAPER STATUS  -  $(date -u '+%F %T') UTC"
echo "=================================================================="

if systemctl is-active --quiet maps-scraper; then
    echo "service      : RUNNING"
    echo "uptime       : $(systemctl show maps-scraper -p ActiveEnterTimestamp --value)"
else
    echo "service      : STOPPED  (systemctl status maps-scraper)"
fi

CHROMES=$(pgrep -c -f 'chrome.*headless' 2>/dev/null || echo 0)
echo "chrome procs : $CHROMES"
echo "load         :$(uptime | sed 's/.*load average://')"
echo "memory       : $(free -h | awk '/^Mem:/{print $3" used / "$2" total"}')"
echo "disk         : $(df -h "$BASE" | awk 'NR==2{print $4" free ("$5" used)"}')"

echo "------------------------------------------------------------------"
DONE=$(find output -name '*_comprehensive.json' 2>/dev/null | wc -l)
TOTAL=$(./venv/bin/python - <<'PY' 2>/dev/null || echo "?"
import sys; sys.path.insert(0,'/opt/maps-scraper')
import os; os.chdir('/opt/maps-scraper')
import run_parallel as r
print(len(r.build_work_items(r.DEFAULT_COUNTRIES)))
PY
)
echo "combos done  : $DONE / $TOTAL"
if [ "$TOTAL" != "?" ] && [ "$TOTAL" -gt 0 ] 2>/dev/null; then
    echo "progress     : $(awk "BEGIN{printf \"%.1f%%\", 100*$DONE/$TOTAL}")"
fi

if [ -f output/_merged/SUMMARY.json ]; then
    echo "------------------------------------------------------------------"
    ./venv/bin/python - <<'PY'
import json
d = json.load(open('/opt/maps-scraper/output/_merged/SUMMARY.json'))
st = d.get('country_status', {})
done = [c for c, s in st.items() if s['complete']]

print("READY TO SEND (country fully scraped):")
if done:
    for c in sorted(done):
        print(f"  [DONE] {c:28} {st[c]['businesses']:>7} businesses"
              f"   -> output/_merged/{c}.json")
else:
    print("  (none finished yet)")

busy = [(c, s) for c, s in st.items() if not s['complete'] and s['combos_done']]
if busy:
    print("\nIN PROGRESS (do NOT send yet - still filling):")
    for c, s in sorted(busy, key=lambda x: -x[1]['combos_done']):
        pct = 100 * s['combos_done'] / max(s['combos_total'], 1)
        print(f"  [{pct:5.1f}%] {c:28} {s['combos_done']}/{s['combos_total']} combos"
              f"  {s['businesses']} businesses")

print(f"\n  TOTAL so far: {d['total_unique_businesses']} unique businesses")
print(f"  (exported {d['generated_utc']})")
PY
fi

echo "------------------------------------------------------------------"
echo "latest snapshot : $(readlink -f snapshots/latest.zip 2>/dev/null || echo 'none yet')"
echo "recent activity :"
tail -n 3 logs/runner.log 2>/dev/null | sed 's/^/  /' || echo "  (no runner log yet)"
echo "=================================================================="
