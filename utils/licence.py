"""MUNIM licence — online activation once, then works offline.

How it works
- Activation (needs internet once): username + password + licence key are checked by the
  MUNIM licence server, which returns a licence signed with MUNIM's private key.
- The signed licence is saved in C:\\MUNIM\\licence_<product>.json and checked OFFLINE on
  every start with the public key below. Editing the file breaks the signature.
- The licence is tied to this computer (machine ID); copying the file to another PC fails.
- When online, MUNIM quietly re-checks in the background, so renewals, module changes and
  suspensions are picked up automatically. Offline use is allowed for 30 days after the
  last successful check.
- No third-party packages needed: Ed25519 signature verification is implemented below.
"""
import base64
import hashlib
import json
import os
import threading
import urllib.error
import urllib.request
from datetime import date, timedelta

# ── Configuration ─────────────────────────────────────────────────────────────
PRODUCT = "books"   # The MUNIM Pro EXE sets  licence.PRODUCT = "pro"  before first use.
SERVER = "https://jfnvddjsgpyowpfzbmqs.supabase.co/functions/v1/munim-licence"
# Public Supabase key — safe to ship (the database is locked; only the server functions can read it).
ANON_KEY = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpmbnZkZGpzZ3B5b3dw"
            "ZnpibXFzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg2NDk2MDEsImV4cCI6MjA5NDIyNTYwMX0."
            "RFdkPuyykaF5fNYbB2QuwJKvzDLrc_TYxHnnLB_tDT4")
# Licence-server public key — can only VERIFY licences, never create them.
PUBLIC_KEY = base64.b64decode("qiC2WRB+H0oUKXBYIcT9brpgKM7PPdGZDrSXqraPlMs=")
DATA_DIR = os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "MUNIM")
SUPPORT = "+91 84276 51580"
MODULE_NAMES = {"tax": "Tax Pro", "gst": "GST Pro", "tds": "TDS Pro"}


class LicenceError(ValueError):
    """Raised when the licence is missing/invalid. str(e) is a message for the user."""
    def __init__(self, message, code=""):
        super().__init__(message)
        self.code = code


class _Offline(Exception):
    pass


# ── Small helpers ─────────────────────────────────────────────────────────────
def _d(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def fmt_date(d):
    return d.strftime("%d-%m-%Y") if d else "—"


def expiry_of(lic):
    return _d((lic or {}).get("exp"))


def _unb64url(s):
    s = s.replace("-", "+").replace("_", "/")
    return base64.b64decode(s + "=" * (-len(s) % 4))


def product_name(p=None):
    p = p or PRODUCT
    return {"books": "MUNIM Books", "pro": "MUNIM Pro", "both": "MUNIM Books + Pro"}.get(p, "MUNIM")


def app_version():
    try:
        import __main__
        return str(getattr(__main__, "CURRENT_VERSION", ""))
    except Exception:
        return ""


_mid_cache = None


def machine_id():
    """Stable ID for this Windows installation (hashed — the real ID never leaves the PC)."""
    global _mid_cache
    if _mid_cache:
        return _mid_cache
    raw = ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            raw = str(winreg.QueryValueEx(k, "MachineGuid")[0])
    except Exception:
        pass
    if not raw:
        import uuid
        raw = f"node-{uuid.getnode():012x}"
    _mid_cache = hashlib.sha256(f"MUNIM|{raw}".encode()).hexdigest()[:32]
    return _mid_cache


# ── Ed25519 signature verification (RFC 8032, pure Python) ───────────────────
_P = 2 ** 255 - 19
_Q = 2 ** 252 + 27742317777372353535851937790883648493


def _inv(x):
    return pow(x, _P - 2, _P)


_D = -121665 * _inv(121666) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _pt_add(a, b):
    A = (a[1] - a[0]) * (b[1] - b[0]) % _P
    B = (a[1] + a[0]) * (b[1] + b[0]) % _P
    C = 2 * a[3] * b[3] * _D % _P
    D = 2 * a[2] * b[2] % _P
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _P, G * H % _P, F * G % _P, E * H % _P)


def _pt_mul(s, pt):
    r = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            r = _pt_add(r, pt)
        pt = _pt_add(pt, pt)
        s >>= 1
    return r


