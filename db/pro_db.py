"""MUNIM Pro — master database: Consultant Master (shared) + separate entity
lists per module (TDS: deductors + deductees, GST: gst_clients, Tax: assessees),
login users, the password vault, the TDS payment-code table and TDS entries.

MUNIM Pro keeps ALL its data in its own folder:  C:\\MUNIM Pro\\
(MUNIM Books stays in C:\\MUNIM\\ — the two never share files.)
"""
import os
import re
import shutil
import sqlite3
import datetime
from decimal import Decimal, ROUND_HALF_UP

from utils import validate as V
from utils import vault

SCHEMA_VERSION = 5
_DRIVE = os.environ.get("SystemDrive", "C:") + os.sep
PRO_ROOT = os.path.join(_DRIVE, "MUNIM Pro")
_OLD_BOOKS_ROOT = os.path.join(_DRIVE, "MUNIM")     # early test builds used this

# GST state codes (current)
STATES = [
    ("01", "Jammu and Kashmir"), ("02", "Himachal Pradesh"), ("03", "Punjab"),
    ("04", "Chandigarh"), ("05", "Uttarakhand"), ("06", "Haryana"), ("07", "Delhi"),
    ("08", "Rajasthan"), ("09", "Uttar Pradesh"), ("10", "Bihar"), ("11", "Sikkim"),
    ("12", "Arunachal Pradesh"), ("13", "Nagaland"), ("14", "Manipur"), ("15", "Mizoram"),
    ("16", "Tripura"), ("17", "Meghalaya"), ("18", "Assam"), ("19", "West Bengal"),
    ("20", "Jharkhand"), ("21", "Odisha"), ("22", "Chhattisgarh"), ("23", "Madhya Pradesh"),
    ("24", "Gujarat"), ("26", "Dadra and Nagar Haveli and Daman and Diu"),
    ("27", "Maharashtra"), ("29", "Karnataka"), ("30", "Goa"), ("31", "Lakshadweep"),
    ("32", "Kerala"), ("33", "Tamil Nadu"), ("34", "Puducherry"),
    ("35", "Andaman and Nicobar Islands"), ("36", "Telangana"), ("37", "Andhra Pradesh"),
    ("38", "Ladakh"), ("97", "Other Territory"),
]
STATE_NAME = dict(STATES)
CONTACT_ROLES = ["Proprietor", "Partner", "Director", "Employee"]

# Deductor types (TAN holders). 'type' stored as the short code.
DEDUCTOR_TYPES = [
    ("company", "Company"), ("firm", "Firm / LLP"), ("individual", "Individual / Proprietor"),
    ("huf", "HUF"), ("aop", "AOP / BOI"), ("trust", "Trust"),
    ("local", "Local Authority"),
]
DEDUCTOR_TYPE_NAME = dict(DEDUCTOR_TYPES)

# Deductee (payee) types
DEDUCTEE_TYPES = [
    ("individual", "Individual"), ("huf", "HUF"), ("company", "Company"),
    ("firm", "Firm / LLP"), ("aop", "AOP / BOI"), ("trust", "Trust"),
    ("local", "Local Authority"), ("govt", "Government"), ("ajp", "Artificial Juridical"),
]
DEDUCTEE_TYPE_NAME = dict(DEDUCTEE_TYPES)
PAN_STATUS = [("active", "Active (valid)"), ("inactive", "Inactive / Inoperative"),
              ("notavbl", "PAN not available")]
PAN_STATUS_NAME = dict(PAN_STATUS)
FORM16A_FREQ = ["Quarterly", "On request", "Yearly"]

# Return forms a payment code can belong to
PAY_FORMS = [
    ("140", "Form 140 — non-salary, residents"),
    ("144", "Form 144 — non-residents"),
    ("138", "Form 138 — salary"),
    ("143", "Form 143 — TCS"),
    ("141", "Form 141 — challan-cum-statement"),
]
PAY_FORM_NAME = dict(PAY_FORMS)

# Why tax is lower / nil / higher on an entry (MUNIM's own keys; the FVU letter
# for each is mapped at the statement step after checking Protean's file format)
TDS_REASONS = [
    ("", "Normal deduction"),
    ("lower_cert", "Lower / nil rate — certificate (section 395)"),
    ("no_pan", "Higher rate — PAN missing or inoperative"),
    ("form121", "No deduction — Form 121 (15G / 15H) received"),
    ("threshold", "No deduction — below threshold"),
    ("exempt", "No deduction — exempt under 393(4) / other"),
]
TDS_REASON_NAME = dict(TDS_REASONS)
NEW_ACT_START = datetime.date(2026, 4, 1)

_ADDR = "addr1 TEXT, addr2 TEXT, addr3 TEXT, city TEXT, state_code TEXT, pin TEXT"
_TAIL = ("books_company TEXT, active INTEGER NOT NULL DEFAULT 1, notes TEXT, "
         "created_at TEXT NOT NULL, updated_at TEXT NOT NULL")

