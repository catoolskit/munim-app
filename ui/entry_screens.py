import customtkinter as ctk
import os, subprocess, sys
from db import setup as s, billing as b
from ui import theme as T
from ui.dialogs import PartyQuickDialog
from ui.voucher_dialog import _num
from ui.widgets import DataTable
from ui.ux import Autocomplete, chain_enter, focus_later
from utils import settings
from utils.fmt import inr, parse_amount, parse_date, today_str, disp_date

GHOST = dict(fg_color="#E7ECF5", text_color=T.TEXT, hover_color="#DCE3F0")

ADDBAR_ROW  = 998
SUMMARY_ROW = 999


def _lbl(parent, text, **grid):
    w = ctk.CTkLabel(parent, text=text, font=T.f(12), text_color=T.MUTED)
    w.grid(**grid)
    return w


class EntryBase(ctk.CTkFrame):
    def _init_base(self, con, username, opener):
        self.con, self.username, self.opener, self._last_vid = (
            con, username, opener, None)
        self._last_pdf_path = ""

    def _make_msg(self, foot):
        self.msg       = ctk.CTkLabel(foot, text="", font=T.f(12))
        self.msg.pack(side="left", padx=8)
        self.view_btn  = T.button(foot, "View",     self._view,
                                  width=74, height=32, **GHOST)
        self.pdf_btn   = T.button(foot, "Save PDF", self._save_pdf,
                                  width=88, height=32, **GHOST)
        self.share_btn = T.button(foot, "Share",    self._share,
                                  width=74, height=32, **GHOST)

    def ok(self, text, vtype=None, vno=None, vdate=None):
        self.msg.configure(text=text, text_color=T.OK)
        self._last_vid = (s.find_voucher(self.con, vtype, vno, vdate)
                          if vtype else None)
        if self._last_vid and self.opener:
            self.view_btn.pack(side="left")
        else:
            self.view_btn.pack_forget()
        if vtype == "Sales" and self._last_vid:
            self.pdf_btn.pack(side="left",   padx=(4, 0))
            self.share_btn.pack(side="left", padx=(4, 0))
        else:
            self.pdf_btn.pack_forget()
            self.share_btn.pack_forget()

    def err(self, text):
        self.msg.configure(text=text, text_color=T.DANGER)
        self.view_btn.pack_forget()
        self.pdf_btn.pack_forget()
        self.share_btn.pack_forget()

    def _view(self):
        if self._last_vid and self.opener:
            self.opener(self._last_vid, lambda: None)

    def _save_pdf(self):
        if not self._last_vid:
            return
        try:
            from utils.pdf_invoice import generate_invoice_pdf
            path = generate_invoice_pdf(self.con, self._last_vid)
            self._last_pdf_path = path
            folder = os.path.dirname(path)
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                subprocess.Popen(["xdg-open", folder])
            self.msg.configure(
                text=f"PDF saved: {os.path.basename(path)}", text_color=T.OK)
        except Exception as e:
            self.msg.configure(text=f"PDF error: {e}", text_color=T.DANGER)

    def _share(self):
        if not self._last_vid:
            return
        try:
            snap    = s.voucher_snapshot(self.con, self._last_vid)
            inv     = snap["invoice"]
            from utils.fmt import inr as _inr, disp_date as _dd
            from utils import settings as _st
            st      = _st.load_settings()
            prefix  = (st.get("invoice_prefix") or "").strip()
            inv_no  = f"{prefix}{snap['vno']}" if prefix else str(snap["vno"])
            company = st.get("company_name", "")
            total   = _inr(inv["total"] / 100)
            vdate   = _dd(snap["vdate"])
            party   = inv["party"]

            p_row = self.con.execute(
                "SELECT phone FROM parties WHERE name=?", (party,)).fetchone()
            phone = (p_row["phone"] or "").strip() if p_row else ""

            msg_text = (
                f"Dear {party},\n\n"
                f"Please find your invoice details:\n"
                f"Invoice No: {inv_no}\n"
                f"Date: {vdate}\n"
                f"Amount: Rs {total}\n\n"
                f"From: {company}\n"
                f"Thank you for your business!"
            )

            import urllib.parse, webbrowser
            encoded = urllib.parse.quote(msg_text)
            if phone:
                digits = "".join(c for c in phone if c.isdigit())
                if len(digits) == 10:
                    digits = "91" + digits
                wa_url = f"https://wa.me/{digits}?text={encoded}"
            else:
                wa_url = f"https://wa.me/?text={encoded}"

            subject  = urllib.parse.quote(f"Invoice {inv_no} from {company}")
            body     = urllib.parse.quote(msg_text)
            mail_url = f"mailto:?subject={subject}&body={body}"

            import tkinter as tk
            dialog = ctk.CTkToplevel(self.winfo_toplevel())
            dialog.title("Share Invoice")
            dialog.geometry("340x200")
            dialog.resizable(False, False)
            dialog.configure(fg_color=T.BG)
            dialog.transient(self.winfo_toplevel())
            dialog.grab_set()

            ctk.CTkLabel(dialog, text="Share invoice via",
                         font=T.f(16, "bold"), text_color=T.TEXT).pack(
                pady=(24, 16))

            def _wa():
                webbrowser.open(wa_url)
                dialog.destroy()

            def _email():
                webbrowser.open(mail_url)
                dialog.destroy()

            btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            btn_frame.pack()
            T.button(btn_frame, "WhatsApp", _wa, width=130).pack(
                side="left", padx=8)
            T.button(btn_frame, "Email", _email, width=130,
                     fg_color="#E7ECF5", text_color=T.TEXT,
                     hover_color="#DCE3F0").pack(side="left", padx=8)
            if phone:
                ctk.CTkLabel(dialog,
                             text=f"WhatsApp will open for {phone}",
                             font=T.f(11), text_color=T.MUTED).pack(pady=(12, 0))
        except Exception as e:
            self.msg.configure(text=f"Share error: {e}", text_color=T.DANGER)

    def is_dirty(self):
        return False


