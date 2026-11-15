"""Read-only reports: ledger, day book, profit & loss, balance sheet. Amounts returned in rupees."""
from db.setup import account_states, fy_range, to_rupees


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
        out.append({"date": v["vdate"], "vtype": v["vtype"], "vno": v["vno"],
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
