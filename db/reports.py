"""Read-only reports: ledger, day book, profit & loss, balance sheet,
cash flow, party statement. Amounts returned in rupees."""
from datetime import date, timedelta
from db.setup import account_states, fy_range, to_rupees
from db.setup import get_stock as s_get_stock, prior_stock_effect as s_prior_stock_effect
from db import billing as bl


def _side(bal):
    return ("Dr" if bal >= 0 else "Cr"), abs(bal)


def ledger_view(con, name, fy, date_from=None, date_to=None):
    start, end = fy_range(fy)
    if date_from: start = max(start, date_from.isoformat())
    if date_to:   end   = min(end,   date_to.isoformat())
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
                     "narration": r["narration"], "dr": to_rupees(r["dr"]),
                     "cr": to_rupees(r["cr"]), "balance": to_rupees(amt), "side": side})
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


def _paise(x):
    return int(round(float(x) * 100))


def profit_and_loss(con, fy, closing_stock=None, opening_stock=None,
                    date_from=None, date_to=None):
    states, _ = account_states(con, fy, date_from, date_to)
    inc, exp = [], []
    ti = te = 0
    for st in states:
        net = st["dr"] - st["cr"]
        if st["nature"] == "Income" and net != 0:
            inc.append((st["name"], to_rupees(-net))); ti += -net
        elif st["nature"] == "Expense" and net != 0:
            exp.append((st["name"], to_rupees(net))); te += net
    o_db, c_db = s_get_stock(con, fy)
    cs  = c_db if closing_stock  is None else _paise(closing_stock)
    os_ = o_db if opening_stock  is None else _paise(opening_stock)
    return {"income": inc, "expenses": exp,
            "closing_stock":  to_rupees(cs),
            "opening_stock":  to_rupees(os_),
            "total_income":   to_rupees(ti),
            "total_expenses": to_rupees(te),
            "net_profit":     to_rupees(ti + cs - te - os_)}


TRADING_EXPENSE_GROUPS = ("Purchase Accounts", "Direct Expenses")
TRADING_INCOME_GROUPS  = ("Sales Accounts", "Direct Income")


def trading_and_pl(con, fy, closing_stock=None, opening_stock=None,
                   date_from=None, date_to=None):
    states, _ = account_states(con, fy, date_from, date_to)
    grp = {r["name"]: r["grp"] for r in con.execute("SELECT name, grp FROM accounts")}
    pl  = profit_and_loss(con, fy, closing_stock, opening_stock, date_from, date_to)
    t_exp, t_inc, i_exp, i_inc = [], [], [], []
    for st in states:
        net = st["dr"] - st["cr"]
        if net == 0:
            continue
        if st["nature"] == "Income":
            (t_inc if grp.get(st["name"]) in TRADING_INCOME_GROUPS else i_inc).append((st["name"], -net))
        elif st["nature"] == "Expense":
            (t_exp if grp.get(st["name"]) in TRADING_EXPENSE_GROUPS else i_exp).append((st["name"], net))
    os_, cs = _paise(pl["opening_stock"]), _paise(pl["closing_stock"])
    gross = sum(a for _, a in t_inc) + cs - sum(a for _, a in t_exp) - os_
    net   = gross + sum(a for _, a in i_inc) - sum(a for _, a in i_exp)
    tl = ([("Opening Stock", os_)] if os_ else []) + t_exp
    tr = t_inc + ([("Closing Stock", cs)] if cs else [])
    if gross > 0:   tl.append(("Gross Profit c/d", gross))
    elif gross < 0: tr.append(("Gross Loss c/d",  -gross))
    pl_l = ([("Gross Loss b/d",  -gross)] if gross < 0 else []) + i_exp
    pl_r = ([("Gross Profit b/d", gross)] if gross > 0 else []) + i_inc
    if net > 0:   pl_l.append(("Net Profit", net))
    elif net < 0: pl_r.append(("Net Loss",  -net))
    cv  = lambda rows: [(n, to_rupees(a)) for n, a in rows]
    tot = lambda rows: to_rupees(sum(a for _, a in rows))
    total_sales = sum(a for _, a in t_inc)
    gross_pct   = round(gross / total_sales * 100, 2) if total_sales else 0.0
    net_pct     = round(net   / total_sales * 100, 2) if total_sales else 0.0
    return {"trading": {"left": cv(tl), "right": cv(tr),
                        "left_total": tot(tl), "right_total": tot(tr),
                        "gross_profit": to_rupees(gross)},
            "pl":      {"left": cv(pl_l), "right": cv(pl_r),
                        "left_total": tot(pl_l), "right_total": tot(pl_r),
                        "net_profit":  to_rupees(net)},
            "opening_stock": pl["opening_stock"],
            "closing_stock": pl["closing_stock"],
            "gross_pct": gross_pct,
            "net_pct":   net_pct}


