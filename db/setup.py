"""MUNIM accounting engine: SQLite schema, double-entry posting, trial balance.
Amounts are stored as integer paise to avoid float rounding errors."""
import os, sqlite3, hashlib, secrets
from datetime import date

def data_dir():
    default = r"C:\MUNIM" if os.name == "nt" else os.path.join(os.path.expanduser("~"), "MUNIM")
    os.makedirs(default, exist_ok=True)
    pointer = os.path.join(default, "data_location.txt")
    if os.path.exists(pointer):
        try:
            with open(pointer, encoding="utf-8") as f:
                custom = f.read().strip()
            if custom and os.path.isdir(custom):
                return custom
        except OSError:
            pass
    return default

def db_path():
    return os.path.join(data_dir(), "munim.db")

def companies_dir():
    d = os.path.join(data_dir(), "companies")
    os.makedirs(d, exist_ok=True)
    return d

def _safe_filename(name):
    import re
    safe = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return safe or "Company"

def company_db_path(name):
    return os.path.join(companies_dir(), _safe_filename(name) + ".db")

def company_settings_path(name):
    return os.path.join(companies_dir(), _safe_filename(name) + ".settings.json")

def list_companies():
    import json, shutil
    cdir = companies_dir()
    legacy = os.path.join(data_dir(), "munim.db")
    legacy_settings = os.path.join(data_dir(), "settings.json")
    if os.path.exists(legacy):
        try:
            name = "My Company"
            if os.path.exists(legacy_settings):
                with open(legacy_settings, encoding="utf-8") as f:
                    name = json.load(f).get("company_name") or "My Company"
        except Exception:
            name = "My Company"
        safe = _safe_filename(name)
        dest = os.path.join(cdir, safe + ".db")
        if not os.path.exists(dest):
            shutil.copy2(legacy, dest)
            dest_st = os.path.join(cdir, safe + ".settings.json")
            if os.path.exists(legacy_settings) and not os.path.exists(dest_st):
                shutil.copy2(legacy_settings, dest_st)
        os.rename(legacy, legacy + ".migrated")
    files = sorted(f for f in os.listdir(cdir) if f.endswith(".db"))
    return [{"name": os.path.splitext(f)[0], "path": os.path.join(cdir, f)} for f in files]

def create_company(name):
    name = (name or "").strip()
    if not name:
        raise ValueError("Company name is required")
    path = company_db_path(name)
    if os.path.exists(path):
        raise ValueError(f"A company named '{name}' already exists")
    con = connect(path)
    con.executescript(SCHEMA)
    for n, g, nat in DEFAULT_ACCOUNTS:
        con.execute("INSERT INTO accounts(name,grp,nature) VALUES(?,?,?)", (n, g, nat))
    add_user(con, "admin", "admin123", "admin", must_change=1)
    con.commit()
    con.close()
    return path

def delete_company(name):
    path = company_db_path(name)
    sp = company_settings_path(name)
    if not os.path.exists(path):
        raise ValueError("Company not found")
    os.remove(path)
    if os.path.exists(sp):
        os.remove(sp)

def rename_company(old_name, new_name):
    new_name = (new_name or "").strip()
    if not new_name:
        raise ValueError("Name cannot be empty")
    old_path = company_db_path(old_name)
    new_path = company_db_path(new_name)
    if not os.path.exists(old_path):
        raise ValueError("Company not found")
    if os.path.exists(new_path):
        raise ValueError(f"A company named '{new_name}' already exists")
    os.rename(old_path, new_path)
    old_sp = company_settings_path(old_name)
    new_sp = company_settings_path(new_name)
    if os.path.exists(old_sp):
        os.rename(old_sp, new_sp)

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
  igst INTEGER NOT NULL, total INTEGER NOT NULL, customer_name TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS invoice_items(
  id INTEGER PRIMARY KEY,
  invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL, description TEXT NOT NULL,
  hsn TEXT NOT NULL DEFAULT '',
  qty TEXT NOT NULL, rate TEXT NOT NULL, gst TEXT NOT NULL, amount INTEGER NOT NULL,
  stock_item_id INTEGER REFERENCES stock_items(id));
CREATE TABLE IF NOT EXISTS stock_items(
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  hsn TEXT NOT NULL DEFAULT '',
  unit TEXT NOT NULL DEFAULT 'pcs',
  gst_rate TEXT NOT NULL DEFAULT '18',
  opening_qty TEXT NOT NULL DEFAULT '0',
  opening_rate TEXT NOT NULL DEFAULT '0');
CREATE TABLE IF NOT EXISTS allocations(
  id INTEGER PRIMARY KEY,
  payment_voucher_id INTEGER NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
  invoice_voucher_id INTEGER NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
  amount INTEGER NOT NULL CHECK(amount > 0));
CREATE TABLE IF NOT EXISTS stock_manual(
  fy TEXT PRIMARY KEY, opening INTEGER, closing INTEGER NOT NULL DEFAULT 0);
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
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    salt = secrets.token_hex(16)
    con.execute("INSERT INTO users(username,salt,pw_hash,role,must_change) VALUES(?,?,?,?,?)",
                (username, salt, hash_pw(password, salt), role, must_change))
    con.commit()

