"""MUNIM accounting engine: SQLite schema, double-entry posting, trial balance.
Amounts are stored as integer paise to avoid float rounding errors."""
import os, sqlite3, hashlib, secrets
from datetime import date

def data_dir():
    base = r"C:\MUNIM" if os.name == "nt" else os.path.join(os.path.expanduser("~"), "MUNIM")
    os.makedirs(base, exist_ok=True)
    return base

def db_path():
    return os.path.join(data_dir(), "munim.db")

def connect(path=None):
    con = sqlite3.connect(path or db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def to_paise(rupees):
    return int(round(float(rupees) * 100))

def to_rupees(paise):
    return paise / 100

def fy_of(d):
    """Indian FY label, e.g. 2026-11-14 -> '2026-27'."""
    y = d.year if d.month >= 4 else d.year - 1
    return f"{y}-{str(y + 1)[2:]}"

def fy_range(label):
    y = int(label[:4])
    return date(y, 4, 1).isoformat(), date(y + 1, 3, 31).isoformat()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
  salt TEXT NOT NULL, pw_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','staff')),
  must_change INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS accounts(
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  grp TEXT NOT NULL,
  nature TEXT NOT NULL CHECK(nature IN ('Asset','Liability','Income','Expense')),
  opening INTEGER NOT NULL DEFAULT 0,
  opening_side TEXT NOT NULL DEFAULT 'Dr' CHECK(opening_side IN ('Dr','Cr')));
CREATE TABLE IF NOT EXISTS vouchers(
  id INTEGER PRIMARY KEY, vtype TEXT NOT NULL, vno INTEGER NOT NULL,
  vdate TEXT NOT NULL, fy TEXT NOT NULL, narration TEXT DEFAULT '',
  UNIQUE(vtype, vno, fy));
CREATE TABLE IF NOT EXISTS entries(
  id INTEGER PRIMARY KEY,
  voucher_id INTEGER NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  dr INTEGER NOT NULL DEFAULT 0 CHECK(dr >= 0),
  cr INTEGER NOT NULL DEFAULT 0 CHECK(cr >= 0),
  CHECK((dr = 0) <> (cr = 0)));
CREATE TABLE IF NOT EXISTS parties(
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  ptype TEXT NOT NULL CHECK(ptype IN ('Customer','Supplier')),
  gstin TEXT DEFAULT '', phone TEXT DEFAULT '', address TEXT DEFAULT '',
  account_id INTEGER NOT NULL REFERENCES accounts(id));
"""

DEFAULT_ACCOUNTS = [
    ("Cash", "Cash-in-hand", "Asset"), ("Bank", "Bank Accounts", "Asset"),
    ("Sundry Debtors", "Current Assets", "Asset"),
    ("Stock-in-Trade", "Current Assets", "Asset"),
    ("Capital", "Capital Account", "Liability"),
    ("Sundry Creditors", "Current Liabilities", "Liability"),
    ("Sales", "Sales Accounts", "Income"), ("Purchase", "Purchase Accounts", "Expense"),
    ("Rent", "Indirect Expenses", "Expense"), ("Salary", "Indirect Expenses", "Expense"),
]

def hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()

def add_user(con, username, password, role="staff", must_change=0):
    salt = secrets.token_hex(16)
    con.execute("INSERT INTO users(username,salt,pw_hash,role,must_change) VALUES(?,?,?,?,?)",
                (username, salt, hash_pw(password, salt), role, must_change))
    con.commit()

def login(con, username, password):
    """Returns the user row on success, else None."""
    r = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if r and secrets.compare_digest(r["pw_hash"], hash_pw(password, r["salt"])):
        return r
    return None

def check_login(con, username, password):
    r = login(con, username, password)
    return r["role"] if r else None

def change_password(con, username, new_password):
    if len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if new_password == "admin123":
        raise ValueError("Choose a password different from the default")
    salt = secrets.token_hex(16)
    con.execute("UPDATE users SET salt=?, pw_hash=?, must_change=0 WHERE username=?",
                (salt, hash_pw(new_password, salt), username))
    con.commit()

def add_account(con, name, grp, nature, opening=0, opening_side="Dr"):
    cur = con.execute(
        "INSERT INTO accounts(name,grp,nature,opening,opening_side) VALUES(?,?,?,?,?)",
        (name, grp, nature, to_paise(opening), opening_side))
    con.commit()
    return cur.lastrowid

def init_db(path=None):
    con = connect(path)
    con.executescript(SCHEMA)
    cols = [r["name"] for r in con.execute("PRAGMA table_info(users)")]
    if "must_change" not in cols:  # database created by an older MUNIM version
        con.execute("ALTER TABLE users ADD COLUMN must_change INTEGER NOT NULL DEFAULT 0")
    if not con.execute("SELECT 1 FROM accounts LIMIT 1").fetchone():
        for n, g, nat in DEFAULT_ACCOUNTS:
            con.execute("INSERT INTO accounts(name,grp,nature) VALUES(?,?,?)", (n, g, nat))
    if not con.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        add_user(con, "admin", "admin123", "admin", must_change=1)
    if login(con, "admin", "admin123"):  # default password still in use
        con.execute("UPDATE users SET must_change=1 WHERE username='admin'")
    con.commit()
    return con

def post_voucher(con, vtype, vdate, narration, lines):
    """lines: list of (account_name, dr_rupees, cr_rupees). Rejects unbalanced vouchers."""
    rows = []
    for name, dr, cr in lines:
        a = con.execute("SELECT id FROM accounts WHERE name=?", (name,)).fetchone()
        if not a:
            raise ValueError(f"Unknown account: {name}")
        rows.append((a["id"], to_paise(dr), to_paise(cr)))
    if len(rows) < 2:
        raise ValueError("A voucher needs at least two lines")
    if sum(r[1] for r in rows) != sum(r[2] for r in rows):
        raise ValueError("Voucher not balanced: total Dr must equal total Cr")
    fy = fy_of(vdate)
    vno = (con.execute("SELECT COALESCE(MAX(vno),0) FROM vouchers WHERE vtype=? AND fy=?",
                       (vtype, fy)).fetchone()[0]) + 1
    try:
        cur = con.execute("INSERT INTO vouchers(vtype,vno,vdate,fy,narration) VALUES(?,?,?,?,?)",
                          (vtype, vno, vdate.isoformat(), fy, narration))
        con.executemany("INSERT INTO entries(voucher_id,account_id,dr,cr) VALUES(?,?,?,?)",
                        [(cur.lastrowid, a, d, c) for a, d, c in rows])
        con.commit()
    except Exception:
        con.rollback()
        raise
    return vno

def trial_balance(con, fy):
    """Returns (rows, total_dr, total_cr) in rupees. Opening balances count as of FY start."""
    start, end = fy_range(fy)
    out, td, tc = [], 0, 0
    for a in con.execute("SELECT * FROM accounts ORDER BY nature, name"):
        t = con.execute(
            """SELECT COALESCE(SUM(e.dr),0) d, COALESCE(SUM(e.cr),0) c FROM entries e
               JOIN vouchers v ON v.id=e.voucher_id
               WHERE e.account_id=? AND v.vdate BETWEEN ? AND ?""",
            (a["id"], start, end)).fetchone()
        dr = t["d"] + (a["opening"] if a["opening_side"] == "Dr" else 0)
        cr = t["c"] + (a["opening"] if a["opening_side"] == "Cr" else 0)
        net = dr - cr
        if net == 0:
            continue
        d, c = (net, 0) if net > 0 else (0, -net)
        out.append((a["name"], to_rupees(d), to_rupees(c)))
        td += d; tc += c
    if td != tc:  # opening balances entered one-sided, as Tally shows it
        diff = abs(td - tc)
        if td > tc:
            out.append(("Difference in opening balances", 0, to_rupees(diff))); tc += diff
        else:
            out.append(("Difference in opening balances", to_rupees(diff), 0)); td += diff
    return out, to_rupees(td), to_rupees(tc)


# ---------- Party master ----------
import re
GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

def add_party(con, name, ptype, gstin="", phone="", address="", opening=0):
    """Creates the party and its ledger account together. Opening: customers Dr, suppliers Cr."""
    name = (name or "").strip()
    gstin = (gstin or "").strip().upper()
    if not name:
        raise ValueError("Party name is required")
    if ptype not in ("Customer", "Supplier"):
        raise ValueError("Type must be Customer or Supplier")
    if gstin and not GSTIN_RE.match(gstin):
        raise ValueError("GSTIN format is invalid (15 characters, e.g. 03ABCDE1234F1Z5)")
    try:
        amount = to_paise(opening or 0)
    except ValueError:
        raise ValueError("Opening balance must be a number")
    if amount < 0:
        raise ValueError("Opening balance cannot be negative")
    if con.execute("SELECT 1 FROM accounts WHERE name=?", (name,)).fetchone():
        raise ValueError("A ledger account with this name already exists")
    grp, nature, side = (("Sundry Debtors", "Asset", "Dr") if ptype == "Customer"
                         else ("Sundry Creditors", "Liability", "Cr"))
    try:
        cur = con.execute(
            "INSERT INTO accounts(name,grp,nature,opening,opening_side) VALUES(?,?,?,?,?)",
            (name, grp, nature, amount, side))
        con.execute(
            "INSERT INTO parties(name,ptype,gstin,phone,address,account_id) VALUES(?,?,?,?,?,?)",
            (name, ptype, gstin, (phone or "").strip(), (address or "").strip(), cur.lastrowid))
        con.commit()
    except Exception:
        con.rollback()
        raise
    return cur.lastrowid

def list_parties(con, ptype=None):
    q = """SELECT p.name, p.ptype, p.gstin, p.phone, p.address, a.opening, a.opening_side
           FROM parties p JOIN accounts a ON a.id=p.account_id"""
    args = ()
    if ptype in ("Customer", "Supplier"):
        q += " WHERE p.ptype=?"
        args = (ptype,)
    return con.execute(q + " ORDER BY p.name COLLATE NOCASE", args).fetchall()

def counts(con):
    one = lambda q: con.execute(q).fetchone()[0]
    return {"parties": one("SELECT COUNT(*) FROM parties"),
            "accounts": one("SELECT COUNT(*) FROM accounts"),
            "vouchers": one("SELECT COUNT(*) FROM vouchers")}
