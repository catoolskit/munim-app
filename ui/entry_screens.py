import customtkinter as ctk
from db import setup as s, billing as b
from ui import theme as T
from ui.dialogs import PartyQuickDialog
from ui.voucher_dialog import _num
from ui.widgets import DataTable
from ui.ux import Autocomplete, chain_enter, focus_later
from utils import settings
from utils.fmt import inr, parse_amount, parse_date, today_str, disp_date

GHOST = dict(fg_color="#E7ECF5", text_color=T.TEXT, hover_color="#DCE3F0")


def _lbl(parent, text, **grid):
    w = ctk.CTkLabel(parent, text=text, font=T.f(12), text_color=T.MUTED)
    w.grid(**grid)
    return w


class EntryBase(ctk.CTkFrame):
    """Shared behaviour: message line, 'View' button after saving, unsaved-work check."""
    def _init_base(self, con, username, opener):
        self.con, self.username, self.opener, self._last_vid = con, username, opener, None

    def _make_msg(self, foot):
        self.msg = ctk.CTkLabel(foot, text="", font=T.f(13))
        self.msg.pack(side="left", padx=16)
        self.view_btn = T.button(foot, "View", self._view, width=70, height=30, **GHOST)

    def ok(self, text, vtype=None, vno=None, vdate=None):
        self.msg.configure(text=text, text_color=T.OK)
        self._last_vid = s.find_voucher(self.con, vtype, vno, vdate) if vtype else None
        if self._last_vid and self.opener:
            self.view_btn.pack(side="left")
        else:
            self.view_btn.pack_forget()

    def err(self, text):
        self.msg.configure(text=text, text_color=T.DANGER)
        self.view_btn.pack_forget()

    def _view(self):
        if self._last_vid and self.opener:
            self.opener(self._last_vid, lambda: None)

    def is_dirty(self):
        return False


