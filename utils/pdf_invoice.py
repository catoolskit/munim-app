"""A4 GST tax invoice PDF generator for MUNIM.
Saves to C:\\MUNIM\\Invoices\\  (creates folder if needed).
Returns the full path of the saved file.
"""
import os
from datetime import date as _date
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer, HRFlowable)
from reportlab.platypus.flowables import KeepTogether
from db import setup as s, billing as b
from utils import settings
from utils.fmt import disp_date

# ── folder ──────────────────────────────────────────────────────────────────
INVOICE_DIR = r"C:\MUNIM\Invoices"

# ── brand colours (match MUNIM theme) ───────────────────────────────────────
NAVY    = colors.HexColor("#1A2B4A")
ACCENT  = colors.HexColor("#2563EB")
LIGHT   = colors.HexColor("#EEF2FF")
MUTED   = colors.HexColor("#6B7280")
WHITE   = colors.white
BLACK   = colors.black
RULE    = colors.HexColor("#D1D5DB")

# ── helpers ──────────────────────────────────────────────────────────────────
def _inr(paise: int) -> str:
    """Format paise integer as Rs 1,23,456.78"""
    rupees = paise / 100
    s_int = f"{int(rupees):,}"
    s_dec = f"{rupees:.2f}".split(".")[1]
    return f"{s_int}.{s_dec}"

def _wrap(text, style):
    return Paragraph(str(text or ""), style)

def _money(paise, style):
    return Paragraph(_inr(paise), style)