def balance_sheet(con, fy, closing_stock=None, opening_stock=None):
    states, prior_pl = account_states(con, fy)
    pl = profit_and_loss(con, fy, closing_stock, opening_stock)
    cs = _paise(pl["closing_stock"])
    assets, liabs = [], []
    for st in states:
        if st["nature"] not in ("Asset", "Liability"): continue
        net = st["bf"] + st["dr"] - st["cr"]
        if net == 0: continue
        (assets if net > 0 else liabs).append((st["name"], abs(net)))
    if cs: assets.append(("Closing Stock", cs))
    profit = prior_pl + s_prior_stock_effect(con, fy) + _paise(pl["net_profit"])
    if profit > 0:   liabs.append(("Profit & Loss A/c", profit))
    elif profit < 0: assets.append(("Profit & Loss A/c (loss)", -profit))
    ta, tl = sum(a for _, a in assets), sum(a for _, a in liabs)
    if ta != tl:
        diff = abs(ta - tl)
        (liabs if ta > tl else assets).append(("Difference in opening balances", diff))
        ta, tl = max(ta, tl), max(ta, tl)
    cv = lambda rows: [(n, to_rupees(a)) for n, a in rows]
    return {"assets": cv(assets), "liabilities": cv(liabs),
            "total_assets": to_rupees(ta), "total_liabilities": to_rupees(tl)}


def invoice_register(con, fy, kind, date_from=None, date_to=None):
    start, end = fy_range(fy)
    if date_from: start = max(start, date_from.isoformat())
    if date_to:   end   = min(end,   date_to.isoformat())
    out = []
    q = """SELECT v.id, v.vdate, v.vno, v.narration, i.party, i.taxable,
                  i.cgst, i.sgst, i.igst, i.total,
                  (SELECT COALESCE(SUM(dr),0) FROM entries WHERE voucher_id=v.id) AS dr_total,
                  COALESCE((SELECT SUM(amount) FROM allocations WHERE invoice_voucher_id=v.id),0) AS settled,
                  i.customer_name
           FROM vouchers v LEFT JOIN invoices i ON i.voucher_id=v.id
           WHERE v.vtype=? AND v.vdate BETWEEN ? AND ? ORDER BY v.vdate, v.vno"""
    for r in con.execute(q, (kind, start, end)):
        has       = r["party"] is not None
        total     = r["total"] if has else r["dr_total"]
        immediate = has and r["party"] in ("Cash", "Bank")
        out.append({"id": r["id"], "date": r["vdate"], "vno": r["vno"],
                    "party": ((f"{r['party']} ({r['customer_name']})"
                               if r["customer_name"] else r["party"])
                              if has else "(details not stored)"),
                    "taxable": to_rupees(r["taxable"]) if has else 0,
                    "cgst":    to_rupees(r["cgst"])    if has else 0,
                    "sgst":    to_rupees(r["sgst"])    if has else 0,
                    "igst":    to_rupees(r["igst"])    if has else 0,
                    "total":   to_rupees(total),
                    "balance": to_rupees(max(total - r["settled"], 0))
                               if has and not immediate else 0,
                    "status":  ("Paid" if immediate
                                else bl.invoice_status(total, r["settled"])) if has else "-"})
    return out


