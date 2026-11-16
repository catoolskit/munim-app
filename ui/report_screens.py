import os
from datetime import date
from tkinter import filedialog, messagebox
import customtkinter as ctk
from db import setup as s, reports as r
from ui import theme as T
from ui.widgets import DataTable
from utils import settings
from utils.export import write_table
from utils.fmt import inr, parse_amount, parse_date, disp_date, today_str

L, R = "w", "e"


def _amt(v):
    return inr(v) if v else ""


class ReportBase(ctk.CTkFrame):
    title_text, sub_text, with_fy = "", "", True

    def __init__(self, master, con):
        super().__init__(master, fg_color="transparent")
        self.con = con
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=28, pady=(24, 12))
        T.title(head, self.title_text, self.sub_text).pack(side="left")
        self.bar = ctk.CTkFrame(head, fg_color="transparent", width=1, height=1)
        self.bar.pack(side="right")
        if self.with_fy:
            self.fy = T.option_menu(self.bar, s.fy_choices(con), width=120,
                                    command=lambda _v: self.refresh())
            self.fy.set(s.fy_of(date.today()))
            self.fy.pack(side="right", padx=(10, 0))
        if hasattr(self, "export_data") and not getattr(self, "own_controls", False):
            T.button(self.bar, "Export Excel", self.export, width=120, fg_color="#E7ECF5",
                     text_color=T.TEXT, hover_color="#DCE3F0").pack(side="right", padx=(10, 0))

    def export(self):
        """Save the report on screen as an Excel file the user picks."""
        try:
            title, headers, rows = self.export_data()
            path = filedialog.asksaveasfilename(
                title="Save report as", defaultextension=".xlsx", filetypes=[("Excel file", "*.xlsx")],
                initialfile=f"{title.replace(' ', '_')}.xlsx")
            if not path:
                return
            path = write_table(path, title, headers, rows)
        except Exception as e:
            messagebox.showerror("MUNIM", f"Could not save the report:\n{e}")
            return
        messagebox.showinfo("MUNIM", f"Report saved:\n{path}")