def list_users(con):
    return con.execute(
        "SELECT username, role, must_change FROM users ORDER BY username COLLATE NOCASE"
    ).fetchall()

def delete_user(con, username):
    if not con.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
        raise ValueError("User not found")
    con.execute("DELETE FROM users WHERE username=?", (username,))
    con.commit()

def login(con, username, password):
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
    if "must_change" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN must_change INTEGER NOT NULL DEFAULT 0")
    if "customer_name" not in [r["name"] for r in con.execute("PRAGMA table_info(invoices)")]:
        con.execute("ALTER TABLE invoices ADD COLUMN customer_name TEXT NOT NULL DEFAULT ''")
    if "credit_days" not in [r["name"] for r in con.execute("PRAGMA table_info(parties)")]:
        con.execute("ALTER TABLE parties ADD COLUMN credit_days INTEGER NOT NULL DEFAULT 0")
    if "hsn" not in [r["name"] for r in con.execute("PRAGMA table_info(invoice_items)")]:
        con.execute("ALTER TABLE invoice_items ADD COLUMN hsn TEXT NOT NULL DEFAULT ''")
    if "stock_item_id" not in [r["name"] for r in con.execute("PRAGMA table_info(invoice_items)")]:
        con.execute("ALTER TABLE invoice_items ADD COLUMN stock_item_id INTEGER REFERENCES stock_items(id)")
    if "opening_rate" not in [r["name"] for r in con.execute("PRAGMA table_info(stock_items)")]:
        con.execute("ALTER TABLE stock_items ADD COLUMN opening_rate TEXT NOT NULL DEFAULT '0'")
    if not con.execute("SELECT 1 FROM accounts LIMIT 1").fetchone():
        for n, g, nat in DEFAULT_ACCOUNTS:
            con.execute("INSERT INTO accounts(name,grp,nature) VALUES(?,?,?)", (n, g, nat))
    if not con.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        add_user(con, "admin", "admin123", "admin", must_change=1)
    if login(con, "admin", "admin123"):
        con.execute("UPDATE users SET must_change=1 WHERE username='admin'")
    con.commit()
    return con

def reset_all_data(con, admin_password):
    admin = con.execute("SELECT * FROM users WHERE role='admin' LIMIT 1").fetchone()
    if not admin:
        raise ValueError("No admin account found")
    if not secrets.compare_digest(admin["pw_hash"], hash_pw(admin_password, admin["salt"])):
        raise ValueError("Wrong admin password")
    con.executescript("""
        DELETE FROM allocations;
        DELETE FROM invoice_items;
        DELETE FROM invoices;
        DELETE FROM entries;
        DELETE FROM vouchers;
        DELETE FROM parties;
        DELETE FROM audit_log;
        DELETE FROM stock_manual;
        DELETE FROM stock_items;
        DELETE FROM accounts;
    """)
    for n, g, nat in DEFAULT_ACCOUNTS:
        con.execute("INSERT INTO accounts(name,grp,nature) VALUES(?,?,?)", (n, g, nat))
    con.commit()

def post_voucher(con, vtype, vdate, narration, lines, username=""):
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
    rows = _resolve(con, lines)
    fy = fy_of(vdate)
    vno = _next_vno(con, vtype, fy)
    cur = con.execute("INSERT INTO vouchers(vtype,vno,vdate,fy,narration) VALUES(?,?,?,?,?)",
                      (vtype, vno, vdate.isoformat(), fy, narration))
    con.executemany("INSERT INTO entries(voucher_id,account_id,dr,cr) VALUES(?,?,?,?)",
                    [(cur.lastrowid, a, d, c) for a, d, c in rows])
    return vno, cur.lastrowid

def post_voucher_paise(con, vtype, vdate, narration, lines, username=""):
    try:
        vno, vid = _insert_voucher(con, vtype, vdate, narration, lines)
        log_action(con, username, "create", after=voucher_snapshot(con, vid))
        con.commit()
    except Exception:
        con.rollback()
        raise
    return vno

def _replace_voucher(con, vid, vtype, vdate, narration, lines):
    rows = _resolve(con, lines)
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
        inv = {k: i[k] for k in ("kind", "party", "customer_name", "interstate", "taxable", "cgst", "sgst", "igst", "total")}
        inv["items"] = [{k: it[k] for k in ("description", "hsn", "qty", "rate", "gst", "amount")}
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
    import json
    from datetime import datetime
    ref = after or before or {}
    con.execute("INSERT INTO audit_log(at,username,action,vtype,vno,fy,detail) VALUES(?,?,?,?,?,?,?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username or "", action,
                 ref.get("vtype"), ref.get("vno"), ref.get("fy"),
                 json.dumps({"before": before, "after": after})))

MANUAL_TYPES = ("Journal", "Payment", "Receipt", "Contra")

