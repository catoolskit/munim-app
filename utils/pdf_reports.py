"""Report PDF generator for MUNIM — Trial Balance, Balance Sheet.
Saves PDFs to <data_dir>/Reports/. Returns the saved file path."""
import os
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


def _page_header(story, company, title, fy, W):
    HDR, BLD, NRM, SML, _, _, _, _, MVAL = _base_styles()
    FY_W = _S("FY_W", fontSize=9, textColor=WHITE, fontName="Helvetica", leading=11)
    hdr = Table(
        [[_p(title, HDR),
          [_p("Company", SML), _p(company, MVAL),
           _p("Financial Year", SML), _p(fy, FY_W)]]],
        colWidths=[W * 0.55, W * 0.45])
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


def generate_trial_balance_pdf(company, fy, grouped_rows, td, tc, detailed=False):
    """
    grouped_rows: output of setup.trial_balance_grouped()
    Returns the saved PDF path.
    """
    fname = (f"Trial_Balance_{fy.replace('-', '_')}_"
             f"{'Detailed' if detailed else 'Summary'}.pdf")
    path = os.path.join(_report_dir(), fname)

    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    W = A4[0] - 28*mm
    HDR, BLD, NRM, SML, RGT, BRGT, GRPH, GRPR, MVAL = _base_styles()

    story = []
    _page_header(story, company,
                 f"TRIAL BALANCE — {'DETAILED' if detailed else 'SUMMARY'}", fy, W)

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

        if kind == "group":
            table_data.append([_p(row["name"], GRPH),
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
            table_data.append([_p(row["name"], NRM),
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
        ("ROWBACKGROUNDS",(0, 1), (-1, n-2), [WHITE, LIGHT]),
    ]
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
            data.append([_p(sec["head"], HEAD_NRM), _p(inr(sec["total"]), HEAD_RGT)])
            s += [("BACKGROUND",    (0, ri), (-1, ri), GRP),
                  ("TOPPADDING",    (0, ri), (-1, ri), 4),
                  ("BOTTOMPADDING", (0, ri), (-1, ri), 4)]
            ri += 1
            # Account rows
            for name, amt in sec["accounts"]:
                data.append([_p(f"  {name}", ACCT_NRM), _p(inr(amt), ACCT_RGT)])
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

        n = len(data)
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
        f"Total: Rs {inr(bs['total_assets'])}  |  Generated by MUNIM  |  {company}  |  FY {fy}",
        FOOT))

    doc.build(story)
    return path