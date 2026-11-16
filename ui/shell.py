import sys
from datetime import date
from tkinter import filedialog, messagebox
import customtkinter as ctk
from db import setup as s, reports as rep
from ui import theme as T
from ui.menus import MENUS
from ui.party import PartyFrame
from ui.entry_screens import JournalFrame, TradeFrame, SummaryFrame, PaymentFrame
from ui.help import HelpFrame
from ui.report_screens import (TrialBalanceFrame, LedgerFrame, DayBookFrame, OutstandingFrame,
                               ProfitLossFrame, BalanceSheetFrame, InvoiceRegisterFrame)
from ui.voucher_dialog import VoucherDialog
from ui.widgets import ErrorPanel
from utils import errlog
from ui.utilities import CompanyFrame, PasswordFrame, AuditFrame
from utils import settings
from utils.fmt import inr, disp_date

PAGES = {
    "party": ("Party Master", lambda sh: PartyFrame(sh.body, sh.con)),
    "company": ("Company Details", lambda sh: CompanyFrame(sh.body, sh.refresh_company)),
    "password": ("Change Password", lambda sh: PasswordFrame(sh.body, sh.con, sh.username)),
    "journal": ("Voucher Entry", lambda sh: JournalFrame(sh.body, sh.con, sh.username, sh.take_edit(), sh.go_back, sh.open_voucher)),
    "sales": ("Sales Invoice", lambda sh: TradeFrame(sh.body, sh.con, "Sales", sh.username, sh.take_edit(), sh.go_back, sh.open_voucher)),
    "purchase": ("Purchase Bill", lambda sh: TradeFrame(sh.body, sh.con, "Purchase", sh.username, sh.take_edit(), sh.go_back, sh.open_voucher)),
    "summary": ("Daily Sales Summary", lambda sh: SummaryFrame(sh.body, sh.con, sh.username, sh.open_voucher)),
    "payment": ("Receipt / Payment", lambda sh: PaymentFrame(sh.body, sh.con, sh.username, sh.open_voucher)),
    "outstanding": ("Outstanding", lambda sh: OutstandingFrame(sh.body, sh.con, sh.open_voucher)),
    "help": ("Help & Shortcuts", lambda sh: HelpFrame(sh.body)),
    "salesreg": ("Sales Register", lambda sh: InvoiceRegisterFrame(sh.body, sh.con, "Sales", sh.open_voucher)),
    "purchasereg": ("Purchase Register", lambda sh: InvoiceRegisterFrame(sh.body, sh.con, "Purchase", sh.open_voucher)),
    "audit": ("Audit Log", lambda sh: AuditFrame(sh.body, sh.con)),
    "trial": ("Trial Balance", lambda sh: TrialBalanceFrame(sh.body, sh.con)),
    "ledger": ("Ledger View", lambda sh: LedgerFrame(sh.body, sh.con)),
    "cashbook": ("Cash Book", lambda sh: LedgerFrame(sh.body, sh.con, ["Cash", "Bank"], "Cash Book",
                                                      "Cash and bank entries with a running balance.")),
    "daybook": ("Day Book", lambda sh: DayBookFrame(sh.body, sh.con, sh.open_voucher)),
    "pl": ("Profit & Loss", lambda sh: ProfitLossFrame(sh.body, sh.con)),
    "bs": ("Balance Sheet", lambda sh: BalanceSheetFrame(sh.body, sh.con)),
}
SEL_BG, HINT = "#E6EEFA", "↑ ↓ move     Enter open     Letter jump     Esc back"


