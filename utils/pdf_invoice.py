"""A4 GST tax invoice PDF generator for MUNIM.
Saves to C:\\MUNIM\\Invoices\\  (creates folder if needed).
Returns the full path of the saved file.
Supports multi-page invoices: the item table splits across pages,
the header row repeats, and each page is numbered.
"""
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as _canvas
from xml.sax.saxutils import escape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer, HRFlowable, KeepTogether)
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
    """Format paise as rupees with Indian comma style (2,00,000.00), no wrapping."""
    rupees = paise / 100
    int_part = int(abs(rupees))
    dec_str = f"{abs(rupees) % 1:.2f}"[1:]   # ".xx"
    sign = "-" if rupees < 0 else ""

    s = str(int_part)
    if len(s) <= 3:
        formatted = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        pairs = []
        while len(rest) > 2:
            pairs.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            pairs.append(rest)
        pairs.reverse()
        formatted = ",".join(pairs) + "," + last3

    return f"{sign}{formatted}{dec_str}"


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

    # ── page numbering canvas ─────────────────────────────────────────────────
    class _NumberedCanvas(_canvas.Canvas):
        """Two-pass canvas so every page can print 'Page X of Y'."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_states = []

        def showPage(self):
            self._saved_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_states)
            for state in self._saved_states:
                self.__dict__.update(state)
                self._stamp(total)
                super().showPage()
            super().save()

        def _stamp(self, total):
            self.setFont("Helvetica", 7.5)
            self.setFillColor(MUTED)
            self.drawRightString(A4[0] - 12 * mm, 7 * mm,
                                 f"Page {self._pageNumber} of {total}")
            left = f"{inv_no}"
            if self._pageNumber < total:
                left += "   •   continued on next page"
            self.drawString(12 * mm, 7 * mm, left)

    # ── page setup ────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=12*mm, rightMargin=12*mm,
        topMargin=10*mm,  bottomMargin=14*mm,   # room for the page-number line
        title=f"Tax Invoice {inv_no}", author=company or "MUNIM",
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

    # ── HEADER ────────────────────────────────────────────────────────────────
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
    row_addr = con.execute("SELECT address FROM parties WHERE name=?", (party,)).fetchone()
    party_addr = row_addr["address"] if row_addr else ""
    buyer_cell  = addr_paras("BUYER",  cust_name, party_gstin, party_addr)

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
    # Clean layout: # | HSN | Description | Qty | Rate/Unit | GST% | Amount
    # Tax amounts removed from items table — shown only in HSN summary below
    IDX  = 16
    HSN  = 46
    QTY  = 28
    PCT  = 36   # GST%
    MON  = 72   # Amount / Rate
    DESC = W - IDX - HSN - QTY - PCT - MON - MON  # Description gets remaining space

    col_ws     = [IDX, HSN, DESC, QTY, MON, PCT, MON]
    hdr_labels = ["#", "HSN", "Description", "Qty", "Rate/Unit", "GST%", "Amount"]
    hdr_aligns = ["CTR", "CTR", "HLFT", "CTR", "HRGT", "HCTR", "HRGT"]

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
        hsn_val = it.get("hsn", "")
        qty     = float(it["qty"])
        rate    = float(it["rate"])
        gst_p   = float(it["gst"])
        tax_p   = round(qty * rate * 100)   # taxable paise

        if interstate:
            igst    = round(tax_p * gst_p / 100)
            total_p = tax_p + igst
        else:
            half    = gst_p / 2
            cgst    = round(tax_p * half / 100)
            total_p = tax_p + cgst * 2

        rows_data.append([
            nw(str(idx),              CTR, col_ws[0]),
            nw(hsn_val,               CTR, col_ws[1]),
            nw(desc,                  NRM, col_ws[2]),
            nw(f"{qty:g}",            CTR, col_ws[3]),
            nw(_fmt(round(rate*100)), RGT, col_ws[4]),
            nw(f"{gst_p:g}%",         CTR, col_ws[5]),
            nw(_fmt(total_p),         RGT, col_ws[6]),
        ])

    # Totals row
    total_cells = [
        nw("", NRM, col_ws[0]),
        nw("", NRM, col_ws[1]),
        nw("Total", BLD, col_ws[2]),
        nw("", NRM, col_ws[3]),
        nw("", NRM, col_ws[4]),
        nw("", NRM, col_ws[5]),
        nw(_fmt(tax["total"]), BRGT, col_ws[6]),
    ]
    rows_data.append(total_cells)

    n = len(rows_data)
    item_tbl = Table(rows_data, colWidths=col_ws, repeatRows=1)

    # Base style. NOSPLIT is applied per row below, never to the whole table,
    # so a long invoice can break across pages while no single row is cut in half.
    item_style = [
        ("BACKGROUND",    (0, 0),     (-1, 0),     NAVY),
        ("FONTSIZE",      (0, 0),     (-1, 0),     8),
        ("TOPPADDING",    (0, 0),     (-1, 0),     5),
        ("BOTTOMPADDING", (0, 0),     (-1, 0),     5),
        ("FONTSIZE",      (0, 1),     (-1, -1),    8),
        ("TOPPADDING",    (0, 1),     (-1, -1),    4),
        ("BOTTOMPADDING", (0, 1),     (-1, -1),    4),
        ("ROWBACKGROUNDS",(0, 1),     (-1, -2),    [WHITE, LIGHT]),
        ("BACKGROUND",    (0, n - 1), (-1, n - 1), LBLUE),
        ("LINEABOVE",     (0, n - 1), (-1, n - 1), 1,   NAVY),
        ("FONTNAME",      (0, n - 1), (-1, n - 1), "Helvetica-Bold"),
        ("LINEBELOW",     (0, 0),     (-1, 0),     0.5, BLUE),
        ("GRID",          (0, 0),     (-1, -1),    0.3, RULE),
        ("VALIGN",        (0, 0),     (-1, -1),    "MIDDLE"),
    ]
    for r in range(n):
        item_style.append(("NOSPLIT", (0, r), (-1, r)))
    item_tbl.setStyle(TableStyle(item_style))

    story.append(item_tbl)
    story.append(Spacer(1, 4*mm))

    # ── HSN SUMMARY TABLE ─────────────────────────────────────────────────────
    hsn_groups = {}
    for it in items:
        key   = it.get("hsn", "") or "—"
        gst_p = float(it["gst"])
        qty   = float(it["qty"])
        rate  = float(it["rate"])
        tax_p = round(qty * rate * 100)
        if key not in hsn_groups:
            hsn_groups[key] = {"taxable": 0, "gst": gst_p, "qty": 0}
        hsn_groups[key]["taxable"] += tax_p
        hsn_groups[key]["qty"]     += qty

    tail = []   # HSN summary + totals + footer, kept together where possible

    if any(it.get("hsn") for it in items):
        HSML = S("HSML", fontSize=7, textColor=WHITE, fontName="Helvetica-Bold", leading=10, alignment=TA_CENTER)
        HNRM = S("HNRM", fontSize=8, textColor=BLACK, fontName="Helvetica",      leading=11, alignment=TA_CENTER)
        HNRT = S("HNRT", fontSize=8, textColor=BLACK, fontName="Helvetica",      leading=11, alignment=TA_RIGHT)
        HNBD = S("HNBD", fontSize=8, textColor=BLACK, fontName="Helvetica-Bold", leading=11, alignment=TA_RIGHT)

        if interstate:
            hw      = [60, 90, 40, 55, 85, 85]
            hsn_hdr = [_p("HSN/SAC", HSML), _p("Taxable Amt", HSML), _p("Qty", HSML),
                       _p("IGST%", HSML), _p("IGST Amt", HSML), _p("Total Tax", HSML)]
        else:
            hw      = [60, 85, 40, 50, 75, 50, 75, 80]
            hsn_hdr = [_p("HSN/SAC", HSML), _p("Taxable Amt", HSML), _p("Qty", HSML),
                       _p("CGST%", HSML), _p("CGST Amt", HSML),
                       _p("SGST%", HSML), _p("SGST Amt", HSML),
                       _p("Total Tax", HSML)]

        hsn_rows = [hsn_hdr]
        for code, grp in hsn_groups.items():
            taxable = grp["taxable"]
            gst_p   = grp["gst"]
            qty_tot = grp["qty"]
            if interstate:
                igst = round(taxable * gst_p / 100)
                hsn_rows.append([
                    _p(code,           HNRM),
                    _p(_fmt(taxable),  HNRT),
                    _p(f"{qty_tot:g}", HNRM),
                    _p(f"{gst_p:g}%",  HNRM),
                    _p(_fmt(igst),     HNRT),
                    _p(_fmt(igst),     HNBD),
                ])
            else:
                half = gst_p / 2
                cgst = round(taxable * half / 100)
                sgst = cgst
                hsn_rows.append([
                    _p(code,              HNRM),
                    _p(_fmt(taxable),     HNRT),
                    _p(f"{qty_tot:g}",    HNRM),
                    _p(f"{half:g}%",      HNRM),
                    _p(_fmt(cgst),        HNRT),
                    _p(f"{half:g}%",      HNRM),
                    _p(_fmt(sgst),        HNRT),
                    _p(_fmt(cgst + sgst), HNBD),
                ])

        hsn_tbl = Table(hsn_rows, colWidths=hw, hAlign="RIGHT", repeatRows=1)
        hsn_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
            ("FONTSIZE",      (0, 0), (-1, 0),  7),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
            ("GRID",          (0, 0), (-1, -1), 0.3, RULE),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LIGHT]),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        tail.append(Spacer(1, 2*mm))
        tail.append(hsn_tbl)
        tail.append(Spacer(1, 3*mm))

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
    tail.append(summ_tbl)
    tail.append(Spacer(1, 8*mm))

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
    tail.append(foot_tbl)

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
    tail.append(Spacer(1, 4*mm))
    tail.append(wave)

    # Keep the closing block on one page when it fits; fall back to a plain
    # flow if it is too tall (very many HSN groups) so nothing is ever lost.
    story.append(KeepTogether(tail))

    doc.build(story, canvasmaker=_NumberedCanvas)
    return filepath
