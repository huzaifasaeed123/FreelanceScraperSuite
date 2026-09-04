# Deployment runbook

Consolidated from two real deployments (a 16-target run and a 6-target run,
both on a 6-core/11GB Ubuntu 24.04 VPS). Follow this in order on a fresh box.

## 1. Chrome + matching chromedriver

There is no `apt install google-chrome` step here — both proven deployments
used a manually-placed **Chrome for Testing** build, which ships without the
auto-update behaviour that would otherwise drift out of sync with a pinned
chromedriver.

- Download a matched Chrome-for-Testing + chromedriver pair for your
  platform: https://googlechromelabs.github.io/chrome-for-testing/
- Last proven pair: **151.0.7922.76** (both Chrome and chromedriver — the
  major version must match or every scrape fails instantly at driver
  startup).
- Put them somewhere stable (e.g. `/opt/chrome/chrome`,
  `/opt/chromedriver-linux64/chromedriver`) and symlink both onto `PATH`:
  ```bash
  ln -s /opt/chrome/chrome /usr/local/bin/chrome
  ln -s /opt/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver
  ```
- `googlescrap72.py`'s `resolve_chromedriver()` looks for `chromedriver(.exe)`
  next to itself first, then falls back to `PATH` — either placement works.

## 2. Python environment

```bash
python3 -m venv /opt/maps-scraper/venv
/opt/maps-scraper/venv/bin/pip install -r requirements.txt
```

Pinned versions in `requirements.txt` are a `pip freeze` from a working
deployment (selenium 4.46.0 + its transitive deps) — start from those exact
pins on a new box rather than "just install selenium latest."

## 3. Layout

```
/opt/maps-scraper/
  googlescrap72.py
  run_parallel.py
  status.sh
  snapshot.sh
  requirements.txt
  countries/<target>.py     one file per scraping target (see _TEMPLATE.py)
  output/                   created automatically
  logs/                     created automatically
  state/                    created automatically
  venv/
```

## 4. Define what to scrape

Copy `countries/_TEMPLATE.py` to `countries/<name>.py` per target, fill in
cities + keywords. With no `--countries` flag, every file in `countries/` is
picked up automatically, alphabetically. Pass `--countries a b c` to run a
specific subset in a specific order — **put anything time-sensitive or
never-before-scraped first**; a batch that stalls partway through still
delivers its earlier targets complete.

## 5. Pre-flight — always, especially for a new target

Before starting a real run, generate every filename the fixed
`safe_filename()` would produce for the new target and check for collisions:

```python
import sys
sys.path.insert(0, "/opt/maps-scraper")
import googlescrap72 as engine

m = engine.load_country_module("yourtarget")
names = set()
dupes = []
for city in m.get_major_cities():
    for kw in m.get_business_keywords(city=city):
        fn = f"yourtarget_{engine.safe_filename(city)}_{engine.safe_filename(kw)}_comprehensive.json"
        if fn in names:
            dupes.append((city, kw, fn))
        names.add(fn)

print(f"combos={sum(len(m.get_business_keywords(city=c)) for c in m.get_major_cities())}  unique_filenames={len(names)}")
print("collisions:", dupes or "none")
```

This is a five-minute check that would have caught the non-Latin filename
bug (README.md, fix #4) before it cost ~95% of a country's data on a real
run — it's not optional when the keyword list has any non-Latin script.

Then run a tiny slice for real before trusting the full batch:

```bash
venv/bin/python run_parallel.py --countries yourtarget --limit 3
```

Confirm Chrome actually launched, files landed in `output/yourtarget/`, and
the merged export includes them (`--export-only` to force a rebuild).

## 6. Memory tuning — the part that matters most

**Sizing is memory-bound, not CPU-bound.** On an 11 GB box, 6 parallel
workers pushed past a 9 GB hard memory cap and got OOM-killed roughly every
13 minutes. Since one combo takes 20-50 minutes, **no combo could ever
survive to completion** — the service showed as "running" continuously while
making zero net progress for hours. Dropping to **4 workers** fixed it
completely: zero OOM-kills across the following multi-week unattended run.

Two changes work together to make a memory spike a slowdown instead of a
kill:

**a) `MemoryHigh` below `MemoryMax`** in the systemd unit — the kernel
throttles and reclaims at the lower threshold instead of hard-killing at the
cap. This is what actually prevented kills; `MemoryMax` alone (the original
config) is what caused the livelock.

**b) A few GB of swap as a cushion** (not as working memory — it should sit
near-idle under normal load):
```bash
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo "/swapfile none swap sw 0 0" >> /etc/fstab
sysctl -w vm.swappiness=10
echo "vm.swappiness=10" >> /etc/sysctl.conf
```

**Sizing rule of thumb**: ~2 GB per Chrome worker, several GB of headroom
below total RAM. 4 workers on 11 GB is the proven number — don't extrapolate
linearly to a different box without a real soak test. Start the service,
watch `memory.current` in its cgroup
(`/sys/fs/cgroup/system.slice/<unit>.service/memory.current`) for 30-60
minutes, and confirm `memory.events` stays at `oom_kill 0`. If usage climbs
past `MemoryHigh` and keeps climbing rather than plateauing, workers is too
high for that box.

## 7. systemd unit

Copy `maps-scraper.service.template` to `/etc/systemd/system/maps-scraper.service`,
adjust paths and `--workers` for the box, then:

```bash
systemctl daemon-reload
systemctl enable maps-scraper
systemctl start maps-scraper
```

Resume-safety (per-combo checkpoint files) means `Restart=on-failure` is
always safe — a crash mid-combo re-scans and continues rather than
re-scraping anything already finished.

## 8. Operating it

```bash
systemctl status maps-scraper           # running?
systemctl stop maps-scraper              # pause, safe at any moment
systemctl start maps-scraper             # resume where it left off
/opt/maps-scraper/status.sh              # progress, per-target completion
tail -f /opt/maps-scraper/logs/runner.log
```

If the box looks stuck (load far above core count, near-zero free memory):

```bash
systemctl stop maps-scraper
killall -9 chrome chromedriver
rm -rf /tmp/chrome-profile-w*
systemctl start maps-scraper
```

It resumes from the last checkpoint — this loses nothing that had already
finished.

## 9. Getting data out mid-run

```bash
scp root@<server>:/opt/maps-scraper/output/_merged/<target>.json .
scp -r root@<server>:/opt/maps-scraper/output/_merged ./maps_output
```

For a slow link, compress server-side first — this took an 8-minute transfer
down to a few seconds on a real pull:

```bash
ssh root@<server> 'tar czf /tmp/out.tar.gz -C /opt/maps-scraper/output/_merged .'
scp root@<server>:/tmp/out.tar.gz .
```

`snapshot.sh` wired to an hourly cron job keeps a `latest.zip` always
pointing at the newest snapshot, so a check-in after a day of unattended
running already has everything up to the last hour without needing to
rebuild anything.

## What not to change without re-testing

- Don't raise `--workers` on a new box without a fresh soak test — the
  proven number is proven for a specific RAM size, not a law of nature.
- Don't touch `safe_filename()` without re-running the collision pre-flight
  from step 5.
- Don't rely on `MemoryMax` alone — it caused the original livelock.
  `MemoryHigh` + swap is what actually fixed it.
- Don't trust `status.sh`'s per-target percentage as ground truth if any
  output files predate the filename fix — cross-check with a real file count
  (`ls output/<target> | wc -l`) against that target's `cities x keywords`.
