"""Read-only reports: ledger, day book, profit & loss, balance sheet. Amounts returned in rupees."""
from datetime import date, timedelta
from db.setup import account_states, fy_range, to_rupees
from db import billing as bl


def _side(bal):
    return ("Dr" if bal >= 0 else "Cr"), abs(bal)


def ledger_view(con, name, fy):
    start, end = fy_range(fy)
    states, _ = account_states(con, fy)
    st = next((s for s in states if s["name"] == name), None)
    if st is None:
        raise ValueError(f"Unknown account: {name}")
    bal = st["bf"]
    s0, a0 = _side(bal)
    rows = []
    q = """SELECT v.vdate, v.vtype, v.vno, v.narration, e.dr, e.cr FROM entries e
           JOIN vouchers v ON v.id=e.voucher_id
           WHERE e.account_id=? AND v.vdate BETWEEN ? AND ? ORDER BY v.vdate, v.id, e.id"""
    tdr = tcr = 0
    for r in con.execute(q, (st["id"], start, end)):
        bal += r["dr"] - r["cr"]
        tdr += r["dr"]; tcr += r["cr"]
        side, amt = _side(bal)
        rows.append({"date": r["vdate"], "vtype": r["vtype"], "vno": r["vno"],
                     "narration": r["narration"], "dr": to_rupees(r["dr"]), "cr": to_rupees(r["cr"]),
                     "balance": to_rupees(amt), "side": side})
    cs, ca = _side(bal)
    return {"account": name, "opening": to_rupees(a0), "opening_side": s0, "rows": rows,
            "total_dr": to_rupees(tdr), "total_cr": to_rupees(tcr),
            "closing": to_rupees(ca), "closing_side": cs}


def day_book(con, date_from, date_to):
    out = []
    vs = con.execute("""SELECT id, vdate, vtype, vno, narration FROM vouchers
                        WHERE vdate BETWEEN ? AND ? ORDER BY vdate, id""",
                     (date_from.isoformat(), date_to.isoformat())).fetchall()
    for v in vs:
        lines = [(r["name"], to_rupees(r["dr"]), to_rupees(r["cr"])) for r in con.execute(
            """SELECT a.name, e.dr, e.cr FROM entries e JOIN accounts a ON a.id=e.account_id
               WHERE e.voucher_id=? ORDER BY e.id""", (v["id"],))]
        out.append({"id": v["id"], "date": v["vdate"], "vtype": v["vtype"], "vno": v["vno"],
                    "narration": v["narration"], "lines": lines})
    return out


def profit_and_loss(con, fy, closing_stock=0):
    """Closing stock is entered manually until the Stock module exists."""
    states, _ = account_states(con, fy)
    inc, exp = [], []
    ti = te = 0
    for st in states:
        net = st["dr"] - st["cr"]
        if st["nature"] == "Income" and net != 0:
            inc.append((st["name"], to_rupees(-net))); ti += -net
        elif st["nature"] == "Expense" and net != 0:
            exp.append((st["name"], to_rupees(net))); te += net
    cs = int(round(float(closing_stock) * 100))
    return {"income": inc, "expenses": exp, "closing_stock": to_rupees(cs),
            "total_income": to_rupees(ti), "total_expenses": to_rupees(te),
            "net_profit": to_rupees(ti + cs - te)}


def balance_sheet(con, fy, closing_stock=0):
    states, prior_pl = account_states(con, fy)
    pl = profit_and_loss(con, fy, closing_stock)
    cs = int(round(float(closing_stock) * 100))
    assets, liabs = [], []
    for st in states:
        if st["nature"] not in ("Asset", "Liability"):
            continue
        net = st["bf"] + st["dr"] - st["cr"]
        if net == 0:
            continue
        to_assets = (net > 0)  # Dr balance sits with assets, Cr balance with liabilities
        (assets if to_assets else liabs).append((st["name"], abs(net)))
    if cs:
        assets.append(("Closing Stock", cs))
    profit = prior_pl + int(round(pl["net_profit"] * 100))
    if profit > 0:
        liabs.append(("Profit & Loss A/c", profit))
    elif profit < 0:
        assets.append(("Profit & Loss A/c (loss)", -profit))
    ta, tl = sum(a for _, a in assets), sum(a for _, a in liabs)
    if ta != tl:  # one-sided opening balances
        diff = abs(ta - tl)
        (liabs if ta > tl else assets).append(("Difference in opening balances", diff))
        ta, tl = max(ta, tl), max(ta, tl)
    cv = lambda rows: [(n, to_rupees(a)) for n, a in rows]
    return {"assets": cv(assets), "liabilities": cv(liabs),
            "total_assets": to_rupees(ta), "total_liabilities": to_rupees(tl)}


