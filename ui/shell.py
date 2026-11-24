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
from ui.report_screens import (TrialBalanceFrame, LedgerFrame, DayBookFrame,
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
    "party":          ("Party Master",        lambda sh: PartyFrame(sh.body, sh.con)),
    "company":        ("Company Details",     lambda sh: CompanyFrame(sh.body, sh.refresh_company)),
    "password":       ("Change Password",     lambda sh: PasswordFrame(sh.body, sh.con, sh.username)),
    "reset":          ("Reset All Data",      lambda sh: ResetDataFrame(sh.body, sh.con, on_done=sh._go_to_gateway)),
    "renew":          ("Renew Licence",       lambda sh: RenewLicenceFrame(sh.body)),
    "datalocation":   ("Data Location",       lambda sh: DataLocationFrame(sh.body)),
    "companies":      ("Manage Companies",    lambda sh: ManageCompaniesFrame(sh.body)),
    "about":          ("About MUNIM",         lambda sh: AboutFrame(sh.body)),
    "journal":        ("Voucher Entry",       lambda sh: JournalFrame(sh.body, sh.con, sh.username, sh.take_edit(), sh.go_back, sh.open_voucher)),
    "sales":          ("Sales Invoice",       lambda sh: TradeFrame(sh.body, sh.con, "Sales", sh.username, sh.take_edit(), sh.go_back, sh.open_voucher)),
    "purchase":       ("Purchase Bill",       lambda sh: TradeFrame(sh.body, sh.con, "Purchase", sh.username, sh.take_edit(), sh.go_back, sh.open_voucher)),
    "salesreturn":    ("Sales Return",        lambda sh: SalesReturnFrame(sh.body, sh.con, sh.username, sh.open_voucher)),
    "purchasereturn": ("Purchase Return",     lambda sh: PurchaseReturnFrame(sh.body, sh.con, sh.username, sh.open_voucher)),
    "summary":        ("Daily Sales Summary", lambda sh: SummaryFrame(sh.body, sh.con, sh.username, sh.open_voucher)),
    "payment":        ("Receipt / Payment",   lambda sh: PaymentFrame(sh.body, sh.con, sh.username, sh.open_voucher)),
    "outstanding":    ("Outstanding",         lambda sh: OutstandingFrame(sh.body, sh.con, sh.open_voucher)),
    "help":           ("Help & Shortcuts",    lambda sh: HelpFrame(sh.body)),
    "accounts":       ("Ledger Accounts",     lambda sh: AccountMasterFrame(sh.body, sh.con)),
    "stockitems":     ("Stock Items",         lambda sh: StockItemsFrame(sh.body, sh.con)),
    "salesreg":       ("Sales Register",      lambda sh: InvoiceRegisterFrame(sh.body, sh.con, "Sales", sh.open_voucher)),
    "purchasereg":    ("Purchase Register",   lambda sh: InvoiceRegisterFrame(sh.body, sh.con, "Purchase", sh.open_voucher)),
    "salesreturnreg":    ("Sales Return Register",    lambda sh: ReturnsRegisterFrame(sh.body, sh.con, "Sales Return",    sh.open_voucher)),
    "purchasereturnreg": ("Purchase Return Register", lambda sh: ReturnsRegisterFrame(sh.body, sh.con, "Purchase Return", sh.open_voucher)),
    "stocksummary":   ("Stock Summary",       lambda sh: StockSummaryFrame(sh.body, sh.con)),
    "itemprofit":     ("Item-wise Profit",    lambda sh: ItemWiseProfitFrame(sh.body, sh.con)),
    "gstr1":          ("GSTR-1",              lambda sh: GSTR1Frame(sh.body, sh.con)),
    "gstr3b":         ("GSTR-3B",             lambda sh: GSTR3BFrame(sh.body, sh.con)),
    "audit":          ("Audit Log",           lambda sh: AuditFrame(sh.body, sh.con, sh.open_voucher)),
    "trial":          ("Trial Balance",       lambda sh: TrialBalanceFrame(sh.body, sh.con)),
    "ledger":         ("Ledger View",         lambda sh: sh._make_ledger_frame()),
    "cashbook":       ("Cash Book",           lambda sh: LedgerFrame(sh.body, sh.con, ["Cash", "Bank"], "Cash Book",
                                                                      "Cash and bank entries with a running balance.")),
    "daybook":        ("Day Book",            lambda sh: DayBookFrame(sh.body, sh.con, sh.open_voucher)),
    "pl":             ("Trading & P&L",       lambda sh: ProfitLossFrame(sh.body, sh.con)),
    "bs":             ("Balance Sheet",       lambda sh: BalanceSheetFrame(sh.body, sh.con)),
    "dashboard":      ("Dashboard",           lambda sh: __import__('ui.dashboard', fromlist=['DashboardFrame']).DashboardFrame(sh.body, sh.con)),
    "cashflow":       ("Cash Flow",           lambda sh: CashFlowFrame(sh.body, sh.con)),
    "partystatement": ("Party Statement",     lambda sh: PartyStatementFrame(sh.body, sh.con)),
    "bankrecon":      ("Bank Reconciliation", lambda sh: BankReconFrame(sh.body, sh.con)),
    "tallyimport":    ("Import from Tally",   lambda sh: TallyImportFrame(sh.body, sh.con)),
    "mobileexport": ("Export Mobile Config",   lambda sh: __import__('ui.utilities', fromlist=['MobileExportFrame']).MobileExportFrame(sh.body, sh.con)),
    "mobileimport": ("Import Mobile Invoices", lambda sh: __import__('ui.utilities', fromlist=['MobileImportFrame']).MobileImportFrame(sh.body, sh.con)),
}