# ── JournalFrame ──────────────────────────────────────────────────────────────

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
                ).pack(anchor="w", padx=28, pady=(10, 6))
        card = T.card(self)
        card.pack(fill="x", padx=28)
        self.vtype = T.option_menu(card, self.VTYPES, width=150)
        self.date  = T.entry(card, width=150)
        self.date.insert(0, today_str())
        self.narr  = T.entry(card, "Narration (optional)", width=420)
        _lbl(card, "Voucher type", row=0, column=0, sticky="w", padx=(20, 8), pady=(14, 2))
        _lbl(card, "Date (type 15 or 1511 or 15-11-2026)", row=0, column=1, sticky="w", padx=8, pady=(14, 2))
        _lbl(card, "Narration", row=0, column=2, sticky="w", padx=8, pady=(14, 2))
        self.vtype.grid(row=1, column=0, padx=(20, 8), pady=(0, 14))
        self.date.grid( row=1, column=1, padx=8,       pady=(0, 14))
        self.narr.grid( row=1, column=2, padx=8,       pady=(0, 14))

        lines = T.card(self)
        lines.pack(fill="x", padx=28, pady=14)
        lines.grid_columnconfigure(0, weight=1)
        self.area = ctk.CTkScrollableFrame(lines, fg_color="transparent", height=250)
        self.area.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=(10, 4))
        _lbl(self.area, "Account (type to search)", row=0, column=0, sticky="w", padx=(10, 6))
        _lbl(self.area, "Debit (Rs)",  row=0, column=1, sticky="w", padx=8)
        _lbl(self.area, "Credit (Rs)", row=0, column=2, sticky="w", padx=8)
        for _ in range(4):
            self.add_line(rechain=False)
        bar = ctk.CTkFrame(lines, fg_color="transparent")
        bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=20, pady=(4, 14))
        T.button(bar, "+ Add line", self.add_line, width=110, **GHOST).pack(side="left")
        self.total = ctk.CTkLabel(bar, text="", font=T.f(13, "bold"))
        self.total.pack(side="right")

        foot = T.card(self)
        foot.pack(fill="x", padx=28, pady=(0, 18))
        T.button(foot, "Update voucher" if edit_id else "Save voucher",
                 self.save, width=170).pack(side="left")
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
        dr.grid( row=r, column=1, padx=6,       pady=4)
        cr.grid( row=r, column=2, padx=6,       pady=4)
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
                s.update_voucher(self.con, self.edit_id, self.vtype.get(), d,
                                 self.narr.get().strip(), lines, self.username)
                vno = None
            else:
                vno = s.post_voucher(self.con, self.vtype.get(), d,
                                     self.narr.get().strip(), lines, self.username)
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


# ── TradeFrame ────────────────────────────────────────────────────────────────

