"""
Jaumo automation engine: signup → set location → upload photo → swipe until
blocked / stopped, plus a separate messaging job for existing accounts.

Everything is instance-scoped so many runners can work in parallel threads,
each with its own proxy, device identity and APK credentials.

NOTE: the request layer (signature, headers, endpoints, payloads) is kept
byte-for-byte equivalent to the original standalone script. Do not change it
without re-checking against the decompiled APK.

Quick manual test (no admin panel):
    set JAUMO_CLIENT_ID / JAUMO_SIGN_SECRET / JAUMO_USER_AGENT env vars, then
    python -m bot.engine path/to/photo.jpg [proxy_line]
"""

import base64
import hashlib
import json
import os
import random
import threading
import uuid
from datetime import datetime, timezone
from urllib.parse import quote, urlencode

import requests

DEFAULT_BASE_URL = "https://api.jaumo.com/v2"

# Gender is always female; Jaumo uses 1 = male, 2 = female.
GENDER_FEMALE = 2
GENDER_MALE = 1

# ---------------------------------------------------------------------------
# Defaults (non-secret). The admin panel stores its own copy per config.
# ---------------------------------------------------------------------------

# Built-in female first names for "auto" naming (common in Germany / Europe).
AUTO_FEMALE_NAMES = [
    "Anna", "Emma", "Mia", "Sophia", "Hannah", "Emilia", "Lina", "Marie", "Lea", "Lena",
    "Clara", "Ella", "Leonie", "Amelie", "Luisa", "Johanna", "Laura", "Lara", "Sophie", "Nele",
    "Charlotte", "Mila", "Ida", "Frieda", "Greta", "Mathilda", "Paula", "Pia", "Lilly", "Maja",
    "Helena", "Elisa", "Antonia", "Isabella", "Jana", "Julia", "Katharina", "Carla", "Melina", "Nora",
    "Romy", "Zoe", "Alina", "Annika", "Miriam", "Sarah", "Lisa", "Nina", "Vanessa", "Jasmin",
    "Franziska", "Theresa", "Valentina", "Victoria", "Elena", "Rosa", "Luna", "Malia", "Mira", "Leni",
    "Fiona", "Selina", "Sina", "Svenja", "Tamara", "Tina", "Vivien", "Yvonne", "Larissa", "Kim",
    "Jule", "Josephine", "Isabel", "Hanna", "Elif", "Emely", "Finja", "Frida", "Gina", "Hailey",
    "Ronja", "Rebecca", "Ricarda", "Sabrina", "Sandra", "Saskia", "Stefanie", "Susanne", "Tanja", "Teresa",
    "Alexandra", "Andrea", "Angelina", "Anja", "Anke", "Anne", "Annabell", "Aylin", "Bianca", "Carina",
    "Caroline", "Celine", "Christina", "Claudia", "Daniela", "Denise", "Diana", "Elisabeth", "Eva", "Fabienne",
    "Felicitas", "Helen", "Ines", "Jacqueline", "Janina", "Jennifer", "Jessica", "Jill", "Juliane", "Karin",
    "Katja", "Kerstin", "Kristina", "Lucia", "Lucy", "Madeleine", "Magdalena", "Mara", "Marlene", "Martina",
    "Melanie", "Michelle", "Milena", "Monika", "Nadine", "Natalie", "Nicole", "Olivia", "Patricia", "Petra",
    "Ramona", "Regina", "Sabine", "Simone", "Sonja", "Stella", "Tatjana", "Ulrike", "Vera", "Viktoria",
    "Amira", "Aurelia", "Bella", "Carolin", "Chiara", "Delia", "Ela", "Elin", "Emilie", "Enna",
    "Esther", "Fenja", "Hedi", "Hermine", "Ilka", "Irina", "Isa", "Jara", "Kira", "Klara",
    "Liv", "Lotta", "Lou", "Luise", "Mareike", "Marla", "Merle", "Nelly", "Noemi", "Olga",
    "Rieke", "Rike", "Ruby", "Smilla", "Thea", "Tilda", "Toni", "Vicky", "Wiebke", "Zara",
    "Alessia", "Alicia", "Bettina", "Cora", "Daria", "Dana", "Edda", "Elaine", "Evelyn", "Grace",
]