def update_voucher(con, vid, vtype, vdate, narration, lines, username=""):
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
    if td != tc:
        diff = abs(td - tc)
        if td > tc:
            out.append(("Difference in opening balances", 0, to_rupees(diff))); tc += diff
        else:
            out.append(("Difference in opening balances", to_rupees(diff), 0)); td += diff
    return out, to_rupees(td), to_rupees(tc)

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

def update_party(con, old_name, name, ptype, gstin="", phone="", address="", credit_days=0):
    """Update an existing party's details. Renames the linked ledger account too."""
    name = (name or "").strip()
    gstin = (gstin or "").strip().upper()
    if not name:
        raise ValueError("Party name is required")
    if ptype not in ("Customer", "Supplier"):
        raise ValueError("Type must be Customer or Supplier")
    if gstin and not GSTIN_RE.match(gstin):
        raise ValueError("GSTIN format is invalid (15 characters, e.g. 03ABCDE1234F1Z5)")
    days = _credit_days(credit_days)

    row = con.execute("SELECT id, account_id, ptype FROM parties WHERE name=?",
                      (old_name,)).fetchone()
    if not row:
        raise ValueError("Party not found")

    if name != old_name:
        if con.execute("SELECT 1 FROM parties WHERE name=? COLLATE NOCASE AND id!=?",
                       (name, row["id"])).fetchone():
            raise ValueError("Another party with this name already exists")
        if con.execute("SELECT 1 FROM accounts WHERE name=? COLLATE NOCASE AND id!=?",
                       (name, row["account_id"])).fetchone():
            raise ValueError("A ledger account with this name already exists")

    try:
        if ptype != row["ptype"]:
            grp, nature, side = (("Sundry Debtors", "Asset", "Dr") if ptype == "Customer"
                                 else ("Sundry Creditors", "Liability", "Cr"))
            con.execute("UPDATE accounts SET name=?, grp=?, nature=?, opening_side=? WHERE id=?",
                        (name, grp, nature, side, row["account_id"]))
        else:
            con.execute("UPDATE accounts SET name=? WHERE id=?", (name, row["account_id"]))

        con.execute(
            "UPDATE parties SET name=?, ptype=?, gstin=?, phone=?, address=?, credit_days=? WHERE id=?",
            (name, ptype, gstin, (phone or "").strip(), (address or "").strip(), days, row["id"]))

        if name != old_name:
            con.execute("UPDATE invoices SET party=? WHERE party=?", (name, old_name))

        con.commit()
    except Exception:
        con.rollback()
        raise

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
    from datetime import datetime
    dest_path = os.path.join(folder, f"munim_backup_{datetime.now():%Y%m%d_%H%M%S}.db")
    dest = sqlite3.connect(dest_path)
    try:
        con.backup(dest)
    finally:
        dest.close()
    return dest_path

def fy_choices(con):
    y = date.today().year if date.today().month >= 4 else date.today().year - 1
    fys = {f"{y}-{str(y + 1)[2:]}", f"{y - 1}-{str(y)[2:]}"}
    fys |= {r[0] for r in con.execute("SELECT DISTINCT fy FROM vouchers")}
    return sorted(fys, reverse=True)

def find_voucher(con, vtype, vno, vdate):
    r = con.execute("SELECT id FROM vouchers WHERE vtype=? AND vno=? AND fy=?",
                    (vtype, vno, fy_of(vdate))).fetchone()
    return r["id"] if r else None

ACCOUNT_GROUPS = [
    ("Direct Expenses", "Expense"), ("Indirect Expenses", "Expense"),
    ("Direct Income", "Income"), ("Indirect Income", "Income"),
    ("Cash-in-hand", "Asset"), ("Bank Accounts", "Asset"), ("Current Assets", "Asset"),
    ("Fixed Assets", "Asset"), ("Loans & Advances (Asset)", "Asset"),
    ("Capital Account", "Liability"), ("Current Liabilities", "Liability"),
    ("Loans (Liability)", "Liability"), ("Duties & Taxes", "Liability"),
]
GROUP_NATURE = dict(ACCOUNT_GROUPS)
SYSTEM_ACCOUNTS = {"Cash", "Bank", "Sales", "Purchase", "Capital", "Sundry Debtors", "Sundry Creditors",
                   "Stock-in-Trade", "Output CGST", "Output SGST", "Output IGST",
                   "Input CGST", "Input SGST", "Input IGST"}

def add_ledger_account(con, name, group, opening=0, side="Dr"):
    name = (name or "").strip()
    if not name:
        raise ValueError("Account name is required")
    if group not in GROUP_NATURE:
        raise ValueError("Choose a group for the account")
    if side not in ("Dr", "Cr"):
        raise ValueError("Opening side must be Dr or Cr")
    try:
        amount = to_paise(opening or 0)
    except ValueError:
        raise ValueError("Opening balance must be a number")
    if amount < 0:
        raise ValueError("Opening balance cannot be negative")
    if con.execute("SELECT 1 FROM accounts WHERE name=? COLLATE NOCASE", (name,)).fetchone():
        raise ValueError("An account with this name already exists")
    con.execute("INSERT INTO accounts(name,grp,nature,opening,opening_side) VALUES(?,?,?,?,?)",
                (name, group, GROUP_NATURE[group], amount, side))
    con.commit()

