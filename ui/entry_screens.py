import customtkinter as ctk
from db import setup as s, billing as b
from ui import theme as T
from utils import settings
from utils.fmt import inr, parse_amount, parse_date, today_str


def _lbl(parent, text, **grid):
    w = ctk.CTkLabel(parent, text=text, font=T.f(12), text_color=T.MUTED)
    w.grid(**grid)
    return w


class JournalFrame(ctk.CTkFrame):
    VTYPES = ["Journal", "Payment", "Receipt", "Contra"]

    def __init__(self, master, con):
        super().__init__(master, fg_color="transparent")
        self.con, self.rows = con, []
        self.names = [r["name"] for r in con.execute(
            "SELECT name FROM accounts ORDER BY name COLLATE NOCASE")]
        T.title(self, "Voucher Entry", "Journal, payment, receipt and contra. Total debit must equal total credit."
                ).pack(anchor="w", padx=28, pady=(24, 12))
        card = T.card(self)
        card.pack(fill="x", padx=28)
        self.vtype = T.option_menu(card, self.VTYPES, width=150)
        self.date = T.entry(card, width=150)
        self.date.insert(0, today_str())
        self.narr = T.entry(card, "Narration (optional)", width=420)
        _lbl(card, "Voucher type", row=0, column=0, sticky="w", padx=(20, 8), pady=(14, 2))
        _lbl(card, "Date (DD-MM-YYYY)", row=0, column=1, sticky="w", padx=8, pady=(14, 2))
        _lbl(card, "Narration", row=0, column=2, sticky="w", padx=8, pady=(14, 2))
        self.vtype.grid(row=1, column=0, padx=(20, 8), pady=(0, 14))
        self.date.grid(row=1, column=1, padx=8, pady=(0, 14))
        self.narr.grid(row=1, column=2, padx=8, pady=(0, 14))

        lines = T.card(self)
        lines.pack(fill="x", padx=28, pady=14)
        lines.grid_columnconfigure(0, weight=1)
        self.area = ctk.CTkScrollableFrame(lines, fg_color="transparent", height=250)
        self.area.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=(10, 4))
        _lbl(self.area, "Account", row=0, column=0, sticky="w", padx=(10, 6))
        _lbl(self.area, "Debit (Rs)", row=0, column=1, sticky="w", padx=8)
        _lbl(self.area, "Credit (Rs)", row=0, column=2, sticky="w", padx=8)
        for _ in range(4):
            self.add_line()
        bar = ctk.CTkFrame(lines, fg_color="transparent")
        bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=20, pady=(4, 14))
        T.button(bar, "+ Add line", self.add_line, width=110,
                 fg_color="#E7ECF5", text_color=T.TEXT, hover_color="#DCE3F0").pack(side="left")
        self.total = ctk.CTkLabel(bar, text="", font=T.f(13, "bold"))
        self.total.pack(side="right")

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=28)
        T.button(foot, "Save voucher", self.save, width=160).pack(side="left")
        self.msg = ctk.CTkLabel(foot, text="", font=T.f(13))
        self.msg.pack(side="left", padx=16)
        self.update_totals()

    def add_line(self):
        r = len(self.rows) + 1
        acc = T.combo(self.area, self.names, width=400)
        acc.set("")
        dr, cr = T.entry(self.area, "0.00", width=160), T.entry(self.area, "0.00", width=160)
        acc.grid(row=r, column=0, padx=(8, 6), pady=4)
        dr.grid(row=r, column=1, padx=6, pady=4)
        cr.grid(row=r, column=2, padx=6, pady=4)
        for e in (dr, cr):
            e.bind("<KeyRelease>", self.update_totals)
        self.rows.append((acc, dr, cr))

    def _sums(self):
        td = tc = 0.0
        for _a, dr, cr in self.rows:
            try:
                td += parse_amount(dr.get()); tc += parse_amount(cr.get())
            except ValueError:
                pass
        return round(td, 2), round(tc, 2)

    def update_totals(self, _e=None):
        td, tc = self._sums()
        diff = round(td - tc, 2)
        ok = diff == 0 and td > 0
        self.total.configure(
            text=f"Debit {inr(td)}     Credit {inr(tc)}     Difference {inr(abs(diff))}",
            text_color=T.OK if ok else T.MUTED)

    def save(self):
        try:
            d = parse_date(self.date.get())
            lines = []
            for acc, dr, cr in self.rows:
                name, a, c = acc.get().strip(), parse_amount(dr.get()), parse_amount(cr.get())
                if not name and not a and not c:
                    continue
                if not name:
                    raise ValueError("Pick an account for every line that has an amount")
                if a and c:
                    raise ValueError(f"{name}: enter either Debit or Credit, not both")
                if not a and not c:
                    raise ValueError(f"{name}: enter an amount")
                lines.append((name, a, c))
            td, tc = self._sums()
            if td != tc:
                raise ValueError(f"Not balanced: debit {inr(td)} vs credit {inr(tc)}")
            vno = s.post_voucher(self.con, self.vtype.get(), d, self.narr.get().strip(), lines)
        except ValueError as e:
            self.msg.configure(text=str(e), text_color=T.DANGER)
            return
        for acc, dr, cr in self.rows:
            acc.set("")
            dr.delete(0, "end"); cr.delete(0, "end")
        self.narr.delete(0, "end")
        self.update_totals()
        self.msg.configure(text=f"{self.vtype.get()} voucher no. {vno} saved", text_color=T.OK)