def _pt_equal(a, b):
    return ((a[0] * b[2] - b[0] * a[2]) % _P == 0 and
            (a[1] * b[2] - b[1] * a[2]) % _P == 0)


def _recover_x(y, sign):
    if y >= _P:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_GY = 4 * _inv(5) % _P
_GX = _recover_x(_GY, 0)
_G = (_GX, _GY, 1, _GX * _GY % _P)


def _decompress(b):
    if len(b) != 32:
        return None
    y = int.from_bytes(b, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _P)


def _ed25519_verify(pub, msg, sig):
    if len(pub) != 32 or len(sig) != 64:
        return False
    A = _decompress(pub)
    R = _decompress(sig[:32])
    if A is None or R is None:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= _Q:
        return False
    h = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % _Q
    return _pt_equal(_pt_mul(s, _G), _pt_add(R, _pt_mul(h, A)))


def _verify_token(token):
    """Returns the licence dict if the token is genuine, else None."""
    try:
        body_b64, sig_b64 = str(token).split(".")
        body, sig = _unb64url(body_b64), _unb64url(sig_b64)
        if not _ed25519_verify(PUBLIC_KEY, body, sig):
            return None
        lic = json.loads(body.decode("utf-8"))
        return lic if isinstance(lic, dict) and lic.get("v") == 1 else None
    except Exception:
        return None


# ── Local storage ─────────────────────────────────────────────────────────────
_lock = threading.Lock()


def _path():
    return os.path.join(DATA_DIR, f"licence_{PRODUCT}.json")


def _load():
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(state):
    with _lock:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = _path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, _path())


def _clear():
    with _lock:
        try:
            os.remove(_path())
        except FileNotFoundError:
            pass
        except Exception:
            pass


def stored_key():
    return _load().get("key", "")


# ── Server calls ──────────────────────────────────────────────────────────────
def _post(payload, timeout):
    req = urllib.request.Request(
        SERVER, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "apikey": ANON_KEY,
                 "Authorization": "Bearer " + ANON_KEY, "User-Agent": "MUNIM"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "code": "server",
                    "error": f"Licence server error ({e.code}). Please try again later."}
    except Exception as e:
        raise _Offline(str(e))


def activate(username, password, key):
    """Online activation. Returns the licence dict or raises LicenceError."""
    payload = {"action": "activate", "username": username.strip().lower(), "password": password,
               "key": key.strip().upper(), "machine_id": machine_id(), "product": PRODUCT,
               "app_version": app_version()}
    try:
        r = _post(payload, timeout=15)
    except _Offline:
        raise LicenceError("No internet connection. Activation needs internet once — "
                           "please connect and try again.", "offline")
    if not r.get("ok"):
        raise LicenceError(r.get("error") or "Activation failed. Please try again.",
                           r.get("code") or "failed")
    lic = _verify_token(r.get("token", ""))
    if lic is None:
        raise LicenceError("The licence server's reply could not be verified. "
                           f"Please contact support on WhatsApp {SUPPORT}.", "bad_reply")
    today = date.today().isoformat()
    state = _load()
    state.update(token=r["token"], key=key.strip().upper(), username=lic.get("u"),
                 checked=today, seen=today)
    _save(state)
    return lic


def refresh(timeout=6):
    """Re-check online. Returns the new licence dict, None if offline/unavailable.
    Raises LicenceError (and removes the local licence) if it was suspended/removed/moved."""
    state = _load()
    token = state.get("token")
    if not token:
        return None
    try:
        r = _post({"action": "refresh", "token": token, "machine_id": machine_id(),
                   "app_version": app_version()}, timeout)
    except _Offline:
        return None
    if r.get("ok"):
        lic = _verify_token(r.get("token", ""))
        if lic is None:
            return None
        state = _load()
        state["token"] = r["token"]
        state["checked"] = date.today().isoformat()
        _save(state)
        return lic
    if r.get("revoked"):
        _clear()
        raise LicenceError(r.get("error") or "This licence is no longer valid.",
                           r.get("code") or "revoked")
    return None


_bg_started = False


def _start_background_refresh():
    global _bg_started
    if _bg_started:
        return
    _bg_started = True

    def run():
        try:
            refresh(timeout=8)
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()