def set_account_opening(con, name, opening, side):
    if side not in ("Dr", "Cr"):
        raise ValueError("Opening side must be Dr or Cr")
    try:
        amount = to_paise(opening or 0)
    except ValueError:
        raise ValueError("Opening balance must be a number")
    if amount < 0:
        raise ValueError("Opening balance cannot be negative")
    if con.execute("UPDATE accounts SET opening=?, opening_side=? WHERE name=?",
                   (amount, side, name)).rowcount == 0:
        raise ValueError("Account not found")
    con.commit()

def delete_ledger_account(con, name):
    a = con.execute("SELECT id FROM accounts WHERE name=?", (name,)).fetchone()
    if not a:
        raise ValueError("Account not found")
    if name in SYSTEM_ACCOUNTS:
        raise ValueError("This is a built-in account and cannot be deleted")
    if con.execute("SELECT 1 FROM parties WHERE account_id=?", (a["id"],)).fetchone():
        raise ValueError("This account belongs to a party. Parties cannot be deleted yet")
    if con.execute("SELECT 1 FROM entries WHERE account_id=?", (a["id"],)).fetchone():
        raise ValueError("This account already has entries, so it cannot be deleted")
    con.execute("DELETE FROM accounts WHERE id=?", (a["id"],))
    con.commit()

def list_accounts(con):
    return con.execute("SELECT name, grp, nature, opening, opening_side FROM accounts "
                       "ORDER BY nature, grp, name COLLATE NOCASE").fetchall()

UNSET = object()

def prev_fy(fy):
    y = int(fy[:4])
    return f"{y - 1}-{str(y)[2:]}"

def set_stock(con, fy, opening=UNSET, closing=UNSET):
    row = con.execute("SELECT opening, closing FROM stock_manual WHERE fy=?", (fy,)).fetchone()
    o = row["opening"] if row else None
    c = row["closing"] if row else 0
    try:
        if opening is not UNSET:
            o = None if opening in (None, "") else to_paise(opening)
        if closing is not UNSET:
            c = 0 if closing in (None, "") else to_paise(closing)
    except ValueError:
        raise ValueError("Stock value must be a number")
    if (o is not None and o < 0) or c < 0:
        raise ValueError("Stock value cannot be negative")
    con.execute("INSERT INTO stock_manual(fy,opening,closing) VALUES(?,?,?) "
                "ON CONFLICT(fy) DO UPDATE SET opening=excluded.opening, closing=excluded.closing",
                (fy, o, c))
    con.commit()

def get_stock(con, fy):
    row = con.execute("SELECT opening, closing FROM stock_manual WHERE fy=?", (fy,)).fetchone()
    closing = row["closing"] if row else 0
    if row and row["opening"] is not None:
        return row["opening"], closing
    prev = con.execute("SELECT closing FROM stock_manual WHERE fy=?", (prev_fy(fy),)).fetchone()
    return (prev["closing"] if prev else 0), closing

def prior_stock_effect(con, fy):
    total = 0
    for r in con.execute("SELECT fy FROM stock_manual WHERE fy < ? ORDER BY fy", (fy,)):
        o, c = get_stock(con, r["fy"])
        total += c - o
    return total

# ---------- Stock Items Master ----------

def list_stock_items(con):
    return con.execute(
        "SELECT id, name, hsn, unit, gst_rate, opening_qty, opening_rate "
        "FROM stock_items ORDER BY name COLLATE NOCASE"
    ).fetchall()

def _check_rate(value):
    try:
        v = float(str(value if value not in (None, "") else 0).strip())
    except ValueError:
        raise ValueError("Opening rate must be a number")
    if v < 0:
        raise ValueError("Opening rate cannot be negative")
    return v

def add_stock_item(con, name, hsn="", unit="pcs", gst_rate="18", opening_qty="0", opening_rate="0"):
    name = (name or "").strip()
    if not name:
        raise ValueError("Item name is required")
    if con.execute("SELECT 1 FROM stock_items WHERE name=? COLLATE NOCASE", (name,)).fetchone():
        raise ValueError("An item with this name already exists")
    _check_rate(opening_rate)
    con.execute(
        "INSERT INTO stock_items(name,hsn,unit,gst_rate,opening_qty,opening_rate) VALUES(?,?,?,?,?,?)",
        (name, (hsn or "").strip(), (unit or "pcs").strip(), str(gst_rate),
         str(opening_qty or "0"), str(opening_rate or "0")))
    con.commit()

