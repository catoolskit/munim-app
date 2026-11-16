"""GST sales and purchase invoices. All maths in integer paise with half-up rounding.
Tax is computed per GST-rate group on the invoice (not per line).
Each invoice is stored (party, items, tax split) and linked to its accounting voucher."""
from decimal import Decimal, ROUND_HALF_UP
from db import setup as s
from db.setup import ensure_account, to_rupees

TAX_GROUP = "Duties & Taxes"


def is_interstate(party_gstin, company_gstin):
    """True when the first two GSTIN digits (state code) differ. Unknown GSTIN counts as local."""
    p, c = (party_gstin or "").strip()[:2], (company_gstin or "").strip()[:2]
    return bool(p.isdigit() and c.isdigit() and p != c)


def compute_tax(items, interstate):
    """items: [(description, qty, rate_rupees, gst_percent)]. Returns dict in paise."""
    if not items:
        raise ValueError("Add at least one item")
    by_rate, taxable = {}, 0
    for desc, qty, rate, gst in items:
        qty, rate, gst = Decimal(str(qty)), Decimal(str(rate)), Decimal(str(gst))
        if qty <= 0:
            raise ValueError("Quantity must be more than zero")
        if rate < 0:
            raise ValueError("Rate cannot be negative")
        if gst < 0 or gst > 40:
            raise ValueError("GST rate must be between 0 and 40")
        amt = int((qty * rate * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        by_rate[gst] = by_rate.get(gst, 0) + amt
        taxable += amt
    cgst = sgst = igst = 0
    for gst, base in by_rate.items():
        if interstate:
            igst += int((Decimal(base) * gst / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        else:
            half = int((Decimal(base) * gst / 200).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            cgst += half; sgst += half
    return {"taxable": taxable, "cgst": cgst, "sgst": sgst, "igst": igst,
            "total": taxable + cgst + sgst + igst}


def _lines(kind, party, t):
    if kind == "Sales":
        return [(party, t["total"], 0), ("Sales", 0, t["taxable"]), ("Output CGST", 0, t["cgst"]),
                ("Output SGST", 0, t["sgst"]), ("Output IGST", 0, t["igst"])]
    return [("Purchase", t["taxable"], 0), ("Input CGST", t["cgst"], 0),
            ("Input SGST", t["sgst"], 0), ("Input IGST", t["igst"], 0), (party, 0, t["total"])]


def _ensure_tax_accounts(con, kind):
    names, nature = (("Output CGST", "Output SGST", "Output IGST"), "Liability") if kind == "Sales" \
        else (("Input CGST", "Input SGST", "Input IGST"), "Asset")
    for n in names:
        ensure_account(con, n, TAX_GROUP, nature)


def _store_invoice(con, vid, kind, party, interstate, items, t):
    cur = con.execute(
        """INSERT INTO invoices(voucher_id,kind,party,interstate,taxable,cgst,sgst,igst,total)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        (vid, kind, party, int(bool(interstate)), t["taxable"], t["cgst"], t["sgst"], t["igst"], t["total"]))
    for seq, (desc, qty, rate, gst) in enumerate(items):
        amt = int((Decimal(str(qty)) * Decimal(str(rate)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        con.execute("""INSERT INTO invoice_items(invoice_id,seq,description,qty,rate,gst,amount)
                       VALUES(?,?,?,?,?,?,?)""", (cur.lastrowid, seq, desc, str(qty), str(rate), str(gst), amt))


def _result(vno, t):
    return {"vno": vno, **{k: to_rupees(v) for k, v in t.items()}}


def _mode_check(mode):
    if mode not in ("Cash", "Bank"):
        raise ValueError("Payment mode must be Cash or Bank")


def settled_paise(con, invoice_vid):
    return con.execute("SELECT COALESCE(SUM(amount),0) FROM allocations WHERE invoice_voucher_id=?",
                       (invoice_vid,)).fetchone()[0]


def open_invoices(con, party, kind, as_of=None):
    """Bills of this party with money still due, oldest first. Amounts in paise.
    With as_of, only bills dated up to then count, and only payments dated up to then."""
    cut = as_of.isoformat() if as_of else "9999-12-31"
    out = []
    for r in con.execute(
            """SELECT v.id, v.vno, v.vdate, i.total,
                      COALESCE((SELECT SUM(a.amount) FROM allocations a
                                JOIN vouchers pv ON pv.id=a.payment_voucher_id
                                WHERE a.invoice_voucher_id=v.id AND pv.vdate<=?),0) AS settled,
                      COALESCE((SELECT credit_days FROM parties WHERE name=i.party),0) AS credit_days
               FROM invoices i JOIN vouchers v ON v.id=i.voucher_id
               WHERE i.kind=? AND i.party=? AND v.vdate<=? ORDER BY v.vdate, v.id""",
            (cut, kind, party, cut)):
        bal = r["total"] - r["settled"]
        if bal > 0:
            out.append({"id": r["id"], "vno": r["vno"], "vdate": r["vdate"], "total": r["total"],
                        "settled": r["settled"], "balance": bal, "credit_days": r["credit_days"]})
    return out


def invoice_status(total, settled):
    return "Paid" if settled >= total else ("Partly paid" if settled > 0 else "Unpaid")


def _payment_lines(pkind, party, mode, amt):
    if pkind == "Receipt":
        return [(mode, amt, 0), (party, 0, amt)]
    return [(party, amt, 0), (mode, 0, amt)]


def _alloc(con, pvid, ivid, amt):
    con.execute("INSERT INTO allocations(payment_voucher_id,invoice_voucher_id,amount) VALUES(?,?,?)",
                (pvid, ivid, amt))


def _post(con, kind, vdate, party, items, interstate, narration, username, received, mode):
    t = compute_tax(items, interstate)
    rec = s.to_paise(received or 0)
    if rec < 0:
        raise ValueError("Amount cannot be negative")
    if rec:
        _mode_check(mode)
        if party in ("Cash", "Bank"):
            raise ValueError("A cash or bank bill is already fully settled")
        if rec > t["total"]:
            raise ValueError("The amount entered is more than the bill total")
    _ensure_tax_accounts(con, kind)
    try:
        vno, vid = s._insert_voucher(con, kind, vdate, narration, _lines(kind, party, t))
        _store_invoice(con, vid, kind, party, interstate, items, t)
        s.log_action(con, username, "create", after=s.voucher_snapshot(con, vid))
        if rec:
            pkind = "Receipt" if kind == "Sales" else "Payment"
            word = "Received" if kind == "Sales" else "Paid"
            _pvno, pvid = s._insert_voucher(con, pkind, vdate, f"{word} with {kind.lower()} no. {vno}",
                                            _payment_lines(pkind, party, mode, rec))
            _alloc(con, pvid, vid, rec)
            s.log_action(con, username, "create", after=s.voucher_snapshot(con, pvid))
        con.commit()
    except Exception:
        con.rollback()
        raise
    res = _result(vno, t)
    res["received"], res["balance"] = to_rupees(rec), to_rupees(t["total"] - rec)
    return res


def post_sale(con, vdate, party, items, interstate=False, narration="", username="", received=0, mode="Cash"):
    return _post(con, "Sales", vdate, party, items, interstate, narration, username, received, mode)


def post_purchase(con, vdate, party, items, interstate=False, narration="", username="", received=0, mode="Cash"):
    """For purchases, 'received' means the amount paid to the supplier now."""
    return _post(con, "Purchase", vdate, party, items, interstate, narration, username, received, mode)


def record_payment(con, kind, party, vdate, amount, mode="Cash", narration="", username="", allocations=None):
    """Money received from a customer (kind 'Receipt') or paid to a supplier (kind 'Payment').
    Settles the party's oldest bills first unless allocations [(invoice_voucher_id, rupees)] is given.
    Any part not matched to a bill stays 'on account'."""
    if kind not in ("Receipt", "Payment"):
        raise ValueError("Kind must be Receipt or Payment")
    inv_kind = "Sales" if kind == "Receipt" else "Purchase"
    amt = s.to_paise(amount)
    if amt <= 0:
        raise ValueError("Amount must be more than zero")
    _mode_check(mode)
    is_party = con.execute("SELECT 1 FROM parties WHERE name=? AND ptype=?",
                           (party, "Customer" if kind == "Receipt" else "Supplier")).fetchone()
    if not is_party:
        raise ValueError(f"'{party}' is not a {'customer' if kind == 'Receipt' else 'supplier'} in Party Master")
    open_ = {o["id"]: o for o in open_invoices(con, party, inv_kind)}
    if allocations is None:
        left, allocs = amt, []
        for o in open_.values():
            take = min(left, o["balance"])
            if take > 0:
                allocs.append((o["id"], take)); left -= take
            if left == 0:
                break
    else:
        allocs = [(vid, s.to_paise(a)) for vid, a in allocations]
        for vid, a in allocs:
            if vid not in open_:
                raise ValueError("A selected bill is not open for this party")
            if a <= 0 or a > open_[vid]["balance"]:
                raise ValueError("Amount against a bill must be more than zero and not above its balance")
        if sum(a for _, a in allocs) > amt:
            raise ValueError("Amounts against bills add up to more than the payment")
    try:
        vno, pvid = s._insert_voucher(con, kind, vdate, narration, _payment_lines(kind, party, mode, amt))
        for ivid, a in allocs:
            _alloc(con, pvid, ivid, a)
        s.log_action(con, username, "create", after=s.voucher_snapshot(con, pvid))
        con.commit()
    except Exception:
        con.rollback()
        raise
    done = sum(a for _, a in allocs)
    return {"vno": vno, "allocated": to_rupees(done), "on_account": to_rupees(amt - done),
            "settled_bills": [(open_[v]["vno"], to_rupees(a)) for v, a in allocs]}


def update_invoice(con, vid, vdate, party, items, interstate=False, narration="", username=""):
    """Edit a stored invoice. Recomputes tax and rewrites its voucher. All-or-nothing."""
    v = con.execute("SELECT vtype FROM vouchers WHERE id=?", (vid,)).fetchone()
    if not v or v["vtype"] not in ("Sales", "Purchase"):
        raise ValueError("Not a sales or purchase invoice")
    if not con.execute("SELECT 1 FROM invoices WHERE voucher_id=?", (vid,)).fetchone():
        raise ValueError("This bill was saved before item details were stored. Delete it and enter it again")
    kind = v["vtype"]
    t = compute_tax(items, interstate)
    done = settled_paise(con, vid)
    if done:
        if con.execute("SELECT party FROM invoices WHERE voucher_id=?", (vid,)).fetchone()["party"] != party:
            raise ValueError("Payments are already recorded against this bill, so its party cannot be changed")
        if t["total"] < done:
            raise ValueError(f"The new total is less than the Rs {to_rupees(done):,.2f} already settled against this bill")
    _ensure_tax_accounts(con, kind)
    before = s.voucher_snapshot(con, vid)
    try:
        s._replace_voucher(con, vid, kind, vdate, narration, _lines(kind, party, t))
        con.execute("DELETE FROM invoices WHERE voucher_id=?", (vid,))
        _store_invoice(con, vid, kind, party, interstate, items, t)
        s.log_action(con, username, "edit", before=before, after=s.voucher_snapshot(con, vid))
        con.commit()
    except Exception:
        con.rollback()
        raise
    return _result(s.voucher_snapshot(con, vid)["vno"], t)


def summary_items(rows, inclusive=False):
    """Turns a daily sales summary [(gst_percent, amount_rupees)] into invoice items, one per rate.
    With inclusive=True the amounts already contain GST, so taxable value is backed out of them
    (the final total may differ from what was typed by a paisa because tax is rounded)."""
    items = []
    for rate, amount in rows:
        amt, g = Decimal(str(amount)), Decimal(str(rate))
        if amt < 0:
            raise ValueError("Amounts cannot be negative")
        if amt == 0:
            continue
        taxable = (amt * 100 / (100 + g)) if inclusive else amt
        taxable = taxable.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        label = str(int(g)) if g == int(g) else str(g)
        items.append((f"Sales summary @{label}%", 1, taxable, g))
    if not items:
        raise ValueError("Enter at least one amount")
    return items
