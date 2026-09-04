# How to run and download — quick reference

Everything below is copy-paste ready.

**Server**: `169.58.117.156` (root)
**Code + data live in**: `/opt/maps-scraper`

---

## 1. Log in

```bash
ssh root@169.58.117.156
```

Enter the root password when prompted.

> Rotate that password — it was shared in plain text. On the server run
> `passwd`, set a new one, and keep the new one out of chat.

---

## 2. Check progress (the one command you'll use most)

```bash
/opt/maps-scraper/status.sh
```

It prints, in one screen:

* whether the scraper is running
* how many combos are done out of 3,262, and the percent
* **READY TO SEND** — countries fully finished, safe to hand the client
* **IN PROGRESS** — countries still filling up, don't send these yet
* total unique businesses collected so far
* where the newest downloadable snapshot is

Countries finish **one at a time in this order**, so the earliest files are
ready within the first days rather than everything landing at the end:

```
canada(420) germany(150) france(108) united_kingdom(90)
united_states_of_america(162) saudi_arabia(340) sweden(30) norway(30)
spain(280) italy(260) russia(100) mexico(60) brazil(300) japan(352)
india(380) australia(200)          <- numbers are combos per country
```

---

## 3. Download the data to your PC

Run these **on your own PC**, not on the server.

**Everything scraped so far, as one zip** (easiest):

```bash
scp root@169.58.117.156:/opt/maps-scraper/snapshots/latest.zip .
```

A fresh snapshot is built automatically **every hour**, so if you come back
after a day this already contains everything up to the last hour.

**One finished country** (this is what you send the client):

```bash
scp root@169.58.117.156:/opt/maps-scraper/output/_merged/canada.json .
```

Swap `canada` for whichever country `status.sh` lists under READY TO SEND.

**All merged country files at once**:

```bash
scp -r root@169.58.117.156:/opt/maps-scraper/output/_merged ./maps_output
```

**Force a fresh snapshot right now** instead of waiting for the hourly cron
(run this one *on the server*):

```bash
/opt/maps-scraper/snapshot.sh
```

---

## 4. Start / stop / restart

```bash
systemctl status maps-scraper     # is it running?
systemctl stop maps-scraper       # pause — safe at any moment
systemctl start maps-scraper      # resume where it left off
systemctl restart maps-scraper
```

**Stopping never loses finished work.** Every `(city, keyword)` combo writes
its own checkpoint file the instant it completes, so restarting skips
everything already done and picks up from the first unfinished combo. The
most you can lose is the handful of combos that were mid-flight.

It also **starts automatically if the server reboots** (`systemctl enable`
is already set).

---

## 5. Watch it live

```bash
tail -f /opt/maps-scraper/logs/runner.log     # overall progress + ETA
tail -f /opt/maps-scraper/logs/worker_0.log   # one worker (0-5)
```

The runner log prints a line per finished combo with a running ETA:

```
[42/3262   1.3%] OK   canada/Downtown Toronto, Toronto | barbershop -> 98 | total=3421 ETA=311.2h
```

---

## 6. What the output looks like

Identical schema to the sample you already sent the client — same keys, same
order, same types. The only differences are the two things they asked for:

```json
{
    "name": "Skyview Barbers",
    "website": "https://skyviewbarbers.sites.getsquire.com/",
    "phone_number": "+1 416-351-1000",
    "latitude": "43.6503759",
    "longitude": "-79.3901779",
    "image": "https://lh3.googleusercontent.com/gps-cs-s/...",
    "open_hours": {
        "Wednesday": "10 am–8 pm",
        "Thursday":  "10 am–8 pm",
        "Friday":    "10 am–10 pm",
        "Saturday":  "10 am–10 pm",
        "Sunday":    "10 am–8 pm",
        "Monday":    "10 am–6 pm",
        "Tuesday":   "10 am–8 pm"
    },
    "rating": 5.0,
    "reviews_count": 572,
    "maps_url": "https://www.google.com/maps/place/Skyview+Barbers/data=..."
}
```

* `open_hours` — **all 7 days** (was 1 day)
* `reviews_count` — **real number** (was always `null`)

---

## 7. If something looks wrong

```bash
systemctl status maps-scraper           # crashed? it auto-restarts on failure
grep FAIL /opt/maps-scraper/logs/worker_*.log | tail -20
free -m                                 # memory should stay above ~1.5 GB free
uptime                                  # load should sit around 6-12
```

If the box ever looks stuck (load above ~30, almost no free memory):

```bash
systemctl stop maps-scraper
killall -9 chrome chromedriver
rm -rf /tmp/chrome-profile-w*
systemctl start maps-scraper
```

It resumes from the last checkpoint, losing nothing that was finished.

**Do not raise the worker count.** 6 is the measured ceiling for this box —
10 workers exhausted the 11 GB of RAM and completed *zero* combos in 7
minutes because everything thrashed. The runner now refuses anything higher
and prints why.