def _net(con, name, as_of):
    r = con.execute(
        """SELECT a.opening, a.opening_side,
                  COALESCE((SELECT SUM(e.dr - e.cr) FROM entries e JOIN vouchers v ON v.id=e.voucher_id
                            WHERE e.account_id=a.id AND v.vdate<=?),0) AS mv
           FROM accounts a WHERE a.name=?""", (as_of.isoformat(), name)).fetchone()
    if r is None: return 0
    return (r["opening"] if r["opening_side"] == "Dr" else -r["opening"]) + r["mv"]


DEFAULT_EDGES = [30, 60, 90]


def parse_edges(text):
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
        labels.append(f"{lo}-{e}"); lo = e + 1
    labels.append(f"{edges[-1]}+")
    return (["Not due"] if due else []) + labels


def _bucket(days, edges, labels, due):
    if due and days <= 0: return "Not due"
    base = labels[1:] if due else labels
    for i, e in enumerate(edges):
        if days <= e: return base[i]
    return base[-1]


def outstanding_report(con, kind, as_of=None, basis="bill", edges=None):
    as_of  = as_of or date.today()
    edges  = edges or DEFAULT_EDGES
    due    = basis == "due"
    labels = ageing_labels(edges, due)
    ptype  = "Customer" if kind == "Sales" else "Supplier"
    parties, totals, total = [], {l: 0 for l in labels}, 0
    for p in con.execute("SELECT name FROM parties WHERE ptype=? ORDER BY name COLLATE NOCASE",
                         (ptype,)):
        name = p["name"]
        bills, bills_total, pb = [], 0, {l: 0 for l in labels}
        for o in bl.open_invoices(con, name, kind, as_of):
            bdate    = date.fromisoformat(o["vdate"])
            due_date = bdate + timedelta(days=o["credit_days"])
            days     = (as_of - (due_date if due else bdate)).days
            bk = _bucket(days, edges, labels, due)
            pb[bk] += o["balance"]; totals[bk] += o["balance"]
            bills_total += o["balance"]
            bills.append({"id": o["id"], "vno": o["vno"], "date": o["vdate"],
                          "due_date": due_date.isoformat(),
                          "total": to_rupees(o["total"]), "settled": to_rupees(o["settled"]),
                          "balance": to_rupees(o["balance"]), "days": days, "bucket": bk})
        net    = _net(con, name, as_of)
        ledger = net if kind == "Sales" else -net
        if not bills and ledger == 0: continue
        total += ledger
        parties.append({"party": name, "bills": bills,
                        "on_account": to_rupees(ledger - bills_total),
                        "balance": to_rupees(ledger),
                        "bucket_amounts": {l: to_rupees(v) for l, v in pb.items()}})
    return {"labels": labels, "parties": parties, "basis": basis,
            "as_of": as_of.isoformat(),
            "buckets": {l: to_rupees(v) for l, v in totals.items()},
            "total": to_rupees(total)}


def receivable_payable(con, as_of=None):
    as_of = as_of or date.today()
    rec = pay = 0
    for p in con.execute("SELECT name, ptype FROM parties"):
        net = _net(con, p["name"], as_of)
        if p["ptype"] == "Customer" and net > 0: rec += net
        elif p["ptype"] == "Supplier" and net < 0: pay += -net
    return to_rupees(rec), to_rupees(pay)


def returns_register(con, fy, kind):
    start, end = fy_range(fy)
    out = []
    q = """SELECT v.id, v.vdate, v.vno, v.narration, i.party, i.taxable,
                  i.cgst, i.sgst, i.igst, i.total, i.customer_name
           FROM vouchers v LEFT JOIN invoices i ON i.voucher_id=v.id
           WHERE v.vtype=? AND v.vdate BETWEEN ? AND ? ORDER BY v.vdate, v.vno"""
    for r in con.execute(q, (kind, start, end)):
        has = r["party"] is not None
        out.append({"id": r["id"], "date": r["vdate"], "vno": r["vno"],
                    "party": ((f"{r['party']} ({r['customer_name']})"
                               if r["customer_name"] else r["party"])
                              if has else "(details not stored)"),
                    "taxable": to_rupees(r["taxable"]) if has else 0,
                    "cgst":    to_rupees(r["cgst"])    if has else 0,
                    "sgst":    to_rupees(r["sgst"])    if has else 0,
                    "igst":    to_rupees(r["igst"])    if has else 0,
                    "total":   to_rupees(r["total"])   if has else 0})
    return out