def update_stock_item(con, item_id, name, hsn="", unit="pcs", gst_rate="18",
                      opening_qty="0", opening_rate="0"):
    name = (name or "").strip()
    if not name:
        raise ValueError("Item name is required")
    if con.execute("SELECT id FROM stock_items WHERE name=? COLLATE NOCASE AND id!=?",
                   (name, item_id)).fetchone():
        raise ValueError("Another item with this name already exists")
    _check_rate(opening_rate)
    con.execute(
        "UPDATE stock_items SET name=?,hsn=?,unit=?,gst_rate=?,opening_qty=?,opening_rate=? WHERE id=?",
        (name, (hsn or "").strip(), (unit or "pcs").strip(), str(gst_rate),
         str(opening_qty or "0"), str(opening_rate or "0"), item_id))
    con.commit()

def delete_stock_item(con, item_id):
    if con.execute("SELECT 1 FROM invoice_items WHERE stock_item_id=?", (item_id,)).fetchone():
        raise ValueError("This item is used in invoices and cannot be deleted")
    con.execute("DELETE FROM stock_items WHERE id=?", (item_id,))
    con.commit()

def _row_get(row, key, default=None):
    """Safe column read from an sqlite3.Row (older DBs may lack a column)."""
    try:
        v = row[key]
    except (IndexError, KeyError):
        return default
    return default if v is None else v

def _pur_pool(con, item_id, vtype, kind_filter, start, end):
    """Sum of qty*rate and qty for one voucher type in a date range."""
    q = """SELECT COALESCE(SUM(CAST(ii.qty AS REAL) * CAST(ii.rate AS REAL)), 0) AS val,
                  COALESCE(SUM(CAST(ii.qty AS REAL)), 0) AS qty
           FROM invoice_items ii
           JOIN invoices inv ON inv.id = ii.invoice_id
           JOIN vouchers v ON v.id = inv.voucher_id
           WHERE ii.stock_item_id=? AND v.vtype=?"""
    if kind_filter:
        q += " AND inv.kind=?"
        args = (item_id, vtype, kind_filter, start, end)
    else:
        args = (item_id, vtype, start, end)
    q += " AND v.vdate BETWEEN ? AND ?"
    r = con.execute(q, args).fetchone()
    return float(r["val"]), float(r["qty"])

def _avg_cost(con, item, fy):
    """Weighted-average cost for one item.

    Pool = opening stock (only when an opening rate is set)
           + this FY's purchases, net of purchase returns.
    Falls back to the previous FY's purchase average when the pool is empty.
    Returns 0.0 when no cost basis exists at all.
    """
    start, end = fy_range(fy)

    pur_val, pur_qty = _pur_pool(con, item["id"], "Purchase", "Purchase", start, end)
    pret_val, pret_qty = _pur_pool(con, item["id"], "Purchase Return", None, start, end)

    try:
        open_qty = float(_row_get(item, "opening_qty", 0) or 0)
    except (ValueError, TypeError):
        open_qty = 0.0
    try:
        open_rate = float(_row_get(item, "opening_rate", 0) or 0)
    except (ValueError, TypeError):
        open_rate = 0.0

    # Opening joins the pool only when it has been given a rate
    use_open = open_qty > 0 and open_rate > 0
    pool_val = (open_qty * open_rate if use_open else 0.0) + pur_val - pret_val
    pool_qty = (open_qty if use_open else 0.0) + pur_qty - pret_qty

    if pool_qty > 0 and pool_val > 0:
        return pool_val / pool_qty

    # Fallback: previous FY's purchase average
    p_start, p_end = fy_range(prev_fy(fy))
    prev_val, prev_qty = _pur_pool(con, item["id"], "Purchase", "Purchase", p_start, p_end)
    if prev_qty > 0:
        return prev_val / prev_qty

    # Last resort: the opening rate on its own
    return open_rate if open_rate > 0 else 0.0

def stock_summary(con, fy):
    """Item-wise stock: opening + purchased - sold = closing,
    plus weighted-avg rate and stock value."""
    from decimal import Decimal
    start, end = fy_range(fy)
    items = list_stock_items(con)
    out = []
    for item in items:
        opening = Decimal(str(item["opening_qty"] or "0"))

        purchased = Decimal(str(con.execute(
            """SELECT COALESCE(SUM(CAST(ii.qty AS REAL)), 0)
               FROM invoice_items ii
               JOIN invoices inv ON inv.id = ii.invoice_id
               JOIN vouchers v ON v.id = inv.voucher_id
               WHERE ii.stock_item_id=? AND inv.kind='Purchase'
               AND v.vtype='Purchase'
               AND v.vdate BETWEEN ? AND ?""",
            (item["id"], start, end)).fetchone()[0]))

        sold = Decimal(str(con.execute(
            """SELECT COALESCE(SUM(CAST(ii.qty AS REAL)), 0)
               FROM invoice_items ii
               JOIN invoices inv ON inv.id = ii.invoice_id
               JOIN vouchers v ON v.id = inv.voucher_id
               WHERE ii.stock_item_id=? AND inv.kind='Sales'
               AND v.vtype='Sales'
               AND v.vdate BETWEEN ? AND ?""",
            (item["id"], start, end)).fetchone()[0]))

        sales_return = Decimal(str(con.execute(
            """SELECT COALESCE(SUM(CAST(ii.qty AS REAL)), 0)
               FROM invoice_items ii
               JOIN invoices inv ON inv.id = ii.invoice_id
               JOIN vouchers v ON v.id = inv.voucher_id
               WHERE ii.stock_item_id=? AND v.vtype='Sales Return'
               AND v.vdate BETWEEN ? AND ?""",
            (item["id"], start, end)).fetchone()[0]))

        purchase_return = Decimal(str(con.execute(
            """SELECT COALESCE(SUM(CAST(ii.qty AS REAL)), 0)
               FROM invoice_items ii
               JOIN invoices inv ON inv.id = ii.invoice_id
               JOIN vouchers v ON v.id = inv.voucher_id
               WHERE ii.stock_item_id=? AND v.vtype='Purchase Return'
               AND v.vdate BETWEEN ? AND ?""",
            (item["id"], start, end)).fetchone()[0]))

        closing = opening + purchased + sales_return - sold - purchase_return

        avg_rate = _avg_cost(con, item, fy)
        stock_value = float(closing) * avg_rate if avg_rate > 0 else 0.0

        out.append({
            "name": item["name"], "hsn": item["hsn"], "unit": item["unit"],
            "opening": float(opening), "purchased": float(purchased),
            "sold": float(sold), "closing": float(closing),
            "avg_rate": avg_rate, "stock_value": stock_value,
        })
    return out