DEFAULT_SETTINGS = {
    "request_timeout": 30,
    "delays": {
        "after_signup": [3, 6],
        "after_location": [2, 4],
        "after_refresh": [1, 3],
        "after_profile": [2, 5],
        "before_photo": [4, 8],
        "after_photo": [3, 6],
        "between_swipes": [2, 5],
        "between_batches": [5, 10],
        "before_message": [3, 7],
    },
    "like_ratio": 0.5,          # probability a card is liked (rest disliked)
    "max_swipes": 0,            # 0 = unlimited (run until blocked/stopped)
    "block_threshold": 3,       # consecutive failed actions → account blocked
    "max_empty_batches": 3,     # consecutive empty zapping batches → finish
    "age_min": 22,
    "age_max": 35,
    "name_source": "auto",      # auto = AUTO_FEMALE_NAMES, custom = name_pool
    "messaging_enabled": False, # allow the messaging job to use this config
    # Signup form fields (defaults = exactly what the original bot sent).
    "looking_for_gender": GENDER_MALE,
    "relationship_search": "FRIENDSHIP",
    "dating_relationship_search": "FRIENDSHIP",
    "allow_in_all_brands": True,
    "name_pool": [
        "Emma", "Sophia", "Olivia", "Ava", "Isabella", "Mia", "Charlotte",
        "Amelia", "Harper", "Evelyn", "Abigail", "Emily", "Madison", "Luna",
        "Chloe", "Grace", "Ella", "Lily", "Aria", "Zoe", "Nora", "Riley",
        "Layla", "Scarlett", "Hannah", "Victoria", "Stella", "Natalie",
        "Clara", "Elena", "Nina", "Rosa", "Lena", "Sara", "Julia",
    ],
    "photo_pool": [],           # photo filenames; empty = all uploaded photos
    "signup_photo_urls": [
        "https://i.jaumo.com/gallery_orig/113550,0339ee18d142fbf39e.jpg",
    ],
    "locations": [
        {"lat": "52.5200", "lon": "13.4050", "label": "Berlin"},
        {"lat": "48.1351", "lon": "11.5820", "label": "Munich"},
        {"lat": "50.1109", "lon": "8.6821", "label": "Frankfurt"},
        {"lat": "53.5511", "lon": "9.9937", "label": "Hamburg"},
        {"lat": "50.9375", "lon": "6.9603", "label": "Cologne"},
        {"lat": "48.7758", "lon": "9.1829", "label": "Stuttgart"},
        {"lat": "51.2277", "lon": "6.7735", "label": "Dusseldorf"},
        {"lat": "51.3397", "lon": "12.3731", "label": "Leipzig"},
        {"lat": "51.0504", "lon": "13.7373", "label": "Dresden"},
        {"lat": "49.4521", "lon": "11.0767", "label": "Nuremberg"},
    ],
    "devices": [
        {"manufacturer": "samsung", "model": "SM-S911B", "brand": "samsung"},
        {"manufacturer": "samsung", "model": "SM-A546B", "brand": "samsung"},
        {"manufacturer": "samsung", "model": "SM-G991B", "brand": "samsung"},
        {"manufacturer": "Google", "model": "Pixel 7", "brand": "google"},
        {"manufacturer": "Google", "model": "Pixel 8", "brand": "google"},
        {"manufacturer": "Xiaomi", "model": "2201116SG", "brand": "Redmi"},
        {"manufacturer": "OnePlus", "model": "CPH2449", "brand": "OnePlus"},
    ],
    "message_templates": [
        "Hey, how are you?",
        "Hi there! How's your day going?",
        "Hey! What are you up to?",
        "Hi! Nice to meet you :)",
        "Hey, what's up?",
    ],
}

DEFAULT_APK = {
    "client_id": "",
    "sign_secret": "",
    "user_agent": "Android 202609.1.4 (1001864) (GooglePlay;Free)",
    "package_id": "com.jaumo",
    "os_version": "14",
    "accept_language": "en_US",
}


class StopRequested(Exception):
    """Raised inside a runner when the admin pressed Stop."""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def jaumo_urlencode(s):
    if not s:
        return ""
    encoded = quote(s, safe="")
    encoded = encoded.replace("+", "%20")
    encoded = encoded.replace("*", "%2A")
    encoded = encoded.replace("%7E", "~")
    return encoded


def generate_device_id(android_id=None):
    if android_id is None:
        android_id = uuid.uuid4().hex[:16]
    device_info = json.dumps({"i": "", "aid": android_id, "s": ""}, separators=(",", ":"))
    return base64.b64encode(device_info.encode()).decode(), android_id