# ── v0.17: Cash Flow Statement ────────────────────────────────────────────────

def cash_flow(con, fy):
    start, end = fy_range(fy)
    pl         = profit_and_loss(con, fy)
    net_profit = _paise(pl["net_profit"])

    def group_movement(grp_list):
        total = 0
        for grp in grp_list:
            r = con.execute(
                """SELECT COALESCE(SUM(e.dr - e.cr), 0) AS net
                   FROM entries e
                   JOIN vouchers v ON v.id = e.voucher_id
                   JOIN accounts a ON a.id = e.account_id
                   WHERE a.grp = ? AND v.vdate BETWEEN ? AND ?""",
                (grp, start, end)).fetchone()
            total += r["net"] if r else 0
        return total

    wc_debtors   = -group_movement(["Current Assets", "Sundry Debtors"])
    wc_creditors =  group_movement(["Current Liabilities", "Sundry Creditors"])
    operating_items = [
        ("Net Profit / (Loss)",                 to_rupees(net_profit)),
        ("Add: Increase in Trade Payables",     to_rupees(wc_creditors)),
        ("Less: Increase in Trade Receivables", to_rupees(-wc_debtors)),
    ]
    operating_total = net_profit + wc_creditors + wc_debtors

    capital_mv = group_movement(["Capital Account", "Reserves & Surplus"])
    loan_mv    = group_movement(["Loans (Liability)", "Long Term Borrowings",
                                 "Short Term Borrowings"])
    financing_items = [
        ("Capital introduced / (withdrawn)", to_rupees(-capital_mv)),
        ("Loans taken / (repaid)",           to_rupees(-loan_mv)),
    ]
    financing_total = -(capital_mv + loan_mv)

    asset_mv  = group_movement(["Fixed Assets", "Intangible Assets"])
    invest_mv = group_movement(["Long Term Investments", "Short Term Investments"])
    investing_items = [
        ("Purchase / (Sale) of Fixed Assets", to_rupees(-asset_mv)),
        ("Purchase / (Sale) of Investments",  to_rupees(-invest_mv)),
    ]
    investing_total = -(asset_mv + invest_mv)

    # Sum all cash & bank accounts dynamically
    cash_names = [r["name"] for r in con.execute(
        "SELECT name FROM accounts WHERE grp IN ('Cash-in-hand','Bank Accounts')")]
    cash_open  = sum(_net(con, n, date.fromisoformat(start) - timedelta(days=1))
                     for n in cash_names)
    cash_close = sum(_net(con, n, date.fromisoformat(end)) for n in cash_names)
    net_change = cash_close - cash_open

    return {
        "operating":    {"items": operating_items,  "total": to_rupees(operating_total)},
        "financing":    {"items": financing_items,  "total": to_rupees(financing_total)},
        "investing":    {"items": investing_items,  "total": to_rupees(investing_total)},
        "net_change":   to_rupees(net_change),
        "opening_cash": to_rupees(cash_open),
        "closing_cash": to_rupees(cash_close),
    }


# ── v0.17: Party Statement ────────────────────────────────────────────────────

