#!/usr/bin/env python3
"""
Big-City-Pass Runner — standalone, isolated from server_missing and every
existing server_* folder. Same pattern as server_6/run_countries72.py:
loops through countries sequentially, rewriting SELECTED_COUNTRY in
googlescrap72.py before each one. 72h timeout per country (all batch-1
countries here are well under the 1,000-combo "big" threshold used in
server_missing, since this pass targets specific districts of 1-3 cities
per country, not full city lists).

Resume-safe: same file-existence skip logic as every other job in this
project — interrupting and rerunning loses no completed work.
"""

import subprocess
import sys
import time

countries = [
    "canada",
    "germany",
    "france",
    "united_kingdom",
    "united_states_of_america",
    "saudi_arabia",
    "sweden",
    "norway",
    "spain",
    "italy",
    "russia",
    "mexico",
    "brazil",
    "japan",
    "india",
    "australia"
]

TIMEOUT_SECONDS = 72 * 3600


def update_country_in_file(country_name):
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
    print(f"\n🏙️  BIG CITY PASS: Starting {country.upper()}")
    print("="*60)
    update_country_in_file(country)
    try:
        result = subprocess.run([sys.executable, 'googlescrap72.py'],
                              capture_output=False, text=True, timeout=TIMEOUT_SECONDS)
        if result.returncode == 0:
            print(f"✅ BIG CITY PASS: {country.upper()} completed successfully")
        else:
            print(f"❌ BIG CITY PASS: {country.upper()} failed")
    except subprocess.TimeoutExpired:
        print(f"⏰ BIG CITY PASS: {country.upper()} timed out after 72 hours")
    except Exception as e:
        print(f"💥 BIG CITY PASS: Error running {country}: {e}")


if __name__ == "__main__":
    print("🎯 BIG CITY PASS STARTING")
    print("Countries:", ", ".join(countries))
    start_time = time.time()
    for country in countries:
        country_start = time.time()
        run_country(country)
        hours_taken = (time.time() - country_start) / 3600
        print(f"⏱️  {country} took {hours_taken:.1f} hours")
        print("-" * 60)
    total_hours = (time.time() - start_time) / 3600
    print(f"\n🏁 BIG CITY PASS COMPLETE! Total time: {total_hours:.1f} hours ({total_hours/24:.1f} days)")