class JournalFrame(EntryBase):
    VTYPES = ["Journal", "Payment", "Receipt", "Contra"]

    def __init__(self, master, con, username="", edit_id=None, on_done=None, opener=None):
        super().__init__(master, fg_color="transparent")
        self._init_base(con, username, opener)
        self.rows, self.edit_id, self.on_done = [], edit_id, on_done
        self.names = [r["name"] for r in con.execute(
            "SELECT name FROM accounts ORDER BY name COLLATE NOCASE")]
        T.title(self, "Edit Voucher" if edit_id else "Voucher Entry",
                "Journal, payment, receipt and contra. Total debit must equal total credit. "
                "Enter moves to the next box, Ctrl+S saves."
                ).pack(anchor="w", padx=28, pady=(24, 12))
        card = T.card(self)
        card.pack(fill="x", padx=28)
        self.vtype = T.option_menu(card, self.VTYPES, width=150)
        self.date = T.entry(card, width=150)
        self.date.insert(0, today_str())
        self.narr = T.entry(card, "Narration (optional)", width=420)
        _lbl(card, "Voucher type", row=0, column=0, sticky="w", padx=(20, 8), pady=(14, 2))
        _lbl(card, "Date (type 15 or 1511 or 15-11-2026)", row=0, column=1, sticky="w", padx=8, pady=(14, 2))
        _lbl(card, "Narration", row=0, column=2, sticky="w", padx=8, pady=(14, 2))
        self.vtype.grid(row=1, column=0, padx=(20, 8), pady=(0, 14))
        self.date.grid(row=1, column=1, padx=8, pady=(0, 14))
        self.narr.grid(row=1, column=2, padx=8, pady=(0, 14))

        lines = T.card(self)
        lines.pack(fill="x", padx=28, pady=14)
        lines.grid_columnconfigure(0, weight=1)
        self.area = ctk.CTkScrollableFrame(lines, fg_color="transparent", height=250)
        self.area.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=(10, 4))
        _lbl(self.area, "Account (type to search)", row=0, column=0, sticky="w", padx=(10, 6))
        _lbl(self.area, "Debit (Rs)", row=0, column=1, sticky="w", padx=8)
        _lbl(self.area, "Credit (Rs)", row=0, column=2, sticky="w", padx=8)
        for _ in range(4):
            self.add_line(rechain=False)
        bar = ctk.CTkFrame(lines, fg_color="transparent")
        bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=20, pady=(4, 14))
        T.button(bar, "+ Add line", self.add_line, width=110, **GHOST).pack(side="left")
        self.total = ctk.CTkLabel(bar, text="", font=T.f(13, "bold"))
        self.total.pack(side="right")

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=28)
        T.button(foot, "Update voucher" if edit_id else "Save voucher", self.save, width=170).pack(side="left")
        self._make_msg(foot)
        self._rechain()
        if edit_id:
            self._prefill()
        else:
            focus_later(self.rows[0][0])
        self.update_totals()

    def _rechain(self):
        order = [self.date, self.narr]
        for acc, dr, cr in self.rows:
            order += [acc, dr, cr]
        chain_enter(order, self.add_line_and_focus)

    def add_line_and_focus(self):
        self.add_line()
        focus_later(self.rows[-1][0], 50)

    def _prefill(self):
        snap = s.voucher_snapshot(self.con, self.edit_id)
        self.vtype.set(snap["vtype"])
        self.date.delete(0, "end"); self.date.insert(0, disp_date(snap["vdate"]))
        self.narr.insert(0, snap["narration"] or "")
        while len(self.rows) < len(snap["lines"]):
            self.add_line(rechain=False)
        for (acc, dr, cr), ln in zip(self.rows, snap["lines"]):
            acc.set(ln["account"])
            if ln["dr"]:
                dr.insert(0, f"{ln['dr'] / 100:.2f}")
            if ln["cr"]:
                cr.insert(0, f"{ln['cr'] / 100:.2f}")
        self._rechain()

    def add_line(self, rechain=True):
        r = len(self.rows) + 1
        acc = T.combo(self.area, self.names, width=400)
        acc.set("")
        Autocomplete(acc, self.names)
        dr, cr = T.entry(self.area, "0.00", width=160), T.entry(self.area, "0.00", width=160)
        acc.grid(row=r, column=0, padx=(8, 6), pady=4)
        dr.grid(row=r, column=1, padx=6, pady=4)
        cr.grid(row=r, column=2, padx=6, pady=4)
        for e in (dr, cr):
            e.bind("<KeyRelease>", self.update_totals)
        self.rows.append((acc, dr, cr))
        if rechain:
            self._rechain()

    def is_dirty(self):
        if self.edit_id:
            return False
        return bool(self.narr.get().strip()) or any(
            a.get().strip() or d.get().strip() or c.get().strip() for a, d, c in self.rows)

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
        self.total.configure(
            text=f"Debit {inr(td)}     Credit {inr(tc)}     Difference {inr(abs(diff))}",
            text_color=T.OK if diff == 0 and td > 0 else T.MUTED)

    def save(self):
        try:
            d = parse_date(self.date.get())
            lines = []
            for acc, dr, cr in self.rows:
                ac = getattr(acc, "_ac", None)
                if ac:
                    ac.commit()
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
            if self.edit_id:
                s.update_voucher(self.con, self.edit_id, self.vtype.get(), d, self.narr.get().strip(),
                                 lines, self.username)
                vno = None
            else:
                vno = s.post_voucher(self.con, self.vtype.get(), d, self.narr.get().strip(), lines,
                                     self.username)
        except ValueError as e:
            self.err(str(e))
            return
        if self.edit_id:
            self.ok("Voucher updated")
            if self.on_done:
                self.after(60, self.on_done)
            return
        vt = self.vtype.get()
        for acc, dr, cr in self.rows:
            acc.set("")
            dr.delete(0, "end"); cr.delete(0, "end")
        self.narr.delete(0, "end")
        self.update_totals()
        self.ok(f"{vt} voucher no. {vno} saved", vt, vno, d)
        focus_later(self.rows[0][0], 50)


