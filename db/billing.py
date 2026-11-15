"""GST sales and purchase posting. All maths in integer paise with half-up rounding.
Tax is computed per GST-rate group on the invoice (not per line)."""
from decimal import Decimal, ROUND_HALF_UP
from db.setup import ensure_account, post_voucher_paise, to_rupees, GSTIN_RE

TAX_GROUP = "Duties & Taxes"

def _paise(x):
    return int((Decimal(str(x)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

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

def _result(vno, t):
    return {"vno": vno, **{k: to_rupees(v) for k, v in t.items()}}

def post_sale(con, vdate, party, items, interstate=False, narration=""):
    t = compute_tax(items, interstate)
    for n in ("Output CGST", "Output SGST", "Output IGST"):
        ensure_account(con, n, TAX_GROUP, "Liability")
    lines = [(party, t["total"], 0), ("Sales", 0, t["taxable"]),
             ("Output CGST", 0, t["cgst"]), ("Output SGST", 0, t["sgst"]),
             ("Output IGST", 0, t["igst"])]
    return _result(post_voucher_paise(con, "Sales", vdate, narration, lines), t)

def post_purchase(con, vdate, party, items, interstate=False, narration=""):
    t = compute_tax(items, interstate)
    for n in ("Input CGST", "Input SGST", "Input IGST"):
        ensure_account(con, n, TAX_GROUP, "Asset")
    lines = [("Purchase", t["taxable"], 0), ("Input CGST", t["cgst"], 0),
             ("Input SGST", t["sgst"], 0), ("Input IGST", t["igst"], 0),
             (party, 0, t["total"])]
    return _result(post_voucher_paise(con, "Purchase", vdate, narration, lines), t)