class TradeFrame(EntryBase):
    """Sales invoice or purchase bill with GST. kind is 'Sales' or 'Purchase'."""
    GST_RATES = ["0", "0.25", "1.5", "3", "5", "12", "18", "28", "40"]
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
        self._stock_map   = self._load_stock_map()
        self._stock_names = list(self._stock_map.keys())

        T.title(self, ("Edit " if edit_id else "New ") + ("Sales Invoice" if self.sales else "Purchase Bill"),
                "Document details  →  item lines  →  tax and total. Ctrl+S saves."
                ).pack(anchor="w", padx=28, pady=(20, 10))
        top = T.card(self)
        top.pack(fill="x", padx=28)
        ctk.CTkLabel(top, text="DOCUMENT DETAILS", font=T.f(10, "bold"),
                     text_color=T.MUTED).grid(row=0, column=0, columnspan=5,
                                              sticky="w", padx=20, pady=(12, 0))
        for _col, _weight in enumerate((1, 2, 1, 2, 1)):
            top.grid_columnconfigure(_col, weight=_weight)
        self.date = T.entry(top, width=140)
        self.date.insert(0, today_str())
        pw = ctk.CTkFrame(top, fg_color="transparent")
        self.party = T.combo(pw, self.parties, width=240, command=self.party_chosen)
        self.party.set(self.parties[0])
        self.party.pack(side="left")
        T.button(pw, "+ New", self.new_party, width=64, **GHOST).pack(side="left", padx=(6, 0))
        self.ac = Autocomplete(self.party, self.parties, on_pick=self.party_chosen)
        self.inter = ctk.CTkCheckBox(top, text="Inter-state (IGST)", command=self.calc,
                                     font=T.f(13), text_color=T.TEXT,
                                     fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER)
        self.rcm = None
        if not self.sales:
            self.rcm = ctk.CTkCheckBox(top, text="Reverse Charge (RCM)",
                                       font=T.f(13), text_color=T.TEXT,
                                       fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER)
        self.narr = T.entry(top, "Narration (optional)", width=300)

        _lbl(top, "Date", row=1, column=0, sticky="w", padx=(20, 8), pady=(10, 2))
        _lbl(top, "Customer" if self.sales else "Supplier",
             row=1, column=1, sticky="w", padx=8, pady=(10, 2))
        _lbl(top, "Narration", row=1, column=3, sticky="w", padx=8, pady=(10, 2))
        self.date.grid(row=2, column=0, padx=(20, 8), pady=(0, 14))
        pw.grid(        row=2, column=1, padx=8,       pady=(0, 14))
        self.inter.grid(row=2, column=2, padx=12,      pady=(0, 14))
        if self.rcm is not None:
            _lbl(top, "RCM", row=1, column=4, sticky="w", padx=8, pady=(10, 2))
            self.rcm.grid(row=2, column=4, padx=8, pady=(0, 14))
        self.narr.grid( row=2, column=3, padx=8,       pady=(0, 14))

        items_wrap = T.card(self)
        items_wrap.pack(fill="both", expand=True, padx=28, pady=(12, 10))
        items_wrap.grid_columnconfigure(0, weight=1)
        items_wrap.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(items_wrap, text="INVOICE ITEMS", font=T.f(10, "bold"),
                     text_color=T.MUTED).grid(row=0, column=0, sticky="w", padx=20, pady=(12, 2))
        self.items_card = ctk.CTkScrollableFrame(items_wrap, fg_color="transparent", height=260)
        self.items_card.grid(row=1, column=0, sticky="nsew", padx=8, pady=(2, 4))
        items = self.items_card
        for c, h in enumerate(("Item", "HSN/SAC", "Qty", "Rate (Rs)", "GST %", "", "Amount")):
            _lbl(items, h, row=0, column=c,
                 sticky="w", padx=(20 if c == 0 else 6, 6), pady=(2, 0))

        for _ in range(self.ROWS):
            self._add_row(rechain=False)

        addbar = ctk.CTkFrame(items, fg_color="transparent")
        addbar.grid(row=ADDBAR_ROW, column=0, columnspan=7, sticky="w", padx=20, pady=(8, 0))
        T.button(addbar, "+ Add item", self.add_row_and_focus, width=110, **GHOST).pack(side="left")
        self.row_count_lbl = ctk.CTkLabel(addbar, text="", font=T.f(11), text_color=T.MUTED)
        self.row_count_lbl.pack(side="left", padx=10)

        self.summary = ctk.CTkLabel(items_wrap, text="", font=T.f(13, "bold"),
                                     text_color=T.TEXT, fg_color="#F0F5FF",
                                     corner_radius=8, anchor="e", height=38)
        self.summary.grid(row=2, column=0, sticky="ew", padx=18, pady=(4, 12))

        foot = T.card(self)
        foot.pack(fill="x", padx=28, pady=(0, 18))
        self.paid = self.mode = self.paid_lbl = None
        if not edit_id:
            self.paid_lbl = ctk.CTkLabel(
                foot, text="Received now (Rs)" if self.sales else "Paid now (Rs)",
                font=T.f(12), text_color=T.MUTED)
            self.paid = T.entry(foot, "0.00", width=120)
            self.paid.bind("<KeyRelease>", self.calc)
            self.mode = T.option_menu(foot, ["Cash", "Bank"], width=90)
        self.bill_lbl = ctk.CTkLabel(
            foot,
            text="Customer name on bill" if self.sales else "Supplier name on bill",
            font=T.f(12), text_color=T.MUTED)
        self.bill_name = T.entry(foot, "(optional)", width=200)
        self.save_btn = T.button(
            foot,
            ("Update " if edit_id else "Save ") + ("invoice" if self.sales else "bill"),
            self.save, width=160)
        self.save_btn.pack(side="left", padx=(14, 8), pady=10)
        self._make_msg(foot)
        self._rechain()
        self._update_row_count()
        if edit_id:
            self._prefill()
        else:
            self.party_chosen(self.party.get())
            focus_later(self.rows[0][0])
        self._cash_mode()

    def _add_row(self, rechain=True):
        items = self.items_card
        idx   = len(self.rows)
        r     = idx + 1
        desc  = T.combo(items, self._stock_names, width=260)
        desc.set("")
        hsn  = T.entry(items, "HSN/SAC", width=90)
        qty  = T.entry(items, "1",       width=80)
        rate = T.entry(items, "0.00",    width=120)
        gst  = T.option_menu(items, self.GST_RATES, width=90, command=lambda _v: self.calc())
        gst.set("18")
        amt  = ctk.CTkLabel(items, text="", width=110, anchor="e",
                            font=T.f(13), text_color=T.TEXT)
        desc.grid(row=r, column=0, padx=(20, 6), pady=4)
        hsn.grid( row=r, column=1, padx=6,       pady=4)
        qty.grid( row=r, column=2, padx=6,       pady=4)
        rate.grid(row=r, column=3, padx=6,       pady=4)
        gst.grid( row=r, column=4, columnspan=2, padx=6, pady=4, sticky="w")
        amt.grid( row=r, column=6, padx=6,       pady=4)
        for e in (qty, rate):
            e.bind("<KeyRelease>", self.calc)
        Autocomplete(desc, self._stock_names,
                     on_pick=lambda name, i=idx: self._on_item_pick(i, name))
        self.rows.append((desc, hsn, qty, rate, gst, amt))
        if rechain:
            self._rechain()
            self._update_row_count()
        return self.rows[-1]

    def add_row_and_focus(self):
        row = self._add_row()
        focus_later(row[0], 50)

    def _update_row_count(self):
        if getattr(self, "row_count_lbl", None) is not None:
            self.row_count_lbl.configure(text=f"{len(self.rows)} rows")

    def _rechain(self):
        if not hasattr(self, "bill_name"):
            return
        order = [self.date, self.party, self.narr]
        for desc, hsn, qty, rate, _g, _a in self.rows:
            order += [desc, hsn, qty, rate]
        order += [self.bill_name]
        if self.paid is not None:
            order.append(self.paid)
        chain_enter(order, self.save if not self.edit_id else None)

    def _load_stock_map(self):
        try:
            rows = self.con.execute(
                "SELECT id, name, hsn, unit, gst_rate FROM stock_items ORDER BY name COLLATE NOCASE"
            ).fetchall()
            return {r["name"]: dict(r) for r in rows}
        except Exception:
            return {}

    def _on_item_pick(self, row_idx, name):
        if row_idx >= len(self.rows):
            return
        if name in self._stock_map:
            it = self._stock_map[name]
            _desc, hsn, _qty, _rate, gst, _amt = self.rows[row_idx]
            hsn.delete(0, "end")
            hsn.insert(0, it["hsn"] or "")
            gst.set(str(it["gst_rate"] or "18"))
            self.calc()

    def _is_cash(self):
        return self.party.get().strip() in ("Cash", "Bank")

    def _cash_mode(self):
        for w in (self.paid_lbl, self.paid, self.mode, self.bill_lbl, self.bill_name):
            if w is not None:
                w.pack_forget()
        if self._is_cash():
            self.bill_lbl.pack(side="left",  padx=(0, 8),  before=self.save_btn)
            self.bill_name.pack(side="left", padx=(0, 18), before=self.save_btn)
        elif self.paid is not None:
            self.paid_lbl.pack(side="left", padx=(0, 8),  before=self.save_btn)
            self.paid.pack(    side="left", padx=(0, 8),  before=self.save_btn)
            self.mode.pack(    side="left", padx=(0, 18), before=self.save_btn)

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
        inv  = snap["invoice"]
        self.date.delete(0, "end")
        self.date.insert(0, disp_date(snap["vdate"]))
        self.party.set(inv["party"])
        (self.inter.select if inv["interstate"] else self.inter.deselect)()
        if self.rcm is not None:
            (self.rcm.select if inv.get("rcm") else self.rcm.deselect)()
        self.narr.insert(0, snap["narration"] or "")
        self.bill_name.insert(0, inv.get("customer_name", ""))
        for i, it in enumerate(inv["items"]):
            while len(self.rows) <= i:
                self._add_row(rechain=False)
            desc, hsn, qty, rate, gst, _a = self.rows[i]
            desc.set(it["description"])
            hsn.delete(0, "end");  hsn.insert(0, it.get("hsn", "") or "")
            qty.delete(0, "end");  qty.insert(0, _num(it["qty"]))
            rate.delete(0, "end"); rate.insert(0, _num(it["rate"]))
            gst.set(_num(it["gst"]))
        self._rechain()
        self._update_row_count()
        self.calc()

    def is_dirty(self):
        if self.edit_id:
            return False
        return any(d.get().strip() or q.get().strip() or r.get().strip()
                   for d, _h, q, r, _g, _a in self.rows) or bool(self.bill_name.get().strip())

    def party_chosen(self, name):
        row = self.con.execute("SELECT gstin FROM parties WHERE name=?", (name,)).fetchone()
        if b.is_interstate(row["gstin"] if row else "", self.company_gstin):
            self.inter.select()
        else:
            self.inter.deselect()
        self._cash_mode()
        self.calc()

    def _collect(self):
        items = []
        for desc, hsn, qty, rate, gst, _amt in self.rows:
            d, h, q, r = (desc.get().strip(), hsn.get().strip(),
                          qty.get().strip(),  rate.get().strip())
            if not (d or q or r):
                continue
            if not q or not r:
                raise ValueError("Every item needs a quantity and a rate")
            sid = self._stock_map[d]["id"] if d in self._stock_map else None
            items.append((d or "Item", h, parse_amount(q), parse_amount(r),
                          float(gst.get()), sid))
        return items

    def calc(self, _e=None):
        # ── v0.18: respect GST registration status ────────────────────────────
        gst_registered = settings.load_settings().get("gst_registered", True)

        for _d, _h, qty, rate, _g, amt in self.rows:
            try:
                q, rt = parse_amount(qty.get()), parse_amount(rate.get())
                amt.configure(text=inr(q * rt) if q and rt else "")
            except ValueError:
                amt.configure(text="")
        try:
            items     = self._collect()
            tax_items = [(d, q, r, g) for d, _h, q, r, g, _sid in items]
            t = b.compute_tax(tax_items, bool(self.inter.get()))
        except ValueError:
            self.summary.configure(text="")
            return
        k = lambda v: inr(v / 100)

        if gst_registered:
            # Registered: show full GST breakdown
            tax = (f"IGST {k(t['igst'])}" if self.inter.get()
                   else f"CGST {k(t['cgst'])}   SGST {k(t['sgst'])}")
            extra = ""
            if self.paid is not None:
                try:
                    p = parse_amount(self.paid.get())
                except ValueError:
                    p = 0
                if p:
                    word = "Received" if self.sales else "Paid"
                    extra = f"     {word} {inr(p)}     Due {inr(t['total'] / 100 - p)}"
            self.summary.configure(
                text=f"Taxable {k(t['taxable'])}     {tax}     Total {k(t['total'])}{extra}")
        else:
            # Unregistered: show only total (no GST breakdown)
            extra = ""
            if self.paid is not None:
                try:
                    p = parse_amount(self.paid.get())
                except ValueError:
                    p = 0
                if p:
                    word = "Received" if self.sales else "Paid"
                    extra = f"     {word} {inr(p)}     Due {inr(t['taxable'] / 100 - p)}"
            # For unregistered, total = taxable amount only (no GST)
            self.summary.configure(
                text=f"Total {k(t['taxable'])}{extra}   (GST not applicable — unregistered)")

    def _stamp_rcm(self, vid):
        if self.rcm is None or vid is None:
            return
        flag = 1 if self.rcm.get() else 0
        try:
            self.con.execute(
                "UPDATE invoices SET rcm=? WHERE voucher_id=?", (flag, vid))
            self.con.commit()
        except Exception:
            pass

    def save(self):
        try:
            d  = parse_date(self.date.get())
            ac = getattr(self.party, "_ac", None)
            if ac:
                ac.commit()
            party = self.party.get().strip()
            bn = self.bill_name.get().strip() if party in ("Cash", "Bank") else ""
            if self.edit_id:
                res = b.update_invoice(
                    self.con, self.edit_id, d, party, self._collect(),
                    bool(self.inter.get()), self.narr.get().strip(),
                    self.username, bn)
            else:
                post = b.post_sale if self.sales else b.post_purchase
                got  = (parse_amount(self.paid.get())
                        if (self.paid and party not in ("Cash", "Bank")) else 0)
                res  = post(self.con, d, party, self._collect(),
                            bool(self.inter.get()), self.narr.get().strip(),
                            self.username, got,
                            self.mode.get() if self.mode else "Cash", bn)
        except ValueError as e:
            self.err(str(e))
            return

        if self.edit_id:
            self.ok(f"{self.kind} no. {res['vno']} updated. Total Rs {inr(res['total'])}")
            self._stamp_rcm(self.edit_id)
            if self.on_done:
                self.after(60, self.on_done)
            return

        for desc, hsn, qty, rate, _g, amt in self.rows:
            desc.set("")
            for e in (hsn, qty, rate):
                e.delete(0, "end")
            amt.configure(text="")
        self.narr.delete(0, "end")
        if self.paid:
            self.paid.delete(0, "end")
        self.bill_name.delete(0, "end")
        self.summary.configure(text="")
        text = f"{self.kind} no. {res['vno']} saved. Total Rs {inr(res['total'])}"
        if res["received"]:
            text += (f", {'received' if self.sales else 'paid'} Rs {inr(res['received'])}"
                     f", balance Rs {inr(res['balance'])}")
        self.ok(text, self.kind, res["vno"], d)
        self._stamp_rcm(s.find_voucher(self.con, self.kind, res["vno"], d))
        focus_later(self.rows[0][0], 50)


