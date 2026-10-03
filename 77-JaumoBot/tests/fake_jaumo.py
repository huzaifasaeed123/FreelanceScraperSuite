"""
Configurable fake Jaumo API used by the test-suite.

* Verifies the request signature of EVERY call with an independent copy of the
  original script's algorithm — a signing bug anywhere fails the request (401)
  and is recorded in state["bad_signatures"].
* Checks the Jaumo headers and keeps per-user state (likes, gallery, tokens).
* Behaviour is switched per test via POST /__control.
"""

import asyncio
import hashlib
import itertools
from urllib.parse import parse_qs, quote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

SECRETS = {"good-client": "good-secret", "other-client": "other-secret", "banned-client": "banned-secret"}
DEFAULT_CONTROL = {
    "banned_clients": ["banned-client"],
    "block_after_likes": 0,        # 0 = never; else like N+1 returns 403
    "verification_required": False,  # every like returns Jaumo's "Verification required" 403 (code 4031)
    "match_every": 3,              # every k-th like matches (0 = never)
    "cards_per_batch": 5,
    "batches": 1000,               # zapping batches with cards before the deck is empty
    "photo_warning": False,
    "no_compliance_link": False,
    "access_token_uses": 0,        # 0 = unlimited; else access token expires after N authed calls
    "signup_fail": False,
    "header_message_fail": False,
    "zapping_status": 200,
    "zapping_script": [],          # bodies served first, one per zapping call (e.g. a Jaumo pause), then normal
    "empty_deck": None,            # body once the deck is empty (default {"items": []}), e.g. Jaumo's unlock dialog
    "slow_ms": 0,
    "user_id_start": 500000000,
    "unseen": {"likes": 4, "visits": 7, "conversations": 2, "matches": 3, "requests": 1, "communities": 0},
    "mutual_ids": ["9001", "9002", "9003"],   # matches list (likes.mutual), 2 per page
    "unseen_status": 200,
    "about_status": 200,           # answer to PUT me/data/aboutme
    "upload_status": 200,          # answer to the photo upload (e.g. 422 = image refused)
    "username_status": 200,        # answer to PUT me/username
}

app = FastAPI()
state = {}
_ids = itertools.count(1)


def reset():
    state.clear()
    state.update(control=dict(DEFAULT_CONTROL), requests=[], bad_signatures=[], bad_headers=[],
                 tokens={}, users={}, registrations=[], messages=[], uploads=[], likes=[], dislikes=[], about=[],
                 usernames=[])
    state["next_user"] = itertools.count(DEFAULT_CONTROL["user_id_start"])


reset()


# --- reference signature (copied from the ORIGINAL standalone script) -------

def _orig_urlencode(s):
    if not s:
        return ""
    encoded = quote(s, safe="")
    encoded = encoded.replace("+", "%20")
    encoded = encoded.replace("*", "%2A")
    encoded = encoded.replace("%7E", "~")
    return encoded


def reference_signature(secret, method, full_url, access_token="", body=b""):
    encoded_url = _orig_urlencode(full_url)
    idx = encoded_url.find("%2Fv2")
    path_from_v2 = encoded_url[idx:] if idx >= 0 else encoded_url
    encoded_token = _orig_urlencode(access_token) if access_token else ""
    message = f"{secret}&{method}&{path_from_v2}&{encoded_token}&"
    data = message.encode("utf-8")
    if body:
        data += body
    return f"2:{hashlib.sha1(data).hexdigest()}"


# --- middleware: signature + header checks ----------------------------------

