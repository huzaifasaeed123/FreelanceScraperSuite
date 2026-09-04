#!/usr/bin/env python3
"""
Missing-Coverage Week 4 — Auto Country Runner
Standalone copy, isolated from every existing server_* folder — run this
on its own PC. Runs each country in countries/ to completion (or until
its timeout) before moving to the next, same pattern as
server_6/run_countries72.py.

Resume-safe: googlescrap72.py's own per-(city,keyword) output-file check
means interrupting this script (Ctrl+C, PC restart, etc.) and rerunning it
loses no completed work — already-done combos are skipped automatically.

Per-country timeout: 72h default, 208h for the
large-combo-count countries in BIG_TIMEOUT_COUNTRIES (>= 1000 combos)
so a big country isn't cut off before finishing — 2026-07-15 decision.
"""

import subprocess
import sys
import time

countries = [
    "japan",
    "south_africa",
    "india",
    "uruguay",
    "ghana",
    "bahrain"
]

BIG_TIMEOUT_COUNTRIES = {"india", "japan"}
DEFAULT_TIMEOUT_SECONDS = 72 * 3600
BIG_TIMEOUT_SECONDS = 208 * 3600


def update_country_in_file(country_name):
    """Update the SELECTED_COUNTRY in googlescrap72.py"""
    with open('googlescrap72.py', 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'SELECTED_COUNTRY = ' in line and not line.strip().startswith('#'):
            lines[i] = f'SELECTED_COUNTRY = "{country_name}"  # Auto-updated by run_countries72.py'
            break

    with open('googlescrap72.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def run_country(country):
    timeout_seconds = BIG_TIMEOUT_SECONDS if country in BIG_TIMEOUT_COUNTRIES else DEFAULT_TIMEOUT_SECONDS
    timeout_hours = timeout_seconds / 3600
    print(f"\n🚀 MISSING COVERAGE WEEK 4: Starting {country.upper()}")
    print("="*60)
    print(f"⏱️  This country has {timeout_hours:.0f} hours to complete scraping...")

    update_country_in_file(country)

    try:
        result = subprocess.run([sys.executable, 'googlescrap72.py'],
                              capture_output=False,
                              text=True,
                              timeout=timeout_seconds)

        if result.returncode == 0:
            print(f"✅ WEEK 4: {country.upper()} completed successfully")
        else:
            print(f"❌ WEEK 4: {country.upper()} failed")

    except subprocess.TimeoutExpired:
        print(f"⏰ WEEK 4: {country.upper()} timed out after {timeout_hours:.0f} hours")
    except Exception as e:
        print(f"💥 WEEK 4: Error running {country}: {e}")


if __name__ == "__main__":
    print("🎯 MISSING COVERAGE WEEK 4 STARTING")
    print("Countries:", ", ".join(countries))
    print(f"⏱️  {DEFAULT_TIMEOUT_SECONDS // 3600}h per country default, {BIG_TIMEOUT_SECONDS // 3600}h for: {', '.join(sorted(BIG_TIMEOUT_COUNTRIES)) or '(none)'}")

    start_time = time.time()

    for country in countries:
        country_start = time.time()
        run_country(country)
        hours_taken = (time.time() - country_start) / 3600
        print(f"⏱️  {country} took {hours_taken:.1f} hours")
        print("-" * 60)

    total_hours = (time.time() - start_time) / 3600
    print(f"\n🏁 MISSING COVERAGE WEEK 4 COMPLETE!")
    print(f"Total time: {total_hours:.1f} hours ({total_hours/24:.1f} days)")
