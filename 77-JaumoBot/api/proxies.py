"""Proxy line parsing, URL building, testing and the concurrent assignment pool."""

import re
import threading
from urllib.parse import quote, unquote, urlparse

import requests
from sqlmodel import Session, select

from bot.engine import StopRequested

from .models import Proxy, engine, utcnow
from .settings import PROXY_TEST_URL

SCHEMES = {"http", "https", "socks5", "socks5h", "socks4"}


class NoProxyAvailable(Exception):
    pass


def parse_proxy_line(line: str) -> dict:
    """
    Accepts:
        host:port
        host:port:user:pass          (pass may contain ':')
        user:pass@host:port
        scheme://[user:pass@]host:port
    """
    line = line.strip()
    if not line:
        raise ValueError("empty line")

    if "://" in line:
        u = urlparse(line)
        if u.scheme not in SCHEMES or not u.hostname or not u.port:
            raise ValueError(f"invalid proxy URL: {line}")
        return {
            "scheme": u.scheme, "host": u.hostname, "port": u.port,
            "username": unquote(u.username or ""), "password": unquote(u.password or ""),
        }

    if "@" in line:
        creds, hostport = line.rsplit("@", 1)
        host, _, port = hostport.rpartition(":")
        user, _, pwd = creds.partition(":")
        if not host or not port.isdigit():
            raise ValueError(f"invalid proxy line: {line}")
        return {"scheme": "http", "host": host, "port": int(port), "username": user, "password": pwd}

    parts = line.split(":", 3)
    if len(parts) not in (2, 4) or not parts[1].isdigit():
        raise ValueError(f"invalid proxy line (expected host:port[:user:pass]): {line}")
    return {
        "scheme": "http", "host": parts[0], "port": int(parts[1]),
        "username": parts[2] if len(parts) == 4 else "",
        "password": parts[3] if len(parts) == 4 else "",
    }


def split_lines(text: str) -> list[str]:
    return [l.strip() for l in re.split(r"[\r\n]+", text or "") if l.strip() and not l.strip().startswith("#")]


def proxy_url(p) -> str:
    auth = ""
    if p.username or p.password:
        auth = f"{quote(p.username, safe='')}:{quote(p.password, safe='')}@"
    return f"{p.scheme}://{auth}{p.host}:{p.port}"


def proxy_display(p) -> str:
    return f"{p.host}:{p.port}" + (f" ({p.label})" if p.label else "")


def test_proxy(p) -> dict:
    url = proxy_url(p)
    try:
        resp = requests.get(PROXY_TEST_URL, proxies={"http": url, "https": url}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        ip = data.get("ip") or data.get("query")
        country = data.get("country") or data.get("countryCode")
        city = data.get("city")
        return {"ok": True, "ip": ip, "country": f"{country}{' / ' + city if city else ''}", "error": None}
    except Exception as e:
        return {"ok": False, "ip": None, "country": None, "error": f"{type(e).__name__}: {e}"[:300]}


def save_test_result(session: Session, p: Proxy, result: dict):
    p.last_test_at = utcnow()
    p.last_test_ok = result["ok"]
    p.last_test_ip = result["ip"]
    p.last_test_country = result["country"]
    p.last_test_error = result["error"]
    session.add(p)


class ProxyPool:
    """
    Hands out proxies to bot threads:
      - dedicated lines (shared=False): one bot at a time, least-recently-used first
      - shared lines (shared=True): any number of bots, least-loaded first
    Dedicated lines are preferred when both kinds exist. When only busy
    dedicated lines exist, the bot waits until one is released.
    """

    def __init__(self):
        self.cond = threading.Condition()
        self.in_use: dict[int, int] = {}

    def usage(self) -> dict[int, int]:
        with self.cond:
            return {k: v for k, v in self.in_use.items() if v}

    def notify(self):
        with self.cond:
            self.cond.notify_all()

    def acquire(self, stop_event, require: bool, on_wait=None):
        waited = False
        while True:
            if stop_event.is_set():
                raise StopRequested()
            with self.cond:
                with Session(engine) as s:
                    enabled = s.exec(select(Proxy).where(Proxy.enabled == True)).all()  # noqa: E712
                    if not enabled:
                        if require:
                            raise NoProxyAvailable("no enabled proxies (config requires a proxy)")
                        return None
                    epoch = utcnow().replace(year=1970)
                    dedicated = [p for p in enabled if not p.shared and not self.in_use.get(p.id)]
                    shared = [p for p in enabled if p.shared]
                    pick = None
                    if dedicated:
                        pick = min(dedicated, key=lambda p: p.last_used_at or epoch)
                    elif shared:
                        pick = min(shared, key=lambda p: (self.in_use.get(p.id, 0), p.last_used_at or epoch))
                    if pick:
                        self.in_use[pick.id] = self.in_use.get(pick.id, 0) + 1
                        pick.last_used_at = utcnow()
                        pick.use_count += 1
                        s.add(pick)
                        s.commit()
                        s.refresh(pick)
                        s.expunge(pick)
                        return pick
                if not waited and on_wait:
                    on_wait()
                    waited = True
                self.cond.wait(timeout=2)

    def release(self, proxy_id):
        if proxy_id is None:
            return
        with self.cond:
            if self.in_use.get(proxy_id):
                self.in_use[proxy_id] -= 1
            self.cond.notify_all()
