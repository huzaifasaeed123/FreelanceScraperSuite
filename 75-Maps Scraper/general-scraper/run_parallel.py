#!/usr/bin/env python3
"""
Parallel Big-City-Pass runner.

Replaces run_countries72.py's one-country-at-a-time, one-browser-at-a-time
loop with a shared work queue drained by N worker processes (default 6, one
per core). Everything is driven from this single entrypoint - you run one
command, it manages the instances internally.

Design notes:

* Unit of work is a (country, area, keyword) combo - the same unit the
  original code checkpointed on, so resume-safety semantics are unchanged:
  a combo whose output file exists is skipped, and a zero-result combo
  still writes an empty [] file to mark itself done.

* Workers never mutate googlescrap72.py. The original runner rewrote
  SELECTED_COUNTRY in the source file before each country, which is
  fundamentally unsafe with concurrency (all workers share one file).
  Instead each worker imports the engine once and swaps the country module
  in-process via configure_country().

* Progress is written continuously, so the run is safe to interrupt and
  the partial data is always downloadable.
"""

import argparse
import json
import multiprocessing as mp
import os
import queue
import random
import signal
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUTPUT_ROOT = BASE / "output"
LOG_DIR = BASE / "logs"
STATE_DIR = BASE / "state"

def _autodetect_countries():
    """Default country list: every *.py file found in countries/ next to this
    script. Drop a new country file in and it's picked up with no code edit -
    override for a specific subset/order with --countries a b c."""
    countries_dir = BASE / "countries"
    if not countries_dir.exists():
        return []
    return sorted(p.stem for p in countries_dir.glob("*.py")
                  if p.stem not in ("__init__", "_TEMPLATE"))


DEFAULT_COUNTRIES = _autodetect_countries()


# --------------------------------------------------------------------------
# work planning
# --------------------------------------------------------------------------

def build_work_items(countries):
    """Expand every country into its (country, area, keyword) combos."""
    sys.path.insert(0, str(BASE))
    import googlescrap72 as engine

    items = []
    for country in countries:
        module = engine.load_country_module(country)
        if module is None:
            print(f"!! skipping {country}: could not load country module")
            continue
        for area in module.get_major_cities():
            for keyword in module.get_business_keywords(city=area):
                items.append((country, area, keyword))
    return items


def output_path_for(country, area, keyword):
    import googlescrap72 as engine
    fname = (f"{country}_{engine.safe_filename(area)}"
             f"_{engine.safe_filename(keyword)}_comprehensive.json")
    return OUTPUT_ROOT / country / fname


def is_done(country, area, keyword):
    """A combo is done when its output file exists - including an empty one,
    which is how a legitimate zero-result combo marks itself complete."""
    path = output_path_for(country, area, keyword)
    if path.exists():
        return True
    # Also honour checkpoints from the original single-process layout.
    legacy = BASE / country / path.name
    return legacy.exists()


# --------------------------------------------------------------------------
# worker
# --------------------------------------------------------------------------

def worker(worker_id, work_q, done_q, args):
    """Drain the queue until it's empty. One Chrome at a time per worker."""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.path.insert(0, str(BASE))

    log_path = LOG_DIR / f"worker_{worker_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logf = open(log_path, "a", encoding="utf-8", buffering=1)

    def log(msg):
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        logf.write(f"[{stamp}] w{worker_id} {msg}\n")

    # Each worker gets its own Chrome profile dir so concurrent instances
    # never fight over the same singleton lock.
    os.environ["MAPS_PROFILE_DIR"] = f"/tmp/chrome-profile-w{worker_id}"

    import googlescrap72 as engine
    engine.QUIET = True

    log(f"worker started (pid {os.getpid()})")

    # A Chrome killed mid-run leaves its profile dir behind holding a stale
    # singleton lock, which makes the next launch in that dir fail. Clear it
    # on startup so a restart after a crash is always clean.
    try:
        import shutil as _shutil
        _shutil.rmtree(os.environ["MAPS_PROFILE_DIR"], ignore_errors=True)
    except Exception:
        pass

    while True:
        try:
            country, area, keyword = work_q.get_nowait()
        except queue.Empty:
            break

        if is_done(country, area, keyword):
            done_q.put(("skip", country, area, keyword, 0))
            continue

        started = time.time()
        try:
            engine.configure_country(country)
            # Stagger worker starts slightly so six browsers don't hit
            # Google in lockstep on every single combo.
            time.sleep(random.uniform(0, args.jitter))

            results = engine.scrape_comprehensive_area(
                keyword, area,
                max_per_search=args.max_per_search,
                output_dir=OUTPUT_ROOT / country,
            )
            elapsed = time.time() - started
            log(f"OK   {country} | {area} | {keyword} -> {len(results)} in {elapsed:.0f}s")
            done_q.put(("ok", country, area, keyword, len(results)))
        except Exception as exc:
            elapsed = time.time() - started
            log(f"FAIL {country} | {area} | {keyword}: {exc!r} after {elapsed:.0f}s")
            log(traceback.format_exc())
            done_q.put(("fail", country, area, keyword, 0))

    log("worker finished - queue empty")
    logf.close()