class TradeFrame(EntryBase):
    """Sales invoice or purchase bill with GST. kind is 'Sales' or 'Purchase'."""
    GST_RATES = ["0", "5", "12", "18", "28"]
    ROWS = 5

    def __init__(self, master, con, kind, username="", edit_id=None, on_done=None, opener=None):
        super().__init__(master, fg_color="transparent")
        self._init_base(con, username, opener)
        self.kind, self.rows = kind, []
        self.edit_id, self.on_done = edit_id, on_done
        self.sales = kind == "Sales"
        self.ptype = "Customer" if self.sales else "Supplier"
        self.parties = self._party_names()
        self.company_gstin = settings.load_settings().get("gstin", "")
        T.title(self, ("Edit " if edit_id else "") + ("Sales Invoice" if self.sales else "Purchase Bill"),
                "GST is added per rate. Enter moves to the next box, Ctrl+S saves."
                ).pack(anchor="w", padx=28, pady=(24, 12))
        top = T.card(self)
        top.pack(fill="x", padx=28)
        self.date = T.entry(top, width=140)
        self.date.insert(0, today_str())
        pw = ctk.CTkFrame(top, fg_color="transparent")
        self.party = T.combo(pw, self.parties, width=240, command=self.party_chosen)
        self.party.set(self.parties[0])
        self.party.pack(side="left")
        T.button(pw, "+ New", self.new_party, width=64, **GHOST).pack(side="left", padx=(6, 0))
        self.ac = Autocomplete(self.party, self.parties, on_pick=self.party_chosen)
        self.inter = ctk.CTkCheckBox(top, text="Inter-state (IGST)", command=self.calc, font=T.f(13),
                                     text_color=T.TEXT, fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER)
        self.narr = T.entry(top, "Narration (optional)", width=300)
        _lbl(top, "Date", row=0, column=0, sticky="w", padx=(20, 8), pady=(14, 2))
        _lbl(top, "Customer" if self.sales else "Supplier", row=0, column=1, sticky="w", padx=8, pady=(14, 2))
        _lbl(top, "Narration", row=0, column=3, sticky="w", padx=8, pady=(14, 2))
        self.date.grid(row=1, column=0, padx=(20, 8), pady=(0, 14))
        pw.grid(row=1, column=1, padx=8, pady=(0, 14))
        self.inter.grid(row=1, column=2, padx=12, pady=(0, 14))
        self.narr.grid(row=1, column=3, padx=8, pady=(0, 14))

        items = T.card(self)
        items.pack(fill="x", padx=28, pady=14)
        for c, h in enumerate(("Item", "Qty", "Rate (Rs)", "GST %", "", "Amount")):
            _lbl(items, h, row=0, column=c, sticky="w", padx=(20 if c == 0 else 6, 6), pady=(12, 0))
        order = [self.date, self.party, self.narr]
        for r in range(self.ROWS):
            desc = T.entry(items, "Description", width=330)
            qty = T.entry(items, "1", width=90)
            rate = T.entry(items, "0.00", width=130)
            gst = T.option_menu(items, self.GST_RATES, width=90, command=lambda _v: self.calc())
            gst.set("18")
            amt = ctk.CTkLabel(items, text="", width=130, anchor="e", font=T.f(13), text_color=T.TEXT)
            desc.grid(row=r + 1, column=0, padx=(20, 6), pady=4)
            qty.grid(row=r + 1, column=1, padx=6, pady=4)
            rate.grid(row=r + 1, column=2, padx=6, pady=4)
            gst.grid(row=r + 1, column=3, columnspan=2, padx=6, pady=4, sticky="w")
            amt.grid(row=r + 1, column=5, padx=6, pady=4)
            for e in (qty, rate):
                e.bind("<KeyRelease>", self.calc)
            self.rows.append((desc, qty, rate, gst, amt))
            order += [desc, qty, rate]
        self.summary = ctk.CTkLabel(items, text="", font=T.f(13, "bold"), text_color=T.TEXT)
        self.summary.grid(row=self.ROWS + 1, column=0, columnspan=6, sticky="e", padx=20, pady=(8, 14))

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=28)
        self.paid = self.mode = None
        if not edit_id:
            ctk.CTkLabel(foot, text="Received now (Rs)" if self.sales else "Paid now (Rs)",
                         font=T.f(12), text_color=T.MUTED).pack(side="left", padx=(0, 8))
            self.paid = T.entry(foot, "0.00", width=120)
            self.paid.pack(side="left", padx=(0, 8))
            self.paid.bind("<KeyRelease>", self.calc)
            self.mode = T.option_menu(foot, ["Cash", "Bank"], width=90)
            self.mode.pack(side="left", padx=(0, 18))
            order.append(self.paid)
        T.button(foot, ("Update " if edit_id else "Save ") + ("invoice" if self.sales else "bill"),
                 self.save, width=160).pack(side="left")
        self._make_msg(foot)
        chain_enter(order, self.save if not edit_id else None)
        if edit_id:
            self._prefill()
        else:
            self.party_chosen(self.party.get())
            focus_later(self.rows[0][0])

    def _party_names(self):
        return [p["name"] for p in s.list_parties(self.con, self.ptype)] + ["Cash"]

    def new_party(self):
        PartyQuickDialog(self.winfo_toplevel(), self.con, self.ptype, self._party_added)

    def _party_added(self, name):
        self.parties = self._party_names()
        self.ac.set_names(self.parties)
        self.party.set(name)
        self.party_chosen(name)
        focus_later(self.rows[0][0], 50)

    def _prefill(self):
        snap = s.voucher_snapshot(self.con, self.edit_id)
        inv = snap["invoice"]
        self.date.delete(0, "end"); self.date.insert(0, disp_date(snap["vdate"]))
        self.party.set(inv["party"])
        (self.inter.select if inv["interstate"] else self.inter.deselect)()
        self.narr.insert(0, snap["narration"] or "")
        for (desc, qty, rate, gst, _a), it in zip(self.rows, inv["items"]):
            desc.insert(0, it["description"]); qty.insert(0, _num(it["qty"])); rate.insert(0, _num(it["rate"]))
            gst.set(_num(it["gst"]))
        self.calc()

    def is_dirty(self):
        if self.edit_id:
            return False
        return any(d.get().strip() or q.get().strip() or r.get().strip() for d, q, r, _g, _a in self.rows)

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
        extra = ""
        if self.paid is not None:
            try:
                p = parse_amount(self.paid.get())
            except ValueError:
                p = 0
            if p:
                word = "Received" if self.sales else "Paid"
                extra = f"     {word} {inr(p)}     Due {inr(t['total'] / 100 - p)}"
        self.summary.configure(text=f"Taxable {k(t['taxable'])}     {tax}     Total {k(t['total'])}{extra}")

    def save(self):
        try:
            d = parse_date(self.date.get())
            ac = getattr(self.party, "_ac", None)
            if ac:
                ac.commit()
            party = self.party.get().strip()
            if self.edit_id:
                res = b.update_invoice(self.con, self.edit_id, d, party, self._collect(),
                                       bool(self.inter.get()), self.narr.get().strip(), self.username)
            else:
                post = b.post_sale if self.sales else b.post_purchase
                got = parse_amount(self.paid.get()) if self.paid else 0
                res = post(self.con, d, party, self._collect(), bool(self.inter.get()),
                           self.narr.get().strip(), self.username, got, self.mode.get() if self.mode else "Cash")
        except ValueError as e:
            self.err(str(e))
            return
        if self.edit_id:
            self.ok(f"{self.kind} no. {res['vno']} updated. Total Rs {inr(res['total'])}")
            if self.on_done:
                self.after(60, self.on_done)
            return
        for desc, qty, rate, _g, amt in self.rows:
            for e in (desc, qty, rate):
                e.delete(0, "end")
            amt.configure(text="")
        self.narr.delete(0, "end")
        if self.paid:
            self.paid.delete(0, "end")
        self.summary.configure(text="")
        text = f"{self.kind} no. {res['vno']} saved. Total Rs {inr(res['total'])}"
        if res["received"]:
            text += f", {'received' if self.sales else 'paid'} Rs {inr(res['received'])}, balance Rs {inr(res['balance'])}"
        self.ok(text, self.kind, res["vno"], d)
        focus_later(self.rows[0][0], 50)


