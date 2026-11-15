from datetime import date
import customtkinter as ctk
from db import setup as s, reports as r
from ui import theme as T
from ui.widgets import DataTable
from utils.fmt import inr, parse_amount, parse_date, disp_date

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
        self.bar = ctk.CTkFrame(head, fg_color="transparent")
        self.bar.pack(side="right")
        if self.with_fy:
            self.fy = T.option_menu(self.bar, s.fy_choices(con), width=120,
                                    command=lambda _v: self.refresh())
            self.fy.set(s.fy_of(date.today()))
            self.fy.pack(side="right", padx=(10, 0))


class TrialBalanceFrame(ReportBase):
    title_text, sub_text = "Trial Balance", "Closing balances of every ledger account."

    def __init__(self, master, con):
        super().__init__(master, con)
        self.table = DataTable(self, [("p", "Particulars", 420, L), ("d", "Debit (Rs)", 160, R),
                                      ("c", "Credit (Rs)", 160, R)], height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

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
    title_text, sub_text, with_fy = "Day Book", "All vouchers between two dates.", False

    def __init__(self, master, con):
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
        self.msg = ctk.CTkLabel(self, text="", font=T.f(13), text_color=T.DANGER)
        self.msg.pack(anchor="w", padx=28)
        self.table = DataTable(self, [("dt", "Date", 100, L), ("v", "Voucher", 130, L),
                                      ("p", "Particulars", 380, L), ("d", "Debit (Rs)", 130, R),
                                      ("c", "Credit (Rs)", 130, R)], height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(4, 24))
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
            rows.append(((disp_date(v["date"]), f"{v['vtype']} #{v['vno']}", v["narration"], "", ""), "head"))
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
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28)
        body.grid_columnconfigure((0, 1), weight=1, uniform="s")
        body.grid_rowconfigure(1, weight=1)
        cols = [("p", "Particulars", 260, L), ("a", "Amount (Rs)", 130, R)]
        self.ltitle = ctk.CTkLabel(body, text="", font=T.f(14, "bold"), text_color=T.TEXT)
        self.rtitle = ctk.CTkLabel(body, text="", font=T.f(14, "bold"), text_color=T.TEXT)
        self.ltitle.grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.rtitle.grid(row=0, column=1, sticky="w", padx=(10, 0), pady=(0, 6))
        self.left, self.right = DataTable(body, cols, height=13), DataTable(body, cols, height=13)
        self.left.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self.right.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        self.footer = ctk.CTkLabel(self, text="", font=T.f(15, "bold"))
        self.footer.pack(anchor="w", padx=28, pady=(10, 20))
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
        if net >= 0:
            left.append(("Net Profit", net))
        else:
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