class TradeFrame(ctk.CTkFrame):
    """Sales invoice or purchase bill with GST. kind is 'Sales' or 'Purchase'."""
    GST_RATES = ["0", "5", "12", "18", "28"]
    ROWS = 5

    def __init__(self, master, con, kind):
        super().__init__(master, fg_color="transparent")
        self.con, self.kind, self.rows = con, kind, []
        sales = kind == "Sales"
        ptype = "Customer" if sales else "Supplier"
        self.parties = [p["name"] for p in s.list_parties(con, ptype)] + ["Cash"]
        self.company_gstin = settings.load_settings().get("gstin", "")
        T.title(self, "Sales Invoice" if sales else "Purchase Bill",
                "GST is added per rate. Choose inter-state to charge IGST instead of CGST + SGST."
                ).pack(anchor="w", padx=28, pady=(24, 12))
        top = T.card(self)
        top.pack(fill="x", padx=28)
        self.date = T.entry(top, width=150)
        self.date.insert(0, today_str())
        self.party = T.combo(top, self.parties, width=330, command=self.party_chosen)
        self.party.set(self.parties[0])
        self.inter = ctk.CTkCheckBox(top, text="Inter-state (IGST)", command=self.calc, font=T.f(13),
                                     text_color=T.TEXT, fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER)
        self.narr = T.entry(top, "Narration (optional)", width=330)
        _lbl(top, "Date (DD-MM-YYYY)", row=0, column=0, sticky="w", padx=(20, 8), pady=(14, 2))
        _lbl(top, "Customer" if sales else "Supplier", row=0, column=1, sticky="w", padx=8, pady=(14, 2))
        _lbl(top, "Narration", row=0, column=3, sticky="w", padx=8, pady=(14, 2))
        self.date.grid(row=1, column=0, padx=(20, 8), pady=(0, 14))
        self.party.grid(row=1, column=1, padx=8, pady=(0, 14))
        self.inter.grid(row=1, column=2, padx=12, pady=(0, 14))
        self.narr.grid(row=1, column=3, padx=8, pady=(0, 14))

        items = T.card(self)
        items.pack(fill="x", padx=28, pady=14)
        for c, (h, w) in enumerate((("Item", 0), ("Qty", 0), ("Rate (Rs)", 0), ("GST %", 0), ("Amount", 0))):
            _lbl(items, h, row=0, column=c, sticky="w", padx=(20 if c == 0 else 6, 6), pady=(12, 0))
        for r in range(self.ROWS):
            desc = T.entry(items, "Description", width=330)
            qty = T.entry(items, "1", width=90)
            rate = T.entry(items, "0.00", width=130)
            gst = T.option_menu(items, self.GST_RATES, width=90, command=lambda _v: self.calc())
            gst.set("18")
            amt = ctk.CTkLabel(items, text="", width=130, anchor="e", font=T.f(13), text_color=T.TEXT)
            for c, w in enumerate((desc, qty, rate, gst, amt)):
                w.grid(row=r + 1, column=c, padx=(20 if c == 0 else 6, 6), pady=4)
            for e in (qty, rate):
                e.bind("<KeyRelease>", self.calc)
            self.rows.append((desc, qty, rate, gst, amt))
        self.summary = ctk.CTkLabel(items, text="", font=T.f(13, "bold"), text_color=T.TEXT)
        self.summary.grid(row=self.ROWS + 1, column=0, columnspan=5, sticky="e", padx=20, pady=(8, 14))

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=28)
        T.button(foot, "Save " + ("invoice" if sales else "bill"), self.save, width=170).pack(side="left")
        self.msg = ctk.CTkLabel(foot, text="", font=T.f(13))
        self.msg.pack(side="left", padx=16)
        self.party_chosen(self.party.get())

    def party_chosen(self, name):
        row = self.con.execute("SELECT gstin FROM parties WHERE name=?", (name,)).fetchone()
        if b.is_interstate(row["gstin"] if row else "", self.company_gstin):
            self.inter.select()
        else:
            self.inter.deselect()
        self.calc()

    def _collect(self):
        items = []
        for desc, qty, rate, gst, _amt in self.rows:
            d, q, r = desc.get().strip(), qty.get().strip(), rate.get().strip()
            if not (d or q or r):
                continue
            if not q or not r:
                raise ValueError("Every item needs a quantity and a rate")
            items.append((d or "Item", parse_amount(q), parse_amount(r), float(gst.get())))
        return items

    def calc(self, _e=None):
        for _d, qty, rate, _g, amt in self.rows:
            try:
                q, rt = parse_amount(qty.get()), parse_amount(rate.get())
                amt.configure(text=inr(q * rt) if q and rt else "")
            except ValueError:
                amt.configure(text="")
        try:
            t = b.compute_tax(self._collect(), bool(self.inter.get()))
        except ValueError:
            self.summary.configure(text="")
            return
        k = lambda v: inr(v / 100)
        tax = f"IGST {k(t['igst'])}" if self.inter.get() else f"CGST {k(t['cgst'])}   SGST {k(t['sgst'])}"
        self.summary.configure(text=f"Taxable {k(t['taxable'])}     {tax}     Total {k(t['total'])}")

    def save(self):
        try:
            d = parse_date(self.date.get())
            post = b.post_sale if self.kind == "Sales" else b.post_purchase
            res = post(self.con, d, self.party.get().strip(), self._collect(),
                       bool(self.inter.get()), self.narr.get().strip())
        except ValueError as e:
            self.msg.configure(text=str(e), text_color=T.DANGER)
            return
        for desc, qty, rate, _g, amt in self.rows:
            for e in (desc, qty, rate):
                e.delete(0, "end")
            amt.configure(text="")
        self.narr.delete(0, "end")
        self.summary.configure(text="")
        self.msg.configure(text=f"{self.kind} no. {res['vno']} saved. Total Rs {inr(res['total'])}",
                           text_color=T.OK)
