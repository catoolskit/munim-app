import sys
from datetime import date
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from db import setup as s, reports as rep
from ui import theme as T
from ui.menus import MENUS
from ui.party import PartyFrame
from ui.entry_screens import (JournalFrame, TradeFrame, SummaryFrame,
                              PaymentFrame, SalesReturnFrame, PurchaseReturnFrame)
from ui.help import HelpFrame
from ui.account_master import AccountMasterFrame
from ui.stock_items import StockItemsFrame
from ui.report_screens import (ReportBase,
                               TrialBalanceFrame, LedgerFrame, DayBookFrame,
                               OutstandingFrame, ProfitLossFrame, BalanceSheetFrame,
                               InvoiceRegisterFrame, ReturnsRegisterFrame,
                               StockSummaryFrame, ItemWiseProfitFrame,
                               GSTR1Frame, GSTR3BFrame,
                               CashFlowFrame, PartyStatementFrame, BankReconFrame)
from ui.about import AboutFrame
from ui.voucher_dialog import VoucherDialog
from ui.widgets import ErrorPanel
from ui.utilities import (CompanyFrame, PasswordFrame, AuditFrame, ResetDataFrame,
                          RenewLicenceFrame, DataLocationFrame, ManageCompaniesFrame,
                          TallyImportFrame)
# ui.dashboard loaded lazily — do NOT import at top level (PyInstaller)
from utils import errlog, logger
from utils import settings
from utils import backup as bkup
from utils.fmt import inr, disp_date
from utils.keyboard import is_text_input_widget, single_key_action, alt_shortcut_action


PAGES = {
    "party": ("Party Master", lambda sh: PartyFrame(sh.body, sh.con)),
    "company": ("Company Details", lambda sh: CompanyFrame(sh.body, sh.refresh_company)),
    "password": ("Change Password", lambda sh: PasswordFrame(sh.body, sh.con, sh.username)),
    "reset": ("Reset All Data", lambda sh: ResetDataFrame(sh.body, sh.con, on_done=sh._go_to_gateway)),
    "renew": ("Renew Licence", lambda sh: RenewLicenceFrame(sh.body)),
    "datalocation": ("Data Location", lambda sh: DataLocationFrame(sh.body)),
    "companies": ("Manage Companies", lambda sh: ManageCompaniesFrame(sh.body)),
    "about": ("About MUNIM", lambda sh: AboutFrame(sh.body)),
    "journal": ("Voucher Entry", lambda sh: JournalFrame(sh.body, sh.con, sh.username, sh.take_edit(), sh.go_back, sh.open_voucher)),
    "sales": ("Sales Invoice", lambda sh: TradeFrame(sh.body, sh.con, "Sales", sh.username, sh.take_edit(), sh.go_back, sh.open_voucher)),
    "purchase": ("Purchase Bill", lambda sh: TradeFrame(sh.body, sh.con, "Purchase", sh.username, sh.take_edit(), sh.go_back, sh.open_voucher)),
    "salesreturn": ("Sales Return", lambda sh: SalesReturnFrame(sh.body, sh.con, sh.username, sh.open_voucher)),
    "purchasereturn": ("Purchase Return", lambda sh: PurchaseReturnFrame(sh.body, sh.con, sh.username, sh.open_voucher)),
    "summary": ("Daily Sales Summary", lambda sh: SummaryFrame(sh.body, sh.con, sh.username, sh.open_voucher)),
    "payment": ("Receipt / Payment", lambda sh: PaymentFrame(sh.body, sh.con, sh.username, sh.open_voucher)),
    "outstanding": ("Outstanding", lambda sh: OutstandingFrame(sh.body, sh.con, sh.open_voucher)),
    "help": ("Help & Shortcuts", lambda sh: HelpFrame(sh.body)),
    "accounts": ("Ledger Accounts", lambda sh: AccountMasterFrame(sh.body, sh.con)),
    "stockitems": ("Stock Items", lambda sh: StockItemsFrame(sh.body, sh.con)),
    "salesreg": ("Sales Register", lambda sh: InvoiceRegisterFrame(sh.body, sh.con, "Sales", sh.open_voucher)),
    "purchasereg": ("Purchase Register", lambda sh: InvoiceRegisterFrame(sh.body, sh.con, "Purchase", sh.open_voucher)),
    "salesreturnreg": ("Sales Return Register", lambda sh: ReturnsRegisterFrame(sh.body, sh.con, "Sales Return", sh.open_voucher)),
    "purchasereturnreg": ("Purchase Return Register", lambda sh: ReturnsRegisterFrame(sh.body, sh.con, "Purchase Return", sh.open_voucher)),
    "stocksummary": ("Stock Summary", lambda sh: StockSummaryFrame(sh.body, sh.con)),
    "itemprofit": ("Item-wise Profit", lambda sh: ItemWiseProfitFrame(sh.body, sh.con)),
    "gstr1": ("GSTR-1", lambda sh: GSTR1Frame(sh.body, sh.con)),
    "gstr3b": ("GSTR-3B", lambda sh: GSTR3BFrame(sh.body, sh.con)),
    "audit": ("Audit Log", lambda sh: AuditFrame(sh.body, sh.con, sh.open_voucher)),
    "trial": ("Trial Balance", lambda sh: TrialBalanceFrame(sh.body, sh.con)),
    "ledger": ("Ledger View", lambda sh: sh._make_ledger_frame()),
    "cashbook": ("Cash Book", lambda sh: LedgerFrame(sh.body, sh.con, ["Cash", "Bank"], "Cash Book",
                                                     "Cash and bank entries with a running balance.")),
    "daybook": ("Day Book", lambda sh: DayBookFrame(sh.body, sh.con, sh.open_voucher)),
    "pl": ("Trading & P&L", lambda sh: ProfitLossFrame(sh.body, sh.con)),
    "bs": ("Balance Sheet", lambda sh: BalanceSheetFrame(sh.body, sh.con)),
    "dashboard": ("Dashboard", lambda sh: __import__('ui.dashboard', fromlist=['DashboardFrame']).DashboardFrame(sh.body, sh.con, sh)),
    "cashflow": ("Cash Flow", lambda sh: CashFlowFrame(sh.body, sh.con)),
    "partystatement": ("Party Statement", lambda sh: PartyStatementFrame(sh.body, sh.con)),
    "bankrecon": ("Bank Reconciliation", lambda sh: BankReconFrame(sh.body, sh.con)),
    "tallyimport": ("Import from Tally", lambda sh: TallyImportFrame(sh.body, sh.con)),
    "mobileexport": ("Export Mobile Config", lambda sh: __import__('ui.utilities', fromlist=['MobileExportFrame']).MobileExportFrame(sh.body, sh.con)),
    "mobileimport": ("Import Mobile Invoices", lambda sh: __import__('ui.utilities', fromlist=['MobileImportFrame']).MobileImportFrame(sh.body, sh.con)),
}

