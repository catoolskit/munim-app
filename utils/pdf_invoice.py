"""A4 GST tax invoice PDF generator for MUNIM.
Saves to C:\\MUNIM\\Invoices\\  (creates folder if needed).
Returns the full path of the saved file.
"""
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from xml.sax.saxutils import escape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer, HRFlowable)
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

    HDR  = S("HDR",  fontSize=13, textColor=WHITE,  fontName="Helvetica-Bold", leading=16)
    BLD  = S("BLD",  fontSize=10, textColor=BLACK,  fontName="Helvetica-Bold", leading=14)
    NRM  = S("NRM",  fontSize=9,  textColor=BLACK,  fontName="Helvetica",      leading=12)
    SML  = S("SML",  fontSize=8,  textColor=MUTED,  fontName="Helvetica",      leading=10)
    RGT  = S("RGT",  fontSize=8,  textColor=BLACK,  fontName="Helvetica",      leading=12, alignment=TA_RIGHT)
    BRGT = S("BRGT", fontSize=8, textColor=BLACK,  fontName="Helvetica-Bold", leading=13, alignment=TA_RIGHT)
    CTR  = S("CTR",  fontSize=8,  textColor=BLACK,  fontName="Helvetica",      leading=12, alignment=TA_CENTER)
    HCTR = S("HCTR", fontSize=7,  textColor=WHITE,  fontName="Helvetica-Bold", leading=11, alignment=TA_CENTER)
    HRGT = S("HRGT", fontSize=8,  textColor=WHITE,  fontName="Helvetica-Bold", leading=11, alignment=TA_RIGHT)
    HLFT = S("HLFT", fontSize=8,  textColor=WHITE,  fontName="Helvetica-Bold", leading=11, alignment=TA_LEFT)
    MLBL = S("MLBL", fontSize=9,  textColor=MUTED,  fontName="Helvetica",      leading=12)
    MVAL = S("MVAL", fontSize=10, textColor=BLACK,  fontName="Helvetica-Bold", leading=14)

    story = []

    # ── HEADER: dark navy band with icon placeholder + title + invoice meta ───
    # Left cell: icon box + "TAX INVOICE"
    # Right cell: Invoice No. / Date

    icon_cell = [
        _p("TAX INVOICE", HDR),
    ]
    meta_cell = [
        _p("Invoice No.", SML),
        _p(inv_no, MVAL),
        _p("Date", SML),
        _p(vdate, S("VD", fontSize=10, textColor=WHITE,
                    fontName="Helvetica", leading=13)),
    ]

    # Override meta colours for dark background
    MVAL_W = S("MVAL_W", fontSize=10, textColor=WHITE, fontName="Helvetica-Bold", leading=12)
    SML_W  = S("SML_W",  fontSize=7,  textColor=LBLUE, fontName="Helvetica",      leading=9)
    VD_W   = S("VD_W",   fontSize=9,  textColor=WHITE, fontName="Helvetica",      leading=11)

    hdr_tbl = Table(
        [[_p("TAX INVOICE", HDR),
          [_p("Invoice No.", SML_W), _p(inv_no, MVAL_W),
           _p("Date", SML_W),        _p(vdate,  VD_W)]]],
        colWidths=[W * 0.55, W * 0.45],
    )
    hdr_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
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
    # Allocate enough room to Description while keeping every heading/value on
    # one line.  Amount columns are compact but still sized for normal invoices.
    IDX = 16
    QTY = 30
    PCT = 32
    MON = 58
    if interstate:
        # #, Description, Qty, Rate, Taxable, IGST%, IGST Amt, Total
        col_ws = [IDX, W - IDX - QTY - MON * 4 - PCT, QTY, MON, MON, PCT, MON, MON]
        hdr_labels = ["#", "Description", "Qty", "Rate", "Taxable", "IGST%", "IGST Amt", "Total"]
        hdr_aligns = ["CTR", "HLFT", "CTR", "HRGT", "HRGT", "HCTR", "HRGT", "HRGT"]
    else:
        # #, Description, Qty, Rate, Taxable, CGST%, CGST Amt, SGST%, SGST Amt, Total
        col_ws = [IDX, W - IDX - QTY - MON * 5 - PCT * 2, QTY, MON, MON, PCT, MON, PCT, MON, MON]
        hdr_labels = ["#", "Description", "Qty", "Rate", "Taxable", "CGST%", "CGST Amt", "SGST%", "SGST Amt", "Total"]
        hdr_aligns = ["CTR", "HLFT", "CTR", "HRGT", "HRGT", "HCTR", "HRGT", "HCTR", "HRGT", "HRGT"]

    # A no-wrap paragraph shrinks slightly when necessary instead of breaking
    # long descriptions or numeric values into multiple lines.
    def nw(text, base_style, width, min_size=6.2):
        raw = str(text or "")
        font_name = base_style.fontName
        size = base_style.fontSize
        available = max(8, width - 5)
        measured = stringWidth(raw, font_name, size)
        if measured > available and measured:
            size = max(min_size, size * available / measured)
        stl = ParagraphStyle(
            f"NW_{id(base_style)}_{len(raw)}", parent=base_style,
            fontSize=size, leading=max(size + 2, base_style.leading * size / base_style.fontSize),
            splitLongWords=0,
        )
        return Paragraph(f"<nobr>{escape(raw)}</nobr>", stl)

    style_map = {"CTR": HCTR, "HLFT": HLFT, "HRGT": HRGT, "HCTR": HCTR}
    hdr_row = [nw(lbl, style_map[aln], col_ws[i], min_size=6.0)
               for i, (lbl, aln) in enumerate(zip(hdr_labels, hdr_aligns))]

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
            t_cells = [nw(f"{gst_p:g}%", CTR, col_ws[5]), nw(_fmt(igst), RGT, col_ws[6])]
        else:
            half    = gst_p / 2
            cgst    = round(tax_p * half / 100)
            sgst    = cgst
            total_p = tax_p + cgst + sgst
            t_cells = [nw(f"{half:g}%", CTR, col_ws[5]), nw(_fmt(cgst), RGT, col_ws[6]),
                       nw(f"{half:g}%", CTR, col_ws[7]), nw(_fmt(sgst), RGT, col_ws[8])]

        rows_data.append(
            [nw(str(idx), CTR, col_ws[0]), nw(desc, NRM, col_ws[1]), nw(f"{qty:g}", CTR, col_ws[2]),
             nw(_fmt(round(rate * 100)), RGT, col_ws[3]), nw(_fmt(tax_p), RGT, col_ws[4])]
            + t_cells + [nw(_fmt(total_p), RGT, col_ws[-1])]
        )

    # totals row
    if interstate:
        tot_cells = [_p("", NRM), _m(tax["igst"], BRGT)]
    else:
        tot_cells = [_p("", NRM), _m(tax["cgst"], BRGT),
                     _p("", NRM), _m(tax["sgst"], BRGT)]

    if interstate:
        total_cells = [nw("", NRM, col_ws[0]), nw("Total", BLD, col_ws[1]),
                       nw("", NRM, col_ws[2]), nw("", NRM, col_ws[3]),
                       nw(_fmt(tax["taxable"]), BRGT, col_ws[4]),
                       nw("", NRM, col_ws[5]), nw(_fmt(tax["igst"]), BRGT, col_ws[6]),
                       nw(_fmt(tax["total"]), BRGT, col_ws[7])]
    else:
        total_cells = [nw("", NRM, col_ws[0]), nw("Total", BLD, col_ws[1]),
                       nw("", NRM, col_ws[2]), nw("", NRM, col_ws[3]),
                       nw(_fmt(tax["taxable"]), BRGT, col_ws[4]),
                       nw("", NRM, col_ws[5]), nw(_fmt(tax["cgst"]), BRGT, col_ws[6]),
                       nw("", NRM, col_ws[7]), nw(_fmt(tax["sgst"]), BRGT, col_ws[8]),
                       nw(_fmt(tax["total"]), BRGT, col_ws[9])]
    rows_data.append(total_cells)

    n = len(rows_data)
    item_tbl = Table(rows_data, colWidths=col_ws, repeatRows=1)
    item_tbl.setStyle(TableStyle([
        # header row
        ("BACKGROUND",    (0, 0),     (-1, 0),     NAVY),
        ("FONTSIZE",      (0, 0),     (-1, 0),     8),
        ("TOPPADDING",    (0, 0),     (-1, 0),     5),
        ("BOTTOMPADDING", (0, 0),     (-1, 0),     5),
        # body
        ("FONTSIZE",      (0, 1),     (-1, -1),    8),
        ("TOPPADDING",    (0, 1),     (-1, -1),    4),
        ("BOTTOMPADDING", (0, 1),     (-1, -1),    4),
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