# ── SummaryFrame ──────────────────────────────────────────────────────────────

class SummaryFrame(EntryBase):
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
        ctk.CTkLabel(top, text="DOCUMENT DETAILS", font=T.f(10, "bold"),
                     text_color=T.MUTED).grid(row=0, column=0, columnspan=5,
                                              sticky="w", padx=20, pady=(12, 0))
        for _col, _weight in enumerate((1, 2, 1, 2, 1)):
            top.grid_columnconfigure(_col, weight=_weight)
        self.date = T.entry(top, width=140)
        self.date.insert(0, today_str())
        self.mode = T.option_menu(top, ["Cash", "Bank"], width=110)
        self.incl = ctk.CTkCheckBox(top, text="Amounts include GST", command=self.calc,
                                    font=T.f(13), text_color=T.TEXT,
                                    fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER)
        self.incl.select()
        self.narr = T.entry(top, "Narration (optional)", width=300)
        _lbl(top, "Date",         row=0, column=0, sticky="w", padx=(20, 8), pady=(14, 2))
        _lbl(top, "Received in",  row=0, column=1, sticky="w", padx=8,       pady=(14, 2))
        _lbl(top, "Narration",    row=0, column=3, sticky="w", padx=8,       pady=(14, 2))
        self.date.grid(row=1, column=0, padx=(20, 8), pady=(0, 14))
        self.mode.grid(row=1, column=1, padx=8,       pady=(0, 14))
        self.incl.grid(row=1, column=2, padx=14,      pady=(0, 14))
        self.narr.grid(row=1, column=3, padx=8,       pady=(0, 14))

        card = T.card(self)
        card.pack(fill="x", padx=28, pady=14)
        for c, h in enumerate(("GST rate", "Sales amount (Rs)", "Tax in it (Rs)")):
            _lbl(card, h, row=0, column=c,
                 sticky="w", padx=(20 if c == 0 else 8, 8), pady=(12, 0))
        self.rows = []
        for i, rate in enumerate(self.RATES):
            ctk.CTkLabel(card, text=f"{rate}%", font=T.f(14, "bold"),
                         text_color=T.TEXT, width=60, anchor="w"
                         ).grid(row=i + 1, column=0, padx=(20, 8), pady=4, sticky="w")
            e = T.entry(card, "0.00", width=180)
            e.grid(row=i + 1, column=1, padx=8, pady=4)
            e.bind("<KeyRelease>", self.calc)
            tax = ctk.CTkLabel(card, text="", width=140, anchor="e",
                               font=T.f(13), text_color=T.MUTED)
            tax.grid(row=i + 1, column=2, padx=8, pady=4)
            self.rows.append((rate, e, tax))
        self.summary = ctk.CTkLabel(card, text="", font=T.f(13, "bold"), text_color=T.TEXT)
        self.summary.grid(row=len(self.RATES) + 1, column=0, columnspan=3,
                          sticky="e", padx=20, pady=(8, 14))

        foot = T.card(self)
        foot.pack(fill="x", padx=28, pady=(0, 18))
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
            items   = b.summary_items(entered, bool(self.incl.get()))
            t       = b.compute_tax(items, False)
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
            text=(f"Taxable {k(t['taxable'])}     CGST {k(t['cgst'])}"
                  f"     SGST {k(t['sgst'])}     Total {k(t['total'])}"))

    def save(self):
        try:
            d     = parse_date(self.date.get())
            items = b.summary_items(self._entered(), bool(self.incl.get()))
            res   = b.post_sale(self.con, d, self.mode.get(), items, False,
                                self.narr.get().strip() or "Daily sales summary",
                                self.username)
        except ValueError as e:
            self.err(str(e))
            return
        for _r, e, tax in self.rows:
            e.delete(0, "end"); tax.configure(text="")
        self.narr.delete(0, "end")
        self.summary.configure(text="")
        self.ok(f"Saved as Sales no. {res['vno']}. "
                f"Total Rs {inr(res['total'])} received in {self.mode.get()}",
                "Sales", res["vno"], d)
        focus_later(self.rows[0][1], 50)


