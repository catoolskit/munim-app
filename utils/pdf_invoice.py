"""A4 GST tax invoice PDF generator for MUNIM.
Saves to C:\\MUNIM\\Invoices\\  (creates folder if needed).
Returns the full path of the saved file.
"""
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer, HRFlowable)
from db import setup as s, billing as b
from utils import settings
from utils.fmt import disp_date

INVOICE_DIR = r"C:\MUNIM\Invoices"

NAVY   = colors.HexColor("#1A2B4A")
ACCENT = colors.HexColor("#2563EB")
LIGHT  = colors.HexColor("#EEF2FF")
MUTED  = colors.HexColor("#6B7280")
WHITE  = colors.white
BLACK  = colors.black
RULE   = colors.HexColor("#D1D5DB")


def _inr(paise: int) -> str:
    """Format paise as plain rupees — no comma grouping in table cells to prevent wrapping."""
    rupees = paise / 100
    return f"{rupees:,.2f}"


def _wrap(text, style):
    return Paragraph(str(text or ""), style)


def _money(paise, style):
    return Paragraph(_inr(paise), style)


def generate_invoice_pdf(con, voucher_id: int) -> str:
    os.makedirs(INVOICE_DIR, exist_ok=True)

    snap = s.voucher_snapshot(con, voucher_id)
    inv  = snap["invoice"]
    st   = settings.load_settings()

    vno        = snap["vno"]
    vdate      = disp_date(snap["vdate"])
    party      = inv["party"]
    cust_name  = inv.get("customer_name") or party
    interstate = bool(inv.get("interstate"))
    items      = inv["items"]
    narration  = snap.get("narration") or ""

    company  = st.get("company_name", "")
    address  = st.get("address", "")
    phone    = st.get("phone", "")
    gstin    = st.get("gstin", "")

    row = con.execute("SELECT gstin, address FROM parties WHERE name=?", (party,)).fetchone()
    party_gstin   = row["gstin"]   if row else ""
    party_address = row["address"] if row else ""

    items_for_tax = [(it["description"], float(it["qty"]), float(it["rate"]), float(it["gst"]))
                     for it in items]
    tax = b.compute_tax(items_for_tax, interstate)

    prefix  = st.get("invoice_prefix", "INV")
    inv_no  = f"{prefix}-{vno:04d}"
    filename = f"{inv_no}_{vdate.replace('-', '')}.pdf"
    filepath = os.path.join(INVOICE_DIR, filename)

    # ── styles ───────────────────────────────────────────────────────────────
    def sty(name, **kw):
        return ParagraphStyle(name, **kw)

    H1   = sty("H1",   fontSize=20, textColor=WHITE, fontName="Helvetica-Bold", leading=24)
    H2   = sty("H2",   fontSize=10, textColor=MUTED, fontName="Helvetica",      leading=14)
    BLD  = sty("BLD",  fontSize=10, textColor=BLACK, fontName="Helvetica-Bold", leading=13)
    NRM  = sty("NRM",  fontSize=9,  textColor=BLACK, fontName="Helvetica",      leading=12)
    SML  = sty("SML",  fontSize=8,  textColor=MUTED, fontName="Helvetica",      leading=11)
    RGT  = sty("RGT",  fontSize=9,  textColor=BLACK, fontName="Helvetica",      leading=12, alignment=TA_RIGHT)
    BRGT = sty("BRGT", fontSize=9,  textColor=BLACK, fontName="Helvetica-Bold", leading=12, alignment=TA_RIGHT)
    CTR  = sty("CTR",  fontSize=9,  textColor=MUTED, fontName="Helvetica",      leading=12, alignment=TA_CENTER)
    HCTR = sty("HCTR", fontSize=8,  textColor=WHITE, fontName="Helvetica-Bold", leading=11, alignment=TA_CENTER)
    HRGT = sty("HRGT", fontSize=8,  textColor=WHITE, fontName="Helvetica-Bold", leading=11, alignment=TA_RIGHT)

    # ── document ─────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=12*mm, rightMargin=12*mm,
        topMargin=10*mm,  bottomMargin=10*mm,
    )
    W = A4[0] - 24*mm

    story = []

    # ── header ───────────────────────────────────────────────────────────────
    hdr_data = [[
        _wrap(company or "TAX INVOICE", H1),
        _wrap("TAX INVOICE", sty("TI", fontSize=11, textColor=WHITE,
              fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=14)),
    ]]
    hdr_tbl = Table(hdr_data, colWidths=[W * 0.65, W * 0.35])
    hdr_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(hdr_tbl)
    story.append(Spacer(1, 4*mm))

    # ── seller / buyer / meta ────────────────────────────────────────────────
    def paras_cell(title, name, addr, gstin_val, ph=None):
        lines = [_wrap(title, SML), _wrap(name, BLD)]
        if addr:
            lines.append(_wrap(addr, NRM))
        if gstin_val:
            lines.append(_wrap(f"GSTIN: {gstin_val}", NRM))
        if ph:
            lines.append(_wrap(f"Ph: {ph}", NRM))
        return lines

    seller_paras = paras_cell("SELLER", company, address, gstin, phone)
    buyer_paras  = paras_cell("BUYER",  cust_name, party_address, party_gstin)

    meta = [_wrap("Invoice No.", SML), _wrap(inv_no, BLD),
            _wrap("Date",        SML), _wrap(vdate,  NRM)]
    if narration:
        meta += [_wrap("Narration", SML), _wrap(narration, NRM)]

    info_tbl = Table(
        [[seller_paras, buyer_paras, meta]],
        colWidths=[W * 0.34, W * 0.38, W * 0.28],
    )
    info_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEAFTER",     (0, 0), (1,  0),  0.5, RULE),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 3*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=RULE))
    story.append(Spacer(1, 2*mm))

    # ── items table ───────────────────────────────────────────────────────────
    if interstate:
        col_tax  = ["IGST %", "IGST Amt"]
        tax_cols = 2
    else:
        col_tax  = ["CGST%", "CGST Amt", "SGST%", "SGST Amt"]
        tax_cols = 4

    hdr_row = (
        [_wrap("#", HCTR), _wrap("Description", HCTR),
         _wrap("Qty", HCTR), _wrap("Rate", HRGT), _wrap("Taxable", HRGT)]
        + [_wrap(h, HCTR) for h in col_tax]
        + [_wrap("Total", HRGT)]
    )

    rows_data = [hdr_row]
    for idx, it in enumerate(items, 1):
        desc        = it["description"]
        qty         = float(it["qty"])
        rate        = float(it["rate"])
        gst_p       = float(it["gst"])
        taxable_p   = round(qty * rate * 100)
        if interstate:
            igst        = round(taxable_p * gst_p / 100)
            total_p     = taxable_p + igst
            tax_cells   = [_wrap(f"{gst_p:.0f}%", CTR), _money(igst, RGT)]
        else:
            half        = gst_p / 2
            cgst        = round(taxable_p * half / 100)
            sgst        = cgst
            total_p     = taxable_p + cgst + sgst
            tax_cells   = [_wrap(f"{half:.1f}%", CTR), _money(cgst, RGT),
                           _wrap(f"{half:.1f}%", CTR), _money(sgst, RGT)]

        rows_data.append(
            [_wrap(str(idx), CTR), _wrap(desc, NRM),
             _wrap(f"{qty:g}", CTR), _money(round(rate * 100), RGT),
             _money(taxable_p, RGT)]
            + tax_cells
            + [_money(total_p, RGT)]
        )

    # totals row
    if interstate:
        total_tax_cells = [_wrap("", NRM), _money(tax["igst"], BRGT)]
    else:
        total_tax_cells = [_wrap("", NRM), _money(tax["cgst"], BRGT),
                           _wrap("", NRM), _money(tax["sgst"], BRGT)]

    rows_data.append(
        [_wrap("", NRM), _wrap("Total", BLD), _wrap("", NRM), _wrap("", NRM),
         _money(tax["taxable"], BRGT)]
        + total_tax_cells
        + [_money(tax["total"], BRGT)]
    )

    # ── column widths — key fix: wider money columns ──────────────────────────
    # Total usable width split across: # | Desc | Qty | Rate | Taxable | tax cols | Total
    # Money columns get 52pt each — wide enough for "1,00,000.00" on one line at font 9
    n_money = 2 + tax_cols          # Rate + Taxable + tax amount cols + Total
    money_w = 62                    # points — fits 10-char number at font 9
    idx_w   = 18
    qty_w   = 28
    pct_w   = 30                    # GST% columns
    desc_w  = W - idx_w - qty_w - money_w * 2 - pct_w * (tax_cols // 2) - money_w * (tax_cols // 2 + 2)

    if interstate:
        col_ws = [idx_w, desc_w, qty_w, money_w, money_w, pct_w, money_w, money_w]
    else:
        col_ws = [idx_w, desc_w, qty_w, money_w, money_w, pct_w, money_w, pct_w, money_w, money_w]

    n = len(rows_data)
    item_tbl = Table(rows_data, colWidths=col_ws, repeatRows=1)
    item_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),     (-1, 0),     NAVY),
        ("FONTNAME",      (0, 0),     (-1, 0),     "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0),     (-1, 0),     8),
        ("TOPPADDING",    (0, 0),     (-1, 0),     5),
        ("BOTTOMPADDING", (0, 0),     (-1, 0),     5),
        ("FONTSIZE",      (0, 1),     (-1, -1),    9),
        ("TOPPADDING",    (0, 1),     (-1, -1),    4),
        ("BOTTOMPADDING", (0, 1),     (-1, -1),    4),
        ("ROWBACKGROUNDS",(0, 1),     (-1, -2),    [WHITE, LIGHT]),
        ("BACKGROUND",    (0, n - 1), (-1, n - 1), LIGHT),
        ("LINEABOVE",     (0, n - 1), (-1, n - 1), 0.8, NAVY),
        ("LINEBELOW",     (0, 0),     (-1, 0),     0.5, NAVY),
        ("GRID",          (0, 0),     (-1, -1),    0.3, RULE),
        ("VALIGN",        (0, 0),     (-1, -1),    "MIDDLE"),
    ]))
    story.append(item_tbl)
    story.append(Spacer(1, 4*mm))

    # ── summary box ───────────────────────────────────────────────────────────
    round_off   = st.get("round_off", False)
    grand_total = tax["total"]
    summary_rows = []
    if not interstate:
        summary_rows += [[_wrap("CGST", NRM),          _money(tax["cgst"], RGT)],
                         [_wrap("SGST", NRM),          _money(tax["sgst"], RGT)]]
    else:
        summary_rows += [[_wrap("IGST", NRM),          _money(tax["igst"], RGT)]]
    summary_rows   += [[_wrap("Taxable Amount", NRM),  _money(tax["taxable"], RGT)]]

    if round_off:
        rounded = round(grand_total / 100) * 100
        roff    = rounded - grand_total
        if roff:
            summary_rows.append([_wrap("Round Off", NRM), _money(roff, RGT)])
        grand_total = rounded

    summary_rows.append([_wrap("GRAND TOTAL", BLD), _money(grand_total, BRGT)])

    summ_tbl = Table(summary_rows, colWidths=[W * 0.5, 70], hAlign="RIGHT")
    summ_tbl.setStyle(TableStyle([
        ("LINEABOVE",     (0, len(summary_rows) - 1), (-1, -1), 1,   NAVY),
        ("BACKGROUND",    (0, len(summary_rows) - 1), (-1, -1), LIGHT),
        ("GRID",          (0, 0), (-1, -1), 0.3, RULE),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(summ_tbl)
    story.append(Spacer(1, 6*mm))

    # ── footer ────────────────────────────────────────────────────────────────
    footer_tbl = Table([[
        _wrap("This is a computer-generated invoice.", SML),
        _wrap(f"For {company}", sty("FS", fontSize=8, textColor=MUTED,
              fontName="Helvetica", alignment=TA_RIGHT, leading=11)),
    ]], colWidths=[W * 0.6, W * 0.4])
    footer_tbl.setStyle(TableStyle([
        ("LINEABOVE",  (0, 0), (-1, 0), 0.5, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(footer_tbl)

    doc.build(story)
    return filepath
