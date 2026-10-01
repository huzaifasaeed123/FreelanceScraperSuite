"""
Shared fixtures: a fake Jaumo API (in-process thread), and the real admin server
started as a subprocess against a temporary storage directory.
No request ever reaches the real Jaumo API.
"""

import io
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

ADMIN_PASS = "test-pass-123"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until(fn, timeout=30.0, interval=0.15, msg="condition"):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        last = fn()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"timed out waiting for {msg} (last={last!r})")


def jpeg_bytes(seed=0, size=(600, 800), fmt="JPEG"):
    im = Image.new("RGB", size, ((seed * 37) % 255, (seed * 91) % 255, (seed * 53) % 255))
    for x in range(0, size[0], 40):   # some structure so images differ after JPEG encoding
        for y in range(0, size[1], 40):
            if (x // 40 + y // 40 + seed) % 3 == 0:
                im.paste((seed % 255, 200, 90), (x, y, x + 20, y + 20))
    buf = io.BytesIO()
    im.save(buf, fmt)
    return buf.getvalue()


# --- fake Jaumo -----------------------------------------------------------------

@pytest.fixture(scope="session")
def jaumo():
    import fake_jaumo
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(fake_jaumo.app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    wait_until(lambda: server.started, msg="fake jaumo start")

    class J:
        base = f"http://127.0.0.1:{port}/v2"
        root = f"http://127.0.0.1:{port}"

        def reset(self):
            httpx.post(self.root + "/__reset")

        def control(self, **kw):
            return httpx.post(self.root + "/__control", json=kw).json()

        def state(self):
            return httpx.get(self.root + "/__state").json()

    j = J()
    yield j
    server.should_exit = True


@pytest.fixture(autouse=True)
def _reset_jaumo(request):
    if "jaumo" in request.fixturenames:
        request.getfixturevalue("jaumo").reset()
    yield


# --- admin server ---------------------------------------------------------------

class AppServer:
    def __init__(self, storage: Path, jaumo_base: str, extra_env=None):
        self.storage = storage
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.env = {**os.environ, "STORAGE_DIR": str(storage), "JAUMO_BASE_URL": jaumo_base,
                    "ADMIN_USER": "admin", "ADMIN_PASS": ADMIN_PASS, "SECRET_KEY": "test-secret",
                    "PROXY_TEST_URL": jaumo_base.rsplit("/v2", 1)[0] + "/ip", "PYTHONIOENCODING": "utf-8",
                    # never seed the real APK keys from the developer's .env into test databases
                    "JAUMO_CLIENT_ID": "", "JAUMO_SIGN_SECRET": "", "JAUMO_USER_AGENT": "",
                    **(extra_env or {})}
        self.proc = None
        self.log = storage / "server.log"

    def start(self):
        self.storage.mkdir(parents=True, exist_ok=True)
        self._logf = open(self.log, "ab")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=ROOT, env=self.env, stdout=self._logf, stderr=subprocess.STDOUT)
        wait_until(self._healthy, timeout=40, msg="admin server start")
        return self

    def _healthy(self):
        if self.proc.poll() is not None:
            raise AssertionError("server exited:\n" + self.log.read_text(errors="replace")[-3000:])
        try:
            return httpx.get(self.url + "/health", timeout=1).status_code == 200
        except httpx.HTTPError:
            return False

    def stop(self, kill=False):
        if self.proc and self.proc.poll() is None:
            if kill:
                self.proc.kill()
            else:
                self.proc.terminate()
            self.proc.wait(15)
        if getattr(self, "_logf", None):
            self._logf.close()

    def client(self, login=True):
        c = httpx.Client(base_url=self.url, timeout=60)
        if login:
            r = c.post("/api/login", json={"username": "admin", "password": ADMIN_PASS})
            assert r.status_code == 200, r.text
        return c

    def tracebacks(self):
        """Server errors in the log: Python tracebacks and swallowed engine callback errors."""
        if not self.log.exists():
            return 0
        text = self.log.read_text(errors="replace")
        # Windows-only asyncio noise when the browser drops a connection (not reachable on the Linux server)
        noise = text.count("Exception in callback _ProactorBasePipeTransport._call_connection_lost")
        return text.count("Traceback") - noise + text.count("[emit error]")


@pytest.fixture
def make_app(tmp_path, jaumo):
    servers = []

    def factory(storage=None, **env):
        s = AppServer(storage or tmp_path / f"storage{len(servers)}", jaumo.base, env)
        servers.append(s)
        return s.start()

    yield factory
    for s in servers:
        s.stop()
        assert s.tracebacks() == 0, f"server log has tracebacks:\n{s.log.read_text(errors='replace')[-4000:]}"


@pytest.fixture
def app(make_app):
    return make_app()


@pytest.fixture
def api(app):
    return app.client()


def ok(r, status=None):
    if status is None:
        assert r.status_code < 400, f"{r.request.method} {r.request.url} -> {r.status_code} {r.text}"
    else:
        assert r.status_code == status, f"{r.request.method} {r.request.url} -> {r.status_code} {r.text}"
    return r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text


FAST_DELAYS = {k: [0, 0.02] for k in ("after_signup", "after_location", "after_refresh", "after_profile", "before_photo",
                                      "after_photo", "between_swipes", "between_batches", "before_message")}


def setup_ready(api, *, photos=6, require_proxy=False, max_swipes=6, **settings):
    """APK profile + fast config + photos; returns config id."""
    apk = ok(api.post("/api/apk-profiles", json={"name": "Good APK", "client_id": "good-client",
                                                  "sign_secret": "good-secret", "user_agent": "Android 202609.1.4 (1001864) (GooglePlay;Free)"}))
    conf = ok(api.get("/api/configs"))[0]
    s = {**conf["settings"], "require_proxy": require_proxy, "max_swipes": max_swipes, "delays": FAST_DELAYS, **settings}
    ok(api.put(f"/api/configs/{conf['id']}", json={"name": conf["name"], "apk_profile_id": apk["id"], "settings": s}))
    if photos:
        files = [("files", (f"p{i}.jpg", jpeg_bytes(i), "image/jpeg")) for i in range(photos)]
        res = ok(api.post("/api/photos", files=files))
        assert res["saved"] == photos, res
    return conf["id"]


def wait_runs_done(api, ids, timeout=60):
    def done():
        runs = [ok(api.get(f"/api/runs/{i}")) for i in ids]
        return runs if all(r["status"] not in ("queued", "running") for r in runs) else None
    return wait_until(done, timeout=timeout, msg=f"runs {ids} to finish")