SEP = "   ·   "
LABEL_TEXT = "#4A5468"       # secondary text, darker than T.MUTED for contrast
SEL_BG = "#EAF0FC"
TILE_BG, TILE_BG_SEL, TILE_BORDER = "#FFFFFF", "#EEF4FF", "#DDE3EE"

# Screens where the user types a voucher: footer leads with Save / Print.
ENTRY_PAGES = {"journal", "sales", "purchase", "salesreturn",
               "purchasereturn", "summary", "payment"}


class MenuView(ctk.CTkFrame):
    """Gateway = workspace tiles. Every other menu = compact option list."""

    GATEWAY_COLS = 2
    LIST_WIDTH = 620

    def __init__(self, master, title, items, on_pick, side=None, selected_index=0):
        super().__init__(master, fg_color=T.BG)
        self.on_pick, self.sel, self.rows, self.chips = on_pick, 0, [], []
        self.is_gateway = title.lower().startswith("gateway")
        if self.is_gateway:
            # Only real workspaces become tiles; Log out is a secondary action.
            self.items = [it for it in items if it["go"] and it["go"][0] == "menu"]
            self.secondary = [it for it in items if it not in self.items]
        else:
            self.items, self.secondary = list(items), []

        page = ctk.CTkFrame(self, fg_color="transparent")
        page.pack(fill="both", expand=True, padx=26, pady=(22, 18))

        heading = ctk.CTkFrame(page, fg_color="transparent")
        heading.pack(fill="x", pady=(0, 14))
        text_box = ctk.CTkFrame(heading, fg_color="transparent")
        text_box.pack(side="left", anchor="w")
        ctk.CTkLabel(text_box, text=("Welcome to MUNIM" if self.is_gateway else title),
                     font=T.f(25, "bold"), text_color=T.TEXT).pack(anchor="w")
        ctk.CTkLabel(text_box,
                     text=("Choose a work area or jump directly into a common task."
                           if self.is_gateway else
                           "Use ↑ ↓ and Enter, or press the letter shown next to an option."),
                     font=T.f(12), text_color=LABEL_TEXT).pack(anchor="w", pady=(3, 0))

        for it in self.secondary:
            ctk.CTkButton(
                heading, text=f"{it['label']}   {it['key']}",
                command=lambda it=it: self.on_pick(it),
                width=120, height=34, corner_radius=8,
                fg_color="transparent", hover_color="#E7ECF5",
                border_width=1, border_color=T.BORDER,
                text_color=T.TEXT, font=T.f(12, "bold")
            ).pack(side="right", anchor="n", padx=(8, 0))

        content = ctk.CTkFrame(page, fg_color="transparent")
        content.pack(fill="both", expand=True)
        if self.is_gateway:
            self._build_gateway(page, content, side)
        else:
            self._build_list(content)

        if self.items:
            self.select(max(0, min(selected_index, len(self.items) - 1)))

    # ── Gateway: tiles ────────────────────────────────────────────────────
    def _build_gateway(self, page, content, side):
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0)
        content.grid_rowconfigure(0, weight=1)

        nav = T.card(content)
        nav.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        ctk.CTkLabel(nav, text="WORKSPACES", font=T.f(10, "bold"),
                     text_color=T.MUTED).pack(anchor="w", padx=22, pady=(18, 12))
        grid = ctk.CTkFrame(nav, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        cols = self.GATEWAY_COLS
        n_rows = max(1, -(-len(self.items) // cols))
        for c in range(cols):
            grid.grid_columnconfigure(c, weight=1, uniform="tiles")
        for r in range(n_rows):
            grid.grid_rowconfigure(r, weight=1, uniform="tiles")

        descs = {"Masters": "Customers, suppliers and stock",
                 "Transactions": "Sales, purchases and vouchers",
                 "Reports": "Ledgers, statements and financials",
                 "Utilities": "Company, data and security"}

        for i, it in enumerate(self.items):
            tile = ctk.CTkFrame(grid, fg_color=TILE_BG, border_width=2,
                                border_color=TILE_BORDER, corner_radius=12, height=128)
            tile.grid(row=i // cols, column=i % cols, sticky="nsew", padx=6, pady=6)
            tile.pack_propagate(False)
            num = ctk.CTkLabel(tile, text=f"{i + 1:02d}", font=T.f(10, "bold"),
                               text_color=T.ACCENT, fg_color=SEL_BG,
                               corner_radius=6, width=34, height=24)
            num.pack(anchor="w", padx=18, pady=(16, 8))
            key = ctk.CTkLabel(tile, text=it["key"], font=T.f(11, "bold"),
                               text_color=LABEL_TEXT, fg_color="#F1F4F9",
                               corner_radius=5, width=26, height=22)
            key.place(relx=1.0, x=-16, y=16, anchor="ne")
            lbl = ctk.CTkLabel(tile, text=it["label"], font=T.f(17, "bold"),
                               text_color=T.TEXT, anchor="w")
            lbl.pack(anchor="w", padx=18)
            sub = ctk.CTkLabel(tile, text=descs.get(it["label"], "Open workspace"),
                               font=T.f(12), text_color=LABEL_TEXT, anchor="w")
            sub.pack(anchor="w", padx=18, pady=(4, 0))
            for w in (tile, num, key, lbl, sub):
                w.bind("<Button-1>", lambda _e, i=i: self.pick(i))
                w.bind("<Enter>", lambda _e, i=i: self.select(i))
            self.rows.append(tile)
            self.chips.append(num)

        if side:
            side(content).grid(row=0, column=1, sticky="ns")

        # Common routes are direct, explicit shortcuts without changing the menu tree.
        quick = T.card(page)
        quick.pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(quick, text="QUICK ACTIONS", font=T.f(10, "bold"),
                     text_color=T.MUTED).pack(anchor="w", padx=18, pady=(10, 7))
        actions = ctk.CTkFrame(quick, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(0, 12))
        for label, key, target in [("＋ Sales Invoice", "S", "sales"),
                                   ("＋ Purchase Bill", "P", "purchase"),
                                   ("▤ Ledger View", "L", "ledger"),
                                   ("▦ Dashboard", "D", "dashboard")]:
            T.button(actions, label,
                     lambda target=target, label=label, key=key: self.on_pick(
                         {"go": ("page", target), "label": label, "key": key}),
                     height=34, fg_color=SEL_BG, text_color=T.TEXT,
                     hover_color="#DCE6F8", font=T.f(11, "bold")
                     ).pack(side="left", fill="x", expand=True, padx=4)

    # ── Other menus: compact list, no side card ───────────────────────────
    def _build_list(self, content):
        nav = T.card(content)
        nav.pack(anchor="nw")
        ctk.CTkLabel(nav, text="AVAILABLE OPTIONS", font=T.f(10, "bold"),
                     text_color=T.MUTED).pack(anchor="w", padx=20, pady=(16, 8))
        if len(self.items) > 10:
            listing = ctk.CTkScrollableFrame(nav, fg_color="transparent",
                                             width=self.LIST_WIDTH, height=460)
        else:
            listing = ctk.CTkFrame(nav, fg_color="transparent")
        listing.pack(padx=10, pady=(0, 12))

        for i, it in enumerate(self.items):
            enabled = it["go"] is not None
            row = ctk.CTkFrame(listing, fg_color="transparent", corner_radius=8,
                               width=self.LIST_WIDTH, height=44,
                               border_width=1, border_color=T.CARD)
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)
            lbl = ctk.CTkLabel(row, text=it["label"],
                               font=T.f(13, "bold" if enabled else "normal"),
                               text_color=T.TEXT if enabled else "#A3ACBF", anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=12)
            chip = ctk.CTkLabel(row, text=it["key"] if enabled else "Soon",
                                font=T.f(10, "bold"),
                                text_color=T.ACCENT if enabled else T.MUTED,
                                fg_color=SEL_BG if enabled else "transparent",
                                corner_radius=5, width=30, height=22)
            chip.pack(side="right", padx=10)
            for w in (row, lbl, chip):
                w.bind("<Button-1>", lambda _e, i=i: self.pick(i))
                w.bind("<Enter>", lambda _e, i=i: self.select(i))
            self.rows.append(row)

    # ── Selection & keys ──────────────────────────────────────────────────
    def select(self, i):
        if not self.rows:
            return
        self.sel = i
        for n, row in enumerate(self.rows):
            on = n == i
            if self.is_gateway:
                row.configure(fg_color=TILE_BG_SEL if on else TILE_BG,
                              border_color=T.ACCENT if on else TILE_BORDER)
                self.chips[n].configure(fg_color=T.ACCENT if on else SEL_BG,
                                        text_color="white" if on else T.ACCENT)
            else:
                row.configure(fg_color=SEL_BG if on else "transparent",
                              border_color="#C9D8F5" if on else T.CARD)

    def pick(self, i):
        self.select(i)
        self.on_pick(self.items[i])

    def _letter(self, k):
        if len(k) != 1:
            return None
        for i, it in enumerate(self.items):
            if it["key"].lower() == k.lower():
                self.pick(i)
                return None
        for it in self.secondary:
            if it["key"].lower() == k.lower():
                self.on_pick(it)
                return None
        return None

    def handle(self, event):
        """Returns "back" when the shell should go back (Left in a list menu)."""
        k, n = event.keysym, len(self.items)
        if not n:
            return None
        if k in ("Return", "KP_Enter"):
            self.pick(self.sel)
            return None
        if self.is_gateway:
            c = self.GATEWAY_COLS
            if k == "Right":
                self.select((self.sel + 1) % n)
            elif k == "Left":
                self.select((self.sel - 1) % n)
            elif k == "Down":
                self.select(self.sel + c if self.sel + c < n else self.sel % c)
            elif k == "Up":
                if self.sel - c >= 0:
                    self.select(self.sel - c)
                else:
                    col = self.sel % c
                    self.select(col + ((n - 1 - col) // c) * c)
            else:
                return self._letter(k)
            return None
        if k == "Down":
            self.select((self.sel + 1) % n)
        elif k == "Up":
            self.select((self.sel - 1) % n)
        elif k == "Right":
            self.pick(self.sel)
        elif k == "Left":
            return "back"
        else:
            return self._letter(k)
        return None


class Shell(ctk.CTkFrame):
    def __init__(self, master, con, username, role, on_logout):
        super().__init__(master, fg_color="transparent")
        self.con, self.username, self.role, self.on_logout = con, username, role, on_logout
        self.stack, self.current, self._edit_id = [], None, None
        self._ledger_account = None
        # Remember each menu's highlighted row while navigating into submenus/pages.
        self._menu_selection = {}
        self._flash_job = None
        self.top = self.winfo_toplevel()

        bar = ctk.CTkFrame(self, fg_color=T.NAVY, corner_radius=0, height=64)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, text="MUNIM", font=T.f(21, "bold"),
                     text_color="white").pack(side="left", padx=(22, 18))
        self.back_btn = ctk.CTkButton(
            bar, text="← Back", width=88, height=34, corner_radius=9,
            fg_color=T.NAVY_HOVER, hover_color=T.NAVY_ACTIVE,
            font=T.f(12, "bold"), command=self.go_back)
        self.home_btn = ctk.CTkButton(
            bar, text="⌂ Home", width=88, height=34, corner_radius=9,
            fg_color=T.NAVY_HOVER, hover_color=T.NAVY_ACTIVE,
            font=T.f(12, "bold"), command=self._go_to_gateway)
        self.crumb = ctk.CTkLabel(bar, text="", font=T.f(13), text_color="#9FB3D9")
        self.crumb.pack(side="left", padx=14)
        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.pack(side="right", padx=20)
        self.company_lbl = ctk.CTkLabel(right, text="", font=T.f(13, "bold"),
                                        text_color="white")
        self.company_lbl.pack(anchor="e")
        from datetime import date as _d
        ctk.CTkLabel(right, text=f"FY {s.fy_of(_d.today())} · {username}",
                     font=T.f(11), text_color="#9FB3D9").pack(anchor="e")

        # Footer: shortcuts relevant to the current screen only.
        self.status = ctk.CTkLabel(self, text="", font=T.f(11), text_color=LABEL_TEXT,
                                   anchor="w", fg_color="#EDF1F7", height=30,
                                   corner_radius=0, padx=18)
        self.status.pack(side="bottom", fill="x")

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)

        self.top.bind("<Key>", self._on_key)
        self.top.bind("<Control-s>", self._on_save)
        self.top.bind("<Control-S>", self._on_save)
        self.top.bind("<Control-e>", self._on_export_excel)
        self.top.bind("<Control-E>", self._on_export_excel)
        self.top.bind("<Control-p>", self._on_print_pdf)
        self.top.bind("<Control-P>", self._on_print_pdf)
        self.top.bind("<Control-Shift-p>", self._on_print_pdf)
        self.top.bind("<Control-Shift-P>", self._on_print_pdf)
        # One global Alt handler avoids duplicate/conflicting bindings.
        self.top.bind("<Alt-Key>", self._on_alt_key)

        self.refresh_company()
        self.push(("menu", "gateway"))

    def destroy(self):
        if self._flash_job is not None:
            try:
                self.after_cancel(self._flash_job)
            except Exception:
                pass
            self._flash_job = None
        try:
            self._do_auto_backup()
        except Exception:
            pass
        try:
            self.top.unbind("<Key>")
            self.top.unbind("<Control-s>")
            self.top.unbind("<Control-S>")
            self.top.unbind("<Control-e>")
            self.top.unbind("<Control-E>")
            self.top.unbind("<Control-p>")
            self.top.unbind("<Control-P>")
            self.top.unbind("<Control-Shift-p>")
            self.top.unbind("<Control-Shift-P>")
            self.top.unbind("<Alt-Key>")
        except Exception:
            pass
        super().destroy()

    def _do_auto_backup(self):
        st = settings.load_settings()
        company = st.get("company_name", "company")
        path = bkup.auto_backup(self.con, company, st)
        if path:
            st = bkup.record_backup(st)
            settings.save_settings(st)

    def _remember_menu_selection(self):
        if self.stack and isinstance(self.current, MenuView):
            self._menu_selection[self.stack[-1][1]] = self.current.sel

    def push(self, node):
        self._remember_menu_selection()
        self.stack.append(node)
        self.render()

    def go_back(self):
        if len(self.stack) > 1:
            dirty = getattr(self.current, "is_dirty", None)
            if callable(dirty) and dirty():
                if not messagebox.askyesno(
                        "Unsaved entry",
                        "You have typed something that is not saved yet.\n\n"
                        "Leave this screen and lose it?"):
                    return
            self._remember_menu_selection()
            self.stack.pop()
            self.render()

    def _go_to_gateway(self):
        self.stack.clear()
        self.push(("menu", "gateway"))

    def render(self):
        if self.current is not None:
            self.current.destroy()
        kind, name = self.stack[-1]
        if kind == "menu":
            title, items = MENUS[name]
            side = self._info_card if name == "gateway" else None
            self.current = MenuView(
                self.body, title, items, self.pick, side,
                selected_index=self._menu_selection.get(name, 0))
            self.top.focus_set()
        else:
            try:
                self.current = PAGES[name][1](self)
            except Exception:
                msg = logger.log_exception(*sys.exc_info())
                self.current = ErrorPanel(self.body, msg)
                messagebox.showerror(
                    "MUNIM — Something went wrong",
                    f"An error occurred opening this screen.\n\n"
                    f"Details saved to:\n{errlog.log_path()}\n\n"
                    f"Share this file with support if the problem continues.")
        self.current.pack(fill="both", expand=True)
        labels = ["Gateway"] + [
            MENUS[n][0] if k == "menu" else PAGES[n][0]
            for k, n in self.stack[1:]]
        self.crumb.configure(text=" › ".join(labels))
        # Show Back and Home only when not at gateway
        if len(self.stack) > 1:
            self.back_btn.pack(side="left", before=self.crumb)
            self.home_btn.pack(side="left", before=self.crumb)
        else:
            self.back_btn.pack_forget()
            self.home_btn.pack_forget()
        self._refresh_hint()

    def pick(self, item):
        go = item["go"]
        if go is None:
            self._flash(f"{item['label']} arrives in a later release.")
        elif go[0] in ("menu", "page"):
            self.push((go[0], go[1]))
        elif go[0] == "fn":
            self.backup()
        elif go[0] == "quit":
            self.on_logout()

    def _make_ledger_frame(self):
        selected = self._ledger_account
        self._ledger_account = None
        return LedgerFrame(self.body, self.con, initial_account=selected)

    def _open_ledger_account(self, account_name):
        self._ledger_account = account_name
        self.push(("page", "ledger"))

    def _goto_items(self):
        """Build searchable navigation destinations and current ledger accounts."""
        items = []
        seen = set()

        def add(label, kind, target, search_terms=()):
            key = (kind, str(target))
            terms = " ".join((label, *search_terms)).casefold()
            if key in seen:
                for existing in items:
                    if (existing["kind"], str(existing["target"])) == key:
                        existing["terms"] += " " + terms
                        break
                return
            seen.add(key)
            items.append({"label": label, "kind": kind, "target": target,
                          "terms": terms})

        # Menus and pages from the actual routing table, so only real destinations appear.
        for menu_key, (menu_title, menu_items) in MENUS.items():
            if menu_key != "gateway":
                add(menu_title, "menu", menu_key)
            for item in menu_items:
                go = item.get("go")
                if go and go[0] == "page" and go[1] in PAGES:
                    add(item["label"], "page", go[1])
                elif go and go[0] == "menu":
                    add(item["label"], "menu", go[1])

        # Include any routed pages not explicitly surfaced by the current menu tree.
        for page_key, (page_title, _factory) in PAGES.items():
            aliases = {
                "pl": ("Profit & Loss", "P&L", "Profit and Loss"),
                "bs": ("Balance Sheet",),
                "ledger": ("Account Ledger", "Ledger Statement"),
                "partystatement": ("Party Ledger",),
            }.get(page_key, ())
            add(page_title, "page", page_key, (page_key, *aliases))

        # Accounts are individual ledger destinations. Party names are already linked
        # to their account names by db.setup.add_party. Hide only unused legacy
        # group-named control ledgers; if they have opening balance or entries,
        # retain them but label them clearly as an existing ledger.
        for row in self.con.execute(
                "SELECT id, name, grp, opening FROM accounts ORDER BY name COLLATE NOCASE"):
            name = row["name"]
            label = name
            if name in ("Sundry Debtors", "Sundry Creditors") and row["grp"] == name:
                has_entries = self.con.execute(
                    "SELECT 1 FROM entries WHERE account_id=? LIMIT 1",
                    (row["id"],)).fetchone() is not None
                if not row["opening"] and not has_entries:
                    continue
                label = f"{name} · Existing ledger"
            add(label, "ledger", name, (name,))
        return items

    def _open_goto(self, _event=None):
        if getattr(self, "_goto_popup", None) is not None:
            try:
                if self._goto_popup.winfo_exists():
                    self._goto_popup.focus_force()
                    return "break"
            except Exception:
                pass

        popup = ctk.CTkToplevel(self.top)
        self._goto_popup = popup
        popup.title("Go To — MUNIM")
        popup.geometry("620x500")
        popup.minsize(520, 380)
        popup.transient(self.top)
        popup.grab_set()

        ctk.CTkLabel(popup, text="Go To", font=T.f(20, "bold"),
                     text_color=T.TEXT).pack(anchor="w", padx=20, pady=(18, 2))
        ctk.CTkLabel(popup, text="Search a screen, party or ledger. Enter opens it.",
                     font=T.f(12), text_color=T.MUTED).pack(anchor="w", padx=20, pady=(0, 12))
        query = ctk.CTkEntry(popup, placeholder_text="Type a name…", height=38)
        query.pack(fill="x", padx=20, pady=(0, 10))

        frame = ctk.CTkFrame(popup, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=(0, 18))
        tree = ttk.Treeview(frame, columns=("type",), show="tree headings",
                            style="Munim.Treeview", selectmode="browse")
        tree.heading("#0", text="Destination", anchor="w")
        tree.heading("type", text="Type", anchor="w")
        tree.column("#0", width=410, stretch=True)
        tree.column("type", width=120, stretch=False)
        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview,
                           style="Munim.Vertical.TScrollbar")
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        items = self._goto_items()
        filtered = []

        def refresh(_value=None):
            nonlocal filtered
            q = query.get().strip().casefold()
            filtered = [x for x in items if not q or q in x["terms"]]
            tree.delete(*tree.get_children())
            for i, item in enumerate(filtered):
                typ = "Ledger" if item["kind"] == "ledger" else (
                    "Screen" if item["kind"] == "page" else "Menu")
                tree.insert("", "end", iid=str(i), text=item["label"], values=(typ,))
            if filtered:
                tree.selection_set("0")
                tree.focus("0")

        def open_selected(_event=None):
            sel = tree.selection()
            if not sel:
                return "break"
            item = filtered[int(sel[0])]
            popup.destroy()
            self._goto_popup = None
            if item["kind"] == "ledger":
                self._open_ledger_account(item["target"])
            elif item["kind"] == "page":
                self.push(("page", item["target"]))
            else:
                self.push(("menu", item["target"]))
            return "break"

        query.bind("<KeyRelease>", refresh)
        query.bind("<Return>", lambda _e: open_selected())
        tree.bind("<Double-1>", open_selected)
        tree.bind("<Return>", open_selected)
        tree.bind("<Escape>", lambda _e: (popup.destroy(), setattr(self, "_goto_popup", None), "break")[-1])
        popup.bind("<Escape>", lambda _e: (popup.destroy(), setattr(self, "_goto_popup", None), "break")[-1])
        popup.protocol("WM_DELETE_WINDOW", lambda: (popup.destroy(), setattr(self, "_goto_popup", None)))
        refresh()
        query.focus_set()
        return "break"

    def open_voucher(self, vid, refresh):
        VoucherDialog(self.top, self.con, vid, self.username,
                      on_edit=self.edit_voucher, on_changed=refresh)

    def edit_voucher(self, vid):
        vt = self.con.execute(
            "SELECT vtype FROM vouchers WHERE id=?", (vid,)).fetchone()["vtype"]
        self._edit_id = vid
        self.push(("page", {"Sales": "sales", "Purchase": "purchase"}.get(vt, "journal")))

    def take_edit(self):
        vid, self._edit_id = self._edit_id, None
        return vid

    # ── Context-sensitive footer ──────────────────────────────────────────
    @staticmethod
    def _excel_action(page):
        act = getattr(page, "_export_excel", None)
        if callable(act):
            return act
        act = getattr(page, "export", None)
        if callable(act):
            # ReportBase.export() needs export_data(); without it, it would crash.
            if (isinstance(page, ReportBase) and not hasattr(page, "export_data")
                    and type(page).export is ReportBase.export):
                return None
            return act
        return None

    @staticmethod
    def _pdf_action(page):
        # Ctrl+P and Ctrl+Shift+P run the screen's existing PDF/print handler;
        # they do not create a new accounting or document-generation path.
        for name in ("_export_pdf", "_save_pdf", "print_report"):
            act = getattr(page, name, None)
            if callable(act):
                return act
        return None

    def _footer_hint(self):
        kind, name = self.stack[-1]
        if kind == "menu":
            if name == "gateway":
                parts = ["↑ ↓ ← → Navigate", "Enter Open", "Alt+G Go To", "Q Log out"]
            else:
                parts = ["↑ ↓ ← → Navigate", "Enter Open", "Alt+G Go To",
                         "Alt+H Home", "Esc Back"]
            return SEP.join(parts)

        page, parts = self.current, []
        if callable(getattr(page, "save", None)):
            parts.append("Ctrl+S Save")
        if name in ENTRY_PAGES:
            if self._pdf_action(page):
                parts.append("Ctrl+P Print")
        else:
            if self._excel_action(page):
                parts.append("Ctrl+E Export Excel")
            if self._pdf_action(page):
                parts.append("Ctrl+Shift+P Print/PDF")
            if getattr(page, "picker", None) is not None:
                parts.append("Alt+O Select ledger")
            table = getattr(page, "table", None)
            if table is not None and getattr(table, "_open_cb", None):
                parts.append("Enter Open voucher")
        parts.append("Esc Back")
        return SEP.join(parts)

    def _refresh_hint(self):
        if self._flash_job is not None:
            try:
                self.after_cancel(self._flash_job)
            except Exception:
                pass
        self._flash_job = None
        try:
            self.status.configure(text=self._footer_hint())
        except Exception:
            pass

    def _flash(self, text, ms=3500):
        """Show a temporary message, then restore the screen's shortcuts."""
        if self._flash_job is not None:
            try:
                self.after_cancel(self._flash_job)
            except Exception:
                pass
        self.status.configure(text=text)
        self._flash_job = self.after(ms, self._refresh_hint)

    def _on_save(self, _event=None):
        save = getattr(self.current, "save", None)
        if callable(save):
            save()
        else:
            self._flash("Ctrl+S · This screen has no Save action.")
        return "break"

    def _on_export_excel(self, _event=None):
        try:
            focused = self.top.focus_get()
        except Exception:
            focused = None
        if is_text_input_widget(focused):
            return None
        action = self._excel_action(self.current)
        if action:
            action()
        else:
            self._flash("Ctrl+E · Excel export is not available on this screen.")
        return "break"

    def _on_print_pdf(self, _event=None):
        try:
            focused = self.top.focus_get()
        except Exception:
            focused = None
        if is_text_input_widget(focused):
            return None
        action = self._pdf_action(self.current)
        if action:
            action()
        else:
            self._flash("Print/PDF is not available on this screen.")
        return "break"

    def _on_alt_key(self, event):
        key = (event.keysym or "").casefold()
        action = alt_shortcut_action(event.keysym)
        if key == "o":
            # Alt+O is a context-specific shortcut for the Ledger View selector.
            picker = getattr(self.current, "picker", None)
            if picker is not None:
                picker.open()
                return "break"
            return None
        if key == "s":
            picker = getattr(self.current, "picker", None)
            if picker is not None and picker.focus_search():
                return "break"
            return None
        if action == "home":
            self._go_to_gateway()
        elif action == "help":
            self._open_help()
        elif action == "goto":
            self._open_goto()
        else:
            return None
        return "break"

    def _open_help(self, _event=None):
        self.push(("page", "help"))
        return "break"

    def _on_key(self, event):
        if event.keysym == "Escape":
            self.go_back()
            return "break"
        if isinstance(self.current, MenuView):
            if self.current.handle(event) == "back":
                self.go_back()
            return "break"
        # R/P are application shortcuts only outside text-entry controls and
        # only when no modifier is held. Never intercept normal typing.
        if event.state & (0x1 | 0x4 | 0x8):
            return
        try:
            focused = self.top.focus_get()
        except Exception:
            focused = getattr(event, "widget", None)
        action = single_key_action(event.keysym,
                                   text_input_focused=is_text_input_widget(focused))
        if action and action in PAGES:
            self.push(("page", action))
            return "break"

    def refresh_company(self):
        name = settings.load_settings().get("company_name", "")
        self.company_lbl.configure(text=name or "Set up your company")

    def _info_card(self, parent):
        from db.setup import stock_summary as _ss
        st = settings.load_settings()
        c = s.counts(self.con)
        receivable, payable = rep.receivable_payable(self.con)
        fy = s.fy_of(date.today())
        today_str = date.today().isoformat()
        month_start = date.today().replace(day=1).isoformat()

        try:
            today_sales = self.con.execute(
                """SELECT COALESCE(SUM(inv.total),0)
                   FROM invoices inv JOIN vouchers v ON v.id=inv.voucher_id
                   WHERE v.vtype='Sales' AND v.vdate=?""",
                (today_str,)).fetchone()[0]
        except Exception:
            today_sales = 0
        try:
            month_sales = self.con.execute(
                """SELECT COALESCE(SUM(inv.total),0)
                   FROM invoices inv JOIN vouchers v ON v.id=inv.voucher_id
                   WHERE v.vtype='Sales' AND v.vdate BETWEEN ? AND ?""",
                (month_start, today_str)).fetchone()[0]
        except Exception:
            month_sales = 0
        try:
            stock_items = _ss(self.con, fy)
            stock_value = sum(it.get("stock_value", 0.0) for it in stock_items)
        except Exception:
            stock_value = 0.0
        try:
            out_rep = rep.outstanding_report(self.con, "Sales")
            top_debtors = sorted(
                (p for p in out_rep["parties"] if p["balance"] > 0),
                key=lambda p: -p["balance"])[:2]
        except Exception:
            top_debtors = []

        # Use the existing accounting engine's account states for liquidity.
        # Values are stored in paise; aggregate by account group, not account
        # name, so additional bank accounts are included automatically.
        try:
            states, _prior_pl = s.account_states(self.con, fy, date_to=date.today())
            cash_paise = sum(x["bf"] + x["dr"] - x["cr"]
                             for x in states if x["grp"] == "Cash-in-hand")
            bank_paise = sum(x["bf"] + x["dr"] - x["cr"]
                             for x in states if x["grp"] == "Bank Accounts")
        except Exception:
            cash_paise = bank_paise = 0

        def balance_text(paise):
            side = "Dr" if paise >= 0 else "Cr"
            return f"Rs {inr(s.to_rupees(abs(paise)))} {side}"

        # Keep the gateway summary inside the visible window. On shorter
        # displays the card scrolls internally instead of clipping its rounded
        # top/bottom edges or pushing the gateway menu off-screen.
        available_h = max(300, min(600, self.top.winfo_screenheight() - 190))
        card = ctk.CTkScrollableFrame(
            parent, width=350, height=available_h, fg_color=T.CARD,
            border_width=1, border_color=T.BORDER, corner_radius=12,
            scrollbar_button_color="#C5CEE0",
            scrollbar_button_hover_color="#A9B6D0")

        ctk.CTkLabel(card, text="CURRENT COMPANY", font=T.f(10, "bold"),
                     text_color=T.MUTED).pack(anchor="w", padx=24, pady=(14, 3))
        ctk.CTkLabel(card, text=st.get("company_name") or "Company name not set",
                     font=T.f(19, "bold"), text_color=T.TEXT,
                     wraplength=300, justify="left").pack(anchor="w", padx=24)
        ctk.CTkLabel(card, text=f"Financial year {fy}", font=T.f(11),
                     text_color=LABEL_TEXT).pack(anchor="w", padx=24, pady=(2, 8))
        ctk.CTkFrame(card, fg_color=T.BORDER, height=1).pack(fill="x", padx=24)

        def section(title):
            ctk.CTkLabel(card, text=title, font=T.f(10, "bold"),
                         text_color=T.ACCENT).pack(anchor="w", padx=24, pady=(10, 2))

        def row(label, value, color=T.TEXT, bold=False):
            r = ctk.CTkFrame(card, fg_color=T.CARD, corner_radius=0, height=26)
            r.pack(fill="x", padx=24)
            r.pack_propagate(False)
            ctk.CTkLabel(r, text=label, font=T.f(12), text_color=LABEL_TEXT,
                         anchor="w", width=154, height=26).pack(side="left")
            ctk.CTkLabel(r, text=value, font=T.f(12, "bold" if bold else "normal"),
                         text_color=color, anchor="e", height=26).pack(side="right")

        section("TODAY")
        row("Today's sales", f"Rs {inr(s.to_rupees(today_sales))}",
            T.OK if today_sales else T.TEXT)
        row("This month", f"Rs {inr(s.to_rupees(month_sales))}")

        section("OUTSTANDING")
        row("Customers owe you", f"Rs {inr(receivable)}",
            T.OK if receivable else T.TEXT, bold=True)
        row("You owe suppliers", f"Rs {inr(payable)}",
            "#B26A00" if payable else T.TEXT, bold=True)

        section("CASH & BANK")
        row("Cash in hand", balance_text(cash_paise))
        row("Bank balance", balance_text(bank_paise))

        section("STOCK")
        row("Stock value", f"Rs {inr(stock_value)}")

        if top_debtors:
            section("TOP DEBTORS")
            for p in top_debtors:
                row(p["party"][:24], f"Rs {inr(p['balance'])}",
                    T.DANGER if p["balance"] > 50000 else T.TEXT)

        ctk.CTkFrame(card, fg_color=T.BORDER, height=1).pack(
            fill="x", padx=24, pady=(8, 0))
        last = st.get("last_backup")
        nag = bkup.should_nag(st)
        section("BACKUP")
        if last:
            row("Last backup", disp_date(last), T.DANGER if nag else T.OK)
        else:
            row("Last backup", "never", T.DANGER)
        if nag:
            banner = ctk.CTkFrame(card, fg_color="#FFF3CD", corner_radius=6)
            banner.pack(fill="x", padx=24, pady=(5, 3))
            ctk.CTkLabel(banner,
                         text="⚠ No backup in over 7 days\nUtilities > Backup Data",
                         font=T.f(11), text_color="#7A4F00",
                         wraplength=240, justify="left").pack(padx=10, pady=6)

        steps = [
            ("Set up your company", bool(st.get("company_name")),
             "Utilities > Company Details"),
            ("Add a customer or supplier", c["parties"] > 0,
             "Masters > Party Master"),
            ("Record a sale or purchase", c["vouchers"] > 0,
             "Transactions"),
            ("Take a backup", bool(last),
             "Utilities > Backup Data"),
        ]
        if not all(done for _t, done, _h in steps):
            completed = sum(done for _t, done, _h in steps)
            ctk.CTkButton(
                card, text=f"Setup guide · {completed}/4 complete",
                height=30, corner_radius=7, fg_color="#E7ECF5",
                text_color=T.TEXT, hover_color="#DCE3F0", font=T.f(11),
                command=lambda: self._show_setup_guide(steps)
            ).pack(fill="x", padx=24, pady=(9, 3))

        ctk.CTkFrame(card, fg_color=T.CARD, corner_radius=0, height=6).pack()
        return card

    def _show_setup_guide(self, steps):
        popup = ctk.CTkToplevel(self.top)
        popup.title("Getting Started — MUNIM")
        popup.geometry("500x340")
        popup.resizable(False, False)
        popup.transient(self.top)
        popup.grab_set()

        completed = sum(done for _text, done, _hint in steps)
        ctk.CTkLabel(
            popup, text="Getting Started",
            font=T.f(20, "bold"), text_color=T.TEXT
        ).pack(anchor="w", padx=24, pady=(22, 4))
        ctk.CTkLabel(
            popup, text=f"{completed} of {len(steps)} steps completed",
            font=T.f(12), text_color=T.MUTED
        ).pack(anchor="w", padx=24, pady=(0, 14))

        for text, done, hint in steps:
            line = ctk.CTkFrame(popup, fg_color="transparent")
            line.pack(fill="x", padx=24, pady=5)
            ctk.CTkLabel(
                line, text=("✓" if done else "○"), width=24,
                font=T.f(14, "bold"), text_color=T.OK if done else T.MUTED
            ).pack(side="left")
            ctk.CTkLabel(
                line, text=text, font=T.f(12),
                text_color=T.OK if done else T.TEXT, anchor="w"
            ).pack(side="left")
            if not done:
                ctk.CTkLabel(
                    popup, text=hint, font=T.f(11),
                    text_color=T.ACCENT, anchor="w"
                ).pack(anchor="w", padx=52, pady=(0, 2))

        ctk.CTkButton(
            popup, text="Close", width=100, height=32,
            command=popup.destroy
        ).pack(pady=(16, 18))

    def backup(self):
        st = settings.load_settings()
        folder = filedialog.askdirectory(
            title="Choose a folder for the backup",
            initialdir=s.data_dir())
        if not folder:
            return
        try:
            path = s.backup_db(self.con, folder)
        except Exception as e:
            messagebox.showerror("MUNIM", f"Backup failed:\n{e}")
            return
        st = bkup.record_backup(st)
        settings.save_settings(st)
        messagebox.showinfo("MUNIM",
                            f"Backup saved:\n{path}\n\n"
                            "Keep a copy on a USB drive or cloud folder, "
                            "not only on this PC.")