def _redact(value, key=""):
    """Return response data that is safe to print in diagnostic logs."""
    sensitive = {
        "access_token", "accesstoken", "refresh_token", "refreshtoken",
        "authorization", "password", "token",
    }
    normalized_key = str(key).lower().replace("-", "_")
    if any(name in normalized_key for name in sensitive):
        return "<redacted>"
    if isinstance(value, dict):
        return {k: _redact(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def proxy_url_to_dict(proxy_url):
    if not proxy_url:
        return None
    return {"http": proxy_url, "https": proxy_url}


def _print_log(level, msg):
    print(msg)


# ---------------------------------------------------------------------------
# Jaumo API client (one per bot / device identity)
# ---------------------------------------------------------------------------

class JaumoClient:
    def __init__(self, apk, proxy_url=None, timeout=30, device_id=None,
                 android_id=None, device_info=None, devices=None, log=None,
                 base_url=None):
        apk = {**DEFAULT_APK, **(apk or {})}
        self.client_id = apk["client_id"]
        self.sign_secret = apk["sign_secret"]
        self.user_agent = apk["user_agent"]
        self.package_id = apk["package_id"]
        self.os_version = apk["os_version"]
        self.accept_language = apk["accept_language"]
        self.base_url = base_url or os.environ.get("JAUMO_BASE_URL") or DEFAULT_BASE_URL
        self.proxies = proxy_url_to_dict(proxy_url)
        self.timeout = timeout
        if device_id is None:
            device_id, android_id = generate_device_id(android_id)
        self.device_id = device_id
        self.android_id = android_id
        self.device_info = device_info or random.choice(devices or DEFAULT_SETTINGS["devices"])
        self._log = log or _print_log

    def log(self, msg, level="info"):
        self._log(level, msg)

    # --- crypto / headers --------------------------------------------------

    def compute_signature(self, method, path_or_url, access_token="", body=b""):
        if path_or_url.startswith("http"):
            full_url = path_or_url
        else:
            full_url = self.base_url + "/" + path_or_url
        encoded_url = jaumo_urlencode(full_url)
        idx = encoded_url.find("%2Fv2")
        path_from_v2 = encoded_url[idx:] if idx >= 0 else encoded_url
        encoded_token = jaumo_urlencode(access_token) if access_token else ""

        message = f"{self.sign_secret}&{method}&{path_from_v2}&{encoded_token}&"
        data = message.encode("utf-8")
        if body:
            data += body if isinstance(body, bytes) else body.encode("utf-8")
        return f"2:{hashlib.sha1(data).hexdigest()}"

    def make_headers(self, method, url, access_token="", body=""):
        device_info = self.device_info
        return {
            "Jaumo-Package-Id": self.package_id,
            "Jaumo-Signature": self.compute_signature(method, url, access_token, body),
            "Jaumo-Client-Token": self.client_id,
            "User-Agent": self.user_agent,
            "Jaumo-Device-Id": self.device_id,
            "Jaumo-Device": f"{device_info['manufacturer']};{device_info['model']};{device_info['brand']}",
            "Jaumo-Os": self.os_version,
            "Accept-Language": self.accept_language,
            **({"Authorization": f"Bearer {access_token}"} if access_token else {}),
        }

    def _url(self, path):
        if path.startswith("http"):
            return path
        return f"{self.base_url}/{path}"

    def print_response_details(self, label, resp):
        """Log enough server information to distinguish success from restriction."""
        lines = [f"  [{label}] HTTP {resp.status_code} {resp.request.method} {resp.url}"]
        useful_headers = {
            key: value for key, value in resp.headers.items()
            if key.lower() in {
                "content-type", "retry-after", "jaumo-node", "jaumo-request-time",
                "x-request-id", "request-id",
            }
        }
        if useful_headers:
            lines.append(f"  [{label}] Headers: {json.dumps(useful_headers, ensure_ascii=False)}")
        try:
            payload = _redact(resp.json())
            rendered = json.dumps(payload, ensure_ascii=False, indent=2)
        except (ValueError, TypeError):
            rendered = resp.text or "<empty body>"
        # Avoid flooding the log if a gateway returns a large HTML page.
        if len(rendered) > 4000:
            rendered = rendered[:4000] + "\n... <truncated>"
        lines.append(f"  [{label}] Body:\n{rendered}")
        self.log("\n".join(lines), "debug")

    # --- transport ---------------------------------------------------------

    def _post(self, path, body_params=None, access_token=""):
        url = self._url(path)
        body = urlencode(body_params) if body_params else ""
        headers = self.make_headers("POST", url, access_token=access_token, body=body)
        if body:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        return requests.post(
            url, headers=headers, data=body if body else None,
            proxies=self.proxies, timeout=self.timeout,
        )

    def _put(self, path, body_params=None, access_token=""):
        url = self._url(path)
        body = urlencode(body_params) if body_params else ""
        headers = self.make_headers("PUT", url, access_token=access_token, body=body)
        if body:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        return requests.put(
            url, headers=headers, data=body if body else None,
            proxies=self.proxies, timeout=self.timeout,
        )

    def _get(self, path, access_token=""):
        url = self._url(path)
        headers = self.make_headers("GET", url, access_token=access_token)
        return requests.get(url, headers=headers, proxies=self.proxies, timeout=self.timeout)

    def _post_multipart(self, path, image_path, body_params=None, access_token=""):
        """Prepare the multipart bytes first so the signature covers the exact body."""
        url = self._url(path)
        headers = self.make_headers("POST", url, access_token=access_token, body=b"")
        headers.pop("Jaumo-Signature", None)

        session = requests.Session()
        with open(image_path, "rb") as image_file:
            request = requests.Request(
                "POST",
                url,
                headers=headers,
                data=body_params or {},
                files={"file": ("file.jpg", image_file, "image/jpeg")},
            )
            prepared = session.prepare_request(request)

        prepared_body = prepared.body or b""
        if not isinstance(prepared_body, bytes):
            prepared_body = prepared_body.encode("utf-8")
        prepared.headers["Jaumo-Signature"] = self.compute_signature(
            "POST", url, access_token, prepared_body
        )
        return session.send(prepared, proxies=self.proxies, timeout=self.timeout)

    # --- API calls ---------------------------------------------------------

    def get_client_token(self):
        resp = self._post("auth/token", {"grant_type": "client_credentials", "client_id": self.client_id})
        self.last_client_token_status = resp.status_code
        self.last_client_token_body = (resp.text or "")[:200]
        if resp.status_code in (200, 201):
            self.log("[CLIENT_TOKEN] OK")
            return resp.json().get("access_token")
        server_header = resp.headers.get("server", "").lower()
        via_header = resp.headers.get("via", "")
        ct = resp.headers.get("content-type", "")
        self.log(
            f"[CLIENT_TOKEN] FAIL {resp.status_code}\n"
            f"  URL: {resp.url}\n"
            f"  Response headers: {dict(resp.headers)}\n"
            f"  Body: {resp.text}\n"
            f"  [DEBUG] server={server_header!r}  via={via_header!r}  content-type={ct!r}",
            "error",
        )
        return None

    def get_signup_defaults(self, client_bearer):
        """APK calls GET signup/defaults before registering — returns allowed values."""
        resp = self._get("signup/defaults", access_token=client_bearer)
        if resp.status_code == 200:
            self.log("[DEFAULTS] OK")
            return resp.json()
        self.log(f"[DEFAULTS] FAIL {resp.status_code}: {resp.text}", "warning")
        return None

    def refresh_access_token(self, refresh_token):
        resp = self._post("auth/token", {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        })
        if resp.status_code in (200, 201):
            try:
                data = resp.json()
            except ValueError:
                self.log("[REFRESH] FAIL — successful HTTP status but response was not JSON", "error")
                return None, None

            # Most token responses are flat, but accept the accessToken container
            # used by some Jaumo responses as well.
            token_data = data.get("accessToken") if isinstance(data.get("accessToken"), dict) else data
            new_access = token_data.get("access_token")
            new_refresh = token_data.get("refresh_token") or refresh_token
            if not new_access:
                self.log(
                    "[REFRESH] FAIL — response contained no access_token; "
                    f"keys={list(data.keys())}", "error",
                )
                return None, None
            expires_in = token_data.get("expires_in")
            self.log(f"[REFRESH] OK — access token present; expires_in={expires_in}")
            return new_access, new_refresh
        self.log(f"[REFRESH] FAIL {resp.status_code}: {resp.text}", "error")
        return None, None

    def signup_account(self, client_bearer, profile):
        resp = self._post("signup/register", {
            "gender": profile["gender"],
            "birthday": profile["birthday"],
            "looking_for_gender": profile["looking_for_gender"],
            "photo_url": profile["photo_url"],
            "name": profile["name"],
            "relationship_search": profile.get("relationship_search", "FRIENDSHIP"),
            "dating_relationship_search": profile.get("dating_relationship_search", "FRIENDSHIP"),
            "allow_in_all_brands": profile.get("allow_in_all_brands", "1"),
            "location_permission": "",
            "notifications_services": "",
        }, access_token=client_bearer)
        if resp.status_code in (200, 201):
            tokens = resp.json()["accessToken"]
            self.log(f"[SIGNUP] OK — {profile['name']}")
            return tokens["access_token"], tokens.get("refresh_token")
        self.log(f"[SIGNUP] FAIL {resp.status_code}: {resp.text}", "error")
        return None, None

    def set_location(self, access_token, loc):
        # Step 1: resolve coordinates to a city
        path = f"signup/city/bycoordinates?longitude={loc['lon']}&latitude={loc['lat']}"
        resp = self._get(path, access_token=access_token)
        city = None
        country_id = None
        if resp.status_code == 200:
            data = resp.json()
            city = data.get("name") or data.get("city") or data.get("ziporcity") or loc["label"]
            country_id = data.get("countryId") or data.get("country_id") or data.get("id")
            self.log(f"[LOCATION] Resolved: {city} (country={country_id})")
        else:
            self.log(f"[LOCATION] City lookup {resp.status_code}: {resp.text}", "warning")

        # Step 2: validate/set location
        if country_id and city:
            resp2 = self._post("me/data/location/validate",
                               {"countryId": country_id, "ziporcity": city},
                               access_token=access_token)
            if resp2.status_code in (200, 201):
                self.log(f"[LOCATION] Set OK — {city}")
                return True
            self.log(f"[LOCATION] Validate {resp2.status_code}: {resp2.text}", "warning")

        # Fallback: try setting location directly
        if country_id:
            resp3 = self._post("me/data/location", {"data": country_id}, access_token=access_token)
            if resp3.status_code in (200, 201):
                self.log("[LOCATION] Set via fallback OK")
                return True
            self.log(f"[LOCATION] Fallback {resp3.status_code}: {resp3.text}", "warning")

        return False

    def get_profile(self, access_token, include_status=False):
        resp = self._get("me", access_token=access_token)
        if resp.status_code == 200:
            data = resp.json()
            return (data, resp.status_code) if include_status else data
        self.log(f"[PROFILE] FAIL {resp.status_code}: {resp.text}", "error")
        return (None, resp.status_code) if include_status else None

    def upload_profile_photo(self, access_token, refresh_token, me, image_path, loc):
        """Upload, confirm, and select one JPEG as the primary profile photo."""
        if not os.path.isfile(image_path):
            self.log(f"[PHOTO] FAIL — file not found: {image_path}", "error")
            return False, access_token, refresh_token
        if os.path.getsize(image_path) == 0:
            self.log(f"[PHOTO] FAIL — image is empty: {image_path}", "error")
            return False, access_token, refresh_token

        links = me.get("links") or {}
        compliance = links.get("compliance") or {}
        upload_url = compliance.get("gallery") if isinstance(compliance, dict) else None
        confirmation_url = links.get("gallery")
        if not upload_url:
            self.log("[PHOTO] FAIL — /me did not provide links.compliance.gallery", "error")
            return False, access_token, refresh_token
        if not confirmation_url:
            self.log("[PHOTO] FAIL — /me did not provide links.gallery", "error")
            return False, access_token, refresh_token
        location_fields = {
            "latitude": loc["lat"],
            "longitude": loc["lon"],
        }
        self.log(f"[PHOTO] Uploading {os.path.basename(image_path)}")
        upload_resp = self._post_multipart(
            upload_url,
            image_path,
            body_params=location_fields,
            access_token=access_token,
        )
        self.print_response_details("PHOTO UPLOAD", upload_resp)
        if upload_resp.status_code not in (200, 201, 202):
            return False, access_token, refresh_token

        try:
            upload_data = upload_resp.json()
        except ValueError:
            self.log("[PHOTO] FAIL — upload response was not JSON", "error")
            return False, access_token, refresh_token

        warning = upload_data.get("warning")
        uploaded_url = upload_data.get("url")
        if warning:
            self.log("[PHOTO] NOT CONFIRMED — server returned a compliance warning", "error")
            return False, access_token, refresh_token
        if not uploaded_url:
            self.log("[PHOTO] FAIL — upload response did not contain a URL", "error")
            return False, access_token, refresh_token

        # The APK confirms the returned URL through the normal gallery endpoint.
        confirmation_fields = {
            "url": uploaded_url,
            **location_fields,
        }
        confirm_resp = self._post(confirmation_url, confirmation_fields, access_token=access_token)
        self.print_response_details("PHOTO CONFIRM", confirm_resp)
        if confirm_resp.status_code not in (200, 201, 204):
            self.log(f"[PHOTO] Confirmation failed ({confirm_resp.status_code}) — skipping", "error")
            return False, access_token, refresh_token

        try:
            photo = confirm_resp.json()
        except ValueError:
            self.log("[PHOTO] FAIL — confirmation did not return a Photo object", "error")
            return False, access_token, refresh_token
        if not isinstance(photo, dict):
            self.log("[PHOTO] FAIL — confirmation JSON was not a Photo object", "error")
            return False, access_token, refresh_token

        if photo.get("isProfilePhoto") is True:
            self.log("[PHOTO] Upload accepted; image is already the profile picture")
            return True, access_token, refresh_token

        photo_links = photo.get("links") or {}
        set_profile_url = photo_links.get("base") if isinstance(photo_links, dict) else None
        if not set_profile_url:
            self.log("[PHOTO] FAIL — confirmed Photo did not provide links.base", "error")
            return False, access_token, refresh_token
        # SetProfilePhoto in the APK sends an authenticated PUT with an empty map
        # to the confirmed Photo object's dynamically supplied links.base URL.
        set_profile_resp = self._put(set_profile_url, access_token=access_token)
        self.print_response_details("PHOTO SET PRIMARY", set_profile_resp)
        if set_profile_resp.status_code not in (200, 201, 204):
            return False, access_token, refresh_token

        # Some API versions return the updated Photo; when present, enforce the
        # server's primary-photo flag. A 204 is also a valid PUT completion.
        if set_profile_resp.content:
            try:
                updated_photo = set_profile_resp.json()
            except ValueError:
                updated_photo = None
            if isinstance(updated_photo, dict) and updated_photo.get("isProfilePhoto") is False:
                self.log("[PHOTO] FAIL — server accepted PUT but photo is not primary", "error")
                return False, access_token, refresh_token

        self.log("[PHOTO] Upload, confirmation, and profile-picture selection accepted")
        return True, access_token, refresh_token

    def get_zapping_cards(self, zapping_url, access_token, include_status=False):
        resp = self._get(zapping_url, access_token=access_token)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                cards = data
            else:
                cards = data.get("items", data.get("cards", []))
            self.log(f"[ZAPPING] Got {len(cards)} cards")
            return (cards, resp.status_code) if include_status else cards
        self.log(f"[ZAPPING] FAIL {resp.status_code}: {resp.text}", "warning")
        return ([], resp.status_code) if include_status else []

    def like_user(self, like_url, access_token):
        resp = self._put(like_url, access_token=access_token)
        try:
            data = resp.json()
        except Exception:
            data = {}
        ok = resp.status_code in (200, 201, 204)
        self.print_response_details("LIKE SUCCESS" if ok else "LIKE FAILED", resp)
        if resp.status_code == 403:
            self.log("  [LIKE FAILED] The server restricted this action; it was not a like.", "warning")
        matched = bool(ok and isinstance(data, dict)
                       and (data.get("match") is True or data.get("matched") is True))
        return resp.status_code, ok, matched, data

    def dislike_user(self, dislike_url, access_token):
        resp = self._put(dislike_url, access_token=access_token)
        ok = resp.status_code in (200, 201, 204)
        self.print_response_details("DISLIKE OK" if ok else "DISLIKE FAILED", resp)
        return resp.status_code, ok

    def send_message_to(self, user_id, text, access_token, conv_url=None):
        # APK flow: POST to conversation/user/{id}/header/ to open conversation,
        # then POST message to the messages URL returned in response.
        message_id = str(uuid.uuid4())

        # Step 1: open/get conversation header
        header_url = conv_url or f"conversation/user/{user_id}/header/"
        resp = self._post(header_url, {"text": text, "messageId": message_id}, access_token=access_token)
        if resp.status_code in (200, 201):
            self.log(f"  [MSG] Sent to {user_id}")
            return True
        self.log(f"  [MSG] header POST {resp.status_code}: {resp.text}", "warning")

        # Step 2: fallback — try messages sub-endpoint
        msgs_url = f"conversation/user/{user_id}/messages/"
        resp2 = self._post(msgs_url, {"text": text, "messageId": message_id}, access_token=access_token)
        if resp2.status_code in (200, 201):
            self.log(f"  [MSG] Sent to {user_id} (via messages endpoint)")
            return True
        self.log(f"  [MSG] messages POST {resp2.status_code}: {resp2.text}", "warning")

        self.log(f"  [MSG] FAIL to {user_id}", "error")
        return False


# ---------------------------------------------------------------------------
# Runner base: logging, events, stop handling, delays
# ---------------------------------------------------------------------------

class _RunnerBase:
    def __init__(self, settings, emit=None, stop_event=None):
        self.settings = {**DEFAULT_SETTINGS, **(settings or {})}
        self.settings["delays"] = {**DEFAULT_SETTINGS["delays"], **(self.settings.get("delays") or {})}
        self._emit = emit or (lambda kind, data: _print_log("info", data.get("msg", f"[{kind}] {data}")) if kind == "log" else None)
        self.stop_event = stop_event or threading.Event()

    def emit(self, kind, **data):
        try:
            self._emit(kind, data)
        except Exception as e:  # never let a sink error kill the bot
            print(f"[emit error] {kind}: {e}")

    def log(self, msg, level="info"):
        self.emit("log", level=level, msg=msg)

    def _client_log(self, level, msg):
        self.log(msg, level)

    def step(self, name):
        self.emit("step", step=name)

    def check_stop(self):
        if self.stop_event.is_set():
            raise StopRequested()

    def delay(self, key):
        lo, hi = self.settings["delays"].get(key) or (0, 0)
        t = round(random.uniform(float(lo), float(hi)), 2)
        self.log(f"  [DELAY] {key} {t}s", "debug")
        if self.stop_event.wait(t):
            raise StopRequested()


# ---------------------------------------------------------------------------
# Signup + swipe runner
# ---------------------------------------------------------------------------

class BotRunner(_RunnerBase):
    """
    Emits events through `emit(kind, data)`:
        log             {level, msg}
        step            {step}
        account_created {account dict}
        account_update  {fields...}
        swipe           {user_id, action, matched}

    run() returns {"status": done|blocked|failed|stopped, "reason": str}.
    """

    def __init__(self, settings, apk, photo_path, proxy_url=None, name=None,
                 emit=None, stop_event=None):
        super().__init__(settings, emit, stop_event)
        self.apk = apk
        self.photo_path = photo_path
        self.proxy_url = proxy_url
        self.name = name
        self.client = JaumoClient(
            apk, proxy_url=proxy_url, timeout=self.settings["request_timeout"],
            devices=self.settings["devices"], log=self._client_log,
        )
        self.access_token = None
        self.refresh_token = None
        self.counters = {"swipes": 0, "liked": 0, "disliked": 0, "matches": 0}
        self.ready = False  # signup + photo verified

    # --- identity ----------------------------------------------------------

    def make_profile(self):
        s = self.settings
        age_min, age_max = int(s["age_min"]), int(s["age_max"])
        if age_max < age_min:
            age_min, age_max = age_max, age_min
        year = datetime.now().year - random.randint(age_min, age_max)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        # The admin panel assigns (and reserves) the name at launch; this is the CLI fallback.
        pool = AUTO_FEMALE_NAMES if s.get("name_source") == "auto" else (s["name_pool"] or AUTO_FEMALE_NAMES)
        name = self.name or random.choice(pool)
        return {
            "name": name,
            "gender": GENDER_FEMALE,
            "birthday": f"{year}-{month:02d}-{day:02d}",
            "looking_for_gender": int(s.get("looking_for_gender") or GENDER_MALE),
            "photo_url": random.choice(s["signup_photo_urls"] or DEFAULT_SETTINGS["signup_photo_urls"]),
            "relationship_search": s.get("relationship_search") or "FRIENDSHIP",
            "dating_relationship_search": s.get("dating_relationship_search") or "FRIENDSHIP",
            "allow_in_all_brands": "1" if s.get("allow_in_all_brands", True) else "0",
        }

    def _set_tokens(self, access, refresh):
        self.access_token = access
        self.refresh_token = refresh
        self.emit("account_update", access_token=access, refresh_token=refresh)

    def _refresh(self):
        if not self.refresh_token:
            return False
        new_tok, new_ref = self.client.refresh_access_token(self.refresh_token)
        if new_tok:
            self._set_tokens(new_tok, new_ref)
            return True
        return False

    # --- main flow ---------------------------------------------------------

    def run(self):
        try:
            return self._run()
        except StopRequested:
            self.log("[STOP] Stopped by admin", "warning")
            if self.access_token:
                # A fully set-up account stays usable after an admin stop.
                self.emit("account_update", status="active" if self.ready else "stopped")
            return {"status": "stopped", "reason": "stopped by admin"}
        except requests.RequestException as e:
            self.log(f"[NETWORK] {type(e).__name__}: {e}", "error")
            if self.access_token:
                self.emit("account_update", status="active" if self.ready else "failed")
            return {"status": "failed", "reason": f"network error: {type(e).__name__}"}
        except Exception as e:
            self.log(f"[CRASH] {type(e).__name__}: {e}", "error")
            if self.access_token:
                self.emit("account_update", status="failed")
            return {"status": "failed", "reason": f"{type(e).__name__}: {e}"}

    def _run(self):
        c = self.client
        profile = self.make_profile()
        loc = random.choice(self.settings["locations"] or DEFAULT_SETTINGS["locations"])

        if self.proxy_url:
            host = self.proxy_url.rsplit("@", 1)[-1]
            self.log(f"[PROXY] Using {host}")
        else:
            self.log("[PROXY] No proxy — direct connection", "warning")
        self.log(f"--- {profile['name']} | F | {profile['birthday']} | {loc['label']} | "
                 f"{c.device_info['model']} ---")

        # 1. Client token
        self.step("client_token")
        self.check_stop()
        client_bearer = c.get_client_token()
        # Health signal for the APK profile (network errors raise before this
        # point and are not counted against the APK).
        if client_bearer:
            self.emit("apk_check", ok=True)
        else:
            status = getattr(c, "last_client_token_status", None)
            self.emit("apk_check", ok=False,
                      error=f"client token HTTP {status}: {getattr(c, 'last_client_token_body', '')}")
            return {"status": "failed", "reason": f"client token failed (HTTP {status})"}

        # 1b. Fetch signup defaults (APK does this before registering)
        c.get_signup_defaults(client_bearer)

        # 2. Signup
        self.step("signup")
        self.check_stop()
        access_token, refresh_token = c.signup_account(client_bearer, profile)
        if not access_token:
            return {"status": "failed", "reason": "signup failed"}
        self.access_token, self.refresh_token = access_token, refresh_token
        self.emit("account_created", account={
            "created": datetime.now(timezone.utc).isoformat(),
            "android_id": c.android_id,
            "device_id": c.device_id,
            "device_info": c.device_info,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "location": loc["label"],
            "photo": os.path.basename(self.photo_path) if self.photo_path else None,
            "status": "signing_up",
            **profile,
        })
        self.delay("after_signup")

        # 3. Set location
        self.step("location")
        c.set_location(self.access_token, loc)
        self.delay("after_location")

        # NOTE: APK uses the signup access_token directly — no refresh_token call here.

        # 4. Get profile
        self.step("profile")
        me, profile_status = c.get_profile(self.access_token, include_status=True)
        if profile_status == 401 and self.refresh_token:
            self.log("[PROFILE] Fresh token was rejected; refreshing once and retrying /me", "warning")
            if self._refresh():
                me, profile_status = c.get_profile(self.access_token, include_status=True)
        if not me:
            self.emit("account_update", status="failed")
            return {"status": "failed", "reason": "could not fetch profile"}
        if me.get("id"):
            self.emit("account_update", jaumo_id=str(me["id"]))

        missing = me.get("missingField") or me.get("missingData") or me.get("missing")
        if missing:
            self.log(f"[INFO] Missing data: {missing}")
        self.log(f"[DEBUG] galleryCount: {me.get('galleryCount')}", "debug")
        self.log(f"[DEBUG] profile links: {json.dumps(me.get('links', {}), indent=2)}", "debug")
        self.delay("after_profile")

        # 5. Upload and confirm the profile photo before any zapping action.
        self.step("photo")
        self.delay("before_photo")
        photo_uploaded, access_token, refresh_token = c.upload_profile_photo(
            self.access_token, self.refresh_token, me, self.photo_path, loc,
        )
        self.access_token, self.refresh_token = access_token, refresh_token
        if not photo_uploaded:
            self.log("[SKIP] Photo upload was not accepted; likes were not attempted.", "error")
            self.emit("account_update", status="photo_failed", photo_uploaded=False)
            return {"status": "failed", "reason": "photo upload not accepted"}
        self.delay("after_photo")

        # Reload /me because its links, missingField and galleryCount may change
        # after the confirmation request.
        self.step("verify")
        me = c.get_profile(self.access_token)
        if not me:
            self.emit("account_update", status="photo_failed")
            return {"status": "failed", "reason": "could not verify profile after photo"}

        gallery_count = me.get("galleryCount") or 0
        missing_after_upload = me.get("missingField") or me.get("missingData") or me.get("missing")
        self.log(f"[PHOTO VERIFY] galleryCount={gallery_count}; missing={missing_after_upload}")
        if gallery_count < 1 or missing_after_upload == "photo":
            self.log("[SKIP] Server has not registered the photo; likes were not attempted.", "error")
            self.emit("account_update", status="photo_failed", gallery_count=gallery_count)
            return {"status": "failed", "reason": "photo not registered by server"}
        self.ready = True
        self.emit("account_update", status="active", photo_uploaded=True, gallery_count=gallery_count)

        zapping_url = None
        links = me.get("links", {})
        zapping = links.get("zapping", {})
        if isinstance(zapping, dict):
            zapping_url = zapping.get("pop")
        if not zapping_url and isinstance(zapping, str) and zapping:
            zapping_url = zapping
        if not zapping_url:
            zapping_url = "zapping/pop/"

        # 6. Swipe until blocked / stopped / out of cards / max_swipes
        self.step("swiping")
        result = self._swipe_loop(zapping_url)
        self.step("finished")
        self.log(f"--- Done: {result['status']} ({result['reason']}) — "
                 f"liked={self.counters['liked']} disliked={self.counters['disliked']} "
                 f"matches={self.counters['matches']} ---")
        return result

    def _swipe_loop(self, zapping_url):
        c = self.client
        s = self.settings
        like_ratio = float(s["like_ratio"])
        max_swipes = int(s["max_swipes"] or 0)
        block_threshold = max(1, int(s["block_threshold"]))
        max_empty = max(1, int(s["max_empty_batches"]))

        consecutive_fail = 0
        empty_batches = 0
        first_batch = True
        last_fail_reason = ""

        def blocked():
            self.log(f"[BLOCKED] {consecutive_fail} consecutive failures — last: {last_fail_reason}", "error")
            self.emit("account_update", status="blocked")
            return {"status": "blocked", "reason": last_fail_reason or "consecutive failures"}

        while True:
            self.check_stop()
            if max_swipes and self.counters["swipes"] >= max_swipes:
                self.emit("account_update", status="active")
                return {"status": "done", "reason": f"max swipes reached ({max_swipes})"}

            try:
                cards, status = c.get_zapping_cards(zapping_url, self.access_token, include_status=True)
                if status == 401 and self._refresh():
                    cards, status = c.get_zapping_cards(zapping_url, self.access_token, include_status=True)
            except requests.RequestException as e:
                cards, status = [], None
                last_fail_reason = f"zapping network error: {type(e).__name__}"
                self.log(f"[ZAPPING] {last_fail_reason}", "warning")

            if first_batch and status == 200:
                # Original flow refreshes the token right after the first batch.
                self._refresh()
                first_batch = False

            if status != 200:
                consecutive_fail += 1
                if status is not None:
                    last_fail_reason = f"zapping HTTP {status}"
                if consecutive_fail >= block_threshold:
                    return blocked()
                self.delay("between_batches")
                continue

            if not cards:
                empty_batches += 1
                if empty_batches >= max_empty:
                    self.emit("account_update", status="active")
                    return {"status": "done", "reason": "no more cards"}
                self.delay("between_batches")
                continue
            empty_batches = 0

            for card in cards:
                self.check_stop()
                if max_swipes and self.counters["swipes"] >= max_swipes:
                    break

                user = card.get("user", {}) or {}
                user_links = user.get("links", {}) or {}
                card_links = card.get("links", {}) or {}

                user_id = user.get("id") or card.get("userId") or card.get("id")
                user_id = str(user_id) if user_id else None
                like_url = card_links.get("top") or user_links.get("like")
                dislike_url = card_links.get("flop") or user_links.get("dislike")
                if not user_id or (not like_url and not dislike_url):
                    continue

                action = "like" if random.random() < like_ratio else "dislike"
                if action == "like" and not like_url:
                    action = "dislike"
                elif action == "dislike" and not dislike_url:
                    action = "like"

                ok, matched, status = self._do_action(action, like_url, dislike_url)
                if ok:
                    consecutive_fail = 0
                    self.counters["swipes"] += 1
                    if action == "like":
                        self.counters["liked"] += 1
                        if matched:
                            self.counters["matches"] += 1
                            self.log(f"  [MATCH] User {user_id}")
                        else:
                            self.log(f"  [LIKED] User {user_id}  (likes={self.counters['liked']})")
                    else:
                        self.counters["disliked"] += 1
                        self.log(f"  [DISLIKED] User {user_id}  (dislikes={self.counters['disliked']})")
                    self.emit("swipe", user_id=user_id, action=action, matched=matched)
                else:
                    consecutive_fail += 1
                    last_fail_reason = f"{action} HTTP {status}" if status else f"{action} network error"
                    if consecutive_fail >= block_threshold:
                        return blocked()

                self.delay("between_swipes")

            self.delay("between_batches")

    def _do_action(self, action, like_url, dislike_url):
        """Returns (ok, matched, status). Retries once after a 401 refresh."""
        c = self.client
        try:
            if action == "like":
                status, ok, matched, _ = c.like_user(like_url, self.access_token)
                if status == 401 and self._refresh():
                    status, ok, matched, _ = c.like_user(like_url, self.access_token)
                return ok, matched, status
            status, ok = c.dislike_user(dislike_url, self.access_token)
            if status == 401 and self._refresh():
                status, ok = c.dislike_user(dislike_url, self.access_token)
            return ok, False, status
        except requests.RequestException as e:
            self.log(f"  [{action.upper()}] network error: {type(e).__name__}: {e}", "warning")
            return False, False, None


# ---------------------------------------------------------------------------
# Messaging job (separate, launched by admin for existing accounts)
# ---------------------------------------------------------------------------

class MessageRunner(_RunnerBase):
    """
    Logs in to an existing account via its refresh token and messages matched
    users that were not messaged yet.

    Emits: log, step, account_update, message {user_id, ok, text}
    """

    def __init__(self, settings, apk, account, proxy_url=None, emit=None, stop_event=None):
        super().__init__(settings, emit, stop_event)
        self.account = account
        self.client = JaumoClient(
            apk, proxy_url=proxy_url, timeout=self.settings["request_timeout"],
            device_id=account.get("device_id"), android_id=account.get("android_id"),
            device_info=account.get("device_info"), devices=self.settings["devices"],
            log=self._client_log,
        )
        if not account.get("device_info"):
            # Legacy accounts did not store the device model.
            self.emit("account_update", device_info=self.client.device_info)
        self.access_token = account.get("access_token")
        self.refresh_token = account.get("refresh_token")

    def fetch_new_matches(self):
        """
        TODO: fetch matches that arrived after the signup run (requires the
        matches/conversations endpoint from the decompiled APK). Until then only
        matches recorded during swiping are messaged.
        """
        return []

    def run(self):
        try:
            return self._run()
        except StopRequested:
            self.log("[STOP] Stopped by admin", "warning")
            return {"status": "stopped", "reason": "stopped by admin"}
        except requests.RequestException as e:
            self.log(f"[NETWORK] {type(e).__name__}: {e}", "error")
            return {"status": "failed", "reason": f"network error: {type(e).__name__}"}
        except Exception as e:
            self.log(f"[CRASH] {type(e).__name__}: {e}", "error")
            return {"status": "failed", "reason": f"{type(e).__name__}: {e}"}

    def _run(self):
        c = self.client
        acc = self.account
        self.log(f"--- Messaging for {acc.get('name')} (account #{acc.get('id')}) ---")

        self.step("login")
        if self.refresh_token:
            new_tok, new_ref = c.refresh_access_token(self.refresh_token)
            if new_tok:
                self.access_token, self.refresh_token = new_tok, new_ref
                self.emit("account_update", access_token=new_tok, refresh_token=new_ref)
            else:
                self.log("[LOGIN] Refresh failed — trying stored access token", "warning")
        if not self.access_token:
            return {"status": "failed", "reason": "no usable token"}
        self.delay("after_refresh")

        self.step("matches")
        matches = list(dict.fromkeys(
            [str(m) for m in (acc.get("matches") or [])] + [str(m) for m in self.fetch_new_matches()]
        ))
        already = {str(m) for m in (acc.get("messaged") or [])}
        targets = [m for m in matches if m not in already]
        self.log(f"[MATCHES] total={len(matches)} already messaged={len(already)} to send={len(targets)}")
        if not targets:
            return {"status": "done", "reason": "no unmessaged matches"}

        self.step("messaging")
        templates = self.settings["message_templates"] or DEFAULT_SETTINGS["message_templates"]
        sent = 0
        for user_id in targets:
            self.check_stop()
            self.delay("before_message")
            text = random.choice(templates)
            ok = c.send_message_to(user_id, text, self.access_token)
            self.emit("message", user_id=user_id, ok=ok, text=text)
            sent += ok
        self.step("finished")
        return {"status": "done", "reason": f"sent {sent}/{len(targets)}"}


# ---------------------------------------------------------------------------
# Manual CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    apk = {
        "client_id": os.environ.get("JAUMO_CLIENT_ID", ""),
        "sign_secret": os.environ.get("JAUMO_SIGN_SECRET", ""),
        "user_agent": os.environ.get("JAUMO_USER_AGENT", DEFAULT_APK["user_agent"]),
    }
    photo = sys.argv[1] if len(sys.argv) > 1 else "photo.jpg"
    proxy = sys.argv[2] if len(sys.argv) > 2 else None

    def _emit(kind, data):
        if kind == "log":
            print(data["msg"])
        elif kind == "step":
            print(f"==> {data['step']}")

    result = BotRunner({"max_swipes": 10}, apk, photo, proxy_url=proxy, emit=_emit).run()
    print(result)
