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
  credit_days INTEGER NOT NULL DEFAULT 0,
  account_id INTEGER NOT NULL REFERENCES accounts(id));
CREATE TABLE IF NOT EXISTS invoices(
  id INTEGER PRIMARY KEY,
  voucher_id INTEGER UNIQUE NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK(kind IN ('Sales','Purchase')),
  party TEXT NOT NULL, interstate INTEGER NOT NULL DEFAULT 0,
  taxable INTEGER NOT NULL, cgst INTEGER NOT NULL, sgst INTEGER NOT NULL,
  igst INTEGER NOT NULL, total INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS invoice_items(
  id INTEGER PRIMARY KEY,
  invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL, description TEXT NOT NULL,
  qty TEXT NOT NULL, rate TEXT NOT NULL, gst TEXT NOT NULL, amount INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS allocations(
  id INTEGER PRIMARY KEY,
  payment_voucher_id INTEGER NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
  invoice_voucher_id INTEGER NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
  amount INTEGER NOT NULL CHECK(amount > 0));
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, username TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL, vtype TEXT, vno INTEGER, fy TEXT, detail TEXT);
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
    if "credit_days" not in [r["name"] for r in con.execute("PRAGMA table_info(parties)")]:
        con.execute("ALTER TABLE parties ADD COLUMN credit_days INTEGER NOT NULL DEFAULT 0")
    if not con.execute("SELECT 1 FROM accounts LIMIT 1").fetchone():
        for n, g, nat in DEFAULT_ACCOUNTS:
            con.execute("INSERT INTO accounts(name,grp,nature) VALUES(?,?,?)", (n, g, nat))
    if not con.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        add_user(con, "admin", "admin123", "admin", must_change=1)
    if login(con, "admin", "admin123"):  # default password still in use
        con.execute("UPDATE users SET must_change=1 WHERE username='admin'")
    con.commit()
    return con

def post_voucher(con, vtype, vdate, narration, lines, username=""):
    """lines: list of (account_name, dr_rupees, cr_rupees). Rejects unbalanced vouchers."""
    return post_voucher_paise(con, vtype, vdate, narration,
                              [(n, to_paise(d), to_paise(c)) for n, d, c in lines], username)

def _resolve(con, lines):
    rows = []
    for name, dr, cr in lines:
        if dr == 0 and cr == 0:
            continue
        a = con.execute("SELECT id FROM accounts WHERE name=?", (name,)).fetchone()
        if not a:
            raise ValueError(f"Unknown account: {name}")
        rows.append((a["id"], dr, cr))
    if len(rows) < 2:
        raise ValueError("A voucher needs at least two lines")
    if sum(r[1] for r in rows) != sum(r[2] for r in rows):
        raise ValueError("Voucher not balanced: total Dr must equal total Cr")
    return rows

def _next_vno(con, vtype, fy):
    return con.execute("SELECT COALESCE(MAX(vno),0)+1 FROM vouchers WHERE vtype=? AND fy=?",
                       (vtype, fy)).fetchone()[0]

def _insert_voucher(con, vtype, vdate, narration, lines):
    """Inserts a voucher WITHOUT committing. Returns (vno, voucher_id)."""
    rows = _resolve(con, lines)
    fy = fy_of(vdate)
    vno = _next_vno(con, vtype, fy)
    cur = con.execute("INSERT INTO vouchers(vtype,vno,vdate,fy,narration) VALUES(?,?,?,?,?)",
                      (vtype, vno, vdate.isoformat(), fy, narration))
    con.executemany("INSERT INTO entries(voucher_id,account_id,dr,cr) VALUES(?,?,?,?)",
                    [(cur.lastrowid, a, d, c) for a, d, c in rows])
    return vno, cur.lastrowid

def post_voucher_paise(con, vtype, vdate, narration, lines, username=""):
    """Same as post_voucher but amounts are integer paise (used by GST billing)."""
    try:
        vno, vid = _insert_voucher(con, vtype, vdate, narration, lines)
        log_action(con, username, "create", after=voucher_snapshot(con, vid))
        con.commit()
    except Exception:
        con.rollback()
        raise
    return vno

def _replace_voucher(con, vid, vtype, vdate, narration, lines):
    """Rewrites a voucher in place WITHOUT committing. Keeps its number unless type or FY changes."""
    rows = _resolve(con, lines)          # validate everything before touching the old data
    old = con.execute("SELECT vtype, vno, fy FROM vouchers WHERE id=?", (vid,)).fetchone()
    fy = fy_of(vdate)
    vno = old["vno"] if (old["vtype"], old["fy"]) == (vtype, fy) else _next_vno(con, vtype, fy)
    con.execute("UPDATE vouchers SET vtype=?, vno=?, vdate=?, fy=?, narration=? WHERE id=?",
                (vtype, vno, vdate.isoformat(), fy, narration, vid))
    con.execute("DELETE FROM entries WHERE voucher_id=?", (vid,))
    con.executemany("INSERT INTO entries(voucher_id,account_id,dr,cr) VALUES(?,?,?,?)",
                    [(vid, a, d, c) for a, d, c in rows])
    return vno

def voucher_snapshot(con, vid):
    v = con.execute("SELECT * FROM vouchers WHERE id=?", (vid,)).fetchone()
    if not v:
        raise ValueError("Voucher not found")
    lines = [{"account": r["name"], "dr": r["dr"], "cr": r["cr"]} for r in con.execute(
        """SELECT a.name, e.dr, e.cr FROM entries e JOIN accounts a ON a.id=e.account_id
           WHERE e.voucher_id=? ORDER BY e.id""", (vid,))]
    inv = None
    i = con.execute("SELECT * FROM invoices WHERE voucher_id=?", (vid,)).fetchone()
    if i:
        inv = {k: i[k] for k in ("kind", "party", "interstate", "taxable", "cgst", "sgst", "igst", "total")}
        inv["items"] = [{k: it[k] for k in ("description", "qty", "rate", "gst", "amount")}
                        for it in con.execute("SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY seq", (i["id"],))]
    pays = [{"id": r["id"], "vtype": r["vtype"], "vno": r["vno"], "vdate": r["vdate"], "amount": r["amount"]}
            for r in con.execute(
                """SELECT v.id, v.vtype, v.vno, v.vdate, a.amount FROM allocations a
                   JOIN vouchers v ON v.id=a.payment_voucher_id
                   WHERE a.invoice_voucher_id=? ORDER BY v.vdate, v.id""", (vid,))]
    applied = [{"id": r["id"], "vtype": r["vtype"], "vno": r["vno"], "vdate": r["vdate"], "amount": r["amount"]}
               for r in con.execute(
                   """SELECT v.id, v.vtype, v.vno, v.vdate, a.amount FROM allocations a
                      JOIN vouchers v ON v.id=a.invoice_voucher_id
                      WHERE a.payment_voucher_id=? ORDER BY v.vdate, v.id""", (vid,))]
    return {"id": vid, "vtype": v["vtype"], "vno": v["vno"], "vdate": v["vdate"], "fy": v["fy"],
            "narration": v["narration"], "lines": lines, "invoice": inv,
            "payments_in": pays, "applied_to": applied}

def log_action(con, username, action, before=None, after=None):
    """Adds an audit row WITHOUT committing."""
    import json
    from datetime import datetime
    ref = after or before or {}
    con.execute("INSERT INTO audit_log(at,username,action,vtype,vno,fy,detail) VALUES(?,?,?,?,?,?,?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username or "", action,
                 ref.get("vtype"), ref.get("vno"), ref.get("fy"),
                 json.dumps({"before": before, "after": after})))