class MenuView(ctk.CTkFrame):
    """A Tally-style centred menu: arrows + Enter, or press the highlighted letter."""
    def __init__(self, master, title, items, on_pick, side=None):
        super().__init__(master, fg_color="transparent")
        self.items, self.on_pick, self.sel, self.rows = items, on_pick, 0, []
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.place(relx=0.5, rely=0.46, anchor="center")
        if side:
            side(wrap).pack(side="left", padx=14, anchor="n")
        card = T.card(wrap, width=400)
        card.pack(side="left", padx=14, anchor="n")
        ctk.CTkLabel(card, text=title.upper(), font=T.f(11, "bold"), text_color=T.MUTED).pack(
            anchor="w", padx=24, pady=(20, 8))
        for i, it in enumerate(items):
            on = it["go"] is not None
            row = ctk.CTkFrame(card, fg_color="transparent", corner_radius=8, height=42, width=352)
            row.pack(padx=16, pady=(2, 16) if i == len(items) - 1 else 2)
            row.pack_propagate(False)
            lbl = ctk.CTkLabel(row, text=it["label"], font=T.f(15), anchor="w",
                               text_color=T.TEXT if on else "#A3ACBF")
            lbl.pack(side="left", padx=14)
            chip = ctk.CTkLabel(row, text=it["key"] if on else "soon", font=T.f(11, "bold"),
                                text_color=T.ACCENT if on else "#A3ACBF",
                                fg_color=SEL_BG if on else "transparent",
                                corner_radius=6, width=34 if on else 40, height=22)
            chip.pack(side="right", padx=12)
            for w in (row, lbl, chip):
                w.bind("<Button-1>", lambda _e, i=i: self.pick(i))
                w.bind("<Motion>", lambda _e, i=i: self.select(i))
            self.rows.append(row)
        self.select(0)

    def select(self, i):
        self.sel = i
        for n, r in enumerate(self.rows):
            r.configure(fg_color=SEL_BG if n == i else "transparent")

    def pick(self, i):
        self.select(i)
        self.on_pick(self.items[i])

    def handle(self, event):
        k = event.keysym
        if k == "Down":
            self.select((self.sel + 1) % len(self.items))
        elif k == "Up":
            self.select((self.sel - 1) % len(self.items))
        elif k in ("Return", "KP_Enter"):
            self.pick(self.sel)
        elif len(k) == 1:
            for i, it in enumerate(self.items):
                if it["key"].lower() == k.lower():
                    self.pick(i)
                    break


