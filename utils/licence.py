"""Offline licence key system for MUNIM.
Key format: MNM-<B32_PAYLOAD>-<6CHAR_HMAC>
Payload encodes username (up to 20 chars) + expiry date (YYYYMMDD).
Works fully offline — no server call needed."""
import base64, hashlib, hmac as _hmac, struct
from datetime import date

_SECRET = b"MUNIM_SUMIT_2026_CATOOLSKIT_XK9"  # keep private; change before wide release

def _pack(username: str, expiry: date) -> bytes:
    u = username.encode()[:20].ljust(20, b"\x00")
    d = struct.pack(">I", expiry.toordinal())
    return u + d

def _unpack(data: bytes):
    username = data[:20].rstrip(b"\x00").decode(errors="replace")
    ordinal = struct.unpack(">I", data[20:24])[0]
    return username, date.fromordinal(ordinal)

def _sign(payload_b32: str) -> str:
    h = _hmac.new(_SECRET, payload_b32.encode(), hashlib.sha256).hexdigest()
    return h[:6].upper()

def generate_key(username: str, expiry: date) -> str:
    """Generate a licence key. Used by the website admin panel."""
    raw = _pack(username, expiry)
    payload = base64.b32encode(raw).decode().rstrip("=")
    return f"MNM-{payload}-{_sign(payload)}"

def validate_key(key: str):
    """Returns (username, expiry_date) or raises ValueError."""
    key = (key or "").strip().upper()
    parts = key.split("-")
    if len(parts) < 3 or parts[0] != "MNM":
        raise ValueError("Invalid licence key format")
    sig = parts[-1]
    payload = "-".join(parts[1:-1])
    if _sign(payload) != sig:
        raise ValueError("Licence key is not valid")
    try:
        raw = base64.b32decode(payload + "=" * ((8 - len(payload) % 8) % 8))
        username, expiry = _unpack(raw)
    except Exception:
        raise ValueError("Licence key could not be decoded")
    if expiry < date.today():
        raise ValueError(f"Licence expired on {expiry.strftime('%d-%m-%Y')}. Please renew.")
    return username, expiry

def days_remaining(key: str) -> int:
    try:
        _, expiry = validate_key(key)
        return max(0, (expiry - date.today()).days)
    except ValueError:
        return 0

def licence_status(key: str) -> str:
    """Human-readable status for display."""
    if not key:
        return "Not activated"
    try:
        _, expiry = validate_key(key)
        d = (expiry - date.today()).days
        if d <= 7:
            return f"Expiring in {d} day{'s' if d != 1 else ''} — please renew"
        return f"Valid until {expiry.strftime('%d-%m-%Y')}"
    except ValueError as e:
        return str(e)