class TrialBalanceFrame(ReportBase):
    title_text, sub_text = "Trial Balance", "Closing balances of every ledger account."

    def __init__(self, master, con):
        super().__init__(master, con)
        self.table = DataTable(self, [("p", "Particulars", 420, L), ("d", "Debit (Rs)", 160, R),
                                      ("c", "Credit (Rs)", 160, R)], height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def export_data(self):
        rows, td, tc = s.trial_balance(self.con, self.fy.get())
        return (f"Trial Balance {self.fy.get()}", ["Particulars", "Debit (Rs)", "Credit (Rs)"],
                [[n, d, c] for n, d, c in rows] + [["Total", td, tc]])

    def refresh(self):
        rows, td, tc = s.trial_balance(self.con, self.fy.get())
        out = [(n, _amt(d), _amt(c)) for n, d, c in rows]
        out.append((("Total", inr(td), inr(tc)), "total"))
        self.table.set_rows(out)


class LedgerFrame(ReportBase):
    def __init__(self, master, con, accounts=None, title="Ledger View",
                 sub="Every entry in one account, with a running balance."):
        self.title_text, self.sub_text = title, sub
        super().__init__(master, con)
        names = accounts or [x["name"] for x in con.execute(
            "SELECT name FROM accounts ORDER BY name COLLATE NOCASE")]
        if accounts:
            self.acct = T.option_menu(self.bar, names, width=160, command=lambda _v: self.refresh())
        else:
            self.acct = T.combo(self.bar, names, width=260, command=lambda _v: self.refresh())
        self.acct.set("Cash" if "Cash" in names else names[0])
        self.acct.pack(side="right", padx=(10, 0))
        if not accounts:
            T.button(self.bar, "Show", self.refresh, width=70).pack(side="right", padx=(10, 0))
        self.summary = ctk.CTkLabel(self, text="", font=T.f(13, "bold"), text_color=T.TEXT)
        self.summary.pack(anchor="w", padx=28, pady=(0, 8))
        self.table = DataTable(self, [("dt", "Date", 100, L), ("v", "Voucher", 120, L),
                                      ("n", "Narration", 300, L), ("d", "Debit (Rs)", 130, R),
                                      ("c", "Credit (Rs)", 130, R), ("b", "Balance", 150, R)], height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def refresh(self):
        try:
            led = r.ledger_view(self.con, self.acct.get().strip(), self.fy.get())
        except ValueError as e:
            self.summary.configure(text=str(e), text_color=T.DANGER)
            self.table.set_rows([])
            return
        rows = [(("", "", "Opening balance", "", "", f"{inr(led['opening'])} {led['opening_side']}"), "head")]
        for x in led["rows"]:
            rows.append((disp_date(x["date"]), f"{x['vtype']} #{x['vno']}", x["narration"],
                         _amt(x["dr"]), _amt(x["cr"]), f"{inr(x['balance'])} {x['side']}"))
        rows.append((("", "", "Total", inr(led["total_dr"]), inr(led["total_cr"]),
                      f"{inr(led['closing'])} {led['closing_side']}"), "total"))
        self.table.set_rows(rows)
        self.summary.configure(
            text=f"{led['account']}   |   Closing balance: Rs {inr(led['closing'])} {led['closing_side']}",
            text_color=T.TEXT)


class DayBookFrame(ReportBase):
    title_text, with_fy = "Day Book", False
    sub_text = "All vouchers between two dates. Double-click a voucher to open, edit or delete it."

    def __init__(self, master, con, opener=None):
        super().__init__(master, con)
        self.opener = opener
        today = date.today()
        self.d1 = T.entry(self.bar, width=120)
        self.d1.insert(0, today.replace(day=1).strftime("%d-%m-%Y"))
        self.d2 = T.entry(self.bar, width=120)
        self.d2.insert(0, today.strftime("%d-%m-%Y"))
        T.button(self.bar, "Show", self.refresh, width=70).pack(side="right")
        self.d2.pack(side="right", padx=6)
        ctk.CTkLabel(self.bar, text="to", text_color=T.MUTED).pack(side="right")
        self.d1.pack(side="right", padx=6)
        self.msg = ctk.CTkLabel(self, text="", font=T.f(13), text_color=T.DANGER)
        self.msg.pack(anchor="w", padx=28)
        self.table = DataTable(self, [("dt", "Date", 100, L), ("v", "Voucher", 130, L),
                                      ("p", "Particulars", 380, L), ("d", "Debit (Rs)", 130, R),
                                      ("c", "Credit (Rs)", 130, R)], height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(4, 24))
        if opener:
            self.table.on_open(lambda vid: self.opener(vid, self.refresh))
        self.refresh()

    def refresh(self):
        try:
            book = r.day_book(self.con, parse_date(self.d1.get()), parse_date(self.d2.get()))
        except ValueError as e:
            self.msg.configure(text=str(e))
            return
        self.msg.configure(text="")
        rows = []
        for v in book:
            rows.append(((disp_date(v["date"]), f"{v['vtype']} #{v['vno']}", v["narration"], "", ""), "head", v["id"]))
            for name, dr, cr in v["lines"]:
                rows.append(("", "", "      " + name, _amt(dr), _amt(cr)))
        self.table.set_rows(rows)


class TwoSideReport(ReportBase):
    """Left and right tables that total to the same figure (Tally T-format)."""
    has_stock_entry = True

    def __init__(self, master, con):
        super().__init__(master, con)
        self.stock = T.entry(self.bar, "Closing stock (Rs)", width=160)
        self.stock.bind("<KeyRelease>", lambda _e: self.refresh())
        self.stock.pack(side="right", padx=(10, 0))
        self.footer = ctk.CTkLabel(self, text="", font=T.f(15, "bold"))
        self.footer.pack(side="bottom", anchor="w", padx=28, pady=(8, 16))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28)
        body.grid_columnconfigure((0, 1), weight=1, uniform="s")
        body.grid_rowconfigure(1, weight=1)
        cols = [("p", "Particulars", 260, L), ("a", "Amount (Rs)", 130, R)]
        self.ltitle = ctk.CTkLabel(body, text="", font=T.f(14, "bold"), text_color=T.TEXT)
        self.rtitle = ctk.CTkLabel(body, text="", font=T.f(14, "bold"), text_color=T.TEXT)
        self.ltitle.grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.rtitle.grid(row=0, column=1, sticky="w", padx=(10, 0), pady=(0, 6))
        self.left, self.right = DataTable(body, cols, height=10), DataTable(body, cols, height=10)
        self.left.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self.right.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        self.refresh()

    def stock_value(self):
        try:
            return parse_amount(self.stock.get())
        except ValueError:
            return 0.0

    def fill(self, ltitle, lrows, ltotal, rtitle, rrows, rtotal, footer, color):
        self.ltitle.configure(text=ltitle)
        self.rtitle.configure(text=rtitle)
        mk = lambda rows, total: [(n, inr(a)) for n, a in rows] + [(("Total", inr(total)), "total")]
        self.left.set_rows(mk(lrows, ltotal))
        self.right.set_rows(mk(rrows, rtotal))
        self.footer.configure(text=footer, text_color=color)


class ProfitLossFrame(TwoSideReport):
    title_text, sub_text = "Profit & Loss", "Income against expenses. GST is not income or expense."

    def refresh(self):
        pl = r.profit_and_loss(self.con, self.fy.get(), self.stock_value())
        net = pl["net_profit"]
        left, right = list(pl["expenses"]), list(pl["income"])
        if pl["closing_stock"]:
            right.append(("Closing Stock", pl["closing_stock"]))
        if net > 0:
            left.append(("Net Profit", net))
        elif net < 0:
            right.append(("Net Loss", -net))
        lt = pl["total_expenses"] + max(net, 0)
        rt = pl["total_income"] + pl["closing_stock"] + max(-net, 0)
        self.fill("Expenses", left, lt, "Income", right, rt,
                  f"Net {'Profit' if net >= 0 else 'Loss'}: Rs {inr(abs(net))}",
                  T.OK if net >= 0 else T.DANGER)


class BalanceSheetFrame(TwoSideReport):
    title_text, sub_text = "Balance Sheet", "What the business owns and owes."

    def refresh(self):
        bs = r.balance_sheet(self.con, self.fy.get(), self.stock_value())
        self.fill("Liabilities", bs["liabilities"], bs["total_liabilities"],
                  "Assets", bs["assets"], bs["total_assets"],
                  f"Total: Rs {inr(bs['total_assets'])}", T.TEXT)


class InvoiceRegisterFrame(ReportBase):
    """Sales or purchase register. Double-click a bill to open, edit or delete it."""
    def __init__(self, master, con, kind, opener=None):
        self.kind, self.opener = kind, opener
        self.title_text = f"{kind} Register"
        self.sub_text = "Every bill in the year, with payment status. Double-click a bill to open, edit or delete it."
        super().__init__(master, con)
        cols = [("dt", "Date", 90, L), ("no", "No.", 50, L), ("p", "Party", 190, L),
                ("tx", "Taxable", 110, R), ("cg", "CGST", 85, R), ("sg", "SGST", 85, R),
                ("ig", "IGST", 85, R), ("t", "Total", 110, R), ("b", "Balance due", 110, R),
                ("st", "Status", 95, L)]
        self.table = DataTable(self, cols, height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        if opener:
            self.table.on_open(lambda vid: self.opener(vid, self.refresh))
        self.refresh()

    def export_data(self):
        reg = r.invoice_register(self.con, self.fy.get(), self.kind)
        headers = ["Date", "No.", "Party", "Taxable", "CGST", "SGST", "IGST", "Total", "Balance due", "Status"]
        rows = [[disp_date(x["date"]), x["vno"], x["party"], x["taxable"], x["cgst"], x["sgst"], x["igst"],
                 x["total"], x["balance"], x["status"]] for x in reg]
        return f"{self.kind} Register {self.fy.get()}", headers, rows

    def refresh(self):
        reg = r.invoice_register(self.con, self.fy.get(), self.kind)
        rows, tot = [], [0] * 6
        for x in reg:
            vals = [x["taxable"], x["cgst"], x["sgst"], x["igst"], x["total"], x["balance"]]
            tot = [a + b for a, b in zip(tot, vals)]
            rows.append(((disp_date(x["date"]), x["vno"], x["party"], *[_amt(v) for v in vals],
                          x["status"]), None, x["id"]))
        rows.append((("", "", f"Total ({len(reg)} bills)", *[inr(v) for v in tot], ""), "total"))
        self.table.set_rows(rows)


class OutstandingFrame(ReportBase):
    """Who owes you (receivable) and whom you owe (payable): bill by bill, or party-wise ageing."""
    title_text, with_fy = "Outstanding", False
    sub_text = "Unpaid bills and their ageing. Double-click a bill to open it."
    own_controls = True

    def __init__(self, master, con, opener=None):
        super().__init__(master, con)
        self.opener, self.table = opener, None
        st = settings.load_settings()
        self.edges = st.get("ageing_edges") or r.DEFAULT_EDGES
        ctrl = T.card(self)
        ctrl.pack(fill="x", padx=28, pady=(0, 10))
        seg = dict(selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER, unselected_color="#E7ECF5",
                   unselected_hover_color="#DCE3F0", text_color=T.TEXT, font=T.f(13))
        self.which = ctk.CTkSegmentedButton(ctrl, values=["Receivable", "Payable"], command=lambda _v: self.refresh(), **seg)
        self.which.set("Receivable")
        self.view = ctk.CTkSegmentedButton(ctrl, values=["Bills", "Ageing"], command=lambda _v: self.refresh(), **seg)
        self.view.set("Ageing")
        self.basis = T.option_menu(ctrl, ["Bill date", "Due date"], width=120, command=lambda _v: self.refresh())
        self.asof = T.entry(ctrl, width=120)
        self.asof.insert(0, today_str())
        self.ranges = T.entry(ctrl, "30,60,90", width=150)
        self.ranges.insert(0, ",".join(str(e) for e in self.edges))
        items = (("Show", self.which), ("View", self.view), ("Age from", self.basis),
                 ("As on date", self.asof), ("Ranges (days)", self.ranges))
        for c, (label, w) in enumerate(items):
            if label != "Show":
                ctk.CTkLabel(ctrl, text=label, font=T.f(12), text_color=T.MUTED).grid(
                    row=0, column=c, sticky="w", padx=(18 if c == 0 else 8, 8), pady=(12, 2))
            w.grid(row=1, column=c, padx=(18 if c == 0 else 8, 8), pady=(0, 14))
        T.button(ctrl, "Refresh", self.refresh, width=90).grid(row=1, column=5, padx=8, pady=(0, 14))
        T.button(ctrl, "Export Excel", self.export, width=120, fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").grid(row=1, column=6, padx=8, pady=(0, 14))
        self.summary = ctk.CTkLabel(self, text="", font=T.f(13, "bold"), text_color=T.TEXT)
        self.summary.pack(anchor="w", padx=28, pady=(0, 8))
        self.holder = ctk.CTkFrame(self, fg_color="transparent")
        self.holder.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    # -- inputs --
    def _inputs(self):
        edges = r.parse_edges(self.ranges.get())
        asof = parse_date(self.asof.get())
        kind = "Sales" if self.which.get() == "Receivable" else "Purchase"
        return kind, asof, ("due" if self.basis.get() == "Due date" else "bill"), edges

    def _report(self):
        kind, asof, basis, edges = self._inputs()
        rep = r.outstanding_report(self.con, kind, asof, basis, edges)
        return kind, rep

    def _set_table(self, columns):
        if self.table is not None:
            self.table.destroy()
        self.table = DataTable(self.holder, columns, height=14)
        self.table.pack(fill="both", expand=True)
        if self.opener:
            self.table.on_open(lambda vid: self.opener(vid, self.refresh))

    def refresh(self):
        try:
            kind, rep = self._report()
        except ValueError as e:
            self.summary.configure(text=str(e), text_color=T.DANGER)
            return
        st = settings.load_settings()
        st["ageing_edges"] = r.parse_edges(self.ranges.get())
        settings.save_settings(st)
        self.summary.configure(text_color=T.TEXT)
        due = rep["basis"] == "due"
        word = "overdue" if due else "old"
        self.summary.configure(text=f"Total Rs {inr(rep['total'])}    |    " + "    ".join(
            f"{l} days: {inr(rep['buckets'][l])}" if l != "Not due" else f"Not due: {inr(rep['buckets'][l])}"
            for l in rep["labels"]))
        if self.view.get() == "Ageing":
            cols = [("p", "Party", 250, L)] + [(f"b{i}", l if l == "Not due" else f"{l} days", 105, R)
                                                for i, l in enumerate(rep["labels"])]
            cols += [("oa", "On account", 110, R), ("t", "Total", 120, R)]
            self._set_table(cols)
            rows = []
            for p in rep["parties"]:
                rows.append((p["party"], *[_amt(p["bucket_amounts"][l]) for l in rep["labels"]],
                             _amt(p["on_account"]), inr(p["balance"])))
            on_acc = sum(p["on_account"] for p in rep["parties"])
            rows.append((("Total", *[inr(rep["buckets"][l]) for l in rep["labels"]], inr(on_acc), inr(rep["total"])), "total"))
        else:
            self._set_table([("p", "Party / bill", 270, L), ("dt", "Bill date", 95, L), ("du", "Due on", 95, L),
                             ("t", "Bill total", 120, R), ("s", "Settled", 115, R), ("b", "Balance", 125, R),
                             ("d", f"Days {word}" if due else "Days old", 90, R), ("k", "Range", 90, L)])
            rows = []
            for p in rep["parties"]:
                rows.append(((p["party"], "", "", "", "", inr(p["balance"]), "", ""), "head"))
                for b in p["bills"]:
                    rows.append(((f"      {kind} #{b['vno']}", disp_date(b["date"]), disp_date(b["due_date"]),
                                  inr(b["total"]), _amt(b["settled"]), inr(b["balance"]),
                                  b["days"] if not (due and b["days"] <= 0) else "-", b["bucket"]), None, b["id"]))
                if p["on_account"]:
                    rows.append((("      On account / opening balance", "", "", "", "", inr(p["on_account"]), "", ""), None))
            rows.append((("Total outstanding", "", "", "", "", inr(rep["total"]), "", ""), "total"))
        self.table.set_rows(rows)

    def export_data(self):
        kind, rep = self._report()
        who = "Receivable" if kind == "Sales" else "Payable"
        basis = "from due date" if rep["basis"] == "due" else "from bill date"
        title = f"{who} {'ageing' if self.view.get() == 'Ageing' else 'bills'} as on {disp_date(rep['as_of'])} ({basis})"
        if self.view.get() == "Ageing":
            headers = ["Party"] + [l if l == "Not due" else f"{l} days" for l in rep["labels"]] + ["On account", "Total"]
            rows = [[p["party"]] + [p["bucket_amounts"][l] for l in rep["labels"]] + [p["on_account"], p["balance"]]
                    for p in rep["parties"]]
            rows.append(["Total"] + [rep["buckets"][l] for l in rep["labels"]] +
                        [sum(p["on_account"] for p in rep["parties"]), rep["total"]])
        else:
            headers = ["Party", "Bill", "Bill date", "Due on", "Bill total", "Settled", "Balance", "Days", "Range"]
            rows = []
            for p in rep["parties"]:
                for b in p["bills"]:
                    rows.append([p["party"], f"{kind} #{b['vno']}", disp_date(b["date"]), disp_date(b["due_date"]),
                                 b["total"], b["settled"], b["balance"], b["days"], b["bucket"]])
                if p["on_account"]:
                    rows.append([p["party"], "On account / opening", "", "", "", "", p["on_account"], "", ""])
            rows.append(["Total", "", "", "", "", "", rep["total"], "", ""])
        return title, headers, rows