class SummaryFrame(EntryBase):
    """Daily sales summary for counter / retail sales that do not need an invoice each."""
    RATES = ["0", "5", "12", "18", "28"]

    def __init__(self, master, con, username="", opener=None):
        super().__init__(master, fg_color="transparent")
        self._init_base(con, username, opener)
        T.title(self, "Daily Sales Summary",
                "One entry for a day's counter sales (customers who do not need a GST invoice). "
                "Sales to registered businesses need an invoice each: use Sales Invoice."
                ).pack(anchor="w", padx=28, pady=(24, 12))
        top = T.card(self)
        top.pack(fill="x", padx=28)
        self.date = T.entry(top, width=140)
        self.date.insert(0, today_str())
        self.mode = T.option_menu(top, ["Cash", "Bank"], width=110)
        self.incl = ctk.CTkCheckBox(top, text="Amounts include GST", command=self.calc, font=T.f(13),
                                    text_color=T.TEXT, fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER)
        self.incl.select()
        self.narr = T.entry(top, "Narration (optional)", width=300)
        _lbl(top, "Date", row=0, column=0, sticky="w", padx=(20, 8), pady=(14, 2))
        _lbl(top, "Received in", row=0, column=1, sticky="w", padx=8, pady=(14, 2))
        _lbl(top, "Narration", row=0, column=3, sticky="w", padx=8, pady=(14, 2))
        self.date.grid(row=1, column=0, padx=(20, 8), pady=(0, 14))
        self.mode.grid(row=1, column=1, padx=8, pady=(0, 14))
        self.incl.grid(row=1, column=2, padx=14, pady=(0, 14))
        self.narr.grid(row=1, column=3, padx=8, pady=(0, 14))

        card = T.card(self)
        card.pack(fill="x", padx=28, pady=14)
        for c, h in enumerate(("GST rate", "Sales amount (Rs)", "Tax in it (Rs)")):
            _lbl(card, h, row=0, column=c, sticky="w", padx=(20 if c == 0 else 8, 8), pady=(12, 0))
        self.rows = []
        for i, rate in enumerate(self.RATES):
            ctk.CTkLabel(card, text=f"{rate}%", font=T.f(14, "bold"), text_color=T.TEXT, width=60,
                         anchor="w").grid(row=i + 1, column=0, padx=(20, 8), pady=4, sticky="w")
            e = T.entry(card, "0.00", width=180)
            e.grid(row=i + 1, column=1, padx=8, pady=4)
            e.bind("<KeyRelease>", self.calc)
            tax = ctk.CTkLabel(card, text="", width=140, anchor="e", font=T.f(13), text_color=T.MUTED)
            tax.grid(row=i + 1, column=2, padx=8, pady=4)
            self.rows.append((rate, e, tax))
        self.summary = ctk.CTkLabel(card, text="", font=T.f(13, "bold"), text_color=T.TEXT)
        self.summary.grid(row=len(self.RATES) + 1, column=0, columnspan=3, sticky="e", padx=20, pady=(8, 14))

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=28)
        T.button(foot, "Save summary", self.save, width=170).pack(side="left")
        self._make_msg(foot)
        chain_enter([self.date, self.narr] + [e for _r, e, _t in self.rows], self.save)
        focus_later(self.rows[0][1])

    def is_dirty(self):
        return any(e.get().strip() for _r, e, _t in self.rows)

    def _entered(self):
        return [(r, parse_amount(e.get())) for r, e, _t in self.rows]

    def calc(self, _e=None):
        try:
            entered = self._entered()
            items = b.summary_items(entered, bool(self.incl.get()))
            t = b.compute_tax(items, False)
        except ValueError:
            self.summary.configure(text="")
            for _r, _e2, tax in self.rows:
                tax.configure(text="")
            return
        by = {}
        for d, _q, rate, g in items:
            by[str(int(g)) if g == int(g) else str(g)] = rate
        for r, _e2, tax in self.rows:
            if r in by:
                base = by[r]
                tax.configure(text=inr(float(base) * float(r) / 100))
            else:
                tax.configure(text="")
        k = lambda v: inr(v / 100)
        self.summary.configure(
            text=f"Taxable {k(t['taxable'])}     CGST {k(t['cgst'])}     SGST {k(t['sgst'])}     Total {k(t['total'])}")

    def save(self):
        try:
            d = parse_date(self.date.get())
            items = b.summary_items(self._entered(), bool(self.incl.get()))
            res = b.post_sale(self.con, d, self.mode.get(), items, False,
                              self.narr.get().strip() or "Daily sales summary", self.username)
        except ValueError as e:
            self.err(str(e))
            return
        for _r, e, tax in self.rows:
            e.delete(0, "end"); tax.configure(text="")
        self.narr.delete(0, "end")
        self.summary.configure(text="")
        self.ok(f"Saved as Sales no. {res['vno']}. Total Rs {inr(res['total'])} received in {self.mode.get()}",
                "Sales", res["vno"], d)
        focus_later(self.rows[0][1], 50)