# ── PaymentFrame ──────────────────────────────────────────────────────────────

class PaymentFrame(EntryBase):
    KINDS = {"Receipt from customer": ("Receipt", "Customer"),
             "Payment to supplier":   ("Payment", "Supplier")}

    def __init__(self, master, con, username="", opener=None):
        super().__init__(master, fg_color="transparent")
        self._init_base(con, username, opener)
        self._open_bills   = []
        self._bill_entries = []

        T.title(self, "Receipt / Payment",
                "Type amount in 'Now Paying' against each bill to settle it. Leave blank to skip."
                ).pack(anchor="w", padx=28, pady=(24, 12))

        card = T.card(self)
        card.pack(fill="x", padx=28)
        self.kind = T.option_menu(card, list(self.KINDS), width=220,
                                  command=lambda _v: self.kind_changed())
        pw = ctk.CTkFrame(card, fg_color="transparent")
        self.party = T.combo(pw, [], width=240, command=lambda _v: self.show_bills())
        self.party.pack(side="left")
        T.button(pw, "+ New", self.new_party, width=64, **GHOST).pack(side="left", padx=(6, 0))
        self.ac   = Autocomplete(self.party, [], on_pick=lambda _n: self.show_bills())
        self.date = T.entry(card, width=130)
        self.date.insert(0, today_str())
        self.mode = T.option_menu(card, ["Cash", "Bank"], width=100)
        self.narr = T.entry(card, "Narration (optional)", width=300)
        heads   = ("Type", "Party", "Date", "Paid by / into", "Narration")
        widgets = (self.kind, pw, self.date, self.mode, self.narr)
        for c, (h, w) in enumerate(zip(heads, widgets)):
            _lbl(card, h, row=0, column=c,
                 sticky="w", padx=(20 if c == 0 else 8, 8), pady=(14, 2))
            w.grid(row=1, column=c, padx=(20 if c == 0 else 8, 8), pady=(0, 14))

        ctk.CTkLabel(self, text="Unpaid bills — type amount to settle against each",
                     font=T.f(14, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=28, pady=(14, 4))

        hdr = ctk.CTkFrame(self, fg_color="#E8EDF5", corner_radius=0, height=28)
        hdr.pack(fill="x", padx=28)
        hdr.pack_propagate(False)
        for txt, w in (("Date", 110), ("Bill", 120), ("Bill Total", 160),
                       ("Balance", 160), ("Now Paying", 160)):
            ctk.CTkLabel(hdr, text=txt, font=T.f(11, "bold"), text_color=T.MUTED,
                         width=w, anchor="w").pack(side="left", padx=(12, 4))

        self.bills_frame = ctk.CTkScrollableFrame(
            self, fg_color="white", border_width=1, border_color="#D1D5DB",
            corner_radius=0, height=180)
        self.bills_frame.pack(fill="x", padx=28)

        tot_bar = ctk.CTkFrame(self, fg_color="#EEF2FF", corner_radius=0, height=32)
        tot_bar.pack(fill="x", padx=28)
        tot_bar.pack_propagate(False)
        ctk.CTkLabel(tot_bar, text="Total being paid:", font=T.f(12, "bold"),
                     text_color=T.TEXT).pack(side="left", padx=12)
        self.total_lbl = ctk.CTkLabel(tot_bar, text="0.00", font=T.f(13, "bold"),
                                       text_color=T.ACCENT)
        self.total_lbl.pack(side="right", padx=12)

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=28, pady=14)
        T.button(foot, "Save", self.save, width=150).pack(side="left")
        self._make_msg(foot)
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
        focus_later(self._bill_entries[0] if self._bill_entries else self.narr, 50)

    def show_bills(self):
        for w in self.bills_frame.winfo_children():
            w.destroy()
        self._bill_entries = []
        pkind, _pt = self._ctx()
        inv_kind   = "Sales" if pkind == "Receipt" else "Purchase"
        self._open_bills = b.open_invoices(self.con, self.party.get().strip(), inv_kind)
        for i, o in enumerate(self._open_bills):
            bg  = "white" if i % 2 == 0 else "#F8FAFD"
            row = ctk.CTkFrame(self.bills_frame, fg_color=bg, corner_radius=0, height=34)
            row.pack(fill="x")
            row.pack_propagate(False)
            ctk.CTkLabel(row, text=disp_date(o["vdate"]), font=T.f(12),
                         text_color=T.TEXT, width=110, anchor="w").pack(side="left", padx=(12, 4))
            ctk.CTkLabel(row, text=f"{inv_kind} #{o['vno']}", font=T.f(12),
                         text_color=T.TEXT, width=120, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=inr(o["total"] / 100), font=T.f(12),
                         text_color=T.MUTED, width=160, anchor="e").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=inr(o["balance"] / 100), font=T.f(12, "bold"),
                         text_color=T.TEXT, width=160, anchor="e").pack(side="left", padx=4)
            entry = T.entry(row, "0.00", width=140)
            entry.pack(side="left", padx=(8, 12))
            entry.bind("<KeyRelease>", self._update_total)
            self._bill_entries.append(entry)
        self._update_total()

    def _update_total(self, _e=None):
        total = 0.0
        for e in self._bill_entries:
            try:
                v = parse_amount(e.get())
                if v > 0:
                    total += v
            except ValueError:
                pass
        self.total_lbl.configure(text=inr(total))

    def _get_allocations(self):
        allocs = []
        for o, e in zip(self._open_bills, self._bill_entries):
            try:
                amt = parse_amount(e.get())
            except ValueError:
                amt = 0
            if amt > 0:
                allocs.append((o["id"], amt))
        return allocs

    def is_dirty(self):
        return any(e.get().strip() and e.get().strip() != "0.00"
                   for e in self._bill_entries) or bool(self.narr.get().strip())

    def save(self):
        try:
            allocs = self._get_allocations()
            ac = getattr(self.party, "_ac", None)
            if ac:
                ac.commit()
            pkind, _pt = self._ctx()
            d      = parse_date(self.date.get())
            party  = self.party.get().strip()
            if not allocs:
                raise ValueError("Enter amount against at least one bill")
            total_amt = sum(a for _, a in allocs)
            res = b.record_payment(
                self.con, pkind, party, d, total_amt,
                self.mode.get(), self.narr.get().strip(),
                self.username, allocations=allocs)
        except ValueError as e:
            self.err(str(e))
            return
        inv_kind = "Sales" if pkind == "Receipt" else "Purchase"
        parts = [f"{inv_kind} #{n} Rs {inr(a)}" for n, a in res["settled_bills"]]
        text  = f"{pkind} no. {res['vno']} saved. Settled " + ", ".join(parts)
        if res["on_account"]:
            text += f". Rs {inr(res['on_account'])} on account"
        self.narr.delete(0, "end")
        self.show_bills()
        self.ok(text, pkind, res["vno"], d)
        focus_later(self.party, 50)


