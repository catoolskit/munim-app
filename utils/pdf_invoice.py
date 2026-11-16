"""A4 GST tax invoice PDF generator for MUNIM.
Saves to C:\\MUNIM\\Invoices\\  (creates folder if needed).
Returns the full path of the saved file.
"""
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, pt
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer, HRFlowable)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from db import setup as s, billing as b
from utils import settings
from utils.fmt import disp_date

INVOICE_DIR = r"C:\MUNIM\Invoices"

# ── colours ──────────────────────────────────────────────────────────────────
NAVY    = colors.HexColor("#1A2B4A")
BLUE    = colors.HexColor("#2563EB")
LBLUE   = colors.HexColor("#DBEAFE")
LIGHT   = colors.HexColor("#EEF2FF")
MUTED   = colors.HexColor("#6B7280")
WHITE   = colors.white
BLACK   = colors.black
RULE    = colors.HexColor("#D1D5DB")


def _fmt(paise) -> str:
    """Format paise as rupees with commas, no wrapping — always one line."""
    return f"{paise / 100:,.2f}"


def _p(text, style):
    return Paragraph(str(text or ""), style)


def _m(paise, style):
    return Paragraph(_fmt(paise), style)


def generate_invoice_pdf(con, voucher_id: int) -> str:
    os.makedirs(INVOICE_DIR, exist_ok=True)

    snap       = s.voucher_snapshot(con, voucher_id)
    inv        = snap["invoice"]
    st         = settings.load_settings()

    vno        = snap["vno"]
    vdate      = disp_date(snap["vdate"])
    party      = inv["party"]
    cust_name  = inv.get("customer_name") or party
    interstate = bool(inv.get("interstate"))
    items      = inv["items"]
    narration  = snap.get("narration") or ""

    company    = st.get("company_name", "")
    address    = st.get("address", "")
    phone      = st.get("phone", "")
    gstin      = st.get("gstin", "")

    row        = con.execute("SELECT gstin FROM parties WHERE name=?", (party,)).fetchone()
    party_gstin = row["gstin"] if row else ""

    items_for_tax = [(it["description"], float(it["qty"]), float(it["rate"]), float(it["gst"]))
                     for it in items]
    tax = b.compute_tax(items_for_tax, interstate)

    prefix   = st.get("invoice_prefix", "INV")
    inv_no   = f"{prefix}-{vno:04d}"
    filename = f"{inv_no}_{vdate.replace('-', '')}.pdf"
    filepath = os.path.join(INVOICE_DIR, filename)

    # ── page setup ────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=12*mm, rightMargin=12*mm,
        topMargin=10*mm,  bottomMargin=10*mm,
    )
    W = A4[0] - 24*mm   # usable width ≈ 537 pt

    # ── styles ────────────────────────────────────────────────────────────────
    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    HDR  = S("HDR",  fontSize=22, textColor=WHITE,  fontName="Helvetica-Bold", leading=26)
    BLD  = S("BLD",  fontSize=10, textColor=BLACK,  fontName="Helvetica-Bold", leading=14)
    NRM  = S("NRM",  fontSize=9,  textColor=BLACK,  fontName="Helvetica",      leading=12)
    SML  = S("SML",  fontSize=8,  textColor=MUTED,  fontName="Helvetica",      leading=10)
    RGT  = S("RGT",  fontSize=9,  textColor=BLACK,  fontName="Helvetica",      leading=12, alignment=TA_RIGHT)
    BRGT = S("BRGT", fontSize=10, textColor=BLACK,  fontName="Helvetica-Bold", leading=13, alignment=TA_RIGHT)
    CTR  = S("CTR",  fontSize=9,  textColor=BLACK,  fontName="Helvetica",      leading=12, alignment=TA_CENTER)
    HCTR = S("HCTR", fontSize=8,  textColor=WHITE,  fontName="Helvetica-Bold", leading=11, alignment=TA_CENTER)
    HRGT = S("HRGT", fontSize=8,  textColor=WHITE,  fontName="Helvetica-Bold", leading=11, alignment=TA_RIGHT)
    HLFT = S("HLFT", fontSize=8,  textColor=WHITE,  fontName="Helvetica-Bold", leading=11, alignment=TA_LEFT)
    MLBL = S("MLBL", fontSize=9,  textColor=MUTED,  fontName="Helvetica",      leading=12)
    MVAL = S("MVAL", fontSize=10, textColor=BLACK,  fontName="Helvetica-Bold", leading=14)

    story = []

    # ── HEADER: dark navy band with icon placeholder + title + invoice meta ───
    # Left cell: icon box + "TAX INVOICE"
    # Right cell: Invoice No. / Date

    icon_cell = [
        _p("🧾  TAX INVOICE", HDR),
    ]
    meta_cell = [
        _p("Invoice No.", SML),
        _p(inv_no, MVAL),
        _p("Date", SML),
        _p(vdate, S("VD", fontSize=10, textColor=WHITE,
                    fontName="Helvetica", leading=13)),
    ]

    # Override meta colours for dark background
    MVAL_W = S("MVAL_W", fontSize=12, textColor=WHITE, fontName="Helvetica-Bold", leading=16)
    SML_W  = S("SML_W",  fontSize=8,  textColor=LBLUE, fontName="Helvetica",      leading=10)
    VD_W   = S("VD_W",   fontSize=10, textColor=WHITE, fontName="Helvetica",      leading=13)

    hdr_tbl = Table(
        [[_p("🧾  TAX INVOICE", HDR),
          [_p("Invoice No.", SML_W), _p(inv_no, MVAL_W),
           _p("Date", SML_W),        _p(vdate,  VD_W)]]],
        colWidths=[W * 0.55, W * 0.45],
    )
    hdr_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LINEAFTER",     (0, 0), (0, 0),   0.5, colors.HexColor("#334E7A")),
    ]))
    story.append(hdr_tbl)
    story.append(Spacer(1, 4*mm))

    # ── SELLER / BUYER block ──────────────────────────────────────────────────
    def addr_paras(role, name, gstin_val, addr_val="", ph_val=""):
        out = [_p(role, SML), _p(name, BLD)]
        if addr_val:
            out.append(_p(addr_val, NRM))
        if gstin_val:
            out.append(_p(f"GSTIN: {gstin_val}", NRM))
        if ph_val:
            out.append(_p(f"Ph: {ph_val}", NRM))
        return out

    seller_cell = addr_paras("SELLER", company, gstin, address, phone)
    buyer_cell  = addr_paras("BUYER",  cust_name, party_gstin)

    info_tbl = Table(
        [[seller_cell, buyer_cell]],
        colWidths=[W * 0.5, W * 0.5],
    )
    info_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEAFTER",     (0, 0), (0, 0),   0.5, RULE),
    ]))
    story.append(info_tbl)
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=4))

    # ── ITEMS TABLE ───────────────────────────────────────────────────────────
    # Fixed column widths — money columns wide enough for any amount, no wrap
    IDX  = 18
    QTY  = 30
    PCT  = 34   # GST % cols
    MON  = 70   # money cols: Rate, Taxable, CGST Amt, SGST Amt, Total
    # Desc gets the remainder
    if interstate:
        # cols: # Desc Qty Rate Taxable IGST% IGST_Amt Total  = 8 cols
        DESC = W - IDX - QTY - MON * 3 - PCT - MON
        col_ws = [IDX, DESC, QTY, MON, MON, PCT, MON, MON]
        hdr_labels = ["#","Description","Qty","Rate","Taxable","IGST%","IGST Amt","Total"]
        hdr_aligns = ["CTR","HLFT","CTR","HRGT","HRGT","HCTR","HRGT","HRGT"]
    else:
        # cols: # Desc Qty Rate Taxable CGST% CGST_Amt SGST% SGST_Amt Total = 10 cols
        DESC = W - IDX - QTY - MON * 5 - PCT * 2
        col_ws = [IDX, DESC, QTY, MON, MON, PCT, MON, PCT, MON, MON]
        hdr_labels = ["#","Description","Qty","Rate","Taxable","CGST%","CGST Amt","SGST%","SGST Amt","Total"]
        hdr_aligns = ["CTR","HLFT","CTR","HRGT","HRGT","HCTR","HRGT","HCTR","HRGT","HRGT"]

    style_map = {"CTR": HCTR, "HLFT": HLFT, "HRGT": HRGT, "HCTR": HCTR}
    hdr_row = [_p(lbl, style_map[aln]) for lbl, aln in zip(hdr_labels, hdr_aligns)]

    rows_data = [hdr_row]
    for idx, it in enumerate(items, 1):
        desc    = it["description"]
        qty     = float(it["qty"])
        rate    = float(it["rate"])
        gst_p   = float(it["gst"])
        tax_p   = round(qty * rate * 100)   # paise

        if interstate:
            igst    = round(tax_p * gst_p / 100)
            total_p = tax_p + igst
            t_cells = [_p(f"{gst_p:g}%", CTR), _m(igst, RGT)]
        else:
            half    = gst_p / 2
            cgst    = round(tax_p * half / 100)
            sgst    = cgst
            total_p = tax_p + cgst + sgst
            t_cells = [_p(f"{half:g}%", CTR), _m(cgst, RGT),
                       _p(f"{half:g}%", CTR), _m(sgst, RGT)]

        rows_data.append(
            [_p(str(idx), CTR), _p(desc, NRM), _p(f"{qty:g}", CTR),
             _m(round(rate * 100), RGT), _m(tax_p, RGT)]
            + t_cells + [_m(total_p, RGT)]
        )

    # totals row
    if interstate:
        tot_cells = [_p("", NRM), _m(tax["igst"], BRGT)]
    else:
        tot_cells = [_p("", NRM), _m(tax["cgst"], BRGT),
                     _p("", NRM), _m(tax["sgst"], BRGT)]

    rows_data.append(
        [_p("", NRM), _p("Total", BLD), _p("", NRM), _p("", NRM),
         _m(tax["taxable"], BRGT)]
        + tot_cells + [_m(tax["total"], BRGT)]
    )

    n = len(rows_data)
    item_tbl = Table(rows_data, colWidths=col_ws, repeatRows=1)
    item_tbl.setStyle(TableStyle([
        # header row
        ("BACKGROUND",    (0, 0),     (-1, 0),     NAVY),
        ("FONTSIZE",      (0, 0),     (-1, 0),     8),
        ("TOPPADDING",    (0, 0),     (-1, 0),     6),
        ("BOTTOMPADDING", (0, 0),     (-1, 0),     6),
        # body
        ("FONTSIZE",      (0, 1),     (-1, -1),    9),
        ("TOPPADDING",    (0, 1),     (-1, -1),    5),
        ("BOTTOMPADDING", (0, 1),     (-1, -1),    5),
        ("ROWBACKGROUNDS",(0, 1),     (-1, -2),    [WHITE, LIGHT]),
        # totals
        ("BACKGROUND",    (0, n - 1), (-1, n - 1), LBLUE),
        ("LINEABOVE",     (0, n - 1), (-1, n - 1), 1,   NAVY),
        ("FONTNAME",      (0, n - 1), (-1, n - 1), "Helvetica-Bold"),
        # grid
        ("LINEBELOW",     (0, 0),     (-1, 0),     0.5, BLUE),
        ("GRID",          (0, 0),     (-1, -1),    0.3, RULE),
        ("VALIGN",        (0, 0),     (-1, -1),    "MIDDLE"),
        ("NOSPLIT",       (0, 0),     (-1, -1)),
    ]))
    story.append(item_tbl)
    story.append(Spacer(1, 5*mm))

    # ── SUMMARY BOX ───────────────────────────────────────────────────────────
    grand = tax["total"]
    if st.get("round_off"):
        rounded = round(grand / 100) * 100
        roff    = rounded - grand
        grand   = rounded
    else:
        roff = 0

    summ = []
    if not interstate:
        summ += [[_p("CGST", NRM),          _p(_fmt(tax["cgst"]), RGT)],
                 [_p("SGST", NRM),          _p(_fmt(tax["sgst"]), RGT)]]
    else:
        summ += [[_p("IGST", NRM),          _p(_fmt(tax["igst"]), RGT)]]
    summ   += [[_p("Taxable Amount", NRM),  _p(_fmt(tax["taxable"]), RGT)]]
    if roff:
        summ += [[_p("Round Off", NRM),     _p(_fmt(roff), RGT)]]
    summ   += [[_p("GRAND TOTAL", BLD),     _p(_fmt(grand), BRGT)]]

    SL = len(summ)
    summ_tbl = Table(summ, colWidths=[W * 0.42, 90], hAlign="RIGHT")
    summ_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, SL - 1), (-1, SL - 1), LBLUE),
        ("LINEABOVE",     (0, SL - 1), (-1, SL - 1), 1.2, NAVY),
        ("LINEBELOW",     (0, SL - 1), (-1, SL - 1), 1.2, NAVY),
        ("GRID",          (0, 0),      (-1, -1),      0.3, RULE),
        ("TOPPADDING",    (0, 0),      (-1, -1),      4),
        ("BOTTOMPADDING", (0, 0),      (-1, -1),      4),
        ("LEFTPADDING",   (0, 0),      (-1, -1),      8),
        ("RIGHTPADDING",  (0, 0),      (-1, -1),      8),
        ("FONTNAME",      (0, SL - 1), (-1, SL - 1), "Helvetica-Bold"),
    ]))
    story.append(summ_tbl)
    story.append(Spacer(1, 8*mm))

    # ── FOOTER ────────────────────────────────────────────────────────────────
    FOOT_L = S("FL", fontSize=9, textColor=MUTED,  fontName="Helvetica-Oblique", leading=12)
    FOOT_R = S("FR", fontSize=9, textColor=BLACK,  fontName="Helvetica",         leading=12, alignment=TA_RIGHT)

    foot_tbl = Table(
        [[_p("This is a computer-generated invoice.", FOOT_L),
          _p(f"For  {company}", FOOT_R)]],
        colWidths=[W * 0.6, W * 0.4],
    )
    foot_tbl.setStyle(TableStyle([
        ("LINEABOVE",     (0, 0), (-1, 0), 1, NAVY),
        ("TOPPADDING",    (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("VALIGN",        (0, 0), (-1, 0), "MIDDLE"),
    ]))
    story.append(foot_tbl)

    # ── blue wave bar at very bottom ──────────────────────────────────────────
    wave = Table(
        [[_p("Thank you for your business!", S("TY", fontSize=10, textColor=WHITE,
              fontName="Helvetica-Oblique", leading=13, alignment=TA_CENTER))]],
        colWidths=[W],
    )
    wave.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(Spacer(1, 4*mm))
    story.append(wave)

    doc.build(story)
    return filepath
