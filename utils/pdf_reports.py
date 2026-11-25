"""Report PDF generator for MUNIM — Trial Balance, Balance Sheet, Trading & P&L.
Saves PDFs to <data_dir>/Reports/. Returns the saved file path."""
import os
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer)
from db.setup import data_dir
from utils.fmt import inr

# ── colours (same palette as pdf_invoice.py) ─────────────────────────────────
NAVY  = colors.HexColor("#1A2B4A")
LBLUE = colors.HexColor("#DBEAFE")
LIGHT = colors.HexColor("#EEF2FF")
MUTED = colors.HexColor("#6B7280")
WHITE = colors.white
BLACK = colors.black
RULE  = colors.HexColor("#D1D5DB")
GRP   = colors.HexColor("#F1F5F9")   # group header background


def _report_dir():
    d = os.path.join(data_dir(), "Reports")
    os.makedirs(d, exist_ok=True)
    return d


def _safe_name(text):
    """Turn a period/label into something safe for a file name."""
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(text))


def _S(name, **kw):
    return ParagraphStyle(name, **kw)


def _p(text, style):
    return Paragraph(str(text or ""), style)


def _base_styles():
    HDR  = _S("HDR",  fontSize=13, textColor=WHITE,  fontName="Helvetica-Bold", leading=16)
    BLD  = _S("BLD",  fontSize=10, textColor=BLACK,  fontName="Helvetica-Bold", leading=14)
    NRM  = _S("NRM",  fontSize=9,  textColor=BLACK,  fontName="Helvetica",      leading=12)
    SML  = _S("SML",  fontSize=7,  textColor=colors.HexColor("#93C5FD"),
              fontName="Helvetica", leading=9)
    RGT  = _S("RGT",  fontSize=9,  textColor=BLACK,  fontName="Helvetica",
              leading=12, alignment=TA_RIGHT)
    BRGT = _S("BRGT", fontSize=9,  textColor=BLACK,  fontName="Helvetica-Bold",
              leading=13, alignment=TA_RIGHT)
    GRPH = _S("GRPH", fontSize=9,  textColor=NAVY,   fontName="Helvetica-Bold", leading=12)
    GRPR = _S("GRPR", fontSize=9,  textColor=NAVY,   fontName="Helvetica-Bold",
              leading=12, alignment=TA_RIGHT)
    MVAL = _S("MVAL", fontSize=10, textColor=WHITE,  fontName="Helvetica-Bold", leading=14)
    return HDR, BLD, NRM, SML, RGT, BRGT, GRPH, GRPR, MVAL


def _page_header(story, company, title, fy, W, label="Financial Year"):
    """Navy header band. `title` may contain markup; `company` and `fy` are escaped."""
    HDR, BLD, NRM, SML, _, _, _, _, MVAL = _base_styles()
    FY_W = _S("FY_W", fontSize=9, textColor=WHITE, fontName="Helvetica", leading=11)
    hdr = Table(
        [[_p(title, HDR),
          [_p(label, SML), _p(escape(str(company)), MVAL),
           _p(label if False else "", SML),
           _p(escape(str(fy)), FY_W)]]],
        colWidths=[W * 0.55, W * 0.45])
    # Right cell layout: "Company" / name / label / value
    hdr._cellvalues[0][1] = [_p("Company", SML), _p(escape(str(company)), MVAL),
                             _p(label, SML), _p(escape(str(fy)), FY_W)]
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEAFTER",     (0, 0), (0, 0),   0.5, colors.HexColor("#334E7A")),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 4 * mm))