# ── _ReturnRowsMixin ──────────────────────────────────────────────────────────

class _ReturnRowsMixin:
    def _add_row(self, rechain=True):
        items = self.items_card
        r     = len(self.rows) + 1
        desc  = T.entry(items, "Description", width=260)
        hsn   = T.entry(items, "HSN/SAC",     width=90)
        qty   = T.entry(items, "1",            width=80)
        rate  = T.entry(items, "0.00",         width=120)
        gst   = T.option_menu(items, self.GST_RATES, width=90,
                              command=lambda _v: self.calc())
        gst.set("18")
        amt   = ctk.CTkLabel(items, text="", width=110, anchor="e",
                             font=T.f(13), text_color=T.TEXT)
        desc.grid(row=r, column=0, padx=(20, 6), pady=4)
        hsn.grid( row=r, column=1, padx=6,       pady=4)
        qty.grid( row=r, column=2, padx=6,       pady=4)
        rate.grid(row=r, column=3, padx=6,       pady=4)
        gst.grid( row=r, column=4, columnspan=2, padx=6, pady=4, sticky="w")
        amt.grid( row=r, column=6, padx=6,       pady=4)
        for e in (qty, rate):
            e.bind("<KeyRelease>", self.calc)
        self.rows.append((desc, hsn, qty, rate, gst, amt))
        if rechain:
            self._update_row_count()
        return self.rows[-1]

    def add_row_and_focus(self):
        row = self._add_row()
        focus_later(row[0], 50)

    def _update_row_count(self):
        if getattr(self, "row_count_lbl", None) is not None:
            self.row_count_lbl.configure(text=f"{len(self.rows)} rows")

    def _build_rows_area(self, parent):
        wrap = T.card(parent)
        wrap.pack(fill="both", expand=True, padx=28, pady=(6, 14))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)
        self.items_card = ctk.CTkScrollableFrame(wrap, fg_color="transparent", height=220)
        self.items_card.grid(row=0, column=0, sticky="nsew", padx=8, pady=(10, 4))
        items = self.items_card
        for c, h in enumerate(("Item", "HSN/SAC", "Qty", "Rate (Rs)", "GST %", "", "Amount")):
            _lbl(items, h, row=0, column=c, sticky="w",
                 padx=(20 if c == 0 else 6, 6), pady=(2, 0))
        for _ in range(self.ROWS):
            self._add_row(rechain=False)
        addbar = ctk.CTkFrame(items, fg_color="transparent")
        addbar.grid(row=ADDBAR_ROW, column=0, columnspan=7, sticky="w", padx=20, pady=(8, 0))
        T.button(addbar, "+ Add item", self.add_row_and_focus,
                 width=110, **GHOST).pack(side="left")
        self.row_count_lbl = ctk.CTkLabel(addbar, text="", font=T.f(11), text_color=T.MUTED)
        self.row_count_lbl.pack(side="left", padx=10)
        self.summary = ctk.CTkLabel(items_wrap, text="", font=T.f(13, "bold"),
                                     text_color=T.TEXT, fg_color="#F0F5FF",
                                     corner_radius=8, anchor="e", height=38)
        self.summary.grid(row=2, column=0, sticky="ew", padx=18, pady=(4, 12))
        self._update_row_count()
        return items


# ── SalesReturnFrame ──────────────────────────────────────────────────────────

