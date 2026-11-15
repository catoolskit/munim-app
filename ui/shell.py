import sys
from datetime import date
from tkinter import filedialog, messagebox
import customtkinter as ctk
from db import setup as s
from ui import theme as T
from ui.menus import MENUS
from ui.party import PartyFrame
from ui.entry_screens import JournalFrame, TradeFrame
from ui.report_screens import (TrialBalanceFrame, LedgerFrame, DayBookFrame,
                               ProfitLossFrame, BalanceSheetFrame)
from ui.widgets import ErrorPanel
from utils import errlog
from ui.utilities import CompanyFrame, PasswordFrame
from utils import settings

PAGES = {
    "party": ("Party Master", lambda sh: PartyFrame(sh.body, sh.con)),
    "company": ("Company Details", lambda sh: CompanyFrame(sh.body, sh.refresh_company)),
    "password": ("Change Password", lambda sh: PasswordFrame(sh.body, sh.con, sh.username)),
    "journal": ("Voucher Entry", lambda sh: JournalFrame(sh.body, sh.con)),
    "sales": ("Sales Invoice", lambda sh: TradeFrame(sh.body, sh.con, "Sales")),
    "purchase": ("Purchase Bill", lambda sh: TradeFrame(sh.body, sh.con, "Purchase")),
    "trial": ("Trial Balance", lambda sh: TrialBalanceFrame(sh.body, sh.con)),
    "ledger": ("Ledger View", lambda sh: LedgerFrame(sh.body, sh.con)),
    "cashbook": ("Cash Book", lambda sh: LedgerFrame(sh.body, sh.con, ["Cash", "Bank"], "Cash Book",
                                                      "Cash and bank entries with a running balance.")),
    "daybook": ("Day Book", lambda sh: DayBookFrame(sh.body, sh.con)),
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
            row = ctk.CTkFrame(card, fg_color="transparent", corner_radius=8, height=46, width=352)
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
        self.stack, self.current = [], None
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
        self.refresh_company()
        self.push(("menu", "gateway"))

    def destroy(self):
        try:
            self.top.unbind("<Key>")
        except Exception:
            pass
        super().destroy()

    # ---- navigation stack ----
    def push(self, node):
        self.stack.append(node)
        self.render()

    def go_back(self):
        if len(self.stack) > 1:
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
        card = T.card(parent, width=300)
        ctk.CTkLabel(card, text="CURRENT COMPANY", font=T.f(11, "bold"), text_color=T.MUTED).pack(
            anchor="w", padx=24, pady=(20, 6))
        ctk.CTkLabel(card, text=st.get("company_name") or "Not set up yet", font=T.f(18, "bold"),
                     text_color=T.TEXT, wraplength=250, justify="left").pack(anchor="w", padx=24)
        ctk.CTkLabel(card, text=f"Financial year {s.fy_of(date.today())}", font=T.f(12),
                     text_color=T.MUTED).pack(anchor="w", padx=24, pady=(2, 14))
        for label, key in (("Parties", "parties"), ("Ledger accounts", "accounts"),
                           ("Vouchers", "vouchers")):
            r = ctk.CTkFrame(card, fg_color="transparent")
            r.pack(fill="x", padx=24, pady=3)
            ctk.CTkLabel(r, text=label, font=T.f(13), text_color=T.MUTED).pack(side="left")
            ctk.CTkLabel(r, text=str(c[key]), font=T.f(13, "bold"), text_color=T.TEXT).pack(side="right")
        if not st.get("company_name"):
            ctk.CTkLabel(card, text="Tip: add your company under Utilities > Company Details.",
                         font=T.f(12), text_color=T.ACCENT, wraplength=250, justify="left").pack(
                anchor="w", padx=24, pady=(14, 0))
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
        messagebox.showinfo("MUNIM", f"Backup saved:\n{path}\n\nKeep a copy on a USB drive or cloud folder, not only on this PC.")