def generate_trial_balance_pdf(company, fy, grouped_rows, td, tc, detailed=False,
                               period=None):
    """
    grouped_rows: output of setup.trial_balance_grouped()
    period: optional "DD-MM-YYYY to DD-MM-YYYY" text shown in the header.
    Returns the saved PDF path.
    """
    tag = _safe_name(period) if period else fy.replace('-', '_')
    fname = (f"Trial_Balance_{tag}_"
             f"{'Detailed' if detailed else 'Summary'}.pdf")
    path = os.path.join(_report_dir(), fname)

    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    W = A4[0] - 28*mm
    HDR, BLD, NRM, SML, RGT, BRGT, GRPH, GRPR, MVAL = _base_styles()

    story = []
    _page_header(story, company,
                 f"TRIAL BALANCE — {'DETAILED' if detailed else 'SUMMARY'}",
                 period or fy, W,
                 label="Period" if period else "Financial Year")

    PW = W - 150 - 150
    col_ws = [PW, 150, 150]

    HH  = _S("HH",  fontSize=9, textColor=WHITE, fontName="Helvetica-Bold", leading=12)
    HR  = _S("HR",  fontSize=9, textColor=WHITE, fontName="Helvetica-Bold",
             leading=12, alignment=TA_RIGHT)

    table_data = [[_p("Particulars", HH), _p("Debit (Rs)", HR), _p("Credit (Rs)", HR)]]
    row_styles = []

    for i, row in enumerate(grouped_rows):
        ri     = i + 1   # +1 for header row
        kind   = row["kind"]
        dr_txt = inr(row["dr"]) if row["dr"] else ""
        cr_txt = inr(row["cr"]) if row["cr"] else ""
        name   = escape(str(row["name"]))

        if kind == "group":
            table_data.append([_p(name, GRPH),
                                _p(dr_txt, GRPR), _p(cr_txt, GRPR)])
            row_styles += [
                ("BACKGROUND",    (0, ri), (-1, ri), GRP),
                ("TOPPADDING",    (0, ri), (-1, ri), 5),
                ("BOTTOMPADDING", (0, ri), (-1, ri), 5),
            ]
        elif kind == "total":
            # Grouped trial-balance row values are rupees; scalar td/tc
            # returned by the engine remain paise for API compatibility.
            table_data.append([_p("Grand Total", BLD),
                                _p(dr_txt, BRGT),
                                _p(cr_txt, BRGT)])
            row_styles += [
                ("BACKGROUND",    (0, ri), (-1, ri), LBLUE),
                ("LINEABOVE",     (0, ri), (-1, ri), 1.2, NAVY),
                ("LINEBELOW",     (0, ri), (-1, ri), 1.2, NAVY),
                ("TOPPADDING",    (0, ri), (-1, ri), 5),
                ("BOTTOMPADDING", (0, ri), (-1, ri), 5),
            ]
        else:
            table_data.append([_p(name, NRM),
                                _p(dr_txt, RGT), _p(cr_txt, RGT)])
            row_styles += [
                ("TOPPADDING",    (0, ri), (-1, ri), 3),
                ("BOTTOMPADDING", (0, ri), (-1, ri), 3),
            ]

    n = len(table_data)
    base_style = [
        ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
        ("TOPPADDING",    (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("GRID",          (0, 0), (-1, -1), 0.3, RULE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]
    if n > 2:
        base_style.append(("ROWBACKGROUNDS", (0, 1), (-1, n-2), [WHITE, LIGHT]))
    tbl = Table(table_data, colWidths=col_ws, repeatRows=1)
    tbl.setStyle(TableStyle(base_style + row_styles))
    story.append(tbl)

    doc.build(story)
    return path


def generate_balance_sheet_pdf(company, fy, bs):
    """
    bs: dict from reports.balance_sheet_grouped() —
        keys: liabilities (list of {head, accounts, total}),
              assets (list of {head, accounts, total}),
              total_liabilities, total_assets
    Returns the saved PDF path.
    """
    fname = f"Balance_Sheet_{fy.replace('-', '_')}.pdf"
    path  = os.path.join(_report_dir(), fname)

    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    W = A4[0] - 28*mm
    HDR, BLD, NRM, SML, RGT, BRGT, GRPH, GRPR, MVAL = _base_styles()

    story = []
    _page_header(story, company, "BALANCE SHEET", fy, W)

    half = (W - 6*mm) / 2

    HEAD_NRM = _S("HEAD_NRM", fontSize=9, textColor=NAVY,
                  fontName="Helvetica-Bold", leading=12)
    HEAD_RGT = _S("HEAD_RGT", fontSize=9, textColor=NAVY,
                  fontName="Helvetica-Bold", leading=12, alignment=TA_RIGHT)
    ACCT_NRM = _S("ACCT_NRM", fontSize=8, textColor=BLACK,
                  fontName="Helvetica", leading=11)
    ACCT_RGT = _S("ACCT_RGT", fontSize=8, textColor=BLACK,
                  fontName="Helvetica", leading=11, alignment=TA_RIGHT)

    def _side_table(title_txt, sections, total):
        HH = _S(f"HH_{title_txt}", fontSize=9, textColor=WHITE,
                fontName="Helvetica-Bold", leading=12)
        HR = _S(f"HR_{title_txt}", fontSize=9, textColor=WHITE,
                fontName="Helvetica-Bold", leading=12, alignment=TA_RIGHT)
        col_ws = [half - 100, 100]
        data   = [[_p(title_txt, HH), _p("Amount (Rs)", HR)]]
        s      = []
        ri     = 1

        for sec in sections:
            # Head row
            data.append([_p(escape(str(sec["head"])), HEAD_NRM),
                         _p(inr(sec["total"]), HEAD_RGT)])
            s += [("BACKGROUND",    (0, ri), (-1, ri), GRP),
                  ("TOPPADDING",    (0, ri), (-1, ri), 4),
                  ("BOTTOMPADDING", (0, ri), (-1, ri), 4)]
            ri += 1
            # Account rows
            for name, amt in sec["accounts"]:
                data.append([_p(f"  {escape(str(name))}", ACCT_NRM),
                             _p(inr(amt), ACCT_RGT)])
                s += [("TOPPADDING",    (0, ri), (-1, ri), 2),
                      ("BOTTOMPADDING", (0, ri), (-1, ri), 2),
                      ("LEFTPADDING",   (0, ri), (0, ri), 16)]
                ri += 1

        # Total row
        data.append([_p("Total", BLD), _p(inr(total), BRGT)])
        s += [("BACKGROUND",    (0, ri), (-1, ri), LBLUE),
              ("LINEABOVE",     (0, ri), (-1, ri), 1.2, NAVY),
              ("LINEBELOW",     (0, ri), (-1, ri), 1.2, NAVY),
              ("TOPPADDING",    (0, ri), (-1, ri), 5),
              ("BOTTOMPADDING", (0, ri), (-1, ri), 5)]

        t = Table(data, colWidths=col_ws, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
            ("TOPPADDING",    (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("GRID",          (0, 0), (-1, -1), 0.3, RULE),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ] + s))
        return t

    liab_tbl  = _side_table("Liabilities", bs["liabilities"],  bs["total_liabilities"])
    asset_tbl = _side_table("Assets",      bs["assets"],       bs["total_assets"])

    outer = Table([[liab_tbl, asset_tbl]], colWidths=[half, half], hAlign="LEFT")
    outer.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("COLPADDING",   (0, 0), (-1, -1), 3),
    ]))
    story.append(outer)
    story.append(Spacer(1, 4*mm))

    FOOT = _S("FOOT", fontSize=8, textColor=MUTED,
              fontName="Helvetica-Oblique", leading=11)
    story.append(_p(
        f"Total: Rs {inr(bs['total_assets'])}  |  Generated by MUNIM  |  "
        f"{escape(str(company))}  |  FY {fy}",
        FOOT))

    doc.build(story)
    return path