@app.middleware("http")
async def verify(request: Request, call_next):
    path = request.url.path
    if path.startswith("/__") or path == "/ip":   # control + proxy-check endpoints are not Jaumo API
        return await call_next(request)
    body = await request.body()
    c = state["control"]
    if c["slow_ms"]:
        await asyncio.sleep(c["slow_ms"] / 1000)
    h = request.headers
    client_id = h.get("jaumo-client-token", "")
    token = h.get("authorization", "")[7:] if h.get("authorization", "").startswith("Bearer ") else ""
    rec = {"method": request.method, "path": path, "query": request.url.query, "device": h.get("jaumo-device-id"),
           "client": client_id, "ua": h.get("user-agent"), "token": token, "via_proxy": h.get("x-test-proxy")}
    state["requests"].append(rec)

    missing = [k for k in ("jaumo-package-id", "jaumo-client-token", "user-agent", "jaumo-device-id", "jaumo-device", "jaumo-os")
               if not h.get(k)]
    if missing:
        state["bad_headers"].append({**rec, "missing": missing})
        return JSONResponse({"error": "missing headers", "missing": missing}, 400)
    secret = SECRETS.get(client_id)
    if not secret:
        return JSONResponse({"error": "invalid_client"}, 401)
    expected = reference_signature(secret, request.method, str(request.url), token, body)
    if h.get("jaumo-signature") != expected:
        state["bad_signatures"].append({**rec, "got": h.get("jaumo-signature"), "expected": expected})
        return JSONResponse({"error": "invalid signature"}, 401)
    request.state.body = body
    request.state.token = token
    return await call_next(request)


def _form(request):
    return {k: v[0] for k, v in parse_qs(request.state.body.decode("utf-8", "replace"), keep_blank_values=True).items()}


def _user(request):
    """Resolve the bearer token to a user; None when missing/invalid/expired."""
    tok = state["tokens"].get(request.state.token)
    if not tok or tok["kind"] != "access" or tok.get("revoked"):
        return None
    limit = state["control"]["access_token_uses"]
    tok["uses"] += 1
    if limit and tok["uses"] > limit:
        tok["revoked"] = True
        return None
    return state["users"][tok["user"]]


def _unauth():
    return JSONResponse({"error": "invalid_token"}, 401)


def _base(request):
    return f"{request.url.scheme}://{request.url.netloc}/v2"


# --- control ----------------------------------------------------------------

@app.post("/__control")
async def control(request: Request):
    state["control"].update(await request.json())
    return state["control"]


@app.post("/__reset")
def do_reset():
    reset()
    return {"ok": True}


@app.get("/__state")
def get_state():
    return {k: v for k, v in state.items() if k not in ("next_user",)}


@app.get("/ip")
def ip(request: Request):
    return {"ip": "203.0.113.7", "country": "DE", "city": "Berlin", "via_proxy": request.headers.get("x-test-proxy")}


# --- auth -------------------------------------------------------------------

@app.post("/v2/auth/token")
async def auth_token(request: Request):
    f = _form(request)
    if f.get("client_id") != request.headers.get("jaumo-client-token"):
        return JSONResponse({"error": "client mismatch"}, 400)
    if f.get("grant_type") == "client_credentials":
        if f["client_id"] in state["control"]["banned_clients"]:
            return JSONResponse({"error": "invalid_client", "error_description": "client banned"}, 401)
        tok = f"client-{next(_ids)}"
        state["tokens"][tok] = {"kind": "client", "uses": 0}
        return {"access_token": tok, "token_type": "bearer", "expires_in": 3600}
    if f.get("grant_type") == "refresh_token":
        ref = state["tokens"].get(f.get("refresh_token"))
        if not ref or ref["kind"] != "refresh":
            return JSONResponse({"error": "invalid_grant"}, 400)
        acc = f"acc-{next(_ids)}"
        state["tokens"][acc] = {"kind": "access", "user": ref["user"], "uses": 0}
        return {"access_token": acc, "refresh_token": f.get("refresh_token"), "expires_in": 3600}
    return JSONResponse({"error": "unsupported_grant_type"}, 400)


# --- signup -----------------------------------------------------------------

@app.get("/v2/signup/defaults")
def defaults(request: Request):
    tok = state["tokens"].get(request.state.token)
    if not tok or tok["kind"] != "client":
        return _unauth()
    return {"gender": [1, 2],
            "relationship_search": {"items": [{"value": "FLIRT", "title": "Flirt"}, {"value": "FRIENDSHIP", "title": "Friends"}]},
            "dating_relationship_search": {"items": [{"value": "FLIRT"}, {"value": "FRIENDSHIP"}]}}