def item_wise_profit(con, fy):
    """Item-wise profit: sale value - (sold qty × weighted-avg cost)."""
    start, end = fy_range(fy)
    items = list_stock_items(con)
    out = []
    for item in items:
        # Sales this FY (qty + value)
        sale_row = con.execute(
            """SELECT COALESCE(SUM(CAST(ii.qty AS REAL)), 0) AS qty,
                      COALESCE(SUM(ii.amount), 0) AS val
               FROM invoice_items ii
               JOIN invoices inv ON inv.id = ii.invoice_id
               JOIN vouchers v ON v.id = inv.voucher_id
               WHERE ii.stock_item_id=? AND inv.kind='Sales'
               AND v.vtype='Sales'
               AND v.vdate BETWEEN ? AND ?""",
            (item["id"], start, end)).fetchone()

        # Sales Returns (net out)
        sret_row = con.execute(
            """SELECT COALESCE(SUM(CAST(ii.qty AS REAL)), 0) AS qty,
                      COALESCE(SUM(ii.amount), 0) AS val
               FROM invoice_items ii
               JOIN invoices inv ON inv.id = ii.invoice_id
               JOIN vouchers v ON v.id = inv.voucher_id
               WHERE ii.stock_item_id=? AND v.vtype='Sales Return'
               AND v.vdate BETWEEN ? AND ?""",
            (item["id"], start, end)).fetchone()

        sold_qty = float(sale_row["qty"]) - float(sret_row["qty"])
        sale_value = (float(sale_row["val"]) - float(sret_row["val"])) / 100.0  # paise → rupees

        if sold_qty <= 0:
            continue  # skip items with no net sales

        avg_rate = _avg_cost(con, item, fy)

        cost_of_sold = sold_qty * avg_rate
        profit = sale_value - cost_of_sold
        margin = (profit / sale_value * 100) if sale_value > 0 else 0.0

        out.append({
            "name": item["name"], "unit": item["unit"],
            "sold_qty": sold_qty, "sale_value": sale_value,
            "avg_cost": avg_rate, "cost_of_sold": cost_of_sold,
            "profit": profit, "margin": margin,
        })
    return out

def _month_range(fy, month_num):
    """Return (start_iso, end_iso) for a month within the FY.
    month_num: 1=April, 2=May, ..., 12=March."""
    from calendar import monthrange
    y = int(fy[:4])
    if month_num <= 9:  # Apr-Dec of starting year
        year, mon = y, month_num + 3
    else:               # Jan-Mar of next year
        year, mon = y + 1, month_num - 9
    last = monthrange(year, mon)[1]
    return date(year, mon, 1).isoformat(), date(year, mon, last).isoformat()