_BASE_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
    salt TEXT NOT NULL, pw_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin','staff')),
    must_change INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS consultants (
    id INTEGER PRIMARY KEY,
    firm_name TEXT NOT NULL, firm_pan TEXT, {_ADDR},
    phone1 TEXT, phone2 TEXT, email TEXT,
    contact_name TEXT, contact_role TEXT,
    membership_no TEXT, pan TEXT, firm_reg_no TEXT, gstin TEXT, tagline TEXT,
    is_tax_auditor INTEGER NOT NULL DEFAULT 0,
    itd_cred_ref TEXT, gstp_cred_ref TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deductors (
    id INTEGER PRIMARY KEY,
    consultant_id INTEGER REFERENCES consultants(id) ON DELETE SET NULL,
    name TEXT NOT NULL, file_code TEXT, tan TEXT NOT NULL UNIQUE, pan TEXT, type TEXT,
    {_ADDR}, phone TEXT, email TEXT,
    rp_name TEXT, rp_pan TEXT, rp_designation TEXT, rp_father TEXT,
    rp_phone TEXT, rp_email TEXT,
    rp_addr1 TEXT, rp_addr2 TEXT, rp_addr3 TEXT, rp_city TEXT, rp_state_code TEXT, rp_pin TEXT,
    rp_same_addr INTEGER NOT NULL DEFAULT 1,
    traces_cred_ref TEXT, itd_cred_ref TEXT, {_TAIL}
);

CREATE TABLE IF NOT EXISTS deductees (
    id INTEGER PRIMARY KEY,
    deductor_id INTEGER NOT NULL REFERENCES deductors(id) ON DELETE CASCADE,
    name TEXT NOT NULL, pan TEXT, pan_status TEXT NOT NULL DEFAULT 'active',
    type TEXT NOT NULL DEFAULT 'individual',
    is_employee INTEGER NOT NULL DEFAULT 0,
    resident INTEGER NOT NULL DEFAULT 1,
    higher_rate INTEGER NOT NULL DEFAULT 0,          -- old 206AB flag (withdrawn; unused)
    lower_cert_no TEXT, lower_rate TEXT, lower_valid_from TEXT, lower_valid_to TEXT,
    form16a_freq TEXT,
    father_name TEXT, dob TEXT, designation TEXT,
    {_ADDR}, phone TEXT, email TEXT,
    active INTEGER NOT NULL DEFAULT 1, notes TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gst_clients (
    id INTEGER PRIMARY KEY,
    consultant_id INTEGER REFERENCES consultants(id) ON DELETE SET NULL,
    legal_name TEXT NOT NULL, trade_name TEXT, gstin TEXT NOT NULL UNIQUE, pan TEXT,
    reg_type TEXT NOT NULL DEFAULT 'regular', return_freq TEXT NOT NULL DEFAULT 'monthly',
    {_ADDR}, phone TEXT, email TEXT,
    gst_cred_ref TEXT, {_TAIL}
);

CREATE TABLE IF NOT EXISTS assessees (
    id INTEGER PRIMARY KEY,
    consultant_id INTEGER REFERENCES consultants(id) ON DELETE SET NULL,
    name TEXT NOT NULL, pan TEXT NOT NULL UNIQUE, status TEXT,
    father_name TEXT, dob TEXT, {_ADDR}, phone TEXT, email TEXT,
    itd_cred_ref TEXT, {_TAIL}
);

CREATE TABLE IF NOT EXISTS pay_codes (
    id INTEGER PRIMARY KEY,
    seed_key TEXT UNIQUE,                 -- set for MUNIM's built-in rows
    code TEXT,                            -- 4-digit payment code (NULL if none)
    old_section TEXT, new_section TEXT, sl_no TEXT,
    nature TEXT NOT NULL,
    form TEXT NOT NULL DEFAULT '140',
    rate_ind REAL, rate_company REAL, rate_other REAL,
    no_pan_rate REAL,
    th_single REAL, th_year REAL, th_month REAL,
    code_checked INTEGER NOT NULL DEFAULT 0,   -- confirmed against Protean file format
    active INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tds_entries (
    id INTEGER PRIMARY KEY,
    deductor_id INTEGER NOT NULL REFERENCES deductors(id) ON DELETE CASCADE,
    deductee_id INTEGER NOT NULL REFERENCES deductees(id),
    pay_code_id INTEGER NOT NULL REFERENCES pay_codes(id),
    tax_year TEXT NOT NULL,               -- e.g. 2026-27
    quarter TEXT NOT NULL,                -- Q1..Q4
    paid_on TEXT NOT NULL,                -- ISO date: earlier of payment / credit
    deducted_on TEXT,                     -- ISO date
    amount REAL NOT NULL,
    rate REAL NOT NULL DEFAULT 0,
    tds REAL NOT NULL DEFAULT 0,
    surcharge REAL NOT NULL DEFAULT 0,
    cess REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL DEFAULT 0,
    reason TEXT,                          -- key from TDS_REASONS ('' = normal)
    cert_no TEXT,                         -- lower-deduction certificate (395)
    challan_id INTEGER,                   -- linked in the Challans step
    notes TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_deductors_name ON deductors(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_deductees_name ON deductees(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_deductees_ded ON deductees(deductor_id);
CREATE INDEX IF NOT EXISTS ix_gst_clients_name ON gst_clients(legal_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_assessees_name ON assessees(name COLLATE NOCASE);
CREATE UNIQUE INDEX IF NOT EXISTS ux_pay_codes_code ON pay_codes(code) WHERE code IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_pay_codes_form ON pay_codes(form);
CREATE INDEX IF NOT EXISTS ix_tds_entries_q ON tds_entries(deductor_id, tax_year, quarter);
CREATE INDEX IF NOT EXISTS ix_tds_entries_dee ON tds_entries(deductee_id);
CREATE INDEX IF NOT EXISTS ix_tds_entries_code ON tds_entries(pay_code_id);
"""

# Columns added to deductors after v1.
_DEDUCTOR_ADDED = [
    ("file_code", "TEXT"), ("rp_father", "TEXT"),
    ("rp_addr1", "TEXT"), ("rp_addr2", "TEXT"), ("rp_addr3", "TEXT"),
    ("rp_city", "TEXT"), ("rp_state_code", "TEXT"), ("rp_pin", "TEXT"),
    ("rp_same_addr", "INTEGER NOT NULL DEFAULT 1"),
]

# ---------------------------------------------------------------------------
# Built-in payment codes, TY 2026-27 (Income-tax Act 2025).
# Rates/thresholds: unchanged from Finance Act 2025 (verified 28-Nov-2026).
# Codes: from published charts; every row starts code_checked = 0 until compared
# with Protean's e-TDS/TCS file format v1.2, Annexure 2.
# Columns: seed_key, code, old, new, sl_no, nature, form,
#          rate_ind, rate_company, rate_other, no_pan_rate,
#          th_single, th_year, th_month, notes
# ---------------------------------------------------------------------------
_SEED_COLS = ("seed_key", "code", "old_section", "new_section", "sl_no", "nature", "form",
              "rate_ind", "rate_company", "rate_other", "no_pan_rate",
              "th_single", "th_year", "th_month", "notes")

PAY_CODE_SEED = [
    # ── 393(1): payments to residents ──
    ("194D", "1005", "194D", "393(1)", "1(i)", "Insurance commission", "140",
     2, 10, 2, 20, None, 20000, None, "10% if the payee is a company; 2% for others."),
    ("194H", "1006", "194H", "393(1)", "1(ii)", "Commission or brokerage (other than insurance)",
     "140", 2, 2, 2, 20, None, 20000, None, ""),
    ("194IB", None, "194-IB", "393(1)", "2(i)",
     "Rent paid by individual / HUF not under tax audit", "141",
     2, 2, 2, 20, None, None, 50000,
     "Filed in Form 141 (challan-cum-statement), not Form 140. Per month or part of a month."),
    ("194I-PM", "1008", "194-I(a)", "393(1)", "2(ii)", "Rent — plant, machinery or equipment",
     "140", 2, 2, 2, 20, None, None, 50000, "Threshold per month or part of a month."),
    ("194I-LB", "1009", "194-I(b)", "393(1)", "2(ii)",
     "Rent — land, building, furniture or fittings", "140",
     10, 10, 10, 20, None, None, 50000, "Threshold per month or part of a month."),
    ("194IA", None, "194-IA", "393(1)", "3(i)",
     "Purchase of immovable property (other than agricultural land)", "141",
     1, 1, 1, 20, 5000000, None, None,
     "On the higher of consideration and stamp-duty value. Filed in Form 141. "
     "Code differs between sources (1010 / 1011) — left blank."),
    ("194K", "1013", "194K", "393(1)", "4(i)", "Income from units of mutual funds", "140",
     10, 10, 10, 20, None, 10000, None, ""),
    ("193", "1019", "193", "393(1)", "5(i)", "Interest on securities", "140",
     10, 10, 10, 20, None, 10000, None, ""),
    ("194A-SR", "1020", "194A", "393(1)", "5(ii)",
     "Interest from bank / co-op bank / post office — senior citizen", "140",
     10, None, None, 20, None, 100000, None, ""),
    ("194A-BANK", "1021", "194A", "393(1)", "5(ii)",
     "Interest from bank / co-op bank / post office — others", "140",
     10, 10, 10, 20, None, 50000, None, ""),
    ("194A-OTH", "1022", "194A", "393(1)", "5(iii)",
     "Interest other than on securities — other payers", "140",
     10, 10, 10, 20, None, 10000, None, ""),
    ("194C-IND", "1023", "194C", "393(1)", "6(i) D(a)",
     "Contractor / sub-contractor — payee individual or HUF", "140",
     1, None, None, 20, 30000, 100000, None, "Use when the payee PAN's 4th letter is P or H."),
    ("194C-OTH", "1024", "194C", "393(1)", "6(i) D(b)",
     "Contractor / sub-contractor — other payees", "140",
     None, 2, 2, 20, 30000, 100000, None, ""),
    ("194M", None, "194M", "393(1)", "6(ii)",
     "Work / professional fees / commission paid by individual or HUF "
     "(not otherwise required to deduct)", "141",
     2, 2, 2, 20, None, 5000000, None, "Filed in Form 141."),
    ("194J-FTS", "1026", "194J(a)", "393(1)", "6(iii)",
     "Fees for technical services, call centre, royalty for films", "140",
     2, 2, 2, 20, None, 50000, None, ""),
    ("194J-PROF", "1027", "194J(b)", "393(1)", "6(iii)",
     "Fees for professional services, other royalty, non-compete fees", "140",
     10, 10, 10, 20, None, 50000, None, ""),
    ("194J-DIR", "1028", "194J", "393(1)", "6(iii)",
     "Director's fees / commission (not salary)", "140",
     10, 10, 10, 20, None, None, None, "No threshold."),
    ("194", "1029", "194", "393(1)", "7", "Dividend", "140",
     10, 10, 10, 20, None, 10000, None,
     "₹10,000 relief only for an individual paid other than in cash (393(4))."),
    ("194DA", "1030", "194DA", "393(1)", "8(i)",
     "Payment under a life insurance policy (income part)", "140",
     2, 2, 2, 20, None, 100000, None, ""),
    ("194Q", "1031", "194Q", "393(1)", "8(ii)",
     "Purchase of goods (buyer turnover above ₹10 crore)", "140",
     0.1, 0.1, 0.1, 5, None, 5000000, None,
     "Deduct on the amount above ₹50 lakh per seller per year."),
    ("194R", "1033", "194R", "393(1)", "8(iv)",
     "Benefit or perquisite of business / profession", "140",
     10, 10, 10, 20, None, 20000, None, ""),
    ("194O", "1035", "194-O", "393(1)", "8(v)",
     "E-commerce operator — sales of participants", "140",
     0.1, 0.1, 0.1, 5, None, None, None,
     "₹5 lakh relief for individual / HUF participants with PAN or Aadhaar (393(4))."),
    ("194S", "1037", "194S", "393(1)", "8(vi)", "Transfer of virtual digital asset", "140",
     1, 1, 1, 20, None, 10000, None,
     "₹50,000 where the payer is a specified individual / HUF (393(4))."),
    # ── 393(3): winnings, cash withdrawals, partners ──
    ("194B", "1058", "194B", "393(3)", "1",
     "Winnings from lottery, crossword, card games, betting", "140",
     30, 30, 30, 20, 10000, None, None, "Threshold per transaction."),
    ("194BA", "1060", "194BA", "393(3)", "2", "Winnings from online games", "140",
     30, 30, 30, 20, None, None, None, ""),
    ("194BB", "1062", "194BB", "393(3)", "3", "Winnings from horse races", "140",
     30, 30, 30, 20, 10000, None, None, "Threshold per transaction."),
    ("194G", "1063", "194G", "393(3)", "4", "Commission on sale of lottery tickets", "140",
     2, 2, 2, 20, None, 20000, None, ""),
    ("194N-COOP", "1064", "194N", "393(3)", "5",
     "Cash withdrawal — co-operative society", "140",
     2, 2, 2, 20, None, 30000000, None,
     "Sources describe this code differently — confirm in the Protean file format."),
    ("194N", "1065", "194N", "393(3)", "5", "Cash withdrawal — others", "140",
     2, 2, 2, 20, None, 10000000, None, ""),
    ("194T", "1067", "194T", "393(3)", "7",
     "Salary, remuneration, commission, bonus or interest to partners", "140",
     10, 10, 10, 20, None, 20000, None, "Paid by a firm / LLP to its partners."),
    # ── 393(2): non-residents ──
    ("195", "1057", "195", "393(2)", "17",
     "Other sums to non-residents (royalty, FTS, interest, etc.)", "144",
     None, None, None, 20, None, None, None,
     "Rate in force or tax-treaty rate. Confirm code in the Protean file format."),
    # ── 392: salary ──
    ("192", None, "192", "392", "", "Salary", "138",
     None, None, None, 20, None, None, None, "As per slab (average rate). Code to be confirmed."),
]


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- paths
def pro_dir():
    os.makedirs(PRO_ROOT, exist_ok=True)
    return PRO_ROOT


def db_path():
    return os.path.join(pro_dir(), "munim_pro.db")


def settings_file():
    return os.path.join(pro_dir(), "settings.json")


def move_old_data():
    new = pro_dir()
    old_dir = os.path.join(_OLD_BOOKS_ROOT, "pro")
    try:
        if os.path.isdir(old_dir) and not os.path.exists(os.path.join(new, "munim_pro.db")):
            for name in os.listdir(old_dir):
                dest = os.path.join(new, name)
                if not os.path.exists(dest):
                    shutil.move(os.path.join(old_dir, name), dest)
            try:
                os.rmdir(old_dir)
            except OSError:
                pass
    except Exception:
        pass
    try:
        old_lic = os.path.join(_OLD_BOOKS_ROOT, "licence_pro.json")
        new_lic = os.path.join(new, "licence_pro.json")
        if os.path.exists(old_lic) and not os.path.exists(new_lic):
            shutil.move(old_lic, new_lic)
    except Exception:
        pass


# ---------------------------------------------------------------- connection
def connect(path=None) -> sqlite3.Connection:
    path = path or db_path()
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _migrate(conn)
    return conn


def _cols(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def _migrate(conn):
    conn.executescript(_BASE_SCHEMA)
    have = _cols(conn, "deductors")
    for col, decl in _DEDUCTOR_ADDED:
        if col not in have:
            conn.execute(f"ALTER TABLE deductors ADD COLUMN {col} {decl}")
    _seed_pay_codes(conn)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    vault.ensure_tables(conn)
    conn.commit()


def has_users(conn) -> bool:
    return conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None


# ---------------------------------------------------------------- small helpers
_DATE_FORMATS = ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%d-%m-%y", "%d/%m/%y")


def to_num(v):
    """'1,00,000' / '₹50000' / '2%' / '' → float or None. Raises ValueError if not a number."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("₹", "").replace("%", "").strip()
    if not s:
        return None
    return float(s)


def parse_date(text):
    """DD-MM-YYYY (also / or . separators, or ISO) → date. '' → None. Bad → ValueError."""
    if isinstance(text, datetime.date):
        return text
    s = (text or "").strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError("Date must be DD-MM-YYYY")


def _try_date(text):
    try:
        return parse_date(text)
    except ValueError:
        return None


def date_text(value):
    """ISO string or date → DD-MM-YYYY for display."""
    if not value:
        return ""
    if isinstance(value, datetime.date):
        return value.strftime("%d-%m-%Y")
    try:
        return datetime.date.fromisoformat(str(value)).strftime("%d-%m-%Y")
    except ValueError:
        return str(value)


def tax_year_of(d):
    y = d.year if d.month >= 4 else d.year - 1
    return f"{y}-{str(y + 1)[2:]}"


def quarter_of(d):
    m = d.month
    if 4 <= m <= 6:
        return "Q1"
    if 7 <= m <= 9:
        return "Q2"
    if 10 <= m <= 12:
        return "Q3"
    return "Q4"


def tax_years_available(today=None):
    """Tax years MUNIM Pro handles (new Act only), newest first."""
    today = today or datetime.date.today()
    last = today.year if today.month >= 4 else today.year - 1
    last = max(last, NEW_ACT_START.year)
    return [f"{y}-{str(y + 1)[2:]}" for y in range(last, NEW_ACT_START.year - 1, -1)]


def round_rupee(x):
    return float(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------- consultants
CONSULTANT_FIELDS = [
    "firm_name", "firm_pan", "addr1", "addr2", "addr3", "city", "state_code", "pin",
    "phone1", "phone2", "email", "contact_name", "contact_role",
    "membership_no", "pan", "firm_reg_no", "gstin", "tagline", "is_tax_auditor",
    "itd_cred_ref", "gstp_cred_ref",
]
_UPPER = {"firm_pan", "pan", "gstin", "firm_reg_no", "tan", "file_code", "rp_pan"}


def _normalise(data: dict, fields) -> dict:
    out = {}
    for f in fields:
        if f not in data:
            continue
        v = data[f]
        if isinstance(v, str):
            v = v.strip()
            if f in _UPPER:
                v = v.upper()
        out[f] = v
    return out


def validate_consultant(d: dict) -> dict:
    errors = {}
    if not (d.get("firm_name") or "").strip():
        errors["firm_name"] = "Firm name is required"
    for field, kind in (("firm_pan", "pan"), ("pan", "pan"), ("gstin", "gstin"),
                        ("pin", "pin"), ("email", "email"), ("phone1", "phone"),
                        ("phone2", "phone"), ("membership_no", "membership")):
        e = V.check(kind, d.get(field))
        if e:
            errors[field] = e
    state = d.get("state_code")
    if state and state not in STATE_NAME:
        errors["state_code"] = "Select a state"
    if not errors.get("gstin") and d.get("gstin") and state \
            and V.gstin_state(d["gstin"]) != state:
        errors["gstin"] = "GSTIN state code does not match the selected state"
    return errors


def save_consultant(conn, data: dict, cid: int = None) -> int:
    d = _normalise(data, CONSULTANT_FIELDS)
    errors = validate_consultant(d)
    if errors:
        raise ValueError(errors)
    d["is_tax_auditor"] = 1 if d.get("is_tax_auditor") else 0
    now = _now()
    if cid:
        cols = ", ".join(f"{k}=?" for k in d)
        conn.execute(f"UPDATE consultants SET {cols}, updated_at=? WHERE id=?",
                     [*d.values(), now, cid])
    else:
        first = conn.execute("SELECT COUNT(*) FROM consultants").fetchone()[0] == 0
        d.update(is_default=1 if first else 0, created_at=now, updated_at=now)
        cols = ", ".join(d)
        marks = ", ".join("?" for _ in d)
        cid = conn.execute(f"INSERT INTO consultants({cols}) VALUES({marks})",
                           list(d.values())).lastrowid
    conn.commit()
    return cid


def list_consultants(conn):
    return conn.execute("SELECT * FROM consultants ORDER BY id").fetchall()


def get_consultant(conn, cid):
    return conn.execute("SELECT * FROM consultants WHERE id=?", (cid,)).fetchone()


def get_default_consultant(conn):
    return conn.execute("SELECT * FROM consultants ORDER BY is_default DESC, id LIMIT 1"
                        ).fetchone()


def set_default_consultant(conn, cid):
    conn.execute("UPDATE consultants SET is_default = (id = ?)", (cid,))
    conn.commit()


def find_consultants(conn, text):
    like = f"%{(text or '').strip()}%"
    return conn.execute(
        "SELECT * FROM consultants WHERE firm_name LIKE ? OR contact_name LIKE ? "
        "OR membership_no LIKE ? OR city LIKE ? ORDER BY firm_name COLLATE NOCASE",
        (like, like, like, like)).fetchall()


def delete_consultant(conn, cid):
    row = get_consultant(conn, cid)
    if not row:
        return
    for ref in (row["itd_cred_ref"], row["gstp_cred_ref"]):
        vault.delete(conn, ref)
    conn.execute("DELETE FROM consultants WHERE id=?", (cid,))
    if row["is_default"]:
        nxt = conn.execute("SELECT id FROM consultants ORDER BY id LIMIT 1").fetchone()
        if nxt:
            conn.execute("UPDATE consultants SET is_default=1 WHERE id=?", (nxt[0],))
    conn.commit()


# ---------------------------------------------------------------- deductors
DEDUCTOR_FIELDS = [
    "name", "file_code", "tan", "pan", "type",
    "addr1", "addr2", "addr3", "city", "state_code", "pin", "phone", "email",
    "rp_name", "rp_pan", "rp_designation", "rp_father", "rp_phone", "rp_email",
    "rp_addr1", "rp_addr2", "rp_addr3", "rp_city", "rp_state_code", "rp_pin",
    "rp_same_addr", "traces_cred_ref",
]


def validate_deductor(d: dict) -> dict:
    errors = {}
    if not (d.get("name") or "").strip():
        errors["name"] = "Deductor name is required"
    e = V.check("tan", d.get("tan"), required=True)
    if e:
        errors["tan"] = e
    for field, kind in (("pan", "pan"), ("pin", "pin"), ("email", "email"),
                        ("phone", "phone"), ("rp_pan", "pan"), ("rp_pin", "pin"),
                        ("rp_email", "email"), ("rp_phone", "phone")):
        e = V.check(kind, d.get(field))
        if e:
            errors[field] = e
    typ = d.get("type")
    if typ and typ not in DEDUCTOR_TYPE_NAME:
        errors["type"] = "Select a type"
    for sfield in ("state_code", "rp_state_code"):
        s = d.get(sfield)
        if s and s not in STATE_NAME:
            errors[sfield] = "Select a state"
    return errors


def save_deductor(conn, data: dict, did: int = None) -> int:
    d = _normalise(data, DEDUCTOR_FIELDS)
    errors = validate_deductor(d)
    if errors:
        raise ValueError(errors)
    d["rp_same_addr"] = 1 if d.get("rp_same_addr") else 0
    tan = d.get("tan")
    clash = conn.execute("SELECT id, name FROM deductors WHERE tan=? AND id != ?",
                         (tan, did or -1)).fetchone()
    if clash:
        raise ValueError({"tan": f"TAN already used by “{clash['name']}”"})
    now = _now()
    if did:
        cols = ", ".join(f"{k}=?" for k in d)
        conn.execute(f"UPDATE deductors SET {cols}, updated_at=? WHERE id=?",
                     [*d.values(), now, did])
    else:
        d.update(active=1, created_at=now, updated_at=now)
        cols = ", ".join(d)
        marks = ", ".join("?" for _ in d)
        did = conn.execute(f"INSERT INTO deductors({cols}) VALUES({marks})",
                           list(d.values())).lastrowid
    conn.commit()
    return did


def get_deductor(conn, did):
    return conn.execute("SELECT * FROM deductors WHERE id=?", (did,)).fetchone()


def list_deductors(conn, include_inactive=False):
    sql = "SELECT * FROM deductors"
    if not include_inactive:
        sql += " WHERE active = 1"
    sql += " ORDER BY name COLLATE NOCASE"
    return conn.execute(sql).fetchall()


def find_deductors(conn, text):
    like = f"%{(text or '').strip()}%"
    return conn.execute(
        "SELECT * FROM deductors WHERE active = 1 AND ("
        "name LIKE ? OR tan LIKE ? OR pan LIKE ? OR city LIKE ? OR file_code LIKE ?) "
        "ORDER BY name COLLATE NOCASE",
        (like, like, like, like, like)).fetchall()


def delete_deductor(conn, did):
    row = get_deductor(conn, did)
    if not row:
        return
    vault.delete(conn, row["traces_cred_ref"])
    conn.execute("DELETE FROM deductors WHERE id=?", (did,))   # deductees + entries cascade
    conn.commit()


# ---------------------------------------------------------------- deductees
DEDUCTEE_FIELDS = [
    "name", "pan", "pan_status", "type", "is_employee", "resident", "higher_rate",
    "lower_cert_no", "lower_rate", "lower_valid_from", "lower_valid_to", "form16a_freq",
    "father_name", "dob", "designation",
    "addr1", "addr2", "addr3", "city", "state_code", "pin", "phone", "email",
]
_UPPER |= {"pan"}  # deductee PAN too


def validate_deductee(d: dict) -> dict:
    errors = {}
    if not (d.get("name") or "").strip():
        errors["name"] = "Deductee name is required"
    status = d.get("pan_status") or "active"
    # PAN required unless explicitly 'not available'
    pan = (d.get("pan") or "").strip()
    if status != "notavbl":
        e = V.check("pan", pan, required=True)
        if e:
            errors["pan"] = e
    elif pan:
        e = V.check("pan", pan)
        if e:
            errors["pan"] = e
    for field, kind in (("pin", "pin"), ("email", "email"), ("phone", "phone")):
        e = V.check(kind, d.get(field))
        if e:
            errors[field] = e
    typ = d.get("type")
    if typ and typ not in DEDUCTEE_TYPE_NAME:
        errors["type"] = "Select a type"
    s = d.get("state_code")
    if s and s not in STATE_NAME:
        errors["state_code"] = "Select a state"
    lr = (d.get("lower_rate") or "").strip()
    if lr:
        try:
            v = float(lr)
            if not 0 <= v <= 100:
                errors["lower_rate"] = "Rate must be between 0 and 100"
        except ValueError:
            errors["lower_rate"] = "Rate must be a number"
    return errors


def save_deductee(conn, deductor_id: int, data: dict, pid: int = None) -> int:
    if not deductor_id:
        raise ValueError({"name": "Pick a deductor first (press F4)."})
    d = _normalise(data, DEDUCTEE_FIELDS)
    errors = validate_deductee(d)
    if errors:
        raise ValueError(errors)
    for flag in ("is_employee", "resident", "higher_rate"):
        d[flag] = 1 if d.get(flag) else 0
    # PAN unique within one deductor (when a PAN is given)
    pan = (d.get("pan") or "").strip()
    if pan:
        clash = conn.execute(
            "SELECT id, name FROM deductees WHERE deductor_id=? AND pan=? AND id != ?",
            (deductor_id, pan, pid or -1)).fetchone()
        if clash:
            raise ValueError({"pan": f"PAN already used by “{clash['name']}” for this deductor"})
    now = _now()
    if pid:
        cols = ", ".join(f"{k}=?" for k in d)
        conn.execute(f"UPDATE deductees SET {cols}, updated_at=? WHERE id=?",
                     [*d.values(), now, pid])
    else:
        d.update(deductor_id=deductor_id, active=1, created_at=now, updated_at=now)
        cols = ", ".join(d)
        marks = ", ".join("?" for _ in d)
        pid = conn.execute(f"INSERT INTO deductees({cols}) VALUES({marks})",
                           list(d.values())).lastrowid
    conn.commit()
    return pid


def get_deductee(conn, pid):
    return conn.execute("SELECT * FROM deductees WHERE id=?", (pid,)).fetchone()


def list_deductees(conn, deductor_id, include_inactive=False):
    sql = "SELECT * FROM deductees WHERE deductor_id=?"
    args = [deductor_id]
    if not include_inactive:
        sql += " AND active = 1"
    sql += " ORDER BY name COLLATE NOCASE"
    return conn.execute(sql, args).fetchall()


def find_deductees(conn, deductor_id, text):
    like = f"%{(text or '').strip()}%"
    return conn.execute(
        "SELECT * FROM deductees WHERE deductor_id=? AND active=1 AND ("
        "name LIKE ? OR pan LIKE ? OR city LIKE ?) ORDER BY name COLLATE NOCASE",
        (deductor_id, like, like, like)).fetchall()


def delete_deductee(conn, pid):
    n = conn.execute("SELECT COUNT(*) FROM tds_entries WHERE deductee_id=?",
                     (pid,)).fetchone()[0]
    if n:
        raise ValueError(f"This deductee has {n} TDS entr{'y' if n == 1 else 'ies'}. "
                         "Delete those entries first.")
    conn.execute("DELETE FROM deductees WHERE id=?", (pid,))
    conn.commit()


# ---------------------------------------------------------------- payment codes
PAY_CODE_FIELDS = [
    "code", "old_section", "new_section", "sl_no", "nature", "form",
    "rate_ind", "rate_company", "rate_other", "no_pan_rate",
    "th_single", "th_year", "th_month", "code_checked", "active", "notes",
]
_PAY_RATES = ("rate_ind", "rate_company", "rate_other", "no_pan_rate")
_PAY_AMOUNTS = ("th_single", "th_year", "th_month")
_CODE_RE = re.compile(r"^\d{4}$")


def _clean_pay_code(data: dict):
    """Returns (clean dict, errors dict)."""
    d, errors = {}, {}
    for f in ("code", "old_section", "new_section", "sl_no", "nature", "form", "notes"):
        d[f] = (data.get(f) or "").strip()
    d["code"] = d["code"] or None
    if not d["nature"]:
        errors["nature"] = "Nature of payment is required"
    if d["code"] and not _CODE_RE.match(d["code"]):
        errors["code"] = "Payment code must be 4 digits"
    if d["form"] not in PAY_FORM_NAME:
        errors["form"] = "Select a return form"
    for f in _PAY_RATES:
        try:
            v = to_num(data.get(f))
        except ValueError:
            errors[f] = "Must be a number"
            continue
        if v is not None and not 0 <= v <= 100:
            errors[f] = "Must be between 0 and 100"
        d[f] = v
    for f in _PAY_AMOUNTS:
        try:
            v = to_num(data.get(f))
        except ValueError:
            errors[f] = "Must be an amount"
            continue
        if v is not None and v < 0:
            errors[f] = "Cannot be negative"
        d[f] = v
    d["code_checked"] = 1 if (data.get("code_checked") and d["code"]) else 0
    d["active"] = 1 if data.get("active") else 0
    return d, errors


def save_pay_code(conn, data: dict, pid: int = None) -> int:
    d, errors = _clean_pay_code(data)
    if errors:
        raise ValueError(errors)
    if d["code"]:
        clash = conn.execute("SELECT id, nature FROM pay_codes WHERE code=? AND id != ?",
                             (d["code"], pid or -1)).fetchone()
        if clash:
            raise ValueError({"code": f"Code already used by “{clash['nature']}”"})
    now = _now()
    if pid:
        cols = ", ".join(f"{k}=?" for k in d)
        conn.execute(f"UPDATE pay_codes SET {cols}, updated_at=? WHERE id=?",
                     [*d.values(), now, pid])
    else:
        d.update(created_at=now, updated_at=now)
        cols = ", ".join(d)
        marks = ", ".join("?" for _ in d)
        pid = conn.execute(f"INSERT INTO pay_codes({cols}) VALUES({marks})",
                           list(d.values())).lastrowid
    conn.commit()
    return pid


def get_pay_code(conn, pid):
    return conn.execute("SELECT * FROM pay_codes WHERE id=?", (pid,)).fetchone()


def list_pay_codes(conn, form=None, text="", include_inactive=True):
    sql = "SELECT * FROM pay_codes WHERE 1=1"
    args = []
    if form:
        sql += " AND form=?"
        args.append(form)
    if not include_inactive:
        sql += " AND active=1"
    t = (text or "").strip()
    if t:
        like = f"%{t}%"
        sql += (" AND (code LIKE ? OR old_section LIKE ? OR new_section LIKE ? "
                "OR sl_no LIKE ? OR nature LIKE ?)")
        args += [like] * 5
    sql += (" ORDER BY CASE form WHEN '140' THEN 1 WHEN '144' THEN 2 WHEN '138' THEN 3 "
            "WHEN '143' THEN 4 ELSE 5 END, COALESCE(code, '9999'), old_section")
    return conn.execute(sql, args).fetchall()


def delete_pay_code(conn, pid):
    row = get_pay_code(conn, pid)
    if not row:
        return
    if row["seed_key"]:
        raise ValueError("Built-in codes can't be deleted. Untick 'Active' to hide one.")
    n = conn.execute("SELECT COUNT(*) FROM tds_entries WHERE pay_code_id=?",
                     (pid,)).fetchone()[0]
    if n:
        raise ValueError(f"This code is used in {n} TDS entr{'y' if n == 1 else 'ies'}. "
                         "Untick 'Active' instead.")
    conn.execute("DELETE FROM pay_codes WHERE id=?", (pid,))
    conn.commit()


def pay_code_rate(row, deductee_type, pan_ok=True):
    """Normal rate for this payee type; with no/inoperative PAN, the higher of
    that rate and the no-PAN rate. None if the row has no rate (e.g. salary, 195)."""
    if deductee_type in ("individual", "huf"):
        rate = row["rate_ind"]
    elif deductee_type == "company":
        rate = row["rate_company"]
    else:
        rate = row["rate_other"]
    if rate is None:
        return None
    if not pan_ok and row["no_pan_rate"] is not None:
        rate = max(rate, row["no_pan_rate"])
    return rate


def _seed_pay_codes(conn, overwrite=False):
    """Insert built-in rows that are missing. overwrite=True resets built-in rows
    to MUNIM's defaults (your own rows are never touched)."""
    have = {r[0] for r in conn.execute(
        "SELECT seed_key FROM pay_codes WHERE seed_key IS NOT NULL")}
    now = _now()
    for values in PAY_CODE_SEED:
        rec = dict(zip(_SEED_COLS, values))
        key = rec["seed_key"]
        if key in have and not overwrite:
            continue
        code = rec["code"] or None
        if code:
            other = conn.execute(
                "SELECT 1 FROM pay_codes WHERE code=? AND (seed_key IS NULL OR seed_key != ?)",
                (code, key)).fetchone()
            if other:
                code = None          # number already used on one of your own rows
        rec["code"] = code
        fields = {k: rec[k] for k in _SEED_COLS if k != "seed_key"}
        if key in have:
            cols = ", ".join(f"{k}=?" for k in fields)
            conn.execute(
                f"UPDATE pay_codes SET {cols}, code_checked=0, active=1, updated_at=? "
                "WHERE seed_key=?", [*fields.values(), now, key])
        else:
            fields.update(seed_key=key, code_checked=0, active=1,
                          created_at=now, updated_at=now)
            cols = ", ".join(fields)
            marks = ", ".join("?" for _ in fields)
            conn.execute(f"INSERT INTO pay_codes({cols}) VALUES({marks})",
                         list(fields.values()))


def restore_pay_code_defaults(conn):
    _seed_pay_codes(conn, overwrite=True)
    conn.commit()


def contractor_code_for(conn, pay_row, deductee):
    """For 194C: return the other contractor row (1023 ↔ 1024) if the chosen one
    doesn't match the deductee's type; else None."""
    key = pay_row["seed_key"]
    if key not in ("194C-IND", "194C-OTH"):
        return None
    want = "194C-IND" if deductee["type"] in ("individual", "huf") else "194C-OTH"
    if key == want:
        return None
    return conn.execute("SELECT * FROM pay_codes WHERE seed_key=? AND active=1",
                        (want,)).fetchone()


# ---------------------------------------------------------------- TDS entries
def suggest_rate(deductee, pay_row, on_date):
    """Returns (rate or None, reason key, certificate no, note for the user)."""
    cert = (deductee["lower_cert_no"] or "").strip()
    lr_text = (deductee["lower_rate"] or "").strip()
    if cert and lr_text:
        try:
            lr = float(lr_text)
        except ValueError:
            lr = None
        if lr is not None:
            vf = _try_date(deductee["lower_valid_from"])
            vt = _try_date(deductee["lower_valid_to"])
            if (vf is None or on_date >= vf) and (vt is None or on_date <= vt):
                return lr, "lower_cert", cert, f"Lower-deduction certificate {cert}: {lr:g}%."
    pan_ok = deductee["pan_status"] == "active" and V.is_pan(deductee["pan"])
    base = pay_code_rate(pay_row, deductee["type"], True)
    if base is None:
        return None, "", "", "No rate in Payment Codes for this payee type — type the rate."
    if not pan_ok:
        r = pay_code_rate(pay_row, deductee["type"], False)
        return r, "no_pan", "", f"PAN missing or inoperative: {r:g}% (normal {base:g}%)."
    return base, "", "", f"Normal rate {base:g}%."


_ENTRY_NUMS = ("amount", "rate", "tds", "surcharge", "cess")


def _clean_tds_entry(conn, deductor_id, data):
    errors, d = {}, {}
    dee = get_deductee(conn, data.get("deductee_id")) if data.get("deductee_id") else None
    if not dee or dee["deductor_id"] != deductor_id:
        errors["deductee"] = "Choose a deductee"
    pc = get_pay_code(conn, data.get("pay_code_id")) if data.get("pay_code_id") else None
    if not pc:
        errors["pay_code"] = "Choose a payment code"
    elif pc["form"] not in ("140", "144"):
        errors["pay_code"] = "Only Form 140 / 144 codes are entered here"
    elif dee:
        if dee["resident"] and pc["form"] == "144":
            errors["pay_code"] = "Form 144 codes are for non-residents"
        elif not dee["resident"] and pc["form"] == "140":
            errors["pay_code"] = "This deductee is a non-resident — use a Form 144 code"

    paid = deducted = None
    try:
        paid = parse_date(data.get("paid_on"))
        if paid is None:
            errors["paid_on"] = "Required"
        elif paid < NEW_ACT_START:
            errors["paid_on"] = "MUNIM Pro covers the new Act only (from 01-04-2026)"
    except ValueError as e:
        errors["paid_on"] = str(e)
    try:
        deducted = parse_date(data.get("deducted_on")) or paid
        if deducted and deducted < NEW_ACT_START:
            errors["deducted_on"] = "MUNIM Pro covers the new Act only (from 01-04-2026)"
        elif deducted and paid and deducted < paid:
            errors["deducted_on"] = "Can't be before the payment / credit date"
    except ValueError as e:
        errors["deducted_on"] = str(e)

    for f in _ENTRY_NUMS:
        try:
            v = to_num(data.get(f))
        except ValueError:
            errors[f] = "Must be a number"
            continue
        v = 0.0 if v is None else round(v, 2)
        if v < 0:
            errors[f] = "Cannot be negative"
        d[f] = v
    if "amount" in d and d["amount"] <= 0 and "amount" not in errors:
        errors["amount"] = "Enter the amount paid / credited"
    if "rate" in d and d["rate"] > 100:
        errors["rate"] = "Must be between 0 and 100"

    reason = data.get("reason") or ""
    if reason not in TDS_REASON_NAME:
        errors["reason"] = "Select a reason"
    elif d.get("tds", 0) == 0 and d.get("amount", 0) > 0 and not reason:
        errors["reason"] = "No tax deducted — choose a reason"

    d.update(
        deductee_id=dee["id"] if dee else None,
        pay_code_id=pc["id"] if pc else None,
        reason=reason,
        cert_no=(data.get("cert_no") or "").strip().upper(),
        notes=(data.get("notes") or "").strip(),
    )
    if paid:
        d["paid_on"] = paid.isoformat()
        d["tax_year"] = tax_year_of(paid)
        d["quarter"] = quarter_of(paid)
    if deducted:
        d["deducted_on"] = deducted.isoformat()
    d["total"] = round(d.get("tds", 0) + d.get("surcharge", 0) + d.get("cess", 0), 2)
    return d, errors


def save_tds_entry(conn, deductor_id, data: dict, eid: int = None) -> int:
    d, errors = _clean_tds_entry(conn, deductor_id, data)
    if errors:
        raise ValueError(errors)
    now = _now()
    if eid:
        cols = ", ".join(f"{k}=?" for k in d)
        conn.execute(f"UPDATE tds_entries SET {cols}, updated_at=? WHERE id=? AND deductor_id=?",
                     [*d.values(), now, eid, deductor_id])
    else:
        d.update(deductor_id=deductor_id, created_at=now, updated_at=now)
        cols = ", ".join(d)
        marks = ", ".join("?" for _ in d)
        eid = conn.execute(f"INSERT INTO tds_entries({cols}) VALUES({marks})",
                           list(d.values())).lastrowid
    conn.commit()
    return eid


_ENTRY_SELECT = """
SELECT e.*, d.name AS dee_name, d.pan AS dee_pan,
       p.code AS pay_code, p.old_section AS old_section, p.nature AS nature
FROM tds_entries e
JOIN deductees d ON d.id = e.deductee_id
JOIN pay_codes p ON p.id = e.pay_code_id
"""


def get_tds_entry(conn, eid):
    return conn.execute(_ENTRY_SELECT + " WHERE e.id=?", (eid,)).fetchone()


def list_tds_entries(conn, deductor_id, tax_year, quarter=None, text=""):
    sql = _ENTRY_SELECT + " WHERE e.deductor_id=? AND e.tax_year=?"
    args = [deductor_id, tax_year]
    if quarter:
        sql += " AND e.quarter=?"
        args.append(quarter)
    t = (text or "").strip()
    if t:
        like = f"%{t}%"
        sql += " AND (d.name LIKE ? OR d.pan LIKE ? OR p.code LIKE ? OR p.old_section LIKE ?)"
        args += [like] * 4
    sql += " ORDER BY e.paid_on, e.id"
    return conn.execute(sql, args).fetchall()


def year_total(conn, deductor_id, deductee_id, pay_code_id, tax_year, exclude_id=None):
    r = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM tds_entries WHERE deductor_id=? AND "
        "deductee_id=? AND pay_code_id=? AND tax_year=? AND id != ?",
        (deductor_id, deductee_id, pay_code_id, tax_year, exclude_id or -1)).fetchone()
    return float(r[0] or 0)


def delete_tds_entry(conn, eid):
    conn.execute("DELETE FROM tds_entries WHERE id=?", (eid,))
    conn.commit()


# ---------------------------------------------------------------- F4 picker
_ENTITY = {
    "tds": ("deductors", "name", "tan"),
    "gst": ("gst_clients", "legal_name", "gstin"),
    "tax": ("assessees", "name", "pan"),
}


def search_entities(conn, module: str, text: str = "", limit: int = 200,
                    include_inactive: bool = False):
    table, name_col, key_col = _ENTITY[module]
    sql = f"SELECT id, {name_col} AS name, {key_col} AS key, city FROM {table} WHERE 1=1"
    args = []
    if not include_inactive:
        sql += " AND active = 1"
    t = (text or "").strip()
    if t:
        like = f"%{t}%"
        sql += f" AND ({name_col} LIKE ? OR {key_col} LIKE ? OR city LIKE ?)"
        args += [like, like, like]
    sql += f" ORDER BY {name_col} COLLATE NOCASE LIMIT ?"
    args.append(limit)
    return conn.execute(sql, args).fetchall()