@app.post("/v2/signup/register")
async def register(request: Request):
    tok = state["tokens"].get(request.state.token)
    if not tok or tok["kind"] != "client":
        return _unauth()
    f = _form(request)
    state["registrations"].append({"raw": request.state.body.decode(), "form": f, "device": request.headers.get("jaumo-device-id")})
    if state["control"]["signup_fail"]:
        return JSONResponse({"error": "signup rejected"}, 400)
    for field in ("relationship_search", "dating_relationship_search"):   # values the app knows
        if f.get(field) not in ("FLIRT", "FRIENDSHIP"):
            return JSONResponse({"error": f"invalid {field}", "value": f.get(field)}, 400)
    uid = next(state["next_user"])
    state["users"][uid] = {"id": uid, "name": f.get("name"), "device": request.headers.get("jaumo-device-id"),
                           "gallery": 0, "likes": 0, "batches": 0, "location": None}
    acc, ref = f"acc-{next(_ids)}", f"ref-{next(_ids)}"
    state["tokens"][acc] = {"kind": "access", "user": uid, "uses": 0}
    state["tokens"][ref] = {"kind": "refresh", "user": uid, "uses": 0}
    return {"accessToken": {"access_token": acc, "refresh_token": ref, "expires_in": 3600}}


@app.get("/v2/signup/city/bycoordinates")
def city(request: Request, latitude: str = "", longitude: str = ""):
    if not _user(request):
        return _unauth()
    return {"name": f"City@{latitude}", "countryId": 49}


@app.post("/v2/me/data/location/validate")
def validate(request: Request):
    u = _user(request)
    if not u:
        return _unauth()
    u["location"] = _form(request).get("ziporcity")
    return {"ok": True}


@app.get("/v2/me")
def me(request: Request):
    u = _user(request)
    if not u:
        return _unauth()
    b = _base(request)
    links = {"gallery": f"{b}/gallery/confirm", "zapping": {"pop": "zapping/pop/"}, "data": f"{b}/me/data"}
    if not state["control"]["no_compliance_link"]:
        links["compliance"] = {"gallery": f"{b}/gallery/upload"}
    return {"id": u["id"], "name": u["name"], "galleryCount": u["gallery"],
            "missingField": None if u["gallery"] else "photo", "links": links}


@app.get("/v2/me/data")
def me_data(request: Request):
    """MeData: edit links of the own profile (the app reads "aboutme" from here)."""
    u = _user(request)
    if not u:
        return _unauth()
    return {"aboutme": f"{_base(request)}/me/data/aboutme", "aboutMe": u.get("about")}


@app.put("/v2/me/data/aboutme")
def set_about(request: Request):
    u = _user(request)
    if not u:
        return _unauth()
    f = _form(request)
    state["about"].append({"user": u["id"], "form": f, "content_type": request.headers.get("content-type")})
    if state["control"]["about_status"] != 200:
        return JSONResponse({"error": "text rejected"}, state["control"]["about_status"])
    u["about"] = f.get("data")
    return {"ok": True}


@app.post("/v2/gallery/upload")
async def upload(request: Request):
    u = _user(request)
    if not u:
        return _unauth()
    body = request.state.body
    ok = b'name="file"' in body and b"\xff\xd8" in body and b'name="latitude"' in body
    state["uploads"].append({"user": u["id"], "bytes": len(body), "valid_multipart": ok})
    if not ok:
        return JSONResponse({"error": "bad upload"}, 400)
    if state["control"]["upload_status"] != 200:
        return JSONResponse({"message": "Image does not meet our guidelines"}, state["control"]["upload_status"])
    if state["control"]["photo_warning"]:
        return {"warning": "face not detected"}
    return {"url": f"https://img.fake/{u['id']}.jpg"}


@app.post("/v2/gallery/confirm")
def confirm(request: Request):
    u = _user(request)
    if not u:
        return _unauth()
    pid = next(_ids)
    return {"id": pid, "isProfilePhoto": False, "links": {"base": f"{_base(request)}/gallery/photo/{pid}"}}


@app.put("/v2/gallery/photo/{pid}")
def set_primary(pid: int, request: Request):
    u = _user(request)
    if not u:
        return _unauth()
    u["gallery"] += 1
    return {"id": pid, "isProfilePhoto": True}


# --- zapping ----------------------------------------------------------------