# ── main function ─────────────────────────────────────────────────────────────
def generate_invoice_pdf(con, voucher_id: int) -> str:
    """Generate a PDF for the given Sales voucher_id. Returns saved file path."""
    os.makedirs(INVOICE_DIR, exist_ok=True)

    snap = s.voucher_snapshot(con, voucher_id)
    inv  = snap["invoice"]
    st   = settings.load_settings()

    # Basic invoice data
    vno      = snap["vno"]
    vdate    = disp_date(snap["vdate"])
    party    = inv["party"]
    cust_name = inv.get("customer_name") or party
    interstate = bool(inv.get("interstate"))
    items    = inv["items"]          # list of dicts: description, qty, rate, gst, amount
    narration = snap.get("narration") or ""

    # Company info
    company  = st.get("company_name", "")
    address  = st.get("address", "")
    phone    = st.get("phone", "")
    gstin    = st.get("gstin", "")

    # Party GSTIN (if exists)
    row = con.execute("SELECT gstin, address FROM parties WHERE name=?", (party,)).fetchone()
    party_gstin   = row["gstin"]   if row else ""
    party_address = row["address"] if row else ""

    # Recompute totals
    items_for_tax = [(it["description"], float(it["qty"]), float(it["rate"]), float(it["gst"]))
                     for it in items]
    tax = b.compute_tax(items_for_tax, interstate)

    # Invoice prefix from settings
    prefix = st.get("invoice_prefix", "INV")
    inv_no = f"{prefix}-{vno:04d}"

    filename = f"{inv_no}_{vdate.replace('-', '')}.pdf"
    filepath = os.path.join(INVOICE_DIR, filename)

    # ── styles ───────────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    def sty(name, **kw):
        return ParagraphStyle(name, **kw)

    H1  = sty("H1",  fontSize=20, textColor=WHITE,  fontName="Helvetica-Bold", leading=24)
    H2  = sty("H2",  fontSize=10, textColor=MUTED,  fontName="Helvetica",      leading=14)
    BLD = sty("BLD", fontSize=10, textColor=BLACK,  fontName="Helvetica-Bold", leading=13)
    NRM = sty("NRM", fontSize=9,  textColor=BLACK,  fontName="Helvetica",      leading=12)
    SML = sty("SML", fontSize=8,  textColor=MUTED,  fontName="Helvetica",      leading=11)
    RGT = sty("RGT", fontSize=9,  textColor=BLACK,  fontName="Helvetica",      leading=12,
              alignment=TA_RIGHT)
    BRGT= sty("BRGT",fontSize=9, textColor=BLACK,  fontName="Helvetica-Bold", leading=12,
              alignment=TA_RIGHT)
    CTR = sty("CTR", fontSize=9,  textColor=MUTED,  fontName="Helvetica",      leading=12,
              alignment=TA_CENTER)
    HCTR= sty("HCTR",fontSize=9, textColor=WHITE,  fontName="Helvetica-Bold", leading=12,
              alignment=TA_CENTER)
    HRGT= sty("HRGT",fontSize=9, textColor=WHITE,  fontName="Helvetica-Bold", leading=12,
              alignment=TA_RIGHT)

    # ── document ─────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm,  bottomMargin=12*mm,
    )
    W = A4[0] - 30*mm   # usable width

    story = []

    # ── header band ──────────────────────────────────────────────────────────
    hdr_data = [[
        _wrap(company or "TAX INVOICE", H1),
        _wrap("TAX INVOICE", sty("TI", fontSize=11, textColor=WHITE,
                                  fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=14)),
    ]]
    hdr_tbl = Table(hdr_data, colWidths=[W * 0.65, W * 0.35])
    hdr_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",(0, 0), (-1, -1), 10),
        ("RIGHTPADDING",(0,0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1),  10),
    ]))
    story.append(hdr_tbl)
    story.append(Spacer(1, 4*mm))

    # ── seller / buyer + invoice meta ────────────────────────────────────────
    def addr_block(title, name, addr, gstin_val, style_title):
        lines = [_wrap(title, SML), _wrap(name, BLD)]
        if addr:
            lines.append(_wrap(addr, NRM))
        if gstin_val:
            lines.append(_wrap(f"GSTIN: {gstin_val}", NRM))
        return lines

    seller_lines = addr_block("SELLER", company, address, gstin, BLD)
    if phone:
        seller_lines.append(_wrap(f"Ph: {phone}", NRM))

    buyer_lines = addr_block("BUYER", cust_name, party_address, party_gstin, BLD)

    meta_lines = [
        _wrap("Invoice No.", SML), _wrap(inv_no, BLD),
        _wrap("Date",        SML), _wrap(vdate,  NRM),
    ]
    if narration:
        meta_lines += [_wrap("Narration", SML), _wrap(narration, NRM)]

    info_data = [[
        seller_lines,
        buyer_lines,
        meta_lines,
    ]]
    # We'll put each column as a nested table of two cols (label / value)
    # Flatten the list approach: just stack paragraphs in a cell
    def paras_cell(paras):
        return [p for p in paras]

    info_tbl = Table(
        [[paras_cell(seller_lines), paras_cell(buyer_lines), paras_cell(meta_lines)]],
        colWidths=[W * 0.34, W * 0.38, W * 0.28],
    )
    info_tbl.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
        ("TOPPADDING",  (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0,0), (-1, -1), 6),
        ("LINEAFTER",   (0, 0), (1, 0),   0.5, RULE),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 3*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=RULE))
    story.append(Spacer(1, 2*mm))

    # ── items table ───────────────────────────────────────────────────────────
    # Columns: #  Description  Qty  Rate  GST%  Taxable  CGST/SGST/IGST  Amount
    if interstate:
        col_tax   = ["IGST %", "IGST Amt"]
        tax_cols  = 2
    else:
        col_tax   = ["CGST %", "CGST Amt", "SGST %", "SGST Amt"]
        tax_cols  = 4

    hdr_row = [
        _wrap("#", HCTR), _wrap("Description", HCTR),
        _wrap("Qty", HCTR), _wrap("Rate", HRGT), _wrap("Taxable", HRGT),
    ] + [_wrap(h, HCTR) for h in col_tax] + [_wrap("Total", HRGT)]

    rows_data = [hdr_row]
    for idx, it in enumerate(items, 1):
        desc  = it["description"]
        qty   = float(it["qty"])
        rate  = float(it["rate"])
        gst_p = float(it["gst"])
        taxable_paise = round(qty * rate * 100)   # paise
        if interstate:
            igst = round(taxable_paise * gst_p / 100)
            total_paise = taxable_paise + igst
            tax_cells = [_wrap(f"{gst_p:.0f}%", CTR), _money(igst, RGT)]
        else:
            half = gst_p / 2
            cgst = round(taxable_paise * half / 100)
            sgst = cgst
            total_paise = taxable_paise + cgst + sgst
            tax_cells = [_wrap(f"{half:.1f}%", CTR), _money(cgst, RGT),
                         _wrap(f"{half:.1f}%", CTR), _money(sgst, RGT)]

        row_cells = [
            _wrap(str(idx), CTR),
            _wrap(desc, NRM),
            _wrap(f"{qty:g}", CTR),
            _money(round(rate * 100), RGT),
            _money(taxable_paise, RGT),
        ] + tax_cells + [_money(total_paise, RGT)]

        rows_data.append(row_cells)

    # Totals row
    cgst_total = tax["cgst"]
    sgst_total = tax["sgst"]
    igst_total = tax["igst"]
    taxable_total = tax["taxable"]
    grand_total   = tax["total"]

    if interstate:
        total_tax_cells = [_wrap("", NRM), _money(igst_total, BRGT)]
    else:
        total_tax_cells = [_wrap("", NRM), _money(cgst_total, BRGT),
                           _wrap("", NRM), _money(sgst_total, BRGT)]

    totals_row = [
        _wrap("", NRM), _wrap("Total", BLD), _wrap("", NRM), _wrap("", NRM),
        _money(taxable_total, BRGT),
    ] + total_tax_cells + [_money(grand_total, BRGT)]
    rows_data.append(totals_row)

    # Column widths
    desc_w  = W * 0.28
    num_w   = (W - desc_w) / (5 + tax_cols)
    col_ws  = [num_w * 0.5, desc_w, num_w * 0.6, num_w, num_w] + [num_w * 0.8] * tax_cols + [num_w]

    item_tbl = Table(rows_data, colWidths=col_ws, repeatRows=1)
    n = len(rows_data)
    item_tbl.setStyle(TableStyle([
        # header
        ("BACKGROUND",    (0, 0), (-1, 0),   NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0),   WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),   "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),   8),
        ("TOPPADDING",    (0, 0), (-1, 0),   5),
        ("BOTTOMPADDING", (0, 0), (-1, 0),   5),
        # body rows
        ("FONTSIZE",      (0, 1), (-1, -1),  8),
        ("TOPPADDING",    (0, 1), (-1, -1),  3),
        ("BOTTOMPADDING", (0, 1), (-1, -1),  3),
        ("ROWBACKGROUNDS",(0, 1), (-1, -2),  [WHITE, LIGHT]),
        # totals row
        ("BACKGROUND",    (0, n-1), (-1, n-1), LIGHT),
        ("LINEABOVE",     (0, n-1), (-1, n-1), 0.8, NAVY),
        # grid
        ("LINEBELOW",     (0, 0), (-1, 0),   0.5, NAVY),
        ("GRID",          (0, 0), (-1, -1),  0.3, RULE),
        ("VALIGN",        (0, 0), (-1, -1),  "MIDDLE"),
    ]))
    story.append(item_tbl)
    story.append(Spacer(1, 4*mm))

    # ── grand total box ───────────────────────────────────────────────────────
    round_off = st.get("round_off", False)
    display_total = grand_total  # already in paise
    rounded_total = round(grand_total / 100) * 100  # round to nearest rupee

    summary_rows = []
    if not interstate:
        summary_rows += [
            [_wrap("CGST", NRM), _money(cgst_total, RGT)],
            [_wrap("SGST", NRM), _money(sgst_total, RGT)],
        ]
    else:
        summary_rows += [[_wrap("IGST", NRM), _money(igst_total, RGT)]]
    summary_rows.append([_wrap("Taxable Amount", NRM), _money(taxable_total, RGT)])
    if round_off:
        roff = rounded_total - grand_total
        if roff:
            summary_rows.append([_wrap("Round Off", NRM), _money(roff, RGT)])
        display_total = rounded_total
    summary_rows.append([_wrap("GRAND TOTAL", BLD), _money(display_total, BRGT)])

    summ_tbl = Table(summary_rows, colWidths=[W * 0.5, W * 0.15],
                     hAlign="RIGHT")
    summ_tbl.setStyle(TableStyle([
        ("LINEABOVE",  (0, len(summary_rows)-1), (-1, len(summary_rows)-1), 1, NAVY),
        ("BACKGROUND", (0, len(summary_rows)-1), (-1, len(summary_rows)-1), LIGHT),
        ("GRID",       (0, 0), (-1, -1), 0.3, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1),  3),
        ("LEFTPADDING",(0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0,0), (-1, -1), 6),
    ]))
    story.append(summ_tbl)
    story.append(Spacer(1, 6*mm))

    # ── footer ────────────────────────────────────────────────────────────────
    footer_data = [[
        _wrap("This is a computer-generated invoice.", SML),
        _wrap(f"For {company}", sty("FS", fontSize=8, textColor=MUTED,
                                     fontName="Helvetica", alignment=TA_RIGHT, leading=11)),
    ]]
    footer_tbl = Table(footer_data, colWidths=[W * 0.6, W * 0.4])
    footer_tbl.setStyle(TableStyle([
        ("LINEABOVE",   (0, 0), (-1, 0), 0.5, RULE),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(footer_tbl)

    doc.build(story)
    return filepath