def party_statement(con, name, fy, date_from=None, date_to=None):
    start, end = fy_range(fy)
    if date_from: start = max(start, date_from.isoformat())
    if date_to:   end   = min(end,   date_to.isoformat())
    party_row = con.execute(
        "SELECT p.ptype, p.gstin, p.phone, a.id AS acc_id, a.opening, a.opening_side "
        "FROM parties p JOIN accounts a ON a.id = p.account_id WHERE p.name=?",
        (name,)).fetchone()
    if not party_row:
        raise ValueError(f"Party not found: {name}")
    acc_id      = party_row["acc_id"]
    signed_open = (party_row["opening"] if party_row["opening_side"] == "Dr"
                   else -party_row["opening"])
    bf_row = con.execute(
        """SELECT COALESCE(SUM(e.dr - e.cr), 0) AS mv
           FROM entries e JOIN vouchers v ON v.id = e.voucher_id
           WHERE e.account_id = ? AND v.vdate < ?""",
        (acc_id, start)).fetchone()
    bf   = signed_open + (bf_row["mv"] if bf_row else 0)
    s0, a0 = _side(bf)
    rows_raw = con.execute(
        """SELECT v.id, v.vdate, v.vtype, v.vno, v.narration,
                  e.dr, e.cr,
                  COALESCE(i.total, 0) AS inv_total,
                  COALESCE(i.taxable, 0) AS taxable,
                  COALESCE(i.cgst + i.sgst + i.igst, 0) AS gst_total
           FROM entries e
           JOIN vouchers v ON v.id = e.voucher_id
           LEFT JOIN invoices i ON i.voucher_id = v.id
           WHERE e.account_id = ? AND v.vdate BETWEEN ? AND ?
           ORDER BY v.vdate, v.id""",
        (acc_id, start, end)).fetchall()
    bal = bf; rows = []; tdr = tcr = 0
    for r in rows_raw:
        bal += r["dr"] - r["cr"]; tdr += r["dr"]; tcr += r["cr"]
        side, amt = _side(bal)
        rows.append({
            "id": r["id"], "date": r["vdate"], "vtype": r["vtype"],
            "vno": r["vno"], "narration": r["narration"] or "",
            "dr": to_rupees(r["dr"]), "cr": to_rupees(r["cr"]),
            "balance": to_rupees(amt), "side": side,
        })
    cs, ca = _side(bal)
    return {
        "party": name, "ptype": party_row["ptype"],
        "gstin": party_row["gstin"] or "", "phone": party_row["phone"] or "",
        "opening": to_rupees(a0), "opening_side": s0, "rows": rows,
        "total_dr": to_rupees(tdr), "total_cr": to_rupees(tcr),
        "closing": to_rupees(ca), "closing_side": cs,
        "period_from": start, "period_to": end,
    }


# ── v0.18: Grouped Balance Sheet ─────────────────────────────────────────────

BS_LIABILITIES_ORDER = [
    "Capital Account", "Reserves & Surplus", "Long Term Borrowings",
    "Short Term Borrowings", "Sundry Creditors", "Current Liabilities",
    "Duties & Taxes", "Provisions", "Loans (Liability)",
]

BS_ASSETS_ORDER = [
    "Fixed Assets", "Intangible Assets", "Long Term Investments",
    "Short Term Investments", "Inventories", "Sundry Debtors",
    "Other Current Assets", "Cash-in-hand", "Bank Accounts",
    "Current Assets", "Short Term Loans & Advances",
    "Loans & Advances (Asset)", "Duties & Taxes",
]

BS_GROUP_LABELS = {
    "Capital Account":             "Capital Account",
    "Reserves & Surplus":          "Reserves & Surplus",
    "Long Term Borrowings":        "Long Term Borrowings",
    "Short Term Borrowings":       "Short Term Borrowings",
    "Sundry Creditors":            "Trade Payables (Creditors)",
    "Current Liabilities":         "Other Current Liabilities",
    "Duties & Taxes":              "Duties & Taxes",
    "Provisions":                  "Provisions",
    "Loans (Liability)":           "Loans (Liability)",
    "Fixed Assets":                "Fixed Assets",
    "Intangible Assets":           "Intangible Assets",
    "Long Term Investments":       "Long Term Investments",
    "Short Term Investments":      "Short Term Investments",
    "Inventories":                 "Inventories",
    "Sundry Debtors":              "Trade Receivables (Debtors)",
    "Other Current Assets":        "Other Current Assets",
    "Cash-in-hand":                "Cash & Cash Equivalents",
    "Bank Accounts":               "Bank Accounts",
    "Current Assets":              "Current Assets",
    "Short Term Loans & Advances": "Short Term Loans & Advances",
    "Loans & Advances (Asset)":    "Loans & Advances (Long Term)",
}