@app.get("/v2/zapping/pop/")
def zapping(request: Request):
    u = _user(request)
    if not u:
        return _unauth()
    c = state["control"]
    if c["zapping_status"] != 200:
        return JSONResponse({"error": "zapping unavailable"}, c["zapping_status"])
    if c["zapping_script"]:
        return c["zapping_script"].pop(0)
    if u["batches"] >= c["batches"]:
        return c["empty_deck"] if c["empty_deck"] is not None else {"items": []}
    u["batches"] += 1
    b = _base(request)
    items = []
    for _ in range(c["cards_per_batch"]):
        other = next(_ids) + 7000000
        items.append({"user": {"id": other, "links": {}},
                      "links": {"top": f"{b}/zapping/like/{other}", "flop": f"{b}/zapping/flop/{other}"}})
    return {"items": items}


@app.put("/v2/zapping/like/{other}")
def like(other: int, request: Request):
    u = _user(request)
    if not u:
        return _unauth()
    if state["control"]["verification_required"]:
        return JSONResponse({"missingField": "verification",
                             "primaryAction": {"type": "verification", "caption": "Verify your profile"},
                             "title": "Verification required",
                             "subtitle": "Please verify your profile to contact this user",
                             "error": {"message": "Verification required Please verify your profile", "code": 4031}}, 403)
    c = state["control"]
    if c["block_after_likes"] and u["likes"] >= c["block_after_likes"]:
        return JSONResponse({"error": "restricted"}, 403)
    u["likes"] += 1
    state["likes"].append({"user": u["id"], "other": other})
    matched = bool(c["match_every"]) and u["likes"] % c["match_every"] == 0
    return {"match": matched}


@app.put("/v2/zapping/flop/{other}")
def flop(other: int, request: Request):
    u = _user(request)
    if not u:
        return _unauth()
    state["dislikes"].append({"user": u["id"], "other": other})
    return {}


# --- messaging --------------------------------------------------------------

@app.post("/v2/conversation/user/{other}/header/")
def msg_header(other: str, request: Request):
    u = _user(request)
    if not u:
        return _unauth()
    if state["control"]["header_message_fail"]:
        return JSONResponse({"error": "header failed"}, 500)
    state["messages"].append({"user": u["id"], "to": other, "form": _form(request), "via": "header"})
    return {"ok": True}


@app.post("/v2/conversation/user/{other}/messages/")
def msg_messages(other: str, request: Request):
    u = _user(request)
    if not u:
        return _unauth()
    state["messages"].append({"user": u["id"], "to": other, "form": _form(request), "via": "messages"})
    return {"ok": True}


# --- API root + read-only stats (what the app uses for its badges) ------------------------

def _count(name):
    state[name] = state.get(name, 0) + 1


@app.get("/v2/")
def api_root(request: Request):
    if not _user(request):
        return _unauth()
    _count("root_calls")
    b = _base(request)
    return {"links": {"unseen": f"{b}/me/unseen/", "username": f"{b}/me/username",
                      "likes": {"in": f"{b}/me/likes/in/", "mutual": f"{b}/me/likes/mutual/", "out": f"{b}/me/likes/out/"},
                      "visits": {"in": f"{b}/me/visits/in/"},
                      "conversations": {"in": f"{b}/conversation/inbox/"}}}


@app.put("/v2/me/username")
def set_username(request: Request):
    u = _user(request)
    if not u:
        return _unauth()
    f = _form(request)
    state["usernames"].append({"user": u["id"], "form": f, "content_type": request.headers.get("content-type")})
    if state["control"]["username_status"] != 200:
        return JSONResponse({"error": "username rejected"}, state["control"]["username_status"])
    u["name"] = f.get("username")
    return {"ok": True}


@app.get("/v2/me/unseen/")
def unseen(request: Request):
    if not _user(request):
        return _unauth()
    c = state["control"]
    if c["unseen_status"] != 200:
        return JSONResponse({"error": "unavailable"}, c["unseen_status"])
    _count("unseen_calls")
    return c["unseen"]


@app.get("/v2/me/likes/mutual/")
def mutual(request: Request, page: int = 1):
    if not _user(request):
        return _unauth()
    _count("mutual_calls")
    ids = state["control"]["mutual_ids"]
    chunk = ids[(page - 1) * 2: page * 2]
    nxt = f"{_base(request)}/me/likes/mutual/?page={page + 1}" if page * 2 < len(ids) else None
    return {"items": [{"user": {"id": int(i)}, "isLocked": True} for i in chunk], "links": {"next": nxt, "previous": None}}