MANUAL_TYPES = ("Journal", "Payment", "Receipt", "Contra")

def update_voucher(con, vid, vtype, vdate, narration, lines, username=""):
    """Edit a Journal/Payment/Receipt/Contra voucher. lines in rupees. All-or-nothing."""
    if vtype not in MANUAL_TYPES:
        raise ValueError("Sales and purchase bills are edited from their own screens")
    if con.execute("SELECT 1 FROM invoices WHERE voucher_id=?", (vid,)).fetchone():
        raise ValueError("This is an invoice. Edit it from the Sales/Purchase screen")
    if con.execute("SELECT 1 FROM allocations WHERE payment_voucher_id=? OR invoice_voucher_id=?",
                   (vid, vid)).fetchone():
        raise ValueError("This entry settles bills, so it cannot be edited. Delete it and enter it again")
    before = voucher_snapshot(con, vid)
    try:
        _replace_voucher(con, vid, vtype, vdate, narration,
                         [(n, to_paise(d), to_paise(c)) for n, d, c in lines])
        log_action(con, username, "edit", before=before, after=voucher_snapshot(con, vid))
        con.commit()
    except Exception:
        con.rollback()
        raise

def delete_voucher(con, vid, username=""):
    before = voucher_snapshot(con, vid)
    try:
        log_action(con, username, "delete", before=before)
        con.execute("DELETE FROM vouchers WHERE id=?", (vid,))
        con.commit()
    except Exception:
        con.rollback()
        raise

def audit_entries(con, limit=300):
    import json
    out = []
    for r in con.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)):
        d = json.loads(r["detail"] or "{}")
        snap = d.get("after") or d.get("before") or {}
        total = sum(l["dr"] for l in snap.get("lines", []))
        out.append({"at": r["at"], "user": r["username"], "action": r["action"],
                    "vtype": r["vtype"], "vno": r["vno"], "amount": to_rupees(total)})
    return out

def ensure_account(con, name, grp, nature):
    if not con.execute("SELECT 1 FROM accounts WHERE name=?", (name,)).fetchone():
        con.execute("INSERT INTO accounts(name,grp,nature) VALUES(?,?,?)", (name, grp, nature))
        con.commit()