# --------------------------------------------------------------------------
# exporting
# --------------------------------------------------------------------------

# Measured on the 11 GB / 6-core target box: 6 concurrent workers ran a full
# combo each with ~2 GB still free, while 10 workers exhausted RAM. That puts
# real steady-state usage near 1.5 GB per Chrome.
MB_PER_WORKER = 1500


def clamp_workers(requested):
    """Cap workers at what RAM and cores can actually sustain.

    Chrome on Maps is memory-hungry, and oversubscribing doesn't just run
    slower - it collapses. Measured on the 11 GB target box: 6 workers fine,
    10 workers thrashed to a standstill with zero combos completed.
    """
    try:
        total_mb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // (1024 * 1024)
    except (ValueError, AttributeError, OSError):
        return requested  # non-POSIX (e.g. Windows dev box): trust the caller

    # Leave ~1.5 GB for the OS, the runner itself, and page cache.
    by_memory = max(1, int((total_mb - 1536) // MB_PER_WORKER))
    # Chrome is I/O-bound, so modest core oversubscription is fine.
    by_cpu = max(1, (os.cpu_count() or 1) * 2)
    allowed = min(by_memory, by_cpu)

    if requested > allowed:
        print(f"!! reducing workers {requested} -> {allowed} "
              f"({total_mb} MB RAM, {os.cpu_count()} cores; "
              f"~{MB_PER_WORKER} MB needed per Chrome)")
        return allowed
    return requested


def export_merged(verbose=True):
    """Merge every per-combo file into one JSON per country plus a global
    combined file. Safe to call while workers are running - it only reads."""
    export_dir = OUTPUT_ROOT / "_merged"
    export_dir.mkdir(parents=True, exist_ok=True)

    grand_total = 0
    summary = {}
    combined = []

    for country_dir in sorted(p for p in OUTPUT_ROOT.iterdir()
                              if p.is_dir() and not p.name.startswith("_")):
        merged, seen = [], set()
        for jf in sorted(country_dir.glob("*_comprehensive.json")):
            try:
                rows = json.loads(jf.read_text(encoding="utf-8"))
            except Exception:
                continue  # a file mid-write; it'll be picked up next export
            for row in rows:
                lat, lng = row.get("latitude"), row.get("longitude")
                name = (row.get("name") or "").strip().lower()
                key = f"{lat}_{lng}" if lat and lng else f"name::{name}"
                if key in seen:
                    continue
                seen.add(key)
                merged.append(row)

        if merged:
            out = export_dir / f"{country_dir.name}.json"
            out.write_text(json.dumps(merged, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            summary[country_dir.name] = len(merged)
            combined.extend(merged)
            grand_total += len(merged)

    if combined:
        (export_dir / "ALL_COUNTRIES.json").write_text(
            json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")

    # Mark which countries are fully scraped, so it's unambiguous which files
    # are finished and safe to hand to the client vs still filling up.
    status = {}
    try:
        sys.path.insert(0, str(BASE))
        import googlescrap72 as engine
        for country in DEFAULT_COUNTRIES:
            module = engine.load_country_module(country)
            if module is None:
                continue
            total = sum(len(module.get_business_keywords(city=a))
                        for a in module.get_major_cities())
            done = sum(1 for a in module.get_major_cities()
                       for k in module.get_business_keywords(city=a)
                       if is_done(country, a, k))
            status[country] = {
                "combos_done": done,
                "combos_total": total,
                "complete": done >= total,
                "businesses": summary.get(country, 0),
            }
    except Exception:
        pass

    summary_payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_unique_businesses": grand_total,
        "per_country": summary,
        "country_status": status,
        "completed_countries": sorted(c for c, s in status.items() if s["complete"]),
    }
    (export_dir / "SUMMARY.json").write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if verbose:
        print(f"[export] {grand_total} unique businesses -> {export_dir}")
    return grand_total


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6,
                    help="parallel browser instances (default 6, one per core)")
    ap.add_argument("--countries", nargs="*", default=DEFAULT_COUNTRIES)
    ap.add_argument("--max-per-search", type=int, default=120)
    ap.add_argument("--jitter", type=float, default=3.0,
                    help="max random delay before each combo, seconds")
    ap.add_argument("--export-every", type=int, default=300,
                    help="seconds between merged exports (0 disables)")
    ap.add_argument("--export-only", action="store_true",
                    help="just rebuild merged exports and exit")
    ap.add_argument("--limit", type=int, default=0,
                    help="process at most N combos (for smoke tests)")
    args = ap.parse_args()

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Each Chrome running Maps needs roughly 1.5-1.8 GB. Measured on this box
    # (11 GB): 6 workers is healthy, 10 workers exhausted RAM and completed
    # zero combos in 7 minutes because everything thrashed. Refuse to start a
    # configuration that cannot fit rather than discovering it hours in.
    args.workers = clamp_workers(args.workers)

    if args.export_only:
        export_merged()
        return

    print("=" * 66)
    print("PARALLEL BIG CITY PASS")
    print(f"workers={args.workers}  countries={len(args.countries)}")
    print("=" * 66)

    all_items = build_work_items(args.countries)
    pending = [it for it in all_items if not is_done(*it)]
    already = len(all_items) - len(pending)
    if args.limit:
        pending = pending[:args.limit]

    print(f"total combos : {len(all_items)}")
    print(f"already done : {already}")
    print(f"to process   : {len(pending)}")
    print("=" * 66, flush=True)

    if not pending:
        export_merged()
        print("nothing to do - everything already scraped")
        return

    # Country-at-a-time ordering. The whole pass takes ~2 weeks at full depth,
    # so finishing countries one after another means deliverable files appear
    # from the first days onward, instead of every country sitting 90% done
    # until the very end.
    #
    # Within a country the combos are still shuffled, so the six workers spread
    # across different cities/keywords rather than hammering one city at once.
    by_country = {}
    for item in pending:
        by_country.setdefault(item[0], []).append(item)
    ordered = []
    for country in args.countries:
        chunk = by_country.get(country, [])
        random.shuffle(chunk)
        ordered.extend(chunk)
    # Any country not named in --countries (shouldn't happen) still gets run.
    for country, chunk in by_country.items():
        if country not in args.countries:
            random.shuffle(chunk)
            ordered.extend(chunk)
    pending = ordered

    print("country order (files land in this sequence):")
    for country in args.countries:
        n = len(by_country.get(country, []))
        if n:
            print(f"    {country:30} {n:>5} combos")
    print("=" * 66, flush=True)

    work_q, done_q = mp.Queue(), mp.Queue()
    for item in pending:
        work_q.put(item)

    procs = []
    for wid in range(args.workers):
        p = mp.Process(target=worker, args=(wid, work_q, done_q, args), daemon=True)
        p.start()
        procs.append(p)
        time.sleep(1.5)  # ramp up gradually rather than 6 Chromes at once

    start = time.time()
    counts = {"ok": 0, "fail": 0, "skip": 0}
    businesses = 0
    processed = 0
    last_export = time.time()

    try:
        while any(p.is_alive() for p in procs) or not done_q.empty():
            try:
                status, country, area, keyword, n = done_q.get(timeout=5)
            except queue.Empty:
                if args.export_every and time.time() - last_export > args.export_every:
                    export_merged(verbose=True)
                    last_export = time.time()
                continue

            counts[status] += 1
            businesses += n
            processed += 1

            if status != "skip":
                elapsed = time.time() - start
                rate = processed / elapsed if elapsed else 0
                remaining = len(pending) - processed
                eta_h = (remaining / rate / 3600) if rate else 0
                pct = 100 * processed / len(pending)
                print(f"[{processed}/{len(pending)} {pct:5.1f}%] {status.upper():4} "
                      f"{country}/{area} | {keyword} -> {n} "
                      f"| total={businesses} ETA={eta_h:.1f}h", flush=True)

            if args.export_every and time.time() - last_export > args.export_every:
                export_merged(verbose=True)
                last_export = time.time()

        for p in procs:
            p.join(timeout=30)

    except KeyboardInterrupt:
        print("\ninterrupted - exporting what we have (safe to rerun to resume)")
        for p in procs:
            p.terminate()

    total_h = (time.time() - start) / 3600
    final = export_merged()
    print("=" * 66)
    print(f"done in {total_h:.2f}h | ok={counts['ok']} fail={counts['fail']} "
          f"skip={counts['skip']}")
    print(f"unique businesses exported: {final}")
    print(f"merged output: {OUTPUT_ROOT / '_merged'}")
    print("=" * 66)


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()