def invoice_register(con, fy, kind):
    """Sales or purchase register for a financial year, with settlement status. Bills saved before
    item details were stored show party '(details not stored)', status '-' and only their total."""
    start, end = fy_range(fy)
    out = []
    q = """SELECT v.id, v.vdate, v.vno, v.narration, i.party, i.taxable, i.cgst, i.sgst, i.igst, i.total,
                  (SELECT COALESCE(SUM(dr),0) FROM entries WHERE voucher_id=v.id) AS dr_total,
                  COALESCE((SELECT SUM(amount) FROM allocations WHERE invoice_voucher_id=v.id),0) AS settled
           FROM vouchers v LEFT JOIN invoices i ON i.voucher_id=v.id
           WHERE v.vtype=? AND v.vdate BETWEEN ? AND ? ORDER BY v.vdate, v.vno"""
    for r in con.execute(q, (kind, start, end)):
        has = r["party"] is not None
        total = r["total"] if has else r["dr_total"]
        immediate = has and r["party"] in ("Cash", "Bank")      # paid at the counter
        out.append({"id": r["id"], "date": r["vdate"], "vno": r["vno"],
                    "party": r["party"] if has else "(details not stored)",
                    "taxable": to_rupees(r["taxable"]) if has else 0,
                    "cgst": to_rupees(r["cgst"]) if has else 0,
                    "sgst": to_rupees(r["sgst"]) if has else 0,
                    "igst": to_rupees(r["igst"]) if has else 0,
                    "total": to_rupees(total),
                    "balance": to_rupees(max(total - r["settled"], 0)) if has and not immediate else 0,
                    "status": ("Paid" if immediate else bl.invoice_status(total, r["settled"])) if has else "-"})
    return out


def _net(con, name, as_of):
    """Signed ledger balance (Dr positive) of an account up to a date, in paise."""
    r = con.execute(
        """SELECT a.opening, a.opening_side,
                  COALESCE((SELECT SUM(e.dr - e.cr) FROM entries e JOIN vouchers v ON v.id=e.voucher_id
                            WHERE e.account_id=a.id AND v.vdate<=?),0) AS mv
           FROM accounts a WHERE a.name=?""", (as_of.isoformat(), name)).fetchone()
    if r is None:
        return 0
    return (r["opening"] if r["opening_side"] == "Dr" else -r["opening"]) + r["mv"]


DEFAULT_EDGES = [30, 60, 90]


def parse_edges(text):
    """'90,120,180' -> [90, 120, 180]. Whole days, ascending, 1 to 6 limits."""
    try:
        edges = [int(x) for x in str(text).replace(";", ",").replace(" ", ",").split(",") if x.strip()]
    except ValueError:
        raise ValueError("Ageing ranges must be whole numbers like 30,60,90")
    if not 1 <= len(edges) <= 6 or edges != sorted(set(edges)) or edges[0] < 1 or edges[-1] > 3650:
        raise ValueError("Give 1 to 6 increasing day limits, for example 30,60,90")
    return edges


def ageing_labels(edges, due=False):
    labels, lo = [], 0
    for e in edges:
        labels.append(f"{lo}-{e}")
        lo = e + 1
    labels.append(f"{edges[-1]}+")
    return (["Not due"] if due else []) + labels


def _bucket(days, edges, labels, due):
    if due and days <= 0:
        return "Not due"
    base = labels[1:] if due else labels
    for i, e in enumerate(edges):
        if days <= e:
            return base[i]
    return base[-1]


def outstanding_report(con, kind, as_of=None, basis="bill", edges=None):
    """kind 'Sales' = receivables (customers), 'Purchase' = payables (suppliers).
    basis 'bill' ages from the bill date; 'due' ages from bill date + the party's credit days
    (bills not yet due go to 'Not due'). edges are the day limits, default 30,60,90.
    'on_account' is the party's ledger balance less its open bills (opening balances, advances,
    unmatched receipts)."""
    as_of = as_of or date.today()
    edges = edges or DEFAULT_EDGES
    due = basis == "due"
    labels = ageing_labels(edges, due)
    ptype = "Customer" if kind == "Sales" else "Supplier"
    parties, totals, total = [], {l: 0 for l in labels}, 0
    for p in con.execute("SELECT name FROM parties WHERE ptype=? ORDER BY name COLLATE NOCASE", (ptype,)):
        name = p["name"]
        bills, bills_total, pb = [], 0, {l: 0 for l in labels}
        for o in bl.open_invoices(con, name, kind, as_of):
            bdate = date.fromisoformat(o["vdate"])
            due_date = bdate + timedelta(days=o["credit_days"])
            days = (as_of - (due_date if due else bdate)).days
            bk = _bucket(days, edges, labels, due)
            pb[bk] += o["balance"]; totals[bk] += o["balance"]
            bills_total += o["balance"]
            bills.append({"id": o["id"], "vno": o["vno"], "date": o["vdate"], "due_date": due_date.isoformat(),
                          "total": to_rupees(o["total"]), "settled": to_rupees(o["settled"]),
                          "balance": to_rupees(o["balance"]), "days": days, "bucket": bk})
        net = _net(con, name, as_of)
        ledger = net if kind == "Sales" else -net
        if not bills and ledger == 0:
            continue
        total += ledger
        parties.append({"party": name, "bills": bills, "on_account": to_rupees(ledger - bills_total),
                        "balance": to_rupees(ledger), "bucket_amounts": {l: to_rupees(v) for l, v in pb.items()}})
    return {"labels": labels, "parties": parties, "basis": basis, "as_of": as_of.isoformat(),
            "buckets": {l: to_rupees(v) for l, v in totals.items()}, "total": to_rupees(total)}


def receivable_payable(con, as_of=None):
    """(money customers owe you, money you owe suppliers), from party ledger balances."""
    as_of = as_of or date.today()
    rec = pay = 0
    for p in con.execute("SELECT name, ptype FROM parties"):
        net = _net(con, p["name"], as_of)
        if p["ptype"] == "Customer" and net > 0:
            rec += net
        elif p["ptype"] == "Supplier" and net < 0:
            pay += -net
    return to_rupees(rec), to_rupees(pay)
