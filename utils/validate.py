"""MUNIM — common validators for Indian tax identifiers (shared by Books and Pro)."""
import re

_PAN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_TAN = re.compile(r"^[A-Z]{4}[0-9]{5}[A-Z]$")
_GSTIN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_PIN = re.compile(r"^[1-9][0-9]{5}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MEMBERSHIP = re.compile(r"^[0-9]{6}$")
_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

PAN_TYPES = {
    "P": "Individual", "H": "HUF", "C": "Company", "F": "Firm / LLP",
    "A": "AOP", "B": "BOI", "T": "Trust", "L": "Local Authority",
    "J": "Artificial Juridical Person", "G": "Government",
}


def clean(value) -> str:
    return (value or "").strip().upper()


def is_pan(value) -> bool:
    return bool(_PAN.match(clean(value)))


def pan_type(value) -> str:
    v = clean(value)
    return PAN_TYPES.get(v[3], "") if is_pan(v) else ""


def is_tan(value) -> bool:
    return bool(_TAN.match(clean(value)))


def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        product = _CHARS.index(ch) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return _CHARS[(36 - total % 36) % 36]


def is_gstin(value) -> bool:
    v = clean(value)
    return bool(_GSTIN.match(v)) and gstin_check_char(v[:14]) == v[14]


def gstin_state(value) -> str:
    return clean(value)[:2]


def gstin_pan(value) -> str:
    return clean(value)[2:12]


def is_pin(value) -> bool:
    return bool(_PIN.match((value or "").strip()))


def is_email(value) -> bool:
    return bool(_EMAIL.match((value or "").strip()))


def is_phone(value) -> bool:
    digits = re.sub(r"[\s\-+()]", "", value or "")
    return digits.isdigit() and 6 <= len(digits) <= 13


def is_membership_no(value) -> bool:
    return bool(_MEMBERSHIP.match((value or "").strip()))


_CHECKS = {
    "pan": (is_pan, "PAN must be like ABCDE1234F"),
    "tan": (is_tan, "TAN must be like ABCD12345E"),
    "gstin": (is_gstin, "Invalid GSTIN (format or check digit)"),
    "pin": (is_pin, "PIN must be 6 digits"),
    "email": (is_email, "Invalid e-mail address"),
    "phone": (is_phone, "Invalid phone number"),
    "membership": (is_membership_no, "Membership No. must be 6 digits"),
}


def check(kind: str, value, required: bool = False):
    """Return an error message, or None if OK. Empty optional values are OK."""
    if not (value or "").strip():
        return "Required" if required else None
    fn, msg = _CHECKS[kind]
    return None if fn(value) else msg