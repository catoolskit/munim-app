"""MUNIM Dashboard — business snapshot with charts.
Shows monthly sales vs purchases, GST payable trend,
top 5 customers by revenue, and stock value summary.
"""
import customtkinter as ctk
from datetime import date
from db import setup as s, reports as r
from ui import theme as T
from utils.fmt import inr
from utils import settings


def _month_label(fy, month_num):
    names = ["Apr","May","Jun","Jul","Aug","Sep",
             "Oct","Nov","Dec","Jan","Feb","Mar"]
    return names[month_num - 1]


def _bar(parent, value, max_val, color, height=18, width=220):
    bg = ctk.CTkFrame(parent, fg_color="#E8EDF5", corner_radius=4,
                      height=height, width=width)
    if max_val > 0:
        fill_w = max(4, int(width * value / max_val))
        fill = ctk.CTkFrame(bg, fg_color=color, corner_radius=4,
                            height=height, width=fill_w)
        fill.place(x=0, y=0)
    return bg


class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master, con, shell=None):
        super().__init__(master, fg_color="transparent")
        self.con = con
        self.shell = shell

        # Redesigned dashboard header: clear reporting scope, quick actions,
        # and a more task-oriented dashboard rather than a passive chart page.
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(18, 8))
        titlebox = ctk.CTkFrame(header, fg_color="transparent")
        titlebox.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(titlebox, text="Business Dashboard", font=T.f(25, "bold"),
                     text_color=T.TEXT).pack(anchor="w")
        ctk.CTkLabel(titlebox,
                     text="Financial snapshot · sales, purchases, receivables and stock",
                     font=T.f(12), text_color=T.MUTED).pack(anchor="w", pady=(3, 0))
        ctk.CTkLabel(header, text="MANAGEMENT OVERVIEW", font=T.f(10, "bold"),
                     text_color=T.ACCENT, fg_color="#EAF0FC",
                     corner_radius=8, padx=12, pady=8).pack(side="right", padx=(12, 0))

        fy_opts = s.fy_choices(con)
        self.fy = s.fy_of(date.today())

        head = ctk.CTkFrame(self, fg_color="#FFFFFF", corner_radius=12,
                            border_width=1, border_color=T.BORDER)
        head.pack(fill="x", padx=28, pady=(0, 10))
        ctk.CTkLabel(head, text="REPORTING PERIOD", font=T.f(10, "bold"),
                     text_color=T.MUTED).pack(side="left", padx=16, pady=10)
        ctk.CTkLabel(head, text="Financial year:", font=T.f(12),
                     text_color=T.MUTED).pack(side="right", padx=(0, 8), pady=8)
        fy_menu = T.option_menu(head, fy_opts, width=120,
                                command=lambda v: self._on_fy(v))
        fy_menu.set(self.fy)
        fy_menu.pack(side="right", padx=(0, 14), pady=8)

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self._build()

    def _on_fy(self, fy):
        self.fy = fy
        for w in self.body.winfo_children():
            w.destroy()
        self._build()

    def _build(self):
        con, fy = self.con, self.fy

        # ── Quick actions ─────────────────────────────────────────────────────
        quick = T.card(self.body, border_color=T.BORDER)
        quick.pack(fill="x", padx=8, pady=(0, 12))
        qhead = ctk.CTkFrame(quick, fg_color="transparent")
        qhead.pack(fill="x", padx=16, pady=(10, 6))
        ctk.CTkLabel(qhead, text="QUICK ACTIONS", font=T.f(10, "bold"),
                     text_color=T.MUTED).pack(side="left")
        ctk.CTkLabel(qhead, text="Create, review or navigate without returning to Gateway",
                     font=T.f(10), text_color=T.MUTED).pack(side="right")
        qrow = ctk.CTkFrame(quick, fg_color="transparent")
        qrow.pack(fill="x", padx=12, pady=(0, 12))
        company_configured = bool(
            (settings.load_settings().get("company_name") or "").strip()
        )
        third_action = (("▤  Ledger View", "ledger") if company_configured
                        else ("▦  Company Details", "company"))
        actions = [("＋  Sales Invoice", "sales"), ("＋  Purchase Bill", "purchase"),
                   third_action, ("▦  Day Book", "daybook")]
        for label, target in actions:
            if self.shell is not None:
                command = lambda target=target: self.shell.push(("page", target))
            else:
                command = lambda: None
            T.button(qrow, label, command, height=34, fg_color="#EAF0FC",
                     text_color=T.TEXT, hover_color="#DCE6F8",
                     font=T.f(11, "bold")).pack(side="left", fill="x", expand=True, padx=4)

        # ── KPI cards ─────────────────────────────────────────────────────────
        kpi_row = ctk.CTkFrame(self.body, fg_color="transparent")
        kpi_row.pack(fill="x", padx=8, pady=(0, 12))
        for i in range(4):
            kpi_row.grid_columnconfigure(i, weight=1, uniform="kpi")

        try:
            receivable, payable = r.receivable_payable(con)
        except Exception:
            receivable = payable = 0.0

        try:
            sales_reg  = r.invoice_register(con, fy, "Sales")
            total_sales = sum(x["total"] for x in sales_reg)
        except Exception:
            total_sales = 0.0

        try:
            pur_reg   = r.invoice_register(con, fy, "Purchase")
            total_pur = sum(x["total"] for x in pur_reg)
        except Exception:
            total_pur = 0.0

        kpis = [
            ("Total Sales",        inr(total_sales), T.OK),
            ("Total Purchases",    inr(total_pur),   "#B26A00"),
            ("Customers owe you",  inr(receivable),  T.OK if receivable else T.TEXT),
            ("You owe suppliers",  inr(payable),     T.DANGER if payable else T.TEXT),
        ]
        for i, (label, value, color) in enumerate(kpis):
            card = T.card(kpi_row, border_color="#D9E3F4")
            card.grid(row=0, column=i, padx=6, pady=4, sticky="nsew")
            ctk.CTkFrame(card, fg_color=color, height=4, corner_radius=2).pack(fill="x", padx=12, pady=(10, 8))
            ctk.CTkLabel(card, text=label.upper(), font=T.f(10, "bold"),
                         text_color=T.MUTED).pack(anchor="w", padx=16, pady=(0, 4))
            ctk.CTkLabel(card, text=f"₹ {value}", font=T.f(18, "bold"),
                         text_color=color).pack(anchor="w", padx=16, pady=(0, 14))

        # ── Monthly sales vs purchases ─────────────────────────────────────────
        chart_card = T.card(self.body)
        chart_card.pack(fill="x", padx=8, pady=(0, 12))
        ctk.CTkLabel(chart_card, text="Sales & Purchase Trend",
                     font=T.f(16, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=20, pady=(16, 3))
        ctk.CTkLabel(chart_card, text="Month-by-month comparison for the selected financial year",
                     font=T.f(11), text_color=T.MUTED).pack(anchor="w", padx=20, pady=(0, 10))

        monthly = self._monthly_data(fy)
        max_val  = max((max(sv, pv) for sv, pv in monthly.values()), default=1) or 1

        chart_body = ctk.CTkFrame(chart_card, fg_color="transparent")
        chart_body.pack(fill="x", padx=20, pady=(0, 16))

        for m_num in range(1, 13):
            label = _month_label(fy, m_num)
            sv, pv = monthly.get(m_num, (0.0, 0.0))
            if sv == 0 and pv == 0:
                continue
            row = ctk.CTkFrame(chart_body, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, font=T.f(11), text_color=T.MUTED,
                         width=36, anchor="e").pack(side="left", padx=(0, 8))
            col = ctk.CTkFrame(row, fg_color="transparent")
            col.pack(side="left", fill="x", expand=True)
            sf = ctk.CTkFrame(col, fg_color="transparent")
            sf.pack(fill="x", pady=1)
            _bar(sf, sv, max_val, T.OK, height=14, width=300).pack(side="left")
            ctk.CTkLabel(sf, text=f"  S  {inr(sv)}", font=T.f(10),
                         text_color=T.OK).pack(side="left")
            pf = ctk.CTkFrame(col, fg_color="transparent")
            pf.pack(fill="x", pady=1)
            _bar(pf, pv, max_val, "#B26A00", height=14, width=300).pack(side="left")
            ctk.CTkLabel(pf, text=f"  P  {inr(pv)}", font=T.f(10),
                         text_color="#B26A00").pack(side="left")

        # ── Top customers + GST payable ────────────────────────────────────────
        row3 = ctk.CTkFrame(self.body, fg_color="transparent")
        row3.pack(fill="x", padx=8, pady=(0, 12))
        row3.grid_columnconfigure(0, weight=1, uniform="r3")
        row3.grid_columnconfigure(1, weight=1, uniform="r3")

        cust_card = T.card(row3)
        cust_card.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        ctk.CTkLabel(cust_card, text="Top 5 Customers by Revenue",
                     font=T.f(15, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=20, pady=(16, 10))

        top_customers = self._top_customers(fy)
        max_cust = top_customers[0][1] if top_customers else 1

        for name, total in top_customers:
            crow = ctk.CTkFrame(cust_card, fg_color="transparent")
            crow.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(crow, text=name, font=T.f(12), text_color=T.TEXT,
                         width=140, anchor="w").pack(side="left")
            _bar(crow, total, max_cust, T.ACCENT, height=16, width=140).pack(
                side="left", padx=8)
            ctk.CTkLabel(crow, text=inr(total), font=T.f(11, "bold"),
                         text_color=T.TEXT).pack(side="left")
        if not top_customers:
            ctk.CTkLabel(cust_card, text="No sales data yet.",
                         font=T.f(12), text_color=T.MUTED).pack(
                anchor="w", padx=20, pady=(0, 16))
        ctk.CTkFrame(cust_card, fg_color=T.CARD, height=12).pack()

        gst_card = T.card(row3)
        gst_card.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
        ctk.CTkLabel(gst_card, text="Monthly GST Payable",
                     font=T.f(15, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=20, pady=(16, 10))

        gst_data = self._gst_trend(fy)
        max_gst  = max((v for v in gst_data.values()), default=1) or 1

        for m_num in range(1, 13):
            label = _month_label(fy, m_num)
            gv = gst_data.get(m_num, 0.0)
            if gv == 0:
                continue
            grow = ctk.CTkFrame(gst_card, fg_color="transparent")
            grow.pack(fill="x", padx=20, pady=3)
            ctk.CTkLabel(grow, text=label, font=T.f(11), text_color=T.MUTED,
                         width=36, anchor="e").pack(side="left", padx=(0, 8))
            _bar(grow, gv, max_gst, T.DANGER, height=16, width=160).pack(side="left")
            ctk.CTkLabel(grow, text=f"  {inr(gv)}", font=T.f(10),
                         text_color=T.DANGER).pack(side="left")
        if not any(gst_data.values()):
            ctk.CTkLabel(gst_card, text="No GST data yet.",
                         font=T.f(12), text_color=T.MUTED).pack(
                anchor="w", padx=20, pady=(0, 16))
        ctk.CTkFrame(gst_card, fg_color=T.CARD, height=12).pack()

        # ── Stock value summary ────────────────────────────────────────────────
        stk_card = T.card(self.body)
        stk_card.pack(fill="x", padx=8, pady=(0, 16))
        ctk.CTkLabel(stk_card, text="Stock Value Summary",
                     font=T.f(15, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=20, pady=(16, 10))

        try:
            stock = s.stock_summary(con, fy)
        except Exception:
            stock = []

        if stock:
            hdr = ctk.CTkFrame(stk_card, fg_color="#E8EDF5",
                               corner_radius=0, height=28)
            hdr.pack(fill="x", padx=20)
            hdr.pack_propagate(False)
            for txt, w in [("Item", 180), ("Closing Qty", 110),
                           ("Avg Rate (Rs)", 140), ("Stock Value (Rs)", 160)]:
                ctk.CTkLabel(hdr, text=txt, font=T.f(11, "bold"),
                             text_color=T.MUTED, width=w, anchor="w").pack(
                    side="left", padx=(12, 4))
            total_val = 0.0
            for it in stock:
                srow = ctk.CTkFrame(stk_card, fg_color="transparent")
                srow.pack(fill="x", padx=20, pady=2)
                sv = it.get("stock_value", 0.0)
                total_val += sv
                closing_str = f"{it['closing']:,.3f}".rstrip("0").rstrip(".")
                for txt, w in [
                    (it["name"],                    180),
                    (closing_str,                   110),
                    (inr(it.get("avg_rate", 0.0)),  140),
                    (inr(sv),                       160),
                ]:
                    ctk.CTkLabel(srow, text=txt, font=T.f(12),
                                 text_color=T.TEXT, width=w, anchor="w").pack(
                        side="left", padx=(12, 4))
            trow = ctk.CTkFrame(stk_card, fg_color="#EEF2FF",
                                corner_radius=0, height=30)
            trow.pack(fill="x", padx=20, pady=(4, 0))
            trow.pack_propagate(False)
            ctk.CTkLabel(trow, text="Total stock value",
                         font=T.f(12, "bold"), text_color=T.TEXT,
                         width=430, anchor="w").pack(side="left", padx=(12, 4))
            ctk.CTkLabel(trow, text=f"Rs {inr(total_val)}",
                         font=T.f(13, "bold"),
                         text_color=T.ACCENT).pack(side="left", padx=(12, 4))
        else:
            ctk.CTkLabel(stk_card, text="No stock items set up yet.",
                         font=T.f(12), text_color=T.MUTED).pack(
                anchor="w", padx=20, pady=(0, 16))
        ctk.CTkFrame(stk_card, fg_color=T.CARD, height=12).pack()

    # ── data helpers ──────────────────────────────────────────────────────────

    def _monthly_data(self, fy):
        from db.setup import _month_range
        result = {}
        for m in range(1, 13):
            start, end = _month_range(fy, m)
            try:
                sv = self.con.execute(
                    """SELECT COALESCE(SUM(inv.total), 0)
                       FROM invoices inv JOIN vouchers v ON v.id=inv.voucher_id
                       WHERE inv.kind='Sales' AND v.vtype='Sales'
                       AND v.vdate BETWEEN ? AND ?""",
                    (start, end)).fetchone()[0]
                pv = self.con.execute(
                    """SELECT COALESCE(SUM(inv.total), 0)
                       FROM invoices inv JOIN vouchers v ON v.id=inv.voucher_id
                       WHERE inv.kind='Purchase' AND v.vtype='Purchase'
                       AND v.vdate BETWEEN ? AND ?""",
                    (start, end)).fetchone()[0]
                result[m] = (s.to_rupees(sv), s.to_rupees(pv))
            except Exception:
                result[m] = (0.0, 0.0)
        return result

    def _top_customers(self, fy):
        from db.setup import fy_range
        start, end = fy_range(fy)
        try:
            rows = self.con.execute(
                """SELECT inv.party,
                          SUM(CASE WHEN v.vtype='Sales' THEN inv.total
                                   ELSE -inv.total END) AS net
                   FROM invoices inv JOIN vouchers v ON v.id=inv.voucher_id
                   WHERE inv.kind='Sales'
                     AND v.vtype IN ('Sales','Sales Return')
                     AND v.vdate BETWEEN ? AND ?
                   GROUP BY inv.party
                   ORDER BY net DESC LIMIT 5""",
                (start, end)).fetchall()
            return [(r["party"], s.to_rupees(r["net"]))
                    for r in rows if r["net"] > 0]
        except Exception:
            return []

    def _gst_trend(self, fy):
        from db.setup import gstr3b_report
        result = {}
        for m in range(1, 13):
            try:
                rep = gstr3b_report(self.con, fy, m)
                result[m] = rep["net"]["total"]
            except Exception:
                result[m] = 0.0
        return result