class PaymentFrame(EntryBase):
    """Money received from a customer, or paid to a supplier, matched to their oldest bills."""
    KINDS = {"Receipt from customer": ("Receipt", "Customer"), "Payment to supplier": ("Payment", "Supplier")}

    def __init__(self, master, con, username="", opener=None):
        super().__init__(master, fg_color="transparent")
        self._init_base(con, username, opener)
        T.title(self, "Receipt / Payment",
                "Record money received from a customer or paid to a supplier. It is matched to their "
                "oldest unpaid bills first."
                ).pack(anchor="w", padx=28, pady=(24, 12))
        card = T.card(self)
        card.pack(fill="x", padx=28)
        self.kind = T.option_menu(card, list(self.KINDS), width=220, command=lambda _v: self.kind_changed())
        pw = ctk.CTkFrame(card, fg_color="transparent")
        self.party = T.combo(pw, [], width=240, command=lambda _v: self.show_bills())
        self.party.pack(side="left")
        T.button(pw, "+ New", self.new_party, width=64, **GHOST).pack(side="left", padx=(6, 0))
        self.ac = Autocomplete(self.party, [], on_pick=lambda _n: self.show_bills())
        self.date = T.entry(card, width=130)
        self.date.insert(0, today_str())
        self.mode = T.option_menu(card, ["Cash", "Bank"], width=100)
        self.amount = T.entry(card, "0.00", width=160)
        self.narr = T.entry(card, "Narration (optional)", width=300)
        heads = ("Type", "Party", "Date", "Paid by / into", "Amount (Rs)", "Narration")
        widgets = (self.kind, pw, self.date, self.mode, self.amount, self.narr)
        for c, (h, w) in enumerate(zip(heads, widgets)):
            _lbl(card, h, row=0, column=c, sticky="w", padx=(20 if c == 0 else 8, 8), pady=(14, 2))
            w.grid(row=1, column=c, padx=(20 if c == 0 else 8, 8), pady=(0, 14))
        ctk.CTkLabel(self, text="Unpaid bills of this party", font=T.f(14, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=28, pady=(14, 6))
        self.table = DataTable(self, [("d", "Date", 100, "w"), ("n", "Bill", 100, "w"), ("t", "Bill total", 140, "e"),
                                      ("s", "Settled", 140, "e"), ("b", "Balance", 140, "e")], height=6)
        self.table.pack(fill="both", expand=True, padx=28)
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=28, pady=14)
        T.button(foot, "Save", self.save, width=150).pack(side="left")
        self._make_msg(foot)
        chain_enter([self.party, self.date, self.amount, self.narr], self.save)
        self.kind_changed()
        focus_later(self.party)

    def _ctx(self):
        return self.KINDS[self.kind.get()]

    def kind_changed(self):
        names = [p["name"] for p in s.list_parties(self.con, self._ctx()[1])]
        self.ac.set_names(names)
        self.party.set(names[0] if names else "")
        self.show_bills()

    def new_party(self):
        PartyQuickDialog(self.winfo_toplevel(), self.con, self._ctx()[1], self._added)

    def _added(self, name):
        self.kind_changed()
        self.party.set(name)
        self.show_bills()
        focus_later(self.amount, 50)

    def show_bills(self):
        pkind, ptype = self._ctx()
        inv_kind = "Sales" if pkind == "Receipt" else "Purchase"
        rows = [(disp_date(o["vdate"]), f"{inv_kind} #{o['vno']}", inr(o["total"] / 100),
                 inr(o["settled"] / 100), inr(o["balance"] / 100))
                for o in b.open_invoices(self.con, self.party.get().strip(), inv_kind)]
        self.table.set_rows(rows)

    def is_dirty(self):
        return bool(self.amount.get().strip() or self.narr.get().strip())

    def save(self):
        try:
            ac = getattr(self.party, "_ac", None)
            if ac:
                ac.commit()
            pkind, _pt = self._ctx()
            d = parse_date(self.date.get())
            res = b.record_payment(self.con, pkind, self.party.get().strip(), d, parse_amount(self.amount.get()),
                                   self.mode.get(), self.narr.get().strip(), self.username)
        except ValueError as e:
            self.err(str(e))
            return
        inv_kind = "Sales" if pkind == "Receipt" else "Purchase"
        parts = [f"{inv_kind} #{n} Rs {inr(a)}" for n, a in res["settled_bills"]]
        text = f"{pkind} no. {res['vno']} saved. " + ("Settled " + ", ".join(parts) if parts else "No open bill to settle")
        if res["on_account"]:
            text += f". Rs {inr(res['on_account'])} kept on account"
        self.amount.delete(0, "end"); self.narr.delete(0, "end")
        self.show_bills()
        self.ok(text, pkind, res["vno"], d)
        focus_later(self.party, 50)