def gstr1_report(con, fy, month_num):
    """GSTR-1: outward supplies. Returns summary (by rate, B2B/B2C) + invoice detail."""
    start, end = _month_range(fy, month_num)

    # Invoice-wise detail (outward only — Sales + Sales Return)
    detail = con.execute(
        """SELECT v.id, v.vdate, v.vno, v.vtype, inv.party, inv.customer_name,
                  inv.interstate, inv.taxable, inv.cgst, inv.sgst, inv.igst, inv.total,
                  COALESCE(p.gstin, '') AS gstin
           FROM vouchers v
           JOIN invoices inv ON inv.voucher_id = v.id
           LEFT JOIN parties p ON p.name = inv.party
           WHERE v.vtype IN ('Sales', 'Sales Return')
             AND v.vdate BETWEEN ? AND ?
           ORDER BY v.vdate, v.vno""",
        (start, end)).fetchall()

    invoices = []
    for r in detail:
        sign = -1 if r["vtype"] == "Sales Return" else 1
        invoices.append({
            "id": r["id"], "date": r["vdate"], "vno": r["vno"], "vtype": r["vtype"],
            "party": r["party"], "customer_name": r["customer_name"] or "",
            "gstin": r["gstin"],
            "supply": "Inter" if r["interstate"] else "Intra",
            "b2b": bool(r["gstin"]),
            "taxable": to_rupees(r["taxable"]) * sign,
            "cgst": to_rupees(r["cgst"]) * sign,
            "sgst": to_rupees(r["sgst"]) * sign,
            "igst": to_rupees(r["igst"]) * sign,
            "total": to_rupees(r["total"]) * sign,
        })

    # Rate-wise summary (group by item gst rate, B2B vs B2C)
    rate_rows = con.execute(
        """SELECT ii.gst AS rate, COALESCE(p.gstin, '') AS gstin, v.vtype,
                  SUM(ii.amount) AS taxable_paise,
                  SUM(CASE WHEN inv.interstate=0 THEN ii.amount ELSE 0 END) AS intra_taxable,
                  SUM(CASE WHEN inv.interstate=1 THEN ii.amount ELSE 0 END) AS inter_taxable
           FROM invoice_items ii
           JOIN invoices inv ON inv.id = ii.invoice_id
           JOIN vouchers v ON v.id = inv.voucher_id
           LEFT JOIN parties p ON p.name = inv.party
           WHERE v.vtype IN ('Sales', 'Sales Return')
             AND v.vdate BETWEEN ? AND ?
           GROUP BY ii.gst, (CASE WHEN COALESCE(p.gstin,'')='' THEN 'B2C' ELSE 'B2B' END), v.vtype""",
        (start, end)).fetchall()

    summary = {}  # key = (rate, "B2B"/"B2C"), value = dict of amounts
    for r in rate_rows:
        rate = str(r["rate"] or "0")
        kind = "B2B" if r["gstin"] else "B2C"
        key = (rate, kind)
        sign = -1 if r["vtype"] == "Sales Return" else 1
        try:
            rate_f = float(rate) / 100.0
        except (ValueError, TypeError):
            rate_f = 0.0
        intra = to_rupees(r["intra_taxable"] or 0) * sign
        inter = to_rupees(r["inter_taxable"] or 0) * sign
        s = summary.setdefault(key, {"rate": rate, "kind": kind,
                                     "taxable": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0})
        s["taxable"] += intra + inter
        s["cgst"] += intra * rate_f / 2
        s["sgst"] += intra * rate_f / 2
        s["igst"] += inter * rate_f

    summary_rows = sorted(summary.values(), key=lambda x: (x["kind"], float(x["rate"] or 0)))
    for s in summary_rows:
        s["total"] = s["taxable"] + s["cgst"] + s["sgst"] + s["igst"]

    totals = {"taxable": sum(s["taxable"] for s in summary_rows),
              "cgst":    sum(s["cgst"] for s in summary_rows),
              "sgst":    sum(s["sgst"] for s in summary_rows),
              "igst":    sum(s["igst"] for s in summary_rows),
              "total":   sum(s["total"] for s in summary_rows)}

    return {"summary": summary_rows, "invoices": invoices, "totals": totals,
            "period_from": start, "period_to": end}