def account_states(con, fy):
    """Per account: opening brought forward, FY movement, and the prior-year profit.
    Balance-sheet accounts carry prior years forward; income/expense accounts start at zero
    each FY and their prior result is rolled into 'prior_pl' (Cr-positive = profit), in paise."""
    start, end = fy_range(fy)
    rows = con.execute(
        """SELECT a.id, a.name, a.nature, a.opening, a.opening_side,
             COALESCE(SUM(CASE WHEN v.vdate < ? THEN e.dr END),0) pdr,
             COALESCE(SUM(CASE WHEN v.vdate < ? THEN e.cr END),0) pcr,
             COALESCE(SUM(CASE WHEN v.vdate BETWEEN ? AND ? THEN e.dr END),0) dr,
             COALESCE(SUM(CASE WHEN v.vdate BETWEEN ? AND ? THEN e.cr END),0) cr
           FROM accounts a LEFT JOIN entries e ON e.account_id=a.id
                           LEFT JOIN vouchers v ON v.id=e.voucher_id
           GROUP BY a.id ORDER BY a.nature, a.name""",
        (start, start, start, end, start, end)).fetchall()
    out, prior_pl = [], 0
    for r in rows:
        signed_open = r["opening"] if r["opening_side"] == "Dr" else -r["opening"]
        if r["nature"] in ("Asset", "Liability"):
            bf = signed_open + r["pdr"] - r["pcr"]
        else:
            bf = 0
            prior_pl += (r["pcr"] - r["pdr"]) - signed_open
        out.append({"id": r["id"], "name": r["name"], "nature": r["nature"],
                    "bf": bf, "dr": r["dr"], "cr": r["cr"]})
    return out, prior_pl

def trial_balance(con, fy):
    """Returns (rows, total_dr, total_cr) in rupees, with prior years carried forward."""
    states, prior_pl = account_states(con, fy)
    out, td, tc = [], 0, 0
    def add(name, net):
        nonlocal td, tc
        if net == 0:
            return
        d, c = (net, 0) if net > 0 else (0, -net)
        out.append((name, to_rupees(d), to_rupees(c)))
        td += d; tc += c
    for st in states:
        add(st["name"], st["bf"] + st["dr"] - st["cr"])
    add("Profit & Loss A/c (b/f)", -prior_pl)
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

def _credit_days(value):
    try:
        days = int(str(value if value not in (None, "") else 0).strip())
    except ValueError:
        raise ValueError("Credit days must be a whole number")
    if not 0 <= days <= 365:
        raise ValueError("Credit days must be between 0 and 365")
    return days

def set_credit_days(con, name, days):
    d = _credit_days(days)
    con.execute("UPDATE parties SET credit_days=? WHERE name=?", (d, name))
    con.commit()

def add_party(con, name, ptype, gstin="", phone="", address="", opening=0, credit_days=0):
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
    days = _credit_days(credit_days)
    if con.execute("SELECT 1 FROM accounts WHERE name=?", (name,)).fetchone():
        raise ValueError("A ledger account with this name already exists")
    grp, nature, side = (("Sundry Debtors", "Asset", "Dr") if ptype == "Customer"
                         else ("Sundry Creditors", "Liability", "Cr"))
    try:
        cur = con.execute(
            "INSERT INTO accounts(name,grp,nature,opening,opening_side) VALUES(?,?,?,?,?)",
            (name, grp, nature, amount, side))
        con.execute(
            "INSERT INTO parties(name,ptype,gstin,phone,address,account_id,credit_days) VALUES(?,?,?,?,?,?,?)",
            (name, ptype, gstin, (phone or "").strip(), (address or "").strip(), cur.lastrowid, days))
        con.commit()
    except Exception:
        con.rollback()
        raise
    return cur.lastrowid

def list_parties(con, ptype=None):
    q = """SELECT p.name, p.ptype, p.gstin, p.phone, p.address, a.opening, a.opening_side, p.credit_days
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


def backup_db(con, folder):
    """Consistent copy of the live database into folder. Returns the new file's path."""
    from datetime import datetime
    dest_path = os.path.join(folder, f"munim_backup_{datetime.now():%Y%m%d_%H%M%S}.db")
    dest = sqlite3.connect(dest_path)
    try:
        con.backup(dest)
    finally:
        dest.close()
    return dest_path


def fy_choices(con):
    """Financial years to offer in pickers: this year, last year, and any year with vouchers."""
    y = date.today().year if date.today().month >= 4 else date.today().year - 1
    fys = {f"{y}-{str(y + 1)[2:]}", f"{y - 1}-{str(y)[2:]}"}
    fys |= {r[0] for r in con.execute("SELECT DISTINCT fy FROM vouchers")}
    return sorted(fys, reverse=True)


def find_voucher(con, vtype, vno, vdate):
    """Voucher id for a type, number and date (used to open a voucher just saved)."""
    r = con.execute("SELECT id FROM vouchers WHERE vtype=? AND vno=? AND fy=?",
                    (vtype, vno, fy_of(vdate))).fetchone()
    return r["id"] if r else None