class SalesReturnFrame(_ReturnRowsMixin, EntryBase):
    GST_RATES = ["0", "0.25", "1.5", "3", "5", "12", "18", "28", "40"]
    ROWS = 3

    def __init__(self, master, con, username="", opener=None):
        super().__init__(master, fg_color="transparent")
        self._init_base(con, username, opener)
        self.rows = []
        self._open_bills   = []
        self.company_gstin = settings.load_settings().get("gstin", "")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        T.title(scroll, "Sales Return / Credit Note",
                "Select the customer and the original invoice to return against. "
                "Enter returned items and quantities."
                ).pack(anchor="w", padx=28, pady=(10, 6))

        top = T.card(scroll)
        top.pack(fill="x", padx=28)
        self.date = T.entry(top, width=140)
        self.date.insert(0, today_str())

        parties = [p["name"] for p in s.list_parties(con, "Customer")]
        pw = ctk.CTkFrame(top, fg_color="transparent")
        self.party = T.combo(pw, parties, width=240, command=self._party_changed)
        self.party.set(parties[0] if parties else "")
        self.party.pack(side="left")
        self.ac = Autocomplete(self.party, parties, on_pick=self._party_changed)

        self.inter = ctk.CTkCheckBox(top, text="Inter-state (IGST)", font=T.f(13),
                                     text_color=T.TEXT, fg_color=T.ACCENT,
                                     hover_color=T.ACCENT_HOVER, command=self.calc)
        self.narr  = T.entry(top, "Reason for return (optional)", width=300)

        _lbl(top, "Date",     row=0, column=0, sticky="w", padx=(20, 8), pady=(14, 2))
        _lbl(top, "Customer", row=0, column=1, sticky="w", padx=8,       pady=(14, 2))
        _lbl(top, "Narration",row=0, column=3, sticky="w", padx=8,       pady=(14, 2))
        self.date.grid(row=1, column=0, padx=(20, 8), pady=(0, 14))
        pw.grid(        row=1, column=1, padx=8,       pady=(0, 14))
        self.inter.grid(row=1, column=2, padx=12,      pady=(0, 14))
        self.narr.grid( row=1, column=3, padx=8,       pady=(0, 14))

        ctk.CTkLabel(scroll, text="Select invoice to return against",
                     font=T.f(14, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=28, pady=(6, 2))

        hdr = ctk.CTkFrame(scroll, fg_color="#E8EDF5", corner_radius=0, height=28)
        hdr.pack(fill="x", padx=28)
        hdr.pack_propagate(False)
        for txt, w in (("Date", 110), ("Invoice", 120), ("Total", 160),
                       ("Balance", 160), ("Select", 80)):
            ctk.CTkLabel(hdr, text=txt, font=T.f(11, "bold"), text_color=T.MUTED,
                         width=w, anchor="w").pack(side="left", padx=(12, 4))

        self.inv_frame = ctk.CTkScrollableFrame(
            scroll, fg_color="white", border_width=1, border_color="#D1D5DB",
            corner_radius=0, height=130)
        self.inv_frame.pack(fill="x", padx=28)
        self._selected_inv_id  = None
        self._inv_radio_var    = ctk.StringVar(value="")

        foot = ctk.CTkFrame(scroll, fg_color="transparent")
        foot.pack(fill="x", padx=28, pady=10)
        T.button(foot, "Save Credit Note", self.save, width=180).pack(side="left")
        self._make_msg(foot)

        self._build_rows_area(scroll)
        self._party_changed(self.party.get())
        focus_later(self.rows[0][0])

    def _party_changed(self, name=None):
        if name is None:
            name = self.party.get()
        row = self.con.execute("SELECT gstin FROM parties WHERE name=?", (name,)).fetchone()
        if row and b.is_interstate(row["gstin"], self.company_gstin):
            self.inter.select()
        else:
            self.inter.deselect()
        self._load_invoices(name)
        self.calc()

    def _load_invoices(self, party):
        for w in self.inv_frame.winfo_children():
            w.destroy()
        self._selected_inv_id = None
        self._inv_radio_var.set("")
        self._open_bills = b.open_invoices(self.con, party, "Sales")
        for i, o in enumerate(self._open_bills):
            bg  = "white" if i % 2 == 0 else "#F8FAFD"
            row = ctk.CTkFrame(self.inv_frame, fg_color=bg, corner_radius=0, height=32)
            row.pack(fill="x")
            row.pack_propagate(False)
            ctk.CTkLabel(row, text=disp_date(o["vdate"]), font=T.f(12),
                         text_color=T.TEXT, width=110, anchor="w").pack(side="left", padx=(12, 4))
            ctk.CTkLabel(row, text=f"Sales #{o['vno']}", font=T.f(12),
                         text_color=T.TEXT, width=120, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=inr(o["total"] / 100), font=T.f(12),
                         text_color=T.MUTED, width=160, anchor="e").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=inr(o["balance"] / 100), font=T.f(12, "bold"),
                         text_color=T.TEXT, width=160, anchor="e").pack(side="left", padx=4)
            rb = ctk.CTkRadioButton(row, text="", variable=self._inv_radio_var,
                                    value=str(o["id"]), width=60,
                                    fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                                    command=lambda oid=o["id"]: self._select_inv(oid))
            rb.pack(side="left", padx=8)

    def _select_inv(self, inv_id):
        self._selected_inv_id = inv_id

    def _collect(self):
        items = []
        for desc, hsn, qty, rate, gst, _amt in self.rows:
            d, h, q, r = (desc.get().strip(), hsn.get().strip(),
                          qty.get().strip(),  rate.get().strip())
            if not (d or q or r):
                continue
            if not q or not r:
                raise ValueError("Every item needs a quantity and a rate")
            items.append((d or "Item", h, parse_amount(q), parse_amount(r), float(gst.get())))
        return items

    def calc(self, _e=None):
        for _d, _h, qty, rate, _g, amt in self.rows:
            try:
                q, rt = parse_amount(qty.get()), parse_amount(rate.get())
                amt.configure(text=inr(q * rt) if q and rt else "")
            except ValueError:
                amt.configure(text="")
        try:
            items     = self._collect()
            tax_items = [(d, q, r, g) for d, _h, q, r, g in items]
            t = b.compute_tax(tax_items, bool(self.inter.get()))
        except ValueError:
            self.summary.configure(text="")
            return
        k   = lambda v: inr(v / 100)
        tax = (f"IGST {k(t['igst'])}" if self.inter.get()
               else f"CGST {k(t['cgst'])}   SGST {k(t['sgst'])}")
        self.summary.configure(
            text=f"Taxable {k(t['taxable'])}     {tax}     Total {k(t['total'])}")

    def is_dirty(self):
        return any(d.get().strip() or q.get().strip() or r.get().strip()
                   for d, _h, q, r, _g, _a in self.rows)

    def save(self):
        try:
            if not self._selected_inv_id:
                raise ValueError("Select the invoice to return against")
            d     = parse_date(self.date.get())
            items = self._collect()
            if not items:
                raise ValueError("Enter at least one item to return")
            res = b.post_sales_return(
                self.con, d, self.party.get().strip(),
                self._selected_inv_id, items,
                bool(self.inter.get()),
                self.narr.get().strip() or "Sales return",
                self.username)
        except ValueError as e:
            self.err(str(e))
            return
        for desc, hsn, qty, rate, _g, amt in self.rows:
            for e in (desc, hsn, qty, rate):
                e.delete(0, "end")
            amt.configure(text="")
        self.narr.delete(0, "end")
        self.summary.configure(text="")
        self._party_changed(self.party.get())
        self.ok(f"Credit Note no. {res['vno']} saved. Total Rs {inr(res['total'])}")
        focus_later(self.rows[0][0], 50)


# ── PurchaseReturnFrame ───────────────────────────────────────────────────────