def gstr3b_report(con, fy, month_num):
    """GSTR-3B: full summary of outward tax, interstate B2C, ITC, net payable,
    suggested payment breakdown, and closing stock reference."""
    start, end = _month_range(fy, month_num)

    # 3.1(a) Outward taxable (non-zero rated)
    out_row = con.execute(
        """SELECT SUM(CASE WHEN v.vtype='Sales' THEN ii.amount ELSE -ii.amount END) AS taxable,
                  SUM(CASE WHEN v.vtype='Sales' THEN
                           CAST(ii.amount AS REAL)*CAST(ii.gst AS REAL)/100.0*
                           (CASE WHEN inv.interstate=0 THEN 0.5 ELSE 0 END)
                      ELSE
                           -CAST(ii.amount AS REAL)*CAST(ii.gst AS REAL)/100.0*
                           (CASE WHEN inv.interstate=0 THEN 0.5 ELSE 0 END)
                      END) AS cgst,
                  SUM(CASE WHEN v.vtype='Sales' THEN
                           CAST(ii.amount AS REAL)*CAST(ii.gst AS REAL)/100.0*
                           (CASE WHEN inv.interstate=0 THEN 0.5 ELSE 0 END)
                      ELSE
                           -CAST(ii.amount AS REAL)*CAST(ii.gst AS REAL)/100.0*
                           (CASE WHEN inv.interstate=0 THEN 0.5 ELSE 0 END)
                      END) AS sgst,
                  SUM(CASE WHEN v.vtype='Sales' THEN
                           CAST(ii.amount AS REAL)*CAST(ii.gst AS REAL)/100.0*
                           (CASE WHEN inv.interstate=1 THEN 1 ELSE 0 END)
                      ELSE
                           -CAST(ii.amount AS REAL)*CAST(ii.gst AS REAL)/100.0*
                           (CASE WHEN inv.interstate=1 THEN 1 ELSE 0 END)
                      END) AS igst
           FROM invoice_items ii
           JOIN invoices inv ON inv.id = ii.invoice_id
           JOIN vouchers v ON v.id = inv.voucher_id
           WHERE v.vtype IN ('Sales', 'Sales Return')
             AND v.vdate BETWEEN ? AND ?
             AND CAST(ii.gst AS REAL) > 0""",
        (start, end)).fetchone()

    # 3.1(c) Nil-rated / exempt (gst = 0)
    nil_row = con.execute(
        """SELECT SUM(CASE WHEN v.vtype='Sales' THEN ii.amount ELSE -ii.amount END) AS val
           FROM invoice_items ii
           JOIN invoices inv ON inv.id = ii.invoice_id
           JOIN vouchers v ON v.id = inv.voucher_id
           WHERE v.vtype IN ('Sales', 'Sales Return')
             AND v.vdate BETWEEN ? AND ?
             AND CAST(ii.gst AS REAL) = 0""",
        (start, end)).fetchone()

    # 3.2 Interstate supplies to unregistered (B2C-interstate)
    b2cus_row = con.execute(
        """SELECT SUM(CASE WHEN v.vtype='Sales' THEN inv.taxable ELSE -inv.taxable END) AS taxable,
                  SUM(CASE WHEN v.vtype='Sales' THEN inv.igst    ELSE -inv.igst    END) AS igst
           FROM invoices inv
           JOIN vouchers v ON v.id = inv.voucher_id
           LEFT JOIN parties p ON p.name = inv.party
           WHERE v.vtype IN ('Sales', 'Sales Return')
             AND v.vdate BETWEEN ? AND ?
             AND inv.interstate = 1
             AND COALESCE(p.gstin, '') = ''""",
        (start, end)).fetchone()

    # 4 ITC available (from purchases)
    itc_row = con.execute(
        """SELECT SUM(CASE WHEN v.vtype='Purchase' THEN inv.cgst ELSE -inv.cgst END) AS cgst,
                  SUM(CASE WHEN v.vtype='Purchase' THEN inv.sgst ELSE -inv.sgst END) AS sgst,
                  SUM(CASE WHEN v.vtype='Purchase' THEN inv.igst ELSE -inv.igst END) AS igst
           FROM invoices inv
           JOIN vouchers v ON v.id = inv.voucher_id
           WHERE v.vtype IN ('Purchase', 'Purchase Return')
             AND v.vdate BETWEEN ? AND ?""",
        (start, end)).fetchone()

    outward = {
        "taxable": to_rupees(out_row["taxable"] or 0),
        "cgst":    float(out_row["cgst"] or 0) / 100.0,
        "sgst":    float(out_row["sgst"] or 0) / 100.0,
        "igst":    float(out_row["igst"] or 0) / 100.0,
    }
    nil_exempt = to_rupees(nil_row["val"] or 0)
    b2c_inter  = {"taxable": to_rupees(b2cus_row["taxable"] or 0),
                  "igst":    to_rupees(b2cus_row["igst"]    or 0)}
    itc = {
        "cgst": to_rupees(itc_row["cgst"] or 0),
        "sgst": to_rupees(itc_row["sgst"] or 0),
        "igst": to_rupees(itc_row["igst"] or 0),
    }

    # Net GST liability
    net = {
        "cgst": outward["cgst"] - itc["cgst"],
        "sgst": outward["sgst"] - itc["sgst"],
        "igst": outward["igst"] - itc["igst"],
    }
    net["total"] = net["cgst"] + net["sgst"] + net["igst"]

    # 6.1 Suggested payment breakdown: ITC used + cash top-up
    # (simplified: ITC applied to same head first; cross-utilization skipped for now)
    paid_by_itc = {
        "cgst": min(outward["cgst"], itc["cgst"]),
        "sgst": min(outward["sgst"], itc["sgst"]),
        "igst": min(outward["igst"], itc["igst"]),
    }
    paid_by_cash = {
        "cgst": max(0.0, outward["cgst"] - itc["cgst"]),
        "sgst": max(0.0, outward["sgst"] - itc["sgst"]),
        "igst": max(0.0, outward["igst"] - itc["igst"]),
    }
    itc_balance = {
        "cgst": max(0.0, itc["cgst"] - outward["cgst"]),
        "sgst": max(0.0, itc["sgst"] - outward["sgst"]),
        "igst": max(0.0, itc["igst"] - outward["igst"]),
    }

    # Closing stock reference
    stock = stock_summary(con, fy)
    stock_value = sum(it.get("stock_value", 0.0) for it in stock)

    return {
        "outward": outward,
        "nil_exempt": nil_exempt,
        "b2c_inter": b2c_inter,
        "itc": itc,
        "net": net,
        "paid_by_itc": paid_by_itc,
        "paid_by_cash": paid_by_cash,
        "itc_balance": itc_balance,
        "stock_value": stock_value,
        "period_from": start,
        "period_to": end,
    }