class Shell(ctk.CTkFrame):
    def __init__(self, master, con, username, role, on_logout):
        super().__init__(master, fg_color="transparent")
        self.con, self.username, self.role, self.on_logout = con, username, role, on_logout
        self.stack, self.current, self._edit_id = [], None, None
        self.top = self.winfo_toplevel()

        bar = ctk.CTkFrame(self, fg_color=T.NAVY, corner_radius=0, height=58)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, text="MUNIM", font=T.f(20, "bold"), text_color="white").pack(
            side="left", padx=(22, 18))
        self.back_btn = ctk.CTkButton(bar, text="←  Back", width=84, height=32, corner_radius=8,
                                      fg_color=T.NAVY_HOVER, hover_color=T.NAVY_ACTIVE,
                                      font=T.f(12, "bold"), command=self.go_back)
        self.crumb = ctk.CTkLabel(bar, text="", font=T.f(13), text_color="#9FB3D9")
        self.crumb.pack(side="left", padx=14)
        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.pack(side="right", padx=20)
        self.company_lbl = ctk.CTkLabel(right, text="", font=T.f(13, "bold"), text_color="white")
        self.company_lbl.pack(anchor="e")
        ctk.CTkLabel(right, text=f"FY {s.fy_of(date.today())}  ·  {username}", font=T.f(11),
                     text_color="#9FB3D9").pack(anchor="e")

        self.status = ctk.CTkLabel(self, text=HINT, font=T.f(11), text_color=T.MUTED, anchor="w",
                                   fg_color="#EAEEF5", height=28, corner_radius=0)
        self.status.pack(side="bottom", fill="x")
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)

        self.top.bind("<Key>", self._on_key)
        self.top.bind("<Control-s>", self._on_save)
        self.top.bind("<Control-S>", self._on_save)
        self.refresh_company()
        self.push(("menu", "gateway"))

    def destroy(self):
        try:
            self.top.unbind("<Key>")
            self.top.unbind("<Control-s>")
            self.top.unbind("<Control-S>")
        except Exception:
            pass
        super().destroy()

    # ---- navigation stack ----
    def push(self, node):
        self.stack.append(node)
        self.render()

    def go_back(self):
        if len(self.stack) > 1:
            dirty = getattr(self.current, "is_dirty", None)
            if callable(dirty) and dirty():
                if not messagebox.askyesno("Unsaved entry", "You have typed something that is not saved yet.\n\n"
                                           "Leave this screen and lose it?"):
                    return
            self.stack.pop()
            self.render()

    def render(self):
        if self.current is not None:
            self.current.destroy()
        kind, name = self.stack[-1]
        self.status.configure(text=HINT)
        if kind == "menu":
            title, items = MENUS[name]
            side = self._info_card if name == "gateway" else None
            self.current = MenuView(self.body, title, items, self.pick, side)
            self.top.focus_set()
        else:
            try:
                self.current = PAGES[name][1](self)
            except Exception:
                self.current = ErrorPanel(self.body, errlog.log_exception(*sys.exc_info()))
        self.current.pack(fill="both", expand=True)
        labels = ["Gateway"] + [MENUS[n][0] if k == "menu" else PAGES[n][0] for k, n in self.stack[1:]]
        self.crumb.configure(text="  ›  ".join(labels))
        if len(self.stack) > 1:
            self.back_btn.pack(side="left", before=self.crumb)
        else:
            self.back_btn.pack_forget()

    def pick(self, item):
        go = item["go"]
        if go is None:
            self.status.configure(text=f"{item['label']} arrives in a later release.")
        elif go[0] in ("menu", "page"):
            self.push((go[0], go[1]))
        elif go[0] == "fn":
            self.backup()
        elif go[0] == "quit":
            self.on_logout()

    def open_voucher(self, vid, refresh):
        VoucherDialog(self.top, self.con, vid, self.username, on_edit=self.edit_voucher, on_changed=refresh)

    def edit_voucher(self, vid):
        vt = self.con.execute("SELECT vtype FROM vouchers WHERE id=?", (vid,)).fetchone()["vtype"]
        self._edit_id = vid
        self.push(("page", {"Sales": "sales", "Purchase": "purchase"}.get(vt, "journal")))

    def take_edit(self):
        vid, self._edit_id = self._edit_id, None
        return vid

    def _on_save(self, _event=None):
        save = getattr(self.current, "save", None)
        if callable(save):
            save()
        return "break"

    def _on_key(self, event):
        if event.keysym == "Escape":
            self.go_back()
        elif isinstance(self.current, MenuView):
            self.current.handle(event)

    # ---- bits ----
    def refresh_company(self):
        name = settings.load_settings().get("company_name", "")
        self.company_lbl.configure(text=name or "Set up your company")

    def _info_card(self, parent):
        st = settings.load_settings()
        c = s.counts(self.con)
        receivable, payable = rep.receivable_payable(self.con)
        card = T.card(parent, width=300)
        ctk.CTkLabel(card, text="CURRENT COMPANY", font=T.f(11, "bold"), text_color=T.MUTED).pack(
            anchor="w", padx=24, pady=(20, 6))
        ctk.CTkLabel(card, text=st.get("company_name") or "Not set up yet", font=T.f(18, "bold"),
                     text_color=T.TEXT, wraplength=250, justify="left").pack(anchor="w", padx=24)
        ctk.CTkLabel(card, text=f"Financial year {s.fy_of(date.today())}", font=T.f(12),
                     text_color=T.MUTED).pack(anchor="w", padx=24, pady=(2, 14))
        def row(label, value, color=T.TEXT):
            r = ctk.CTkFrame(card, fg_color=T.CARD, corner_radius=0)
            r.pack(fill="x", padx=24, pady=3)
            ctk.CTkLabel(r, text=label, font=T.f(13), text_color=T.MUTED).pack(side="left")
            ctk.CTkLabel(r, text=value, font=T.f(13, "bold"), text_color=color).pack(side="right")
        row("Customers owe you", inr(receivable), T.OK if receivable else T.TEXT)
        row("You owe suppliers", inr(payable), "#B26A00" if payable else T.TEXT)
        row("Vouchers", str(c["vouchers"]))
        last = st.get("last_backup")
        if last:
            days = (date.today() - date.fromisoformat(last)).days
            row("Last backup", disp_date(last), T.DANGER if days > 7 else T.OK)
        else:
            row("Last backup", "never", T.DANGER)
        steps = [("Set up your company", bool(st.get("company_name")), "Utilities > Company Details"),
                 ("Add a customer or supplier", c["parties"] > 0, "Masters > Party Master"),
                 ("Record a sale or purchase", c["vouchers"] > 0, "Transactions"),
                 ("Take a backup", bool(last), "Utilities > Backup Data")]
        if not all(done for _t, done, _h in steps):
            ctk.CTkLabel(card, text="GETTING STARTED", font=T.f(11, "bold"), text_color=T.MUTED).pack(
                anchor="w", padx=24, pady=(16, 4))
            for text, done, hint in steps:
                ctk.CTkLabel(card, text=("✓  " if done else "○  ") + text, font=T.f(13),
                             text_color=T.OK if done else T.TEXT).pack(anchor="w", padx=24, pady=(3, 0))
                if not done:
                    ctk.CTkLabel(card, text="     " + hint, font=T.f(11), text_color=T.ACCENT).pack(
                        anchor="w", padx=24)
        ctk.CTkFrame(card, fg_color=T.CARD, corner_radius=0, height=18).pack()
        return card

    def backup(self):
        folder = filedialog.askdirectory(title="Choose a folder for the backup")
        if not folder:
            return
        try:
            path = s.backup_db(self.con, folder)
        except Exception as e:
            messagebox.showerror("MUNIM", f"Backup failed:\n{e}")
            return
        st = settings.load_settings()
        st["last_backup"] = date.today().isoformat()
        settings.save_settings(st)
        messagebox.showinfo("MUNIM", f"Backup saved:\n{path}\n\nKeep a copy on a USB drive or cloud folder, not only on this PC.")