def balance_sheet_grouped(con, fy, closing_stock=None, opening_stock=None,
                          detailed=True, date_to=None):
    """
    Grouped Balance Sheet.
    date_to: show position as on this date (defaults to FY end).
    detailed=True  → individual accounts; False → head totals only.
    Duties & Taxes split by sign: Cr balance → Liabilities, Dr balance → Assets.
    """
    dt = date_to if date_to else None
    states, prior_pl = account_states(con, fy, date_to=dt)
    pl = profit_and_loss(con, fy, closing_stock, opening_stock, date_to=dt)
    cs = _paise(pl["closing_stock"])

    grp_map = {}
    for st in states:
        if st["nature"] not in ("Asset", "Liability"): continue
        net = st["bf"] + st["dr"] - st["cr"]
        if net == 0: continue
        grp_map.setdefault(st["grp"], []).append((st["name"], net))

    def _build_side(group_order, is_liabilities):
        sections = []; grand = 0
        for grp_key in group_order:
            members  = grp_map.get(grp_key, [])
            filtered = []
            for name, net in members:
                if is_liabilities and net < 0:      filtered.append((name, abs(net)))
                elif not is_liabilities and net > 0: filtered.append((name, net))
            if not filtered: continue
            subtotal = sum(a for _, a in filtered); grand += subtotal
            accts = ([(n, to_rupees(a)) for n, a in
                      sorted(filtered, key=lambda x: x[0].lower())]
                     if detailed else [])
            sections.append({"head": BS_GROUP_LABELS.get(grp_key, grp_key),
                             "accounts": accts, "total": to_rupees(subtotal)})
        return sections, grand

    liab_sections, tl = _build_side(BS_LIABILITIES_ORDER, is_liabilities=True)
    asset_sections, ta = _build_side(BS_ASSETS_ORDER,     is_liabilities=False)

    # Closing stock → Inventories
    if cs:
        inv_sec = next((s for s in asset_sections if s["head"] == "Inventories"), None)
        if inv_sec:
            if detailed: inv_sec["accounts"].append(("Closing Stock", to_rupees(cs)))
            inv_sec["total"] += to_rupees(cs)
        else:
            asset_sections.insert(0, {
                "head":     "Inventories",
                "accounts": [("Closing Stock", to_rupees(cs))] if detailed else [],
                "total":    to_rupees(cs)})
        ta += cs

    # Net profit → Capital Account
    profit = prior_pl + s_prior_stock_effect(con, fy) + _paise(pl["net_profit"])
    if profit > 0:
        cap = next((s for s in liab_sections if s["head"] == "Capital Account"), None)
        if cap:
            if detailed: cap["accounts"].append(("Profit & Loss A/c", to_rupees(profit)))
            cap["total"] += to_rupees(profit)
        else:
            liab_sections.insert(0, {
                "head":     "Capital Account",
                "accounts": [("Profit & Loss A/c", to_rupees(profit))] if detailed else [],
                "total":    to_rupees(profit)})
        tl += profit
    elif profit < 0:
        asset_sections.append({
            "head":     "Profit & Loss A/c (Loss)",
            "accounts": [("Net Loss", to_rupees(-profit))] if detailed else [],
            "total":    to_rupees(-profit)})
        ta += -profit

    # Equalise
    if round(ta) != round(tl):
        diff = abs(ta - tl)
        if ta > tl:
            liab_sections.append({"head": "Difference in opening balances",
                                   "accounts": [], "total": to_rupees(diff)}); tl += diff
        else:
            asset_sections.append({"head": "Difference in opening balances",
                                    "accounts": [], "total": to_rupees(diff)}); ta += diff

    return {
        "liabilities":       liab_sections,
        "assets":            asset_sections,
        "total_liabilities": to_rupees(tl),
        "total_assets":      to_rupees(ta),
        "net_profit":        pl["net_profit"],
    }