class PurchaseReturnFrame(_ReturnRowsMixin, EntryBase):
    GST_RATES = ["0", "0.25", "1.5", "3", "5", "12", "18", "28", "40"]
    ROWS = 3

    def __init__(self, master, con, username="", opener=None):
        super().__init__(master, fg_color="transparent")
        self._init_base(con, username, opener)
        self.rows = []
        self._open_bills   = []
        self.company_gstin = settings.load_settings().get("gstin", "")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        T.title(scroll, "Purchase Return / Debit Note",
                "Select the supplier and the original bill to return against. "
                "Enter returned items and quantities."
                ).pack(anchor="w", padx=28, pady=(10, 6))

        top = T.card(scroll)
        top.pack(fill="x", padx=28)
        self.date = T.entry(top, width=140)
        self.date.insert(0, today_str())

        parties = [p["name"] for p in s.list_parties(con, "Supplier")]
        pw = ctk.CTkFrame(top, fg_color="transparent")
        self.party = T.combo(pw, parties, width=240, command=self._party_changed)
        self.party.set(parties[0] if parties else "")
        self.party.pack(side="left")
        self.ac = Autocomplete(self.party, parties, on_pick=self._party_changed)

        self.inter = ctk.CTkCheckBox(top, text="Inter-state (IGST)", font=T.f(13),
                                     text_color=T.TEXT, fg_color=T.ACCENT,
                                     hover_color=T.ACCENT_HOVER, command=self.calc)
        self.narr  = T.entry(top, "Reason for return (optional)", width=300)

        _lbl(top, "Date",     row=0, column=0, sticky="w", padx=(20, 8), pady=(14, 2))
        _lbl(top, "Supplier", row=0, column=1, sticky="w", padx=8,       pady=(14, 2))
        _lbl(top, "Narration",row=0, column=3, sticky="w", padx=8,       pady=(14, 2))
        self.date.grid(row=1, column=0, padx=(20, 8), pady=(0, 14))
        pw.grid(        row=1, column=1, padx=8,       pady=(0, 14))
        self.inter.grid(row=1, column=2, padx=12,      pady=(0, 14))
        self.narr.grid( row=1, column=3, padx=8,       pady=(0, 14))

        ctk.CTkLabel(scroll, text="Select bill to return against",
                     font=T.f(14, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=28, pady=(6, 2))

        hdr = ctk.CTkFrame(scroll, fg_color="#E8EDF5", corner_radius=0, height=28)
        hdr.pack(fill="x", padx=28)
        hdr.pack_propagate(False)
        for txt, w in (("Date", 110), ("Bill", 120), ("Total", 160),
                       ("Balance", 160), ("Select", 80)):
            ctk.CTkLabel(hdr, text=txt, font=T.f(11, "bold"), text_color=T.MUTED,
                         width=w, anchor="w").pack(side="left", padx=(12, 4))

        self.inv_frame = ctk.CTkScrollableFrame(
            scroll, fg_color="white", border_width=1, border_color="#D1D5DB",
            corner_radius=0, height=130)
        self.inv_frame.pack(fill="x", padx=28)
        self._selected_inv_id = None
        self._inv_radio_var   = ctk.StringVar(value="")

        foot = ctk.CTkFrame(scroll, fg_color="transparent")
        foot.pack(fill="x", padx=28, pady=10)
        T.button(foot, "Save Debit Note", self.save, width=180).pack(side="left")
        self._make_msg(foot)

        self._build_rows_area(scroll)
        self._party_changed(self.party.get())
        focus_later(self.rows[0][0])

    def _party_changed(self, name=None):
        if name is None:
            name = self.party.get()
        row = self.con.execute("SELECT gstin FROM parties WHERE name=?", (name,)).fetchone()
        if row and b.is_interstate(row["gstin"], self.company_gstin):
            self.inter.select()
        else:
            self.inter.deselect()
        self._load_bills(name)
        self.calc()

    def _load_bills(self, party):
        for w in self.inv_frame.winfo_children():
            w.destroy()
        self._selected_inv_id = None
        self._inv_radio_var.set("")
        self._open_bills = b.open_invoices(self.con, party, "Purchase")
        for i, o in enumerate(self._open_bills):
            bg  = "white" if i % 2 == 0 else "#F8FAFD"
            row = ctk.CTkFrame(self.inv_frame, fg_color=bg, corner_radius=0, height=32)
            row.pack(fill="x")
            row.pack_propagate(False)
            ctk.CTkLabel(row, text=disp_date(o["vdate"]), font=T.f(12),
                         text_color=T.TEXT, width=110, anchor="w").pack(side="left", padx=(12, 4))
            ctk.CTkLabel(row, text=f"Purchase #{o['vno']}", font=T.f(12),
                         text_color=T.TEXT, width=120, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=inr(o["total"] / 100), font=T.f(12),
                         text_color=T.MUTED, width=160, anchor="e").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=inr(o["balance"] / 100), font=T.f(12, "bold"),
                         text_color=T.TEXT, width=160, anchor="e").pack(side="left", padx=4)
            rb = ctk.CTkRadioButton(row, text="", variable=self._inv_radio_var,
                                    value=str(o["id"]), width=60,
                                    fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                                    command=lambda oid=o["id"]: self._select_inv(oid))
            rb.pack(side="left", padx=8)

    def _select_inv(self, inv_id):
        self._selected_inv_id = inv_id

    def _collect(self):
        items = []
        for desc, hsn, qty, rate, gst, _amt in self.rows:
            d, h, q, r = (desc.get().strip(), hsn.get().strip(),
                          qty.get().strip(),  rate.get().strip())
            if not (d or q or r):
                continue
            if not q or not r:
                raise ValueError("Every item needs a quantity and a rate")
            items.append((d or "Item", h, parse_amount(q), parse_amount(r), float(gst.get())))
        return items

    def calc(self, _e=None):
        for _d, _h, qty, rate, _g, amt in self.rows:
            try:
                q, rt = parse_amount(qty.get()), parse_amount(rate.get())
                amt.configure(text=inr(q * rt) if q and rt else "")
            except ValueError:
                amt.configure(text="")
        try:
            items     = self._collect()
            tax_items = [(d, q, r, g) for d, _h, q, r, g in items]
            t = b.compute_tax(tax_items, bool(self.inter.get()))
        except ValueError:
            self.summary.configure(text="")
            return
        k   = lambda v: inr(v / 100)
        tax = (f"IGST {k(t['igst'])}" if self.inter.get()
               else f"CGST {k(t['cgst'])}   SGST {k(t['sgst'])}")
        self.summary.configure(
            text=f"Taxable {k(t['taxable'])}     {tax}     Total {k(t['total'])}")

    def is_dirty(self):
        return any(d.get().strip() or q.get().strip() or r.get().strip()
                   for d, _h, q, r, _g, _a in self.rows)

    def save(self):
        try:
            if not self._selected_inv_id:
                raise ValueError("Select the bill to return against")
            d     = parse_date(self.date.get())
            items = self._collect()
            if not items:
                raise ValueError("Enter at least one item to return")
            res = b.post_purchase_return(
                self.con, d, self.party.get().strip(),
                self._selected_inv_id, items,
                bool(self.inter.get()),
                self.narr.get().strip() or "Purchase return",
                self.username)
        except ValueError as e:
            self.err(str(e))
            return
        for desc, hsn, qty, rate, _g, amt in self.rows:
            for e in (desc, hsn, qty, rate):
                e.delete(0, "end")
            amt.configure(text="")
        self.narr.delete(0, "end")
        self.summary.configure(text="")
        self._party_changed(self.party.get())
        self.ok(f"Debit Note no. {res['vno']} saved. Total Rs {inr(res['total'])}")
        focus_later(self.rows[0][0], 50)