def generate_pl_pdf(company, period, ta):
    """
    ta: dict from reports.trading_and_pl() —
        trading: {left, left_total, right, right_total, gross_profit}
        pl:      {left, left_total, right, right_total, net_profit}
        gross_pct, net_pct
    Rows in left/right are (name, amount in rupees).
    Returns the saved PDF path.
    """
    fname = f"Trading_PL_{_safe_name(period)}.pdf"
    path  = os.path.join(_report_dir(), fname)

    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    W = A4[0] - 28*mm
    HDR, BLD, NRM, SML, RGT, BRGT, GRPH, GRPR, MVAL = _base_styles()

    story = []
    _page_header(story, company, "TRADING AND PROFIT &amp; LOSS ACCOUNT",
                 period, W, label="Period")

    HH  = _S("PL_HH", fontSize=9, textColor=WHITE, fontName="Helvetica-Bold", leading=12)
    HR  = _S("PL_HR", fontSize=9, textColor=WHITE, fontName="Helvetica-Bold",
             leading=12, alignment=TA_RIGHT)
    SEC = _S("PL_SEC", fontSize=11, textColor=NAVY, fontName="Helvetica-Bold",
             leading=14, spaceBefore=4, spaceAfter=4)

    amt_w  = 30 * mm
    part_w = (W - 2 * amt_w) / 2

    def _two_side(left, ltotal, right, rtotal):
        n = max(len(left), len(right))
        lrows = list(left) + [("", None)] * (n - len(left))
        rrows = list(right) + [("", None)] * (n - len(right))
        data = [[_p("Particulars (Dr)", HH), _p("Amount (Rs)", HR),
                 _p("Particulars (Cr)", HH), _p("Amount (Rs)", HR)]]
        for (ln, la), (rn, ra) in zip(lrows, rrows):
            data.append([_p(escape(str(ln)), NRM),
                         _p(inr(la) if la is not None else "", RGT),
                         _p(escape(str(rn)), NRM),
                         _p(inr(ra) if ra is not None else "", RGT)])
        data.append([_p("Total", BLD), _p(inr(ltotal), BRGT),
                     _p("Total", BLD), _p(inr(rtotal), BRGT)])
        last = len(data) - 1
        style = [
            ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
            ("TOPPADDING",    (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("GRID",          (0, 0), (-1, -1), 0.3, RULE),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBEFORE",    (2, 0), (2, -1), 1.0, NAVY),
            ("BACKGROUND",    (0, last), (-1, last), LBLUE),
            ("LINEABOVE",     (0, last), (-1, last), 1.2, NAVY),
            ("LINEBELOW",     (0, last), (-1, last), 1.2, NAVY),
            ("TOPPADDING",    (0, last), (-1, last), 5),
            ("BOTTOMPADDING", (0, last), (-1, last), 5),
        ]
        if last > 1:
            style.append(("ROWBACKGROUNDS", (0, 1), (-1, last - 1), [WHITE, LIGHT]))
        t = Table(data, colWidths=[part_w, amt_w, part_w, amt_w], repeatRows=1)
        t.setStyle(TableStyle(style))
        return t

    t, p = ta["trading"], ta["pl"]
    story.append(_p("Trading Account", SEC))
    story.append(_two_side(t["left"], t["left_total"], t["right"], t["right_total"]))
    story.append(Spacer(1, 5 * mm))
    story.append(_p("Profit &amp; Loss Account", SEC))
    story.append(_two_side(p["left"], p["left_total"], p["right"], p["right_total"]))
    story.append(Spacer(1, 5 * mm))

    gp, npf = t["gross_profit"], p["net_profit"]
    gp_pct, np_pct = ta.get("gross_pct", 0.0), ta.get("net_pct", 0.0)
    story.append(_p(
        f"<b>Gross {'Profit' if gp >= 0 else 'Loss'}:</b> Rs {inr(abs(gp))} "
        f"({abs(gp_pct):.1f}%) &nbsp;&nbsp;&nbsp;&nbsp; "
        f"<b>Net {'Profit' if npf >= 0 else 'Loss'}:</b> Rs {inr(abs(npf))} "
        f"({abs(np_pct):.1f}%)", NRM))
    story.append(Spacer(1, 4 * mm))

    FOOT = _S("PL_FOOT", fontSize=8, textColor=MUTED,
              fontName="Helvetica-Oblique", leading=11)
    story.append(_p(
        f"Generated by MUNIM  |  {escape(str(company))}  |  Period {escape(str(period))}",
        FOOT))

    doc.build(story)
    return path
