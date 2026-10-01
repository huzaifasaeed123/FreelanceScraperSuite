"""Minimal forwarding HTTP proxy for tests: records Proxy-Authorization and tags requests."""

import base64
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

HOP = {"proxy-authorization", "proxy-connection", "connection", "keep-alive", "transfer-encoding", "te", "upgrade", "host"}


class FakeProxy:
    def __init__(self, name, user="puser", password="ppass"):
        self.name, self.user, self.password = name, user, password
        self.hits, self.auth_failures = 0, 0
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _forward(self):
                auth = self.headers.get("Proxy-Authorization", "")
                expected = "Basic " + base64.b64encode(f"{proxy.user}:{proxy.password}".encode()).decode()
                if auth != expected:
                    proxy.auth_failures += 1
                    self.send_response(407)
                    self.send_header("Proxy-Authenticate", 'Basic realm="test"')
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                proxy.hits += 1
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else None
                headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
                headers["X-Test-Proxy"] = proxy.name
                r = requests.request(self.command, self.path, headers=headers, data=body, timeout=30, allow_redirects=False)
                self.send_response(r.status_code)
                for k, v in r.headers.items():
                    if k.lower() not in HOP | {"content-length", "content-encoding"}:
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(r.content)))
                self.end_headers()
                self.wfile.write(r.content)

            do_GET = do_POST = do_PUT = do_DELETE = _forward

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def line(self):
        return f"127.0.0.1:{self.port}:{self.user}:{self.password}"

    def close(self):
        self.server.shutdown()
