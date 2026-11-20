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
            T.button(self.bar, "Export Excel", self.export, width=120,
                     fg_color="#E7ECF5", text_color=T.TEXT,
                     hover_color="#DCE3F0").pack(side="right", padx=(10, 0))

    def export(self):
        try:
            title, headers, rows = self.export_data()
            path = filedialog.asksaveasfilename(
                title="Save report as", defaultextension=".xlsx",
                filetypes=[("Excel file", "*.xlsx")],
                initialfile=f"{title.replace(' ', '_')}.xlsx")
            if not path:
                return
            path = write_table(path, title, headers, rows)
        except Exception as e:
            messagebox.showerror("MUNIM", f"Could not save the report:\n{e}")
            return
        messagebox.showinfo("MUNIM", f"Report saved:\n{path}")


class TrialBalanceFrame(ReportBase):
    title_text = "Trial Balance"
    sub_text   = "Closing balances of every ledger account."

    def __init__(self, master, con):
        super().__init__(master, con)
        self.table = DataTable(self, [("p", "Particulars", 420, L),
                                      ("d", "Debit (Rs)", 160, R),
                                      ("c", "Credit (Rs)", 160, R)], height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def export_data(self):
        rows, td, tc = s.trial_balance(self.con, self.fy.get())
        return (f"Trial Balance {self.fy.get()}",
                ["Particulars", "Debit (Rs)", "Credit (Rs)"],
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
        self._is_cashbook = accounts is not None
        super().__init__(master, con)
        names = accounts or [x["name"] for x in con.execute(
            "SELECT name FROM accounts ORDER BY name COLLATE NOCASE")]
        if accounts:
            self.acct = T.option_menu(self.bar, names, width=160,
                                      command=lambda _v: self.refresh())
        else:
            self.acct = T.combo(self.bar, names, width=260,
                                command=lambda _v: self.refresh())
        self.acct.set("Cash" if "Cash" in names else names[0])
        self.acct.pack(side="right", padx=(10, 0))
        if not accounts:
            T.button(self.bar, "Show", self.refresh, width=70).pack(
                side="right", padx=(10, 0))
        if self._is_cashbook:
            today = date.today()
            self.d2 = T.entry(self.bar, width=120)
            self.d2.insert(0, today.strftime("%d-%m-%Y"))
            self.d1 = T.entry(self.bar, width=120)
            self.d1.insert(0, today.replace(day=1).strftime("%d-%m-%Y"))
            T.button(self.bar, "Show", self.refresh, width=70).pack(side="right")
            self.d2.pack(side="right", padx=6)
            ctk.CTkLabel(self.bar, text="to", text_color=T.MUTED).pack(side="right")
            self.d1.pack(side="right", padx=6)
        self.summary = ctk.CTkLabel(self, text="", font=T.f(13, "bold"), text_color=T.TEXT)
        self.summary.pack(anchor="w", padx=28, pady=(0, 8))
        self.table = DataTable(self, [
            ("dt", "Date",        100, L), ("v",  "Voucher",    120, L),
            ("n",  "Narration",   300, L), ("d",  "Debit (Rs)", 130, R),
            ("c",  "Credit (Rs)", 130, R), ("b",  "Balance",    150, R)], height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def refresh(self):
        try:
            if self._is_cashbook:
                d1  = parse_date(self.d1.get())
                d2  = parse_date(self.d2.get())
                led = r.ledger_view(self.con, self.acct.get().strip(),
                                    self.fy.get(), date_from=d1, date_to=d2)
            else:
                led = r.ledger_view(self.con, self.acct.get().strip(), self.fy.get())
        except ValueError as e:
            self.summary.configure(text=str(e), text_color=T.DANGER)
            self.table.set_rows([])
            return
        rows = [(("", "", "Opening balance", "", "",
                  f"{inr(led['opening'])} {led['opening_side']}"), "head")]
        for x in led["rows"]:
            rows.append((disp_date(x["date"]), f"{x['vtype']} #{x['vno']}", x["narration"],
                         _amt(x["dr"]), _amt(x["cr"]),
                         f"{inr(x['balance'])} {x['side']}"))
        rows.append((("", "", "Total", inr(led["total_dr"]), inr(led["total_cr"]),
                      f"{inr(led['closing'])} {led['closing_side']}"), "total"))
        self.table.set_rows(rows)
        self.summary.configure(
            text=(f"{led['account']}   |   "
                  f"Closing balance: Rs {inr(led['closing'])} {led['closing_side']}"),
            text_color=T.TEXT)

    def export_data(self):
        try:
            d1  = parse_date(self.d1.get())
            d2  = parse_date(self.d2.get())
            led = r.ledger_view(self.con, self.acct.get().strip(),
                                self.fy.get(), date_from=d1, date_to=d2)
        except ValueError:
            return "Ledger", ["Date","Voucher","Narration","Debit (Rs)","Credit (Rs)","Balance"], []
        headers = ["Date","Voucher","Narration","Debit (Rs)","Credit (Rs)","Balance"]
        rows = [[disp_date(x["date"]), f"{x['vtype']} #{x['vno']}", x["narration"],
                 x["dr"], x["cr"], x["balance"]] for x in led["rows"]]
        return f"Ledger {led['account']} {self.fy.get()}", headers, rows


class DayBookFrame(ReportBase):
    title_text, with_fy = "Day Book", False
    sub_text = "All vouchers between two dates. Double-click to open, edit or delete."

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
        self.table = DataTable(self, [
            ("dt", "Date",         100, L), ("v",  "Voucher",    130, L),
            ("p",  "Particulars",  380, L), ("d",  "Debit (Rs)", 130, R),
            ("c",  "Credit (Rs)", 130, R)], height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(4, 24))
        if opener:
            self.table.on_open(lambda vid: self.opener(vid, self.refresh))
        self.refresh()

    def refresh(self):
        try:
            book = r.day_book(self.con, parse_date(self.d1.get()),
                              parse_date(self.d2.get()))
        except ValueError as e:
            self.msg.configure(text=str(e))
            return
        self.msg.configure(text="")
        rows = []
        for v in book:
            rows.append(((disp_date(v["date"]), f"{v['vtype']} #{v['vno']}",
                          v["narration"], "", ""), "head", v["id"]))
            for name, dr, cr in v["lines"]:
                rows.append(("", "", "      " + name, _amt(dr), _amt(cr)))
        self.table.set_rows(rows)


class TwoSideReport(ReportBase):
    def __init__(self, master, con):
        super().__init__(master, con)
        self.fy.configure(command=lambda _v: self.on_fy())
        self.extra_controls()
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
        self.left  = DataTable(body, cols, height=10)
        self.right = DataTable(body, cols, height=10)
        self.left.grid( row=1, column=0, sticky="nsew", padx=(0, 10))
        self.right.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        self.refresh()

    def extra_controls(self): pass
    def on_fy(self): self.refresh()

    def fill(self, ltitle, lrows, ltotal, rtitle, rrows, rtotal, footer, color):
        self.ltitle.configure(text=ltitle)
        self.rtitle.configure(text=rtitle)
        mk = lambda rows, total: [(n, inr(a)) for n, a in rows] + \
                                  [(("Total", inr(total)), "total")]
        self.left.set_rows(mk(lrows, ltotal))
        self.right.set_rows(mk(rrows, rtotal))
        self.footer.configure(text=footer, text_color=color)

    def _two_side_export(self, title, lrows, ltotal, rrows, rtotal, ltitle, rtitle):
        n = max(len(lrows), len(rrows))
        lrows = list(lrows) + [("", "")] * (n - len(lrows))
        rrows = list(rrows) + [("", "")] * (n - len(rrows))
        rows = [[a, b, c, d] for (a, b), (c, d) in zip(lrows, rrows)] + \
               [["Total", ltotal, "Total", rtotal]]
        return title, [ltitle, "Amount (Rs)", rtitle, "Amount (Rs)"], rows


class ProfitLossFrame(TwoSideReport):
    title_text = "Trading & Profit/Loss"
    sub_text   = "Trading Account gives gross profit; P&L carries it to net profit."

    def extra_controls(self):
        seg = dict(selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER,
                   unselected_color="#E7ECF5", unselected_hover_color="#DCE3F0",
                   text_color=T.TEXT, font=T.f(13))
        row = T.card(self)
        row.pack(fill="x", padx=28, pady=(0, 10))
        self.opening = T.entry(row, "0.00", width=150)
        self.closing = T.entry(row, "0.00", width=150)
        self.mode = ctk.CTkSegmentedButton(
            row, values=["Trading Account", "Profit & Loss"],
            command=lambda _v: self.refresh(), **seg)
        self.mode.set("Trading Account")
        for c, (label, w) in enumerate((("Show", self.mode),
                                        ("Opening stock (Rs)", self.opening),
                                        ("Closing stock (Rs)", self.closing))):
            if label != "Show":
                ctk.CTkLabel(row, text=label, font=T.f(12), text_color=T.MUTED).grid(
                    row=0, column=c, sticky="w",
                    padx=(18 if c == 0 else 10, 10), pady=(12, 2))
            w.grid(row=1, column=c, padx=(18 if c == 0 else 10, 10), pady=(0, 14))
        ctk.CTkLabel(row,
                     text="Opening stock follows last year's closing unless you change it.",
                     font=T.f(11), text_color=T.MUTED, wraplength=330,
                     justify="left").grid(row=1, column=3, padx=14, pady=(0, 14), sticky="w")
        for w in (self.closing, self.opening):
            w._entry.bind("<FocusOut>", lambda _e: self._save_stock(), add="+")
            w._entry.bind("<Return>",   lambda _e: self._save_stock(), add="+")
        self._load_stock()

    @property
    def stock(self): return self.closing

    def _load_stock(self):
        o, c = s.get_stock(self.con, self.fy.get())
        for box, v in ((self.opening, o), (self.closing, c)):
            box.delete(0, "end")
            if v:
                box.insert(0, f"{v / 100:.2f}")

    def _save_stock(self):
        fy = self.fy.get()
        try:
            o_val = parse_amount(self.opening.get())
            c_val = parse_amount(self.closing.get())
        except ValueError:
            self.footer.configure(text="Stock values must be numbers", text_color=T.DANGER)
            return
        auto = s.get_stock(self.con, s.prev_fy(fy))[1] / 100
        s.set_stock(self.con, fy,
                    opening=None if abs(o_val - auto) < 0.005 else o_val,
                    closing=c_val)
        self.refresh()

    def on_fy(self):
        self._load_stock()
        self.refresh()

    def _data(self):
        return r.trading_and_pl(self.con, self.fy.get())

    def refresh(self):
        ta = self._data()
        t, p = ta["trading"], ta["pl"]
        gp, npf = t["gross_profit"], p["net_profit"]
        foot = (f"Gross {'Profit' if gp >= 0 else 'Loss'}: Rs {inr(abs(gp))}      "
                f"Net {'Profit' if npf >= 0 else 'Loss'}: Rs {inr(abs(npf))}")
        color = T.OK if npf >= 0 else T.DANGER
        if self.mode.get() == "Trading Account":
            self.fill("Debit side", t["left"], t["left_total"],
                      "Credit side", t["right"], t["right_total"], foot, color)
        else:
            self.fill("Debit side", p["left"], p["left_total"],
                      "Credit side", p["right"], p["right_total"], foot, color)

    def export_data(self):
        ta = self._data()
        out_rows, title = [], f"Trading and Profit Loss {self.fy.get()}"
        _t, h, rows = self._two_side_export(
            "Trading Account", ta["trading"]["left"], ta["trading"]["left_total"],
            ta["trading"]["right"], ta["trading"]["right_total"], "Debit", "Credit")
        out_rows += [["TRADING ACCOUNT", "", "", ""]] + rows + [["", "", "", ""]]
        _t, h, rows = self._two_side_export(
            "Profit & Loss", ta["pl"]["left"], ta["pl"]["left_total"],
            ta["pl"]["right"], ta["pl"]["right_total"], "Debit", "Credit")
        out_rows += [["PROFIT & LOSS ACCOUNT", "", "", ""]] + rows
        return title, h, out_rows


class BalanceSheetFrame(TwoSideReport):
    title_text = "Balance Sheet"
    sub_text   = "What the business owns and owes."

    def extra_controls(self):
        self.note = ctk.CTkLabel(self, text="", font=T.f(12), text_color=T.MUTED)
        self.note.pack(anchor="w", padx=28, pady=(0, 8))

    def refresh(self):
        bs = r.balance_sheet(self.con, self.fy.get())
        cs = s.get_stock(self.con, self.fy.get())[1] / 100
        self.note.configure(
            text=f"Closing stock: Rs {inr(cs)} (set under Trading & P&L)")
        self.fill("Liabilities", bs["liabilities"], bs["total_liabilities"],
                  "Assets", bs["assets"], bs["total_assets"],
                  f"Total: Rs {inr(bs['total_assets'])}", T.TEXT)

    def export_data(self):
        bs = r.balance_sheet(self.con, self.fy.get())
        return self._two_side_export(
            f"Balance Sheet {self.fy.get()}",
            bs["liabilities"], bs["total_liabilities"],
            bs["assets"], bs["total_assets"], "Liabilities", "Assets")


class InvoiceRegisterFrame(ReportBase):
    def __init__(self, master, con, kind, opener=None):
        self.kind, self.opener = kind, opener
        self.title_text = f"{kind} Register"
        self.sub_text = ("Every bill in the year, with payment status. "
                         "Double-click a bill to open, edit or delete it.")
        super().__init__(master, con)
        cols = [("dt", "Date",        90,  L), ("no", "No.",      50,  L),
                ("p",  "Party",      190,  L), ("tx", "Taxable", 110,  R),
                ("cg", "CGST",        85,  R), ("sg", "SGST",     85,  R),
                ("ig", "IGST",        85,  R), ("t",  "Total",   110,  R),
                ("b",  "Balance due", 110, R), ("st", "Status",   95,  L)]
        self.table = DataTable(self, cols, height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        if opener:
            self.table.on_open(lambda vid: self.opener(vid, self.refresh))
        self.refresh()

    def export_data(self):
        reg = r.invoice_register(self.con, self.fy.get(), self.kind)
        headers = ["Date","No.","Party","Taxable","CGST","SGST","IGST",
                   "Total","Balance due","Status"]
        rows = [[disp_date(x["date"]), x["vno"], x["party"],
                 x["taxable"], x["cgst"], x["sgst"], x["igst"],
                 x["total"], x["balance"], x["status"]] for x in reg]
        return f"{self.kind} Register {self.fy.get()}", headers, rows

    def refresh(self):
        reg = r.invoice_register(self.con, self.fy.get(), self.kind)
        rows, tot = [], [0] * 6
        for x in reg:
            vals = [x["taxable"], x["cgst"], x["sgst"],
                    x["igst"], x["total"], x["balance"]]
            tot  = [a + b for a, b in zip(tot, vals)]
            rows.append(((disp_date(x["date"]), x["vno"], x["party"],
                          *[_amt(v) for v in vals], x["status"]), None, x["id"]))
        rows.append((("", "", f"Total ({len(reg)} bills)",
                      *[inr(v) for v in tot], ""), "total"))
        self.table.set_rows(rows)


class OutstandingFrame(ReportBase):
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
        seg = dict(selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER,
                   unselected_color="#E7ECF5", unselected_hover_color="#DCE3F0",
                   text_color=T.TEXT, font=T.f(13))
        self.which  = ctk.CTkSegmentedButton(ctrl, values=["Receivable","Payable"],
                                              command=lambda _v: self.refresh(), **seg)
        self.which.set("Receivable")
        self.view   = ctk.CTkSegmentedButton(ctrl, values=["Bills","Ageing"],
                                              command=lambda _v: self.refresh(), **seg)
        self.view.set("Ageing")
        self.basis  = T.option_menu(ctrl, ["Bill date","Due date"], width=120,
                                    command=lambda _v: self.refresh())
        self.asof   = T.entry(ctrl, width=120)
        self.asof.insert(0, today_str())
        self.ranges = T.entry(ctrl, "30,60,90", width=150)
        self.ranges.insert(0, ",".join(str(e) for e in self.edges))
        items = (("Show", self.which), ("View", self.view),
                 ("Age from", self.basis), ("As on date", self.asof),
                 ("Ranges (days)", self.ranges))
        for c, (label, w) in enumerate(items):
            if label != "Show":
                ctk.CTkLabel(ctrl, text=label, font=T.f(12), text_color=T.MUTED).grid(
                    row=0, column=c, sticky="w",
                    padx=(18 if c == 0 else 8, 8), pady=(12, 2))
            w.grid(row=1, column=c, padx=(18 if c == 0 else 8, 8), pady=(0, 14))
        T.button(ctrl, "Refresh", self.refresh, width=90).grid(
            row=1, column=5, padx=8, pady=(0, 14))
        T.button(ctrl, "Export Excel", self.export, width=120,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").grid(row=1, column=6, padx=8, pady=(0, 14))
        self.summary = ctk.CTkLabel(self, text="", font=T.f(13, "bold"), text_color=T.TEXT)
        self.summary.pack(anchor="w", padx=28, pady=(0, 8))
        self.holder = ctk.CTkFrame(self, fg_color="transparent")
        self.holder.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def _inputs(self):
        edges = r.parse_edges(self.ranges.get())
        asof  = parse_date(self.asof.get())
        kind  = "Sales" if self.which.get() == "Receivable" else "Purchase"
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
        due  = rep["basis"] == "due"
        word = "overdue" if due else "old"
        self.summary.configure(
            text=f"Total Rs {inr(rep['total'])}    |    " +
                 "    ".join(
                     f"{l} days: {inr(rep['buckets'][l])}"
                     if l != "Not due" else f"Not due: {inr(rep['buckets'][l])}"
                     for l in rep["labels"]))
        if self.view.get() == "Ageing":
            cols = ([("p", "Party", 250, L)] +
                    [(f"b{i}", l if l == "Not due" else f"{l} days", 105, R)
                     for i, l in enumerate(rep["labels"])] +
                    [("oa", "On account", 110, R), ("t", "Total", 120, R)])
            self._set_table(cols)
            rows = []
            for p in rep["parties"]:
                rows.append((p["party"],
                             *[_amt(p["bucket_amounts"][l]) for l in rep["labels"]],
                             _amt(p["on_account"]), inr(p["balance"])))
            on_acc = sum(p["on_account"] for p in rep["parties"])
            rows.append((("Total",
                          *[inr(rep["buckets"][l]) for l in rep["labels"]],
                          inr(on_acc), inr(rep["total"])), "total"))
        else:
            self._set_table([
                ("p",  "Party / bill",  270, L), ("dt", "Bill date",  95, L),
                ("du", "Due on",         95, L), ("t",  "Bill total", 120, R),
                ("s",  "Settled",       115, R), ("b",  "Balance",   125, R),
                ("d",  f"Days {word}" if due else "Days old", 90, R),
                ("k",  "Range", 90, L)])
            rows = []
            for p in rep["parties"]:
                rows.append(((p["party"], "", "", "", "",
                               inr(p["balance"]), "", ""), "head"))
                for b in p["bills"]:
                    rows.append(((
                        f"      {kind} #{b['vno']}",
                        disp_date(b["date"]), disp_date(b["due_date"]),
                        inr(b["total"]), _amt(b["settled"]), inr(b["balance"]),
                        b["days"] if not (due and b["days"] <= 0) else "-",
                        b["bucket"]), None, b["id"]))
                if p["on_account"]:
                    rows.append((("      On account / opening balance",
                                  "", "", "", "", inr(p["on_account"]),
                                  "", ""), None))
            rows.append((("Total outstanding", "", "", "", "",
                           inr(rep["total"]), "", ""), "total"))
        self.table.set_rows(rows)

    def export_data(self):
        kind, rep = self._report()
        who   = "Receivable" if kind == "Sales" else "Payable"
        basis = "from due date" if rep["basis"] == "due" else "from bill date"
        title = (f"{who} {'ageing' if self.view.get() == 'Ageing' else 'bills'} "
                 f"as on {disp_date(rep['as_of'])} ({basis})")
        if self.view.get() == "Ageing":
            headers = (["Party"] +
                       [l if l == "Not due" else f"{l} days" for l in rep["labels"]] +
                       ["On account", "Total"])
            rows = ([[p["party"]] +
                     [p["bucket_amounts"][l] for l in rep["labels"]] +
                     [p["on_account"], p["balance"]]
                     for p in rep["parties"]] +
                    [["Total"] + [rep["buckets"][l] for l in rep["labels"]] +
                     [sum(p["on_account"] for p in rep["parties"]), rep["total"]]])
        else:
            headers = ["Party","Bill","Bill date","Due on","Bill total",
                       "Settled","Balance","Days","Range"]
            rows = []
            for p in rep["parties"]:
                for b in p["bills"]:
                    rows.append([p["party"], f"{kind} #{b['vno']}",
                                 disp_date(b["date"]), disp_date(b["due_date"]),
                                 b["total"], b["settled"], b["balance"],
                                 b["days"], b["bucket"]])
                if p["on_account"]:
                    rows.append([p["party"], "On account / opening",
                                 "", "", "", "", p["on_account"], "", ""])
            rows.append(["Total","","","","","",rep["total"],"",""])
        return title, headers, rows


class ReturnsRegisterFrame(ReportBase):
    own_controls = True

    def __init__(self, master, con, kind, opener=None):
        self.kind, self.opener = kind, opener
        label = "Sales Return" if kind == "Sales Return" else "Purchase Return"
        self.title_text = f"{label} Register"
        self.sub_text = ("Credit Notes issued to customers." if kind == "Sales Return"
                         else "Debit Notes raised on suppliers.")
        self.with_fy = False
        super().__init__(master, con)
        today = date.today()
        self.d1 = T.entry(self.bar, width=120)
        self.d1.insert(0, today.replace(day=1).strftime("%d-%m-%Y"))
        self.d2 = T.entry(self.bar, width=120)
        self.d2.insert(0, today.strftime("%d-%m-%Y"))
        T.button(self.bar, "Show", self.refresh, width=70).pack(side="right")
        self.d2.pack(side="right", padx=6)
        ctk.CTkLabel(self.bar, text="to", text_color=T.MUTED).pack(side="right")
        self.d1.pack(side="right", padx=6)
        T.button(self.bar, "Export Excel", self.export, width=120,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="right", padx=(10, 0))
        self.msg = ctk.CTkLabel(self, text="", font=T.f(13), text_color=T.DANGER)
        self.msg.pack(anchor="w", padx=28)
        cols = [("dt", "Date",    90,  L), ("no", "No.",    50,  L),
                ("p",  "Party",  190,  L), ("tx", "Taxable",110, R),
                ("cg", "CGST",    85,  R), ("sg", "SGST",    85, R),
                ("ig", "IGST",    85,  R), ("t",  "Total",  110, R)]
        self.table = DataTable(self, cols, height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(4, 24))
        if opener:
            self.table.on_open(lambda vid: self.opener(vid, self.refresh))
        self.refresh()

    def _get_rows(self):
        try:
            d1 = parse_date(self.d1.get())
            d2 = parse_date(self.d2.get())
        except ValueError as e:
            self.msg.configure(text=str(e))
            return None, None, None
        self.msg.configure(text="")
        from db.setup import to_rupees
        q = """SELECT v.id, v.vdate, v.vno, v.narration, i.party, i.taxable,
                      i.cgst, i.sgst, i.igst, i.total, i.customer_name
               FROM vouchers v LEFT JOIN invoices i ON i.voucher_id=v.id
               WHERE v.vtype=? AND v.vdate BETWEEN ? AND ?
               ORDER BY v.vdate, v.vno"""
        rows = self.con.execute(
            q, (self.kind, d1.isoformat(), d2.isoformat())).fetchall()
        return rows, d1, d2

    def refresh(self):
        rows, d1, d2 = self._get_rows()
        if rows is None:
            return
        from db.setup import to_rupees
        out, tot = [], [0] * 5
        for x in rows:
            has   = x["party"] is not None
            party = ((f"{x['party']} ({x['customer_name']})"
                      if x["customer_name"] else x["party"])
                     if has else "(details not stored)")
            vals = [to_rupees(x["taxable"]) if has else 0,
                    to_rupees(x["cgst"])    if has else 0,
                    to_rupees(x["sgst"])    if has else 0,
                    to_rupees(x["igst"])    if has else 0,
                    to_rupees(x["total"])   if has else 0]
            for i in range(5):
                tot[i] += vals[i]
            out.append(((disp_date(x["vdate"]), x["vno"], party,
                         *[_amt(v) for v in vals]), None, x["id"]))
        out.append((("", "", f"Total ({len(rows)} vouchers)",
                     inr(tot[0]), inr(tot[1]), inr(tot[2]), inr(tot[3]), inr(tot[4])),
                    "total"))
        self.table.set_rows(out)

    def export_data(self):
        rows, d1, d2 = self._get_rows()
        if rows is None:
            return f"{self.title_text}", [], []
        from db.setup import to_rupees
        label = "Sales Return" if self.kind == "Sales Return" else "Purchase Return"
        title = (f"{label} Register "
                 f"{disp_date(d1.isoformat())} to {disp_date(d2.isoformat())}")
        headers = ["Date", "No.", "Party", "Taxable", "CGST", "SGST", "IGST", "Total"]
        out = []
        for x in rows:
            has   = x["party"] is not None
            party = ((f"{x['party']} ({x['customer_name']})"
                      if x["customer_name"] else x["party"])
                     if has else "(details not stored)")
            out.append([disp_date(x["vdate"]), x["vno"], party,
                        to_rupees(x["taxable"]) if has else 0,
                        to_rupees(x["cgst"])    if has else 0,
                        to_rupees(x["sgst"])    if has else 0,
                        to_rupees(x["igst"])    if has else 0,
                        to_rupees(x["total"])   if has else 0])
        return title, headers, out


class StockSummaryFrame(ReportBase):
    title_text = "Stock Summary"
    sub_text   = "Item-wise stock position and value for the financial year."

    def __init__(self, master, con):
        super().__init__(master, con)
        self.table = DataTable(self, [
            ("n", "Item",        200, L), ("h", "HSN",         80, L),
            ("u", "Unit",         60, L), ("o", "Opening",     90, "c"),
            ("p", "Purchased",  100, "c"), ("s", "Sold",        90, "c"),
            ("c", "Closing",    100, "c"), ("r", "Avg Rate",   110, R),
            ("v", "Stock Value",130, R)], height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def _fmt(self, v):
        return f"{v:,.3f}".rstrip("0").rstrip(".")

    def refresh(self):
        from db.setup import stock_summary
        rows = stock_summary(self.con, self.fy.get())
        out = []
        totals      = [0.0] * 4
        total_value = 0.0
        for it in rows:
            vals = [it["opening"], it["purchased"], it["sold"], it["closing"]]
            for i, v in enumerate(vals):
                totals[i] += v
            total_value += it.get("stock_value", 0.0)
            out.append((it["name"], it["hsn"] or "-", it["unit"],
                        self._fmt(it["opening"]), self._fmt(it["purchased"]),
                        self._fmt(it["sold"]),    self._fmt(it["closing"]),
                        inr(it.get("avg_rate",    0.0)) if it.get("avg_rate")    else "",
                        inr(it.get("stock_value", 0.0)) if it.get("stock_value") else ""))
        out.append((("", "", "Total",
                     self._fmt(totals[0]), self._fmt(totals[1]),
                     self._fmt(totals[2]), self._fmt(totals[3]),
                     "", inr(total_value)), "total"))
        self.table.set_rows(out)

    def export_data(self):
        from db.setup import stock_summary
        rows = stock_summary(self.con, self.fy.get())
        headers = ["Item", "HSN", "Unit", "Opening", "Purchased", "Sold",
                   "Closing", "Avg Rate", "Stock Value"]
        data = [[it["name"], it["hsn"], it["unit"], it["opening"],
                 it["purchased"], it["sold"], it["closing"],
                 it.get("avg_rate", 0.0), it.get("stock_value", 0.0)]
                for it in rows]
        return f"Stock Summary {self.fy.get()}", headers, data


class ItemWiseProfitFrame(ReportBase):
    title_text = "Item-wise Profit"
    sub_text   = "Profit per item based on weighted-average cost of goods sold."

    def __init__(self, master, con):
        super().__init__(master, con)
        self.table = DataTable(self, [
            ("n", "Item",         200, L), ("u", "Unit",          60, L),
            ("q", "Sold Qty",     100, "e"), ("s", "Sale Value",  140, R),
            ("a", "Avg Cost",     120, R),  ("c", "Cost of Sold", 140, R),
            ("p", "Profit",       140, R),  ("m", "Margin %",      90, R)], height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def _fmt_qty(self, v):
        return f"{v:,.3f}".rstrip("0").rstrip(".")

    def refresh(self):
        from db.setup import item_wise_profit
        rows = item_wise_profit(self.con, self.fy.get())
        out = []
        tot_sale = tot_cost = tot_profit = 0.0
        for it in rows:
            tot_sale   += it["sale_value"]
            tot_cost   += it["cost_of_sold"]
            tot_profit += it["profit"]
            out.append((it["name"], it["unit"],
                        self._fmt_qty(it["sold_qty"]),
                        inr(it["sale_value"]),
                        inr(it["avg_cost"]) if it["avg_cost"] else "",
                        inr(it["cost_of_sold"]),
                        inr(it["profit"]),
                        f"{it['margin']:.2f}"))
        tot_margin = (tot_profit / tot_sale * 100) if tot_sale > 0 else 0.0
        out.append((("", "", "Total",
                     inr(tot_sale), "", inr(tot_cost),
                     inr(tot_profit), f"{tot_margin:.2f}"), "total"))
        self.table.set_rows(out)

    def export_data(self):
        from db.setup import item_wise_profit
        rows = item_wise_profit(self.con, self.fy.get())
        headers = ["Item", "Unit", "Sold Qty", "Sale Value",
                   "Avg Cost", "Cost of Sold", "Profit", "Margin %"]
        data = [[it["name"], it["unit"], it["sold_qty"], it["sale_value"],
                 it["avg_cost"], it["cost_of_sold"], it["profit"],
                 round(it["margin"], 2)] for it in rows]
        return f"Item-wise Profit {self.fy.get()}", headers, data


# ── GST Reports ───────────────────────────────────────────────────────────────

_MONTHS = ["April","May","June","July","August","September",
           "October","November","December","January","February","March"]


class GSTR1Frame(ReportBase):
    title_text = "GSTR-1 (Outward)"
    sub_text   = "Monthly outward supply summary and invoice-wise detail."

    def __init__(self, master, con):
        super().__init__(master, con)
        from datetime import date as _d
        today = _d.today()
        default_month = (today.month - 3) % 12 or 12
        self.month = T.option_menu(self.bar, _MONTHS, width=130,
                                   command=lambda _v: self.refresh())
        self.month.set(_MONTHS[default_month - 1])
        self.month.pack(side="right", padx=(10, 0))
        # JSON export button
        T.button(self.bar, "Export JSON", self._export_json, width=120,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="right", padx=(10, 0))

        self.summary_lbl = ctk.CTkLabel(self, text="SUMMARY (by GST rate)",
                                        font=T.f(12, "bold"), text_color=T.MUTED)
        self.summary_lbl.pack(anchor="w", padx=28, pady=(4, 4))
        self.summary_tbl = DataTable(self, [
            ("k",  "Type",     70, L), ("r",  "Rate %",  70, R),
            ("tx", "Taxable", 140, R), ("cg", "CGST",   110, R),
            ("sg", "SGST",    110, R), ("ig", "IGST",   110, R),
            ("t",  "Total",   140, R)], height=6)
        self.summary_tbl.pack(fill="x", padx=28, pady=(0, 10))

        self.detail_lbl = ctk.CTkLabel(self, text="INVOICE DETAIL",
                                       font=T.f(12, "bold"), text_color=T.MUTED)
        self.detail_lbl.pack(anchor="w", padx=28, pady=(4, 4))
        self.detail_tbl = DataTable(self, [
            ("dt", "Date",    90, L), ("no", "No.",     50, L),
            ("p",  "Party",  170, L), ("g",  "GSTIN",  140, L),
            ("s",  "Supply",  70, L), ("tx", "Taxable",110, R),
            ("cg", "CGST",    90, R), ("sg", "SGST",    90, R),
            ("ig", "IGST",    90, R), ("t",  "Total",  110, R)], height=10)
        self.detail_tbl.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def _mnum(self):
        return _MONTHS.index(self.month.get()) + 1

    def refresh(self):
        from db.setup import gstr1_report
        rep   = gstr1_report(self.con, self.fy.get(), self._mnum())
        srows = [(s["kind"], s["rate"], inr(s["taxable"]), inr(s["cgst"]),
                  inr(s["sgst"]), inr(s["igst"]), inr(s["total"]))
                 for s in rep["summary"]]
        t = rep["totals"]
        srows.append((("", "Total", inr(t["taxable"]), inr(t["cgst"]),
                       inr(t["sgst"]), inr(t["igst"]), inr(t["total"])), "total"))
        self.summary_tbl.set_rows(srows)
        drows = [(disp_date(i["date"]), i["vno"],
                  (i["party"] + (" (CN)" if i["vtype"] == "Sales Return" else "")),
                  i["gstin"] or "-", i["supply"],
                  inr(i["taxable"]), _amt(i["cgst"]), _amt(i["sgst"]),
                  _amt(i["igst"]), inr(i["total"])) for i in rep["invoices"]]
        drows.append((("", "", f"Total ({len(rep['invoices'])} invoices)", "", "",
                       inr(t["taxable"]), inr(t["cgst"]), inr(t["sgst"]),
                       inr(t["igst"]), inr(t["total"])), "total"))
        self.detail_tbl.set_rows(drows)

    def _export_json(self):
        import json
        from db.setup import gstr1_json
        from utils import settings as _st
        st    = _st.load_settings()
        gstin = (st.get("gstin") or "GSTIN").strip().upper().replace("/", "")
        default_name = f"GSTR1_{gstin}_{self.month.get()}_{self.fy.get()}.json"
        path = filedialog.asksaveasfilename(
            title="Save GSTR-1 JSON",
            defaultextension=".json",
            filetypes=[("JSON file", "*.json")],
            initialfile=default_name)
        if not path:
            return
        try:
            data = gstr1_json(self.con, self.fy.get(), self._mnum())
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("MUNIM", f"Could not save JSON:\n{e}")
            return
        messagebox.showinfo("MUNIM",
                            f"GSTR-1 JSON saved:\n{path}\n\n"
                            "Upload this file in the GST portal offline tool.")

    def export_data(self):
        from db.setup import gstr1_report
        rep  = gstr1_report(self.con, self.fy.get(), self._mnum())
        rows = [["SUMMARY", "", "", "", "", "", ""]]
        rows.append(["Type", "Rate %", "Taxable", "CGST", "SGST", "IGST", "Total"])
        for s in rep["summary"]:
            rows.append([s["kind"], s["rate"], s["taxable"], s["cgst"],
                         s["sgst"], s["igst"], s["total"]])
        t = rep["totals"]
        rows.append(["", "Total", t["taxable"], t["cgst"], t["sgst"], t["igst"], t["total"]])
        rows.append(["", "", "", "", "", "", ""])
        rows.append(["INVOICE DETAIL", "", "", "", "", "", ""])
        rows.append(["Date", "No.", "Party", "GSTIN", "Supply", "Taxable", "Total"])
        for i in rep["invoices"]:
            rows.append([disp_date(i["date"]), i["vno"], i["party"],
                         i["gstin"] or "", i["supply"], i["taxable"], i["total"]])
        title = f"GSTR-1 {self.month.get()} {self.fy.get()}"
        return title, ["Col1","Col2","Col3","Col4","Col5","Col6","Col7"], rows


class GSTR3BFrame(ReportBase):
    title_text = "GSTR-3B (Summary)"
    sub_text   = "Monthly GST: outward tax, ITC, net payable, and suggested payment breakdown."

    def __init__(self, master, con):
        super().__init__(master, con)
        from datetime import date as _d
        today = _d.today()
        default_month = (today.month - 3) % 12 or 12
        self.month = T.option_menu(self.bar, _MONTHS, width=130,
                                   command=lambda _v: self.refresh())
        self.month.set(_MONTHS[default_month - 1])
        self.month.pack(side="right", padx=(10, 0))
        self.table = DataTable(self, [
            ("s",  "Section",               380, L),
            ("tx", "Taxable / Amount (Rs)", 180, R),
            ("cg", "CGST (Rs)",             140, R),
            ("sg", "SGST (Rs)",             140, R),
            ("ig", "IGST (Rs)",             140, R)], height=26)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def _mnum(self):
        return _MONTHS.index(self.month.get()) + 1

    def refresh(self):
        from db.setup import gstr3b_report
        rep = gstr3b_report(self.con, self.fy.get(), self._mnum())
        o   = rep["outward"]
        i   = rep["net_itc"]
        ir  = rep["itc_reversed"]
        rcm = rep["rcm_liability"]
        n   = rep["net"]
        itc_used, cash, bal = rep["paid_by_itc"], rep["paid_by_cash"], rep["itc_balance"]

        rows = [
            # 3.1 OUTWARD
            (("3.1  OUTWARD SUPPLIES", "", "", "", ""), "head"),
            (("     (a) Outward taxable supplies (other than zero-rated, nil, exempted)",
              inr(o["taxable"]), inr(o["cgst"]), inr(o["sgst"]), inr(o["igst"])), None),
            (("     (b) Zero-rated / exports (not applicable)",
              "", "", "", ""), None),
            (("     (c) Other outward supplies (nil-rated, exempt)",
              inr(rep["nil_exempt"]), "", "", ""), None),
            (("     (d) Inward supplies liable to reverse charge (RCM)",
              inr(rcm["taxable"]), inr(rcm["cgst"]), inr(rcm["sgst"]), inr(rcm["igst"])), None),

            # 3.2 INTER-STATE B2C
            (("3.2  INTER-STATE SUPPLIES TO UNREGISTERED PERSONS",
              inr(rep["b2c_inter"]["taxable"]), "", "",
              inr(rep["b2c_inter"]["igst"])), "head"),

            # 4 ITC
            (("4    ELIGIBLE ITC", "", "", "", ""), "head"),
            (("     (A) ITC available — normal purchases",
              "", inr(rep["itc"]["cgst"]), inr(rep["itc"]["sgst"]),
              inr(rep["itc"]["igst"])), None),
            (("     (B) ITC reversed — RCM (self-assessed)",
              "", inr(ir["cgst"]), inr(ir["sgst"]), inr(ir["igst"])), None),
            (("     (C) Net ITC available (A − B)",
              "", inr(i["cgst"]), inr(i["sgst"]), inr(i["igst"])), None),
            (("     (D) Ineligible ITC",
              "", "—", "—", "—"), None),

            # NET PAYABLE
            (("     Net GST payable after cross-utilisation",
              "", inr(n["cgst"]), inr(n["sgst"]), inr(n["igst"])), "total"),
            (("     Total net payable", inr(n["total"]), "", "", ""), "total"),

            # 5 EXEMPT INWARD
            (("5    Exempt / nil-rated inward supplies", "", "—", "—", "—"), "head"),

            # 6.1 PAYMENT
            (("", "", "", "", ""), None),
            (("6.1  SUGGESTED PAYMENT BREAKDOWN (ITC cross-utilisation applied)",
              "", "", "", ""), "head"),
            (("     Paid through ITC",
              "", inr(itc_used["cgst"]), inr(itc_used["sgst"]),
              inr(itc_used["igst"])), None),
            (("     Paid in cash",
              "", inr(cash["cgst"]), inr(cash["sgst"]), inr(cash["igst"])), None),
            (("     Unused ITC balance (c/f)",
              "", inr(bal["cgst"]), inr(bal["sgst"]), inr(bal["igst"])), None),

            # 6.2 TDS/TCS
            (("6.2  TDS / TCS credits", "", "—", "—", "—"), "head"),

            # REFERENCE
            (("", "", "", "", ""), None),
            (("Closing stock value (reference, from Stock Summary)",
              inr(rep["stock_value"]), "", "", ""), "head"),
        ]
        self.table.set_rows(rows)

    def export_data(self):
        from db.setup import gstr3b_report
        rep = gstr3b_report(self.con, self.fy.get(), self._mnum())
        o   = rep["outward"]
        i   = rep["net_itc"]
        ir  = rep["itc_reversed"]
        rcm = rep["rcm_liability"]
        n   = rep["net"]
        itc_used, cash, bal = rep["paid_by_itc"], rep["paid_by_cash"], rep["itc_balance"]
        rows = [
            ["3.1  OUTWARD SUPPLIES",    "", "", "", ""],
            ["(a) Outward taxable",       o["taxable"], o["cgst"],  o["sgst"],  o["igst"]],
            ["(b) Zero-rated / exports",  0,            0,          0,          0],
            ["(c) Nil-rated, exempt",     rep["nil_exempt"], "",    "",         ""],
            ["(d) RCM inward",            rcm["taxable"], rcm["cgst"], rcm["sgst"], rcm["igst"]],
            ["3.2  Inter-state B2C",      rep["b2c_inter"]["taxable"], "", "",
                                          rep["b2c_inter"]["igst"]],
            ["4    ELIGIBLE ITC",         "", "", "", ""],
            ["(A) ITC available",         "",
             rep["itc"]["cgst"], rep["itc"]["sgst"], rep["itc"]["igst"]],
            ["(B) ITC reversed (RCM)",    "", ir["cgst"],  ir["sgst"],  ir["igst"]],
            ["(C) Net ITC",               "", i["cgst"],   i["sgst"],   i["igst"]],
            ["(D) Ineligible ITC",        "", 0,           0,           0],
            ["Net payable",               "", n["cgst"],   n["sgst"],   n["igst"]],
            ["Total net payable",         n["total"],      "", "",       ""],
            ["5    Exempt inward",        0,  0,           0,           0],
            ["6.1  Paid through ITC",     "",
             itc_used["cgst"], itc_used["sgst"], itc_used["igst"]],
            ["6.1  Paid in cash",         "",
             cash["cgst"],     cash["sgst"],     cash["igst"]],
            ["6.1  Unused ITC (c/f)",     "",
             bal["cgst"],      bal["sgst"],      bal["igst"]],
            ["6.2  TDS/TCS",             0, 0, 0, 0],
            ["Closing stock (reference)", rep["stock_value"], "", "", ""],
        ]
        headers = ["Section", "Amount (Rs)", "CGST", "SGST", "IGST"]
        title   = f"GSTR-3B {self.month.get()} {self.fy.get()}"
        return title, headers, rows


# ── ADD at bottom of report_screens.py ───────────────────────────────────────

class CashFlowFrame(ReportBase):
    title_text = "Cash Flow Statement"
    sub_text   = ("Sources and uses of cash: operating, financing, "
                  "and investing activities.")

    def __init__(self, master, con):
        super().__init__(master, con)
        self.table = DataTable(self, [
            ("s", "Particulars", 400, L),
            ("a", "Amount (Rs)", 160, R)], height=18)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def refresh(self):
        from db.reports import cash_flow
        cf   = cash_flow(self.con, self.fy.get())
        rows = []

        def section(title, items, total):
            rows.append((("", ""), "head"))
            rows.append(((title, ""), "head"))
            for name, amt in items:
                rows.append((name, _amt(amt)))
            rows.append((("  Total", inr(total)), "total"))

        section("A. OPERATING ACTIVITIES",
                cf["operating"]["items"], cf["operating"]["total"])
        section("B. FINANCING ACTIVITIES",
                cf["financing"]["items"], cf["financing"]["total"])
        section("C. INVESTING ACTIVITIES",
                cf["investing"]["items"], cf["investing"]["total"])

        rows.append((("", ""), None))
        rows.append((("Net increase / (decrease) in cash",
                      inr(cf["net_change"])), "total"))
        rows.append((("Opening cash & bank balance",
                      inr(cf["opening_cash"])), None))
        rows.append((("Closing cash & bank balance",
                      inr(cf["closing_cash"])), "total"))
        self.table.set_rows(rows)

    def export_data(self):
        from db.reports import cash_flow
        cf   = cash_flow(self.con, self.fy.get())
        rows = []
        for section, key in (("Operating", "operating"),
                              ("Financing", "financing"),
                              ("Investing", "investing")):
            rows.append([section, ""])
            for name, amt in cf[key]["items"]:
                rows.append([name, amt])
            rows.append(["Total", cf[key]["total"]])
            rows.append(["", ""])
        rows.append(["Net change in cash",    cf["net_change"]])
        rows.append(["Opening cash & bank",   cf["opening_cash"]])
        rows.append(["Closing cash & bank",   cf["closing_cash"]])
        return (f"Cash Flow {self.fy.get()}",
                ["Particulars", "Amount (Rs)"], rows)


class PartyStatementFrame(ReportBase):
    title_text = "Party Statement"
    sub_text   = ("Full account statement for one party — "
                  "opening, all transactions, closing.")
    with_fy    = True

    def __init__(self, master, con):
        super().__init__(master, con)
        names = [p["name"] for p in con.execute(
            "SELECT name FROM parties ORDER BY name COLLATE NOCASE")]
        self.party = T.combo(self.bar, names, width=240,
                             command=lambda _v: self.refresh())
        self.party.set(names[0] if names else "")
        self.party.pack(side="right", padx=(10, 0))
        T.button(self.bar, "Show", self.refresh, width=70).pack(
            side="right", padx=(10, 0))

        self.summary = ctk.CTkLabel(self, text="", font=T.f(13, "bold"),
                                    text_color=T.TEXT)
        self.summary.pack(anchor="w", padx=28, pady=(0, 8))
        self.table = DataTable(self, [
            ("dt", "Date",        100, L), ("v",  "Voucher",    140, L),
            ("n",  "Narration",   280, L), ("d",  "Debit (Rs)", 130, R),
            ("c",  "Credit (Rs)", 130, R), ("b",  "Balance",    150, R)],
            height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def refresh(self):
        from db.reports import party_statement
        name = self.party.get().strip()
        if not name:
            return
        try:
            ps = party_statement(self.con, name, self.fy.get())
        except ValueError as e:
            self.summary.configure(text=str(e), text_color=T.DANGER)
            self.table.set_rows([])
            return
        rows = [(("", "", "Opening balance", "", "",
                  f"{inr(ps['opening'])} {ps['opening_side']}"), "head")]
        for x in ps["rows"]:
            rows.append((disp_date(x["date"]),
                         f"{x['vtype']} #{x['vno']}",
                         x["narration"],
                         _amt(x["dr"]), _amt(x["cr"]),
                         f"{inr(x['balance'])} {x['side']}"))
        rows.append((("", "", "Total",
                      inr(ps["total_dr"]), inr(ps["total_cr"]),
                      f"{inr(ps['closing'])} {ps['closing_side']}"), "total"))
        self.table.set_rows(rows)
        gstin = f"  |  GSTIN: {ps['gstin']}" if ps["gstin"] else ""
        self.summary.configure(
            text=(f"{name} ({ps['ptype']}){gstin}   |   "
                  f"Closing: Rs {inr(ps['closing'])} {ps['closing_side']}"),
            text_color=T.TEXT)

    def export_data(self):
        from db.reports import party_statement
        name = self.party.get().strip()
        if not name:
            return "Party Statement", [], []
        try:
            ps = party_statement(self.con, name, self.fy.get())
        except ValueError:
            return "Party Statement", [], []
        headers = ["Date", "Voucher", "Narration",
                   "Debit (Rs)", "Credit (Rs)", "Balance"]
        rows = [[disp_date(x["date"]), f"{x['vtype']} #{x['vno']}",
                 x["narration"], x["dr"], x["cr"],
                 f"{x['balance']} {x['side']}"]
                for x in ps["rows"]]
        return (f"Party Statement {name} {self.fy.get()}", headers, rows)


class BankReconFrame(ReportBase):
    title_text = "Bank Reconciliation"
    sub_text   = ("Import your bank statement CSV and match entries to your books. "
                  "Unmatched items on either side need investigation.")
    with_fy    = False

    def __init__(self, master, con):
        super().__init__(master, con)
        self.own_controls  = True
        self._recon_rows   = []

        ctrl = T.card(self)
        ctrl.pack(fill="x", padx=28, pady=(0, 10))

        bank_names = [r["name"] for r in con.execute(
            "SELECT name FROM accounts "
            "WHERE grp IN ('Bank Accounts','Cash-in-hand') "
            "ORDER BY name")]
        if not bank_names:
            bank_names = ["Bank", "Cash"]

        self.account = T.option_menu(ctrl, bank_names, width=160,
                                     command=lambda _v: self.refresh())
        self.account.set("Bank" if "Bank" in bank_names else bank_names[0])

        ctk.CTkLabel(ctrl, text="Account", font=T.f(12),
                     text_color=T.MUTED).grid(
            row=0, column=0, sticky="w", padx=(20, 8), pady=(12, 2))
        self.account.grid(row=1, column=0, padx=(20, 8), pady=(0, 14))

        T.button(ctrl, "Import CSV", self._import_csv, width=120).grid(
            row=1, column=1, padx=8, pady=(0, 14))
        T.button(ctrl, "Clear all", self._clear, width=100,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").grid(row=1, column=2, padx=8, pady=(0, 14))
        T.button(ctrl, "Export Excel", self.export, width=120,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").grid(row=1, column=3, padx=8, pady=(0, 14))

        ctk.CTkLabel(ctrl,
                     text="CSV format: Date (DD-MM-YYYY), Description, Amount, Dr/Cr",
                     font=T.f(11), text_color=T.MUTED).grid(
            row=2, column=0, columnspan=4, sticky="w", padx=20, pady=(0, 10))

        self.summary_lbl = ctk.CTkLabel(self, text="", font=T.f(13, "bold"),
                                        text_color=T.TEXT)
        self.summary_lbl.pack(anchor="w", padx=28, pady=(0, 8))

        self.table = DataTable(self, [
            ("dt",  "Stmt Date",   100, L),
            ("dsc", "Description", 240, L),
            ("amt", "Amount",      110, R),
            ("typ", "Dr/Cr",        60, L),
            ("mat", "Best match",  200, L),
            ("sts", "Status",       90, L)], height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 10))
        self.table.on_open(self._on_row_open)

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=28, pady=(0, 16))
        T.button(foot, "Mark selected as reconciled",
                 self._reconcile_selected, width=220).pack(side="left")
        self.foot_msg = ctk.CTkLabel(foot, text="", font=T.f(12),
                                     text_color=T.MUTED)
        self.foot_msg.pack(side="left", padx=12)
        self.refresh()

    def _import_csv(self):
        from tkinter import filedialog, messagebox
        import csv
        from db.setup import import_bank_statement
        from utils.fmt import parse_date
        path = filedialog.askopenfilename(
            title="Open bank statement CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        rows = []
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                for line in reader:
                    if len(line) < 4:
                        continue
                    try:
                        d     = parse_date(line[0].strip())
                        desc  = line[1].strip()
                        amt   = float(line[2].strip().replace(",", ""))
                        dr_cr = line[3].strip().upper()
                        dr_cr = ("Dr" if dr_cr in ("DR", "D", "DEBIT")
                                 else "Cr")
                        rows.append((d.isoformat(), desc, amt, dr_cr))
                    except Exception:
                        continue
        except Exception as e:
            messagebox.showerror("MUNIM", f"Could not read CSV:\n{e}")
            return
        if not rows:
            messagebox.showwarning(
                "MUNIM",
                "No valid rows found.\n\n"
                "Expected format: Date, Description, Amount, Dr/Cr")
            return
        from db.setup import import_bank_statement as _ibs
        count = _ibs(self.con, self.account.get(), rows)
        messagebox.showinfo("MUNIM", f"{count} rows imported.")
        self.refresh()

    def _clear(self):
        from tkinter import messagebox
        from db.setup import clear_recon
        if not messagebox.askyesno(
                "Clear reconciliation",
                "Remove all imported statement rows for this account?"):
            return
        clear_recon(self.con, self.account.get())
        self.refresh()

    def refresh(self):
        from db.setup import get_recon_rows, recon_summary
        account = self.account.get()
        rows    = get_recon_rows(self.con, account)
        summary = recon_summary(self.con, account)
        self.summary_lbl.configure(
            text=(f"Total: {summary['total']} rows  |  "
                  f"Matched: {summary['matched']}  |  "
                  f"Unmatched: {summary['unmatched']}  |  "
                  f"Statement balance: Rs {inr(summary['stmt_balance'])}"))
        self._recon_rows = rows
        out = []
        for r in rows:
            match_text = ""
            if r["matches"]:
                m = r["matches"][0]
                match_text = f"{m['vtype']} #{m['vno']}"
            status = ("✓ Matched"  if r["voucher_id"] else
                      "Suggested"  if r["matches"]    else
                      "Unmatched")
            out.append(((disp_date(r["date"]), r["desc"][:40],
                          inr(r["amount"]), r["type"],
                          match_text, status),
                         "total" if status == "✓ Matched" else None,
                         r["id"]))
        self.table.set_rows(out)

    def _on_row_open(self, recon_id):
        from db.setup import reconcile_row
        row = next((r for r in self._recon_rows if r["id"] == recon_id), None)
        if not row:
            return
        if row["matches"]:
            reconcile_row(self.con, recon_id, row["matches"][0]["id"])
            self.foot_msg.configure(
                text=(f"Matched to "
                      f"{row['matches'][0]['vtype']} #{row['matches'][0]['vno']}"),
                text_color=T.OK)
        else:
            reconcile_row(self.con, recon_id, None)
            self.foot_msg.configure(
                text="Marked reconciled (no voucher match)",
                text_color=T.MUTED)
        self.refresh()

    def _reconcile_selected(self):
        key = self.table.selected_key()
        if not key:
            self.foot_msg.configure(text="Select a row first",
                                    text_color=T.DANGER)
            return
        self._on_row_open(key)

    def export_data(self):
        from db.setup import get_recon_rows
        rows    = get_recon_rows(self.con, self.account.get())
        headers = ["Date", "Description", "Amount", "Dr/Cr",
                   "Best match", "Status"]
        data    = []
        for r in rows:
            match_text = ""
            if r["matches"]:
                m = r["matches"][0]
                match_text = f"{m['vtype']} #{m['vno']}"
            status = ("Matched"   if r["voucher_id"] else
                      "Suggested" if r["matches"]    else
                      "Unmatched")
            data.append([disp_date(r["date"]), r["desc"],
                          r["amount"], r["type"], match_text, status])
        return (f"Bank Reconciliation {self.account.get()}",
                headers, data)