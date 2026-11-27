"""MUNIM Pro — master database: Consultant Master (shared) + separate entity
lists per module (TDS: deductors + deductees, GST: gst_clients, Tax: assessees),
login users and the password vault.

MUNIM Pro keeps ALL its data in its own folder:  C:\\MUNIM Pro\\
(MUNIM Books stays in C:\\MUNIM\\ — the two never share files.)
"""
import os
import shutil
import sqlite3
import datetime

from utils import validate as V
from utils import vault

SCHEMA_VERSION = 3
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
    higher_rate INTEGER NOT NULL DEFAULT 0,          -- 206AB/206CCA non-filer
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

CREATE INDEX IF NOT EXISTS ix_deductors_name ON deductors(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_deductees_name ON deductees(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_deductees_ded ON deductees(deductor_id);
CREATE INDEX IF NOT EXISTS ix_gst_clients_name ON gst_clients(legal_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_assessees_name ON assessees(name COLLATE NOCASE);
"""

# Columns added to deductors after v1.
_DEDUCTOR_ADDED = [
    ("file_code", "TEXT"), ("rp_father", "TEXT"),
    ("rp_addr1", "TEXT"), ("rp_addr2", "TEXT"), ("rp_addr3", "TEXT"),
    ("rp_city", "TEXT"), ("rp_state_code", "TEXT"), ("rp_pin", "TEXT"),
    ("rp_same_addr", "INTEGER NOT NULL DEFAULT 1"),
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
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    vault.ensure_tables(conn)
    conn.commit()


def has_users(conn) -> bool:
    return conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None


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
    conn.execute("DELETE FROM deductors WHERE id=?", (did,))   # deductees cascade
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
    conn.execute("DELETE FROM deductees WHERE id=?", (pid,))
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