# ── Main check ────────────────────────────────────────────────────────────────
def _wrong_product_msg(lic):
    return (f"This licence is for {product_name(lic.get('p'))}, not {product_name()}. "
            f"Please contact support on WhatsApp {SUPPORT}.")


def check(allow_network=True):
    """Returns the licence dict if this PC may use MUNIM, else raises LicenceError.
    Works offline. Only if the licence has expired or needs its 30-day re-check does it
    try the internet (max ~6 seconds) — so a renewal is picked up automatically."""
    state = _load()
    token = state.get("token")
    if not token:
        raise LicenceError(f"{product_name()} is not activated on this computer yet.",
                           "not_activated")
    lic = _verify_token(token)
    if lic is None:
        _clear()
        raise LicenceError("Licence data is damaged. Please activate again.", "invalid")
    if lic.get("mid") != machine_id():
        raise LicenceError("This licence was activated on a different computer. "
                           "Please activate again.", "other_pc")
    if not (lic.get("p") == "both" or lic.get("p") == PRODUCT):
        raise LicenceError(_wrong_product_msg(lic), "wrong_product")

    today = date.today()
    seen = _d(state.get("seen"))
    if seen and today < seen - timedelta(days=1):
        raise LicenceError("Your computer's date is earlier than the last time MUNIM was used. "
                           "Please correct the date and time, then open MUNIM again.", "clock")

    exp, grace = _d(lic.get("exp")), _d(lic.get("gu"))
    problem = None
    if not exp or exp < today:
        problem = LicenceError(f"Your licence expired on {fmt_date(exp)}. To renew, contact us "
                               f"on WhatsApp {SUPPORT}. After renewal, just open MUNIM with "
                               "internet ON.", "expired")
    elif not grace or grace < today:
        problem = LicenceError("Please connect to the internet once so MUNIM can re-check your "
                               "licence (needed every 30 days), then open MUNIM again.", "recheck")
    if problem:
        if allow_network:
            fresh = refresh(timeout=6)          # may raise if suspended/removed
            if fresh:
                return check(allow_network=False)
        raise problem

    if not seen or today > seen:
        state["seen"] = today.isoformat()
        try:
            _save(state)
        except Exception:
            pass
    _start_background_refresh()
    return lic


def has_module(name):
    """True if this licence includes a MUNIM Pro module: 'tax', 'gst' or 'tds'."""
    try:
        lic = check(allow_network=False)
    except LicenceError:
        return False
    return lic.get("p") in ("pro", "both") and name in (lic.get("m") or [])


def info():
    """Licence details for the About / Help screen (None if not activated)."""
    try:
        lic = check(allow_network=False)
    except LicenceError:
        return None
    exp = expiry_of(lic)
    return {
        "username": lic.get("u", ""),
        "firm": lic.get("f", ""),
        "product": product_name(lic.get("p")),
        "modules": [MODULE_NAMES.get(m, m) for m in (lic.get("m") or [])],
        "trial": bool(lic.get("t")),
        "expires": fmt_date(exp),
        "days_left": max(0, (exp - date.today()).days) if exp else 0,
        "last_checked": fmt_date(_d(lic.get("iat"))),
    }


# ── Backward-compatible API (used by main.py and other screens) ───────────────
def validate_key(key=None):
    """Returns (username, expiry_date) or raises LicenceError (a ValueError).
    The `key` argument is ignored — the signed licence stored on this PC is checked."""
    lic = check()
    return lic.get("u", ""), expiry_of(lic)


def days_remaining(key=None):
    try:
        lic = check(allow_network=False)
    except LicenceError:
        return 0
    exp = expiry_of(lic)
    return max(0, (exp - date.today()).days) if exp else 0


def licence_status(key=None):
    try:
        lic = check(allow_network=False)
    except LicenceError as e:
        return "Not activated" if e.code == "not_activated" else str(e)
    exp = expiry_of(lic)
    d = (exp - date.today()).days
    plural = "s" if d != 1 else ""
    if lic.get("t"):
        return f"Free trial — {d} day{plural} left (till {fmt_date(exp)})"
    if d <= 7:
        return f"Expiring in {d} day{plural} — please renew"
    return f"Valid until {fmt_date(exp)}"


def generate_key(*_args, **_kwargs):
    raise RuntimeError("Licence keys are created in the MUNIM admin panel now.")