SEL_BG, HINT = "#EAF0FC", "↑ ↓ Navigate    Enter Open    Alt+G Go To    Alt+H Home    Alt+1 Help    Esc Back"


class MenuView(ctk.CTkFrame):
    def __init__(self, master, title, items, on_pick, side=None, selected_index=0):
        super().__init__(master, fg_color="transparent")
        self.items, self.on_pick, self.sel, self.rows = items, on_pick, 0, []
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.place(relx=0.5, rely=0.50, anchor="center")
        if side:
            side(wrap).pack(side="left", padx=10, pady=10, anchor="center")
        card = T.card(wrap, width=400)
        card.pack(side="left", padx=10, pady=10, anchor="center")
        ctk.CTkLabel(card, text=title.upper(), font=T.f(11, "bold"),
                     text_color=T.MUTED).pack(anchor="w", padx=24, pady=(16, 6))
        for i, it in enumerate(items):
            on = it["go"] is not None
            row = ctk.CTkFrame(card, fg_color="transparent",
                               corner_radius=8, height=42, width=352)
            row.pack(padx=16, pady=(2, 8) if i == len(items) - 1 else 2)
            row.pack_propagate(False)
            lbl = ctk.CTkLabel(row, text=it["label"], font=T.f(15), anchor="w",
                               text_color=T.TEXT if on else "#A3ACBF")
            lbl.pack(side="left", padx=14)
            chip = ctk.CTkLabel(row,
                                text=it["key"] if on else "soon",
                                font=T.f(11, "bold"),
                                text_color=T.ACCENT if on else "#9AA5B8",
                                fg_color=SEL_BG if on else "transparent",
                                corner_radius=6,
                                width=34 if on else 40, height=22)
            chip.pack(side="right", padx=12)
            for w in (row, lbl, chip):
                w.bind("<Button-1>", lambda _e, i=i: self.pick(i))
                w.bind("<Motion>",   lambda _e, i=i: self.select(i))
            self.rows.append(row)
        self.select(max(0, min(selected_index, len(self.items) - 1)))

    def select(self, i):
        self.sel = i
        for n, r in enumerate(self.rows):
            r.configure(fg_color=SEL_BG if n == i else "transparent",
                        border_width=1 if n == i else 0,
                        border_color="#D7E3F8" if n == i else SEL_BG)

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
        self._ledger_account = None
        # Remember each menu's highlighted row while navigating into submenus/pages.
        self._menu_selection = {}
        self.top = self.winfo_toplevel()

        bar = ctk.CTkFrame(self, fg_color=T.NAVY, corner_radius=0, height=64)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, text="MUNIM", font=T.f(21, "bold"),
                     text_color="white").pack(side="left", padx=(22, 18))
        self.back_btn = ctk.CTkButton(
            bar, text="←  Back", width=88, height=34, corner_radius=9,
            fg_color=T.NAVY_HOVER, hover_color=T.NAVY_ACTIVE,
            font=T.f(12, "bold"), command=self.go_back)
        self.home_btn = ctk.CTkButton(
            bar, text="⌂  Home", width=88, height=34, corner_radius=9,
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
        ctk.CTkLabel(right, text=f"FY {s.fy_of(_d.today())}  ·  {username}",
                     font=T.f(11), text_color="#9FB3D9").pack(anchor="e")

        self.status = ctk.CTkLabel(self, text=HINT, font=T.f(11), text_color=T.MUTED,
                                   anchor="w", fg_color="#EDF1F7", height=30,
                                   corner_radius=0)
        self.status.pack(side="bottom", fill="x")
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)

        self.top.bind("<Key>",       self._on_key)
        self.top.bind("<Control-s>", self._on_save)
        self.top.bind("<Control-S>", self._on_save)
        # One global Alt handler avoids duplicate/conflicting bindings.
        self.top.bind("<Alt-Key>", self._on_alt_key)
        self.refresh_company()
        self.push(("menu", "gateway"))

    def destroy(self):
        try:
            self._do_auto_backup()
        except Exception:
            pass
        try:
            self.top.unbind("<Key>")
            self.top.unbind("<Control-s>")
            self.top.unbind("<Control-S>")
            self.top.unbind("<Alt-Key>")
        except Exception:
            pass
        super().destroy()

    def _do_auto_backup(self):
        st      = settings.load_settings()
        company = st.get("company_name", "company")
        path    = bkup.auto_backup(self.con, company, st)
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
        self.status.configure(text=HINT)
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
        self.crumb.configure(text="  ›  ".join(labels))
        # Show Back and Home only when not at gateway
        if len(self.stack) > 1:
            self.back_btn.pack(side="left", before=self.crumb)
            self.home_btn.pack(side="left", before=self.crumb)
        else:
            self.back_btn.pack_forget()
            self.home_btn.pack_forget()

    def pick(self, item):
        go = item["go"]
        if go is None:
            self.status.configure(
                text=f"{item['label']} arrives in a later release.")
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

    def _on_save(self, _event=None):
        save = getattr(self.current, "save", None)
        if callable(save):
            save()
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
            self.current.handle(event)
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
        c  = s.counts(self.con)
        receivable, payable = rep.receivable_payable(self.con)
        fy = s.fy_of(date.today())

        today_str   = date.today().isoformat()
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
            cash_paise = sum(st["bf"] + st["dr"] - st["cr"]
                             for st in states if st["grp"] == "Cash-in-hand")
            bank_paise = sum(st["bf"] + st["dr"] - st["cr"]
                             for st in states if st["grp"] == "Bank Accounts")
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

        ctk.CTkLabel(card, text="CURRENT COMPANY", font=T.f(11, "bold"),
                     text_color=T.MUTED).pack(anchor="w", padx=24, pady=(12, 3))
        ctk.CTkLabel(card,
                     text=st.get("company_name") or "Company name not set",
                     font=T.f(18, "bold"), text_color=T.TEXT,
                     wraplength=300, justify="left").pack(anchor="w", padx=24)
        ctk.CTkLabel(card, text=f"Financial year {fy}", font=T.f(11),
                     text_color=T.MUTED).pack(anchor="w", padx=24, pady=(1, 5))

        ctk.CTkFrame(card, fg_color=T.BORDER, height=1).pack(fill="x", padx=24)

        def row(label, value, color=T.TEXT, bold=False):
            r = ctk.CTkFrame(card, fg_color=T.CARD, corner_radius=0, height=24)
            r.pack(fill="x", padx=24, pady=0)
            r.pack_propagate(False)
            ctk.CTkLabel(r, text=label, font=T.f(11), text_color=T.MUTED,
                         anchor="w", width=154, height=24).pack(side="left")
            ctk.CTkLabel(r, text=value,
                         font=T.f(11, "bold" if bold else "normal"),
                         text_color=color, anchor="e", height=24).pack(side="right")

        ctk.CTkLabel(card, text="TODAY", font=T.f(10, "bold"),
                     text_color=T.MUTED).pack(anchor="w", padx=24, pady=(5, 1))
        row("Today's sales",  f"Rs {inr(s.to_rupees(today_sales))}",
            T.OK if today_sales else T.TEXT)
        row("This month",     f"Rs {inr(s.to_rupees(month_sales))}")

        ctk.CTkLabel(card, text="OUTSTANDING", font=T.f(10, "bold"),
                     text_color=T.MUTED).pack(anchor="w", padx=24, pady=(5, 1))
        row("Customers owe you", f"Rs {inr(receivable)}",
            T.OK if receivable else T.TEXT, bold=True)
        row("You owe suppliers", f"Rs {inr(payable)}",
            "#B26A00" if payable else T.TEXT, bold=True)

        ctk.CTkLabel(card, text="CASH & BANK", font=T.f(10, "bold"),
                     text_color=T.MUTED).pack(anchor="w", padx=24, pady=(5, 1))
        row("Cash in hand", balance_text(cash_paise))
        row("Bank balance", balance_text(bank_paise))

        ctk.CTkLabel(card, text="STOCK", font=T.f(10, "bold"),
                     text_color=T.MUTED).pack(anchor="w", padx=24, pady=(5, 1))
        row("Stock value", f"Rs {inr(stock_value)}")

        if top_debtors:
            ctk.CTkLabel(card, text="TOP DEBTORS", font=T.f(10, "bold"),
                         text_color=T.MUTED).pack(anchor="w", padx=24, pady=(5, 1))
            for p in top_debtors:
                row(p["party"][:24], f"Rs {inr(p['balance'])}",
                    T.DANGER if p["balance"] > 50000 else T.TEXT)

        ctk.CTkFrame(card, fg_color=T.BORDER, height=1).pack(
            fill="x", padx=24, pady=(5, 0))

        last = st.get("last_backup")
        nag  = bkup.should_nag(st)
        ctk.CTkLabel(card, text="BACKUP", font=T.f(10, "bold"),
                     text_color=T.MUTED).pack(anchor="w", padx=24, pady=(4, 1))
        if last:
            row("Last backup", disp_date(last), T.DANGER if nag else T.OK)
        else:
            row("Last backup", "never", T.DANGER)

        if nag:
            banner = ctk.CTkFrame(card, fg_color="#FFF3CD", corner_radius=6)
            banner.pack(fill="x", padx=24, pady=(5, 3))
            ctk.CTkLabel(banner,
                         text="⚠  No backup in over 7 days\nUtilities > Backup Data",
                         font=T.f(11), text_color="#7A4F00",
                         wraplength=240, justify="left").pack(padx=10, pady=6)

        steps = [
            ("Set up your company",        bool(st.get("company_name")),
             "Utilities > Company Details"),
            ("Add a customer or supplier", c["parties"] > 0,
             "Masters > Party Master"),
            ("Record a sale or purchase",  c["vouchers"] > 0,
             "Transactions"),
            ("Take a backup",              bool(last),
             "Utilities > Backup Data"),
        ]
        if not all(done for _t, done, _h in steps):
            completed = sum(done for _t, done, _h in steps)
            ctk.CTkButton(
                card, text=f"Setup guide  ·  {completed}/4 complete",
                height=30, corner_radius=7, fg_color="#E7ECF5",
                text_color=T.TEXT, hover_color="#DCE3F0", font=T.f(11),
                command=lambda: self._show_setup_guide(steps)
            ).pack(fill="x", padx=24, pady=(7, 3))

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
