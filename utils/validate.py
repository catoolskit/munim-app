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

# Which "Type" names fit each PAN 4th letter (matched against the app's own
# type names, so wording like "Company (domestic)" still matches).
_PAN_TYPE_PATTERNS = {
    "P": re.compile(r"\bindividual\b", re.I),
    "H": re.compile(r"\bhuf\b|hindu\s+undivided", re.I),
    "C": re.compile(r"\bcompan(y|ies)\b", re.I),
    "F": re.compile(r"\bfirm\b|\bllp\b|partnership", re.I),
    "A": re.compile(r"\baop\b|association\s+of\s+persons", re.I),
    "B": re.compile(r"\bboi\b|body\s+of\s+individuals", re.I),
    "T": re.compile(r"\btrust\b", re.I),
    "L": re.compile(r"local\s+authority", re.I),
    "J": re.compile(r"artificial|juridical", re.I),
    "G": re.compile(r"\bgovernment\b|\bgovt\b", re.I),
}
_FOREIGN = re.compile(r"foreign|non[\s-]?(resident|domestic)", re.I)

# Words in a name that hint at the kind of entity
_LLP_WORDS = re.compile(r"\bllp\b|limited\s+liability\s+partnership", re.I)
_COMPANY_WORDS = re.compile(r"\b(pvt|private|ltd|limited)\b", re.I)
_HUF_WORDS = re.compile(r"\bhuf\b", re.I)


def clean(value) -> str:
    return (value or "").strip().upper()


def is_pan(value) -> bool:
    return bool(_PAN.match(clean(value)))


def pan_type(value) -> str:
    v = clean(value)
    return PAN_TYPES.get(v[3], "") if is_pan(v) else ""


def type_for_pan(pan, choices, prefer_foreign=False):
    """Pick the entry from 'choices' (Type names) that fits the PAN's 4th letter.
    Returns None if the PAN is invalid or nothing fits."""
    v = clean(pan)
    if not is_pan(v):
        return None
    pat = _PAN_TYPE_PATTERNS.get(v[3])
    if not pat:
        return None
    hits = [c for c in choices if pat.search(c)]
    if not hits:
        return None
    if len(hits) > 1:
        foreign = [c for c in hits if _FOREIGN.search(c)]
        local = [c for c in hits if c not in foreign]
        pick = foreign if prefer_foreign else local
        if pick:
            return pick[0]
    return hits[0]


def pan_type_warning(pan, type_name):
    """Message if the chosen Type clearly doesn't fit the PAN, else None.
    Types the checker can't classify (e.g. 'Others') are not flagged."""
    v = clean(pan)
    if not is_pan(v) or not type_name:
        return None
    letter = v[3]
    pat = _PAN_TYPE_PATTERNS.get(letter)
    if not pat or pat.search(type_name):
        return None
    if not any(p.search(type_name) for p in _PAN_TYPE_PATTERNS.values()):
        return None
    return (f"Type is '{type_name}', but PAN {v} has '{letter}' as its 4th letter, "
            f"which means {PAN_TYPES.get(letter, 'a different type')}.")


def pan_name_warning(pan, name):
    """Message if the name suggests a different kind of entity than the PAN, else None."""
    v = clean(pan)
    name = (name or "").strip()
    if not is_pan(v) or not name:
        return None
    letter = v[3]
    kind = PAN_TYPES.get(letter, "another type")
    if _LLP_WORDS.search(name):
        if letter != "F":
            return (f"The name looks like an LLP, but PAN {v} has '{letter}' ({kind}) as "
                    "its 4th letter. An LLP's PAN has 'F'.")
        return None
    if _COMPANY_WORDS.search(name) and letter != "C":
        return (f"The name looks like a company (Pvt / Ltd), but PAN {v} has '{letter}' "
                f"({kind}) as its 4th letter. A company's PAN has 'C'.")
    if _HUF_WORDS.search(name) and letter != "H":
        return (f"The name says HUF, but PAN {v} has '{letter}' ({kind}) as its "
                "4th letter. An HUF's PAN has 'H'.")
    return None


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