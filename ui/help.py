"""Help & Shortcuts — three tabs: Keyboard shortcuts, How to use, Support & about.

Switch tabs with the buttons, the ← → keys, or 1 / 2 / 3.
"""
import os
import urllib.parse
import webbrowser

import customtkinter as ctk

from ui import theme as T

WEBSITE = "https://technicalmunim.vercel.app"
DOWNLOAD = "https://technicalmunim.vercel.app/download.html"

SUPPORT_PHONE_DISPLAY = "+91 84276 51580"
SUPPORT_PHONE_INTL = "918427651580"          # for wa.me links: country code, no '+'
SUPPORT_EMAIL = "sumitverma2880@gmail.com"

LABEL_TEXT = "#4A5468"
CHIP_BG = "#EAF0FC"
WHATSAPP_GREEN = "#1FAF5A"
WHATSAPP_HOVER = "#188F49"
TABS = ("Keyboard shortcuts", "How to use", "Support & about")

SHORTCUTS = [
    ("Anywhere", [
        ("Alt + G", "Go To: search any screen, party or ledger"),
        ("Alt + H", "Back to the Gateway (home)"),
        ("Alt + 1", "Open this Help page"),
        ("Esc", "Go back one screen (asks first if an entry is not saved)"),
        ("F2", "Jump to the date or period box"),
        ("R  /  P", "Receipt / Payment or Purchase Bill (when not typing in a box)"),
    ]),
    ("Menus and Gateway", [
        ("↑ ↓ ← →", "Move the highlight"),
        ("Enter", "Open the highlighted option"),
        ("Letter key", "Open the option showing that letter, e.g. T for Transactions"),
        ("←", "Back to the previous menu (in option lists)"),
        ("↓ on bottom tiles", "Move into Quick Actions on the Gateway"),
        ("Q", "Log out (on the Gateway)"),
    ]),
    ("Entry screens", [
        ("Enter", "Move to the next box"),
        ("Tab / Shift+Tab", "Next / previous box"),
        ("Ctrl + S", "Save the entry"),
        ("Ctrl + P", "Save the PDF of the sales invoice you just saved"),
        ("Type letters", "Search a party, account or item; Enter picks it"),
    ]),
    ("Reports", [
        ("F2", "Change the period, then Enter to refresh"),
        ("Ctrl + E", "Export to Excel"),
        ("Ctrl + Shift + P", "Export to PDF"),
        ("Enter / double-click", "Open the voucher in the selected row"),
        ("Alt + O", "Choose a ledger (Ledger View)"),
    ]),
    ("Typing dates", [
        ("15", "15th of this month"),
        ("1511", "15 November of this year"),
        ("15-11-2026", "Full date"),
    ]),
]

HOW_TO = [
    ("First-time setup", [
        "Utilities › Company & Settings › Company Details: name, GSTIN, address and "
        "whether you are GST registered.",
        "Masters › Party Master: add customers and suppliers with GSTIN and opening balance.",
        "Masters › Stock Items: add items with HSN code, unit and GST rate.",
        "Masters › Ledger Accounts: add bank accounts, expenses, capital and loans.",
    ]),
    ("Everyday entries", [
        "Sales Invoice / Purchase Bill: pick the party, add items, Ctrl+S to save.",
        "Receipt / Payment: choose the party and type the amount against each unpaid bill.",
        "Sales or Purchase Return: select the original bill, then enter the returned items.",
        "Daily Sales Summary: one entry for the day's counter sales.",
    ]),
    ("Month end and GST", [
        "Reports › GST › GSTR-1: check outward supplies and Export JSON for the GST portal.",
        "Reports › GST › GSTR-3B: tax payable after input tax credit.",
        "Reports › Accounting › Bank Reconciliation: import the bank CSV and match entries.",
        "Reports › Financial › Outstanding: who owes what, and for how long.",
    ]),
    ("Year end", [
        "Reports › Financial › Trading & P&L: enter closing stock, then check gross and net profit.",
        "Reports › Financial › Balance Sheet: position as on any date.",
        "Reports › Accounting › Trial Balance: Summary or Detailed, export to Excel or PDF.",
    ]),
    ("Keep your data safe", [
        "Utilities › Data Management › Backup Data: save a copy to a folder or USB drive.",
        "Keep one copy away from this PC, on a USB drive or cloud folder.",
        "The Gateway warns you when there has been no backup for 7 days.",
    ]),
    ("Customize the Gateway", [
        "Click Customize in Quick Actions and tick up to 8 screens.",
        "Press ↓ from the bottom tiles to reach them, ← → to move, Enter to open.",
    ]),
]


def _app_version():
    try:
        import __main__
        return getattr(__main__, "CURRENT_VERSION", "") or "—"
    except Exception:
        return "—"


def _company_name():
    try:
        from utils import settings
        return settings.load_settings().get("company_name") or "Not set"
    except Exception:
        return "Not set"


def _logs_folder():
    """Folder where MUNIM writes its error logs (…\\logs inside the data folder)."""
    try:
        from db import setup as s
        return os.path.join(str(s.data_dir()), "logs")
    except Exception:
        return ""


def _licence_status():
    try:
        from utils import licence
        return licence.licence_status()
    except Exception:
        return "—"


def _support_text():
    return (f"Hello, I need help with MUNIM Books.\n\n"
            f"Version: {_app_version()}\n"
            f"Company: {_company_name()}\n\n"
            f"My question / problem:\n")


class HelpFrame(ctk.CTkFrame):
    def __init__(self, master, start_tab=0):
        super().__init__(master, fg_color="transparent")
        self.tab = 0

        T.title(self, "Help & Shortcuts",
                "Press ← → or 1, 2, 3 to switch tabs. Esc goes back."
                ).pack(anchor="w", padx=28, pady=(24, 12))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=28, pady=(0, 12))
        for c in range(len(TABS)):
            bar.grid_columnconfigure(c, weight=1, uniform="tabs")
        self.tab_btns = []
        for i, name in enumerate(TABS):
            b = ctk.CTkButton(bar, text=f"{i + 1}   {name}", height=46, corner_radius=10,
                              font=T.f(14, "bold"), border_width=1,
                              command=lambda i=i: self.show(i))
            b.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            self.tab_btns.append(b)

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=22, pady=(0, 16))
        self.show(start_tab)

    # ── Tabs ──────────────────────────────────────────────────────────────
    def show(self, i):
        self.tab = i
        for n, b in enumerate(self.tab_btns):
            on = n == i
            b.configure(fg_color=T.ACCENT if on else T.CARD,
                        hover_color=T.ACCENT_HOVER if on else "#F1F4F9",
                        text_color="white" if on else T.TEXT,
                        border_color=T.ACCENT if on else T.BORDER)
        for w in self.body.winfo_children():
            w.destroy()
        grid = ctk.CTkFrame(self.body, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure((0, 1), weight=1, uniform="help")
        (self._shortcuts_tab, self._howto_tab, self._support_tab)[i](grid)
        try:
            self.body._parent_canvas.yview_moveto(0)
        except Exception:
            pass

    def handle_key(self, event):
        k = event.keysym
        if k == "Right":
            self.show((self.tab + 1) % len(TABS))
            return True
        if k == "Left":
            self.show((self.tab - 1) % len(TABS))
            return True
        if k in ("1", "2", "3"):
            self.show(int(k) - 1)
            return True
        return False

    # ── Building blocks ───────────────────────────────────────────────────
    @staticmethod
    def _card(parent, title, row, col, colspan=1):
        card = ctk.CTkFrame(parent, fg_color=T.CARD, border_width=1,
                            border_color=T.BORDER, corner_radius=12)
        card.grid(row=row, column=col, columnspan=colspan, sticky="nsew",
                  padx=6, pady=6)
        ctk.CTkLabel(card, text=title.upper(), font=T.f(10, "bold"),
                     text_color=T.ACCENT).pack(anchor="w", padx=18, pady=(14, 8))
        return card

    @staticmethod
    def _end(card):
        ctk.CTkFrame(card, fg_color="transparent", height=10).pack()

    @staticmethod
    def _key_row(card, key, desc):
        line = ctk.CTkFrame(card, fg_color="transparent")
        line.pack(fill="x", padx=16, pady=3)
        ctk.CTkLabel(line, text=key, width=150, height=26, corner_radius=6,
                     fg_color=CHIP_BG, text_color=T.ACCENT,
                     font=T.f(11, "bold")).pack(side="left", anchor="n")
        ctk.CTkLabel(line, text=desc, font=T.f(12), text_color=T.TEXT,
                     anchor="w", justify="left", wraplength=340
                     ).pack(side="left", fill="x", expand=True, padx=10)

    @staticmethod
    def _step_row(card, n, text):
        line = ctk.CTkFrame(card, fg_color="transparent")
        line.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(line, text=str(n), width=24, height=24, corner_radius=12,
                     fg_color=CHIP_BG, text_color=T.ACCENT,
                     font=T.f(11, "bold")).pack(side="left", anchor="n")
        ctk.CTkLabel(line, text=text, font=T.f(12), text_color=T.TEXT,
                     anchor="w", justify="left", wraplength=380
                     ).pack(side="left", fill="x", expand=True, padx=10)

    @staticmethod
    def _info_row(card, label, value):
        line = ctk.CTkFrame(card, fg_color="transparent")
        line.pack(fill="x", padx=18, pady=3)
        ctk.CTkLabel(line, text=label, font=T.f(12), text_color=LABEL_TEXT,
                     width=130, anchor="w").pack(side="left")
        ctk.CTkLabel(line, text=value, font=T.f(12, "bold"), text_color=T.TEXT,
                     anchor="w", justify="left", wraplength=320
                     ).pack(side="left", fill="x", expand=True)

    # ── Tab 1: Keyboard shortcuts ─────────────────────────────────────────
    def _shortcuts_tab(self, grid):
        for idx, (title, rows) in enumerate(SHORTCUTS):
            card = self._card(grid, title, idx // 2, idx % 2)
            for key, desc in rows:
                self._key_row(card, key, desc)
            self._end(card)

    # ── Tab 2: How to use ─────────────────────────────────────────────────
    def _howto_tab(self, grid):
        for idx, (title, steps) in enumerate(HOW_TO):
            card = self._card(grid, title, idx // 2, idx % 2)
            for n, text in enumerate(steps, 1):
                self._step_row(card, n, text)
            self._end(card)

    # ── Tab 3: Support & about ────────────────────────────────────────────
    def _whatsapp(self):
        text = urllib.parse.quote(_support_text())
        webbrowser.open(f"https://wa.me/{SUPPORT_PHONE_INTL}?text={text}")

    def _email(self):
        subject = urllib.parse.quote(f"MUNIM Books support - {_app_version()}")
        body = urllib.parse.quote(_support_text())
        webbrowser.open(f"mailto:{SUPPORT_EMAIL}?subject={subject}&body={body}")

    def _copy_contact(self):
        text = (f"MUNIM Books support\n"
                f"WhatsApp / Phone: {SUPPORT_PHONE_DISPLAY}\n"
                f"Email: {SUPPORT_EMAIL}\n"
                f"Version: {_app_version()}")
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._copy_note.configure(text="Copied to clipboard.")
            self.after(2500, lambda: self._copy_note.configure(text=""))
        except Exception:
            pass

    def _support_tab(self, grid):
        from db import setup as s

        # Row 0 — About | Contact support
        about = self._card(grid, "About this copy", 0, 0)
        self._info_row(about, "Version", _app_version())
        self._info_row(about, "Licence", _licence_status())
        self._info_row(about, "Company", _company_name())
        try:
            self._info_row(about, "Data folder", str(s.data_dir()))
        except Exception:
            pass
        self._end(about)

        contact = self._card(grid, "Contact support", 0, 1)
        self._info_row(contact, "WhatsApp / Call", SUPPORT_PHONE_DISPLAY)
        self._info_row(contact, "Email", SUPPORT_EMAIL)
        btns = ctk.CTkFrame(contact, fg_color="transparent")
        btns.pack(anchor="w", padx=16, pady=(10, 4))
        T.button(btns, "WhatsApp us", self._whatsapp, width=140,
                 fg_color=WHATSAPP_GREEN, hover_color=WHATSAPP_HOVER,
                 text_color="white").pack(side="left")
        T.button(btns, "Send email", self._email, width=120).pack(side="left", padx=(8, 0))
        T.button(btns, "Copy details", self._copy_contact, width=120,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="left", padx=(8, 0))
        self._copy_note = ctk.CTkLabel(contact, text="", font=T.f(11), text_color=T.OK)
        self._copy_note.pack(anchor="w", padx=18)
        ctk.CTkLabel(contact, text="WhatsApp and email open with your MUNIM Books version "
                                   "already filled in. Just add your question.",
                     font=T.f(11), text_color=LABEL_TEXT, justify="left",
                     wraplength=420).pack(anchor="w", padx=18, pady=(2, 0))
        self._end(contact)

        # Row 1 — If something goes wrong | Get help and updates
        wrong = self._card(grid, "If something goes wrong", 1, 0)
        for n, text in enumerate([
                "If a screen fails to open, MUNIM Books shows \"This screen hit a problem\". "
                "Your saved entries are not affected.",
                "Click Copy error details, then send it to us on WhatsApp or email.",
                "Press Esc to go back and carry on working."], 1):
            self._step_row(wrong, n, text)
        logs = _logs_folder()
        if logs:
            self._info_row(wrong, "Error logs", logs)
        self._end(wrong)

        get = self._card(grid, "Get help and updates", 1, 1)
        ctk.CTkLabel(get, text="Guides and the latest version are on the MUNIM website. "
                               "MUNIM Books also shows a banner at the top when a new "
                               "version is available.",
                     font=T.f(12), text_color=T.TEXT, justify="left",
                     wraplength=420).pack(anchor="w", padx=18, pady=(0, 10))
        wbtns = ctk.CTkFrame(get, fg_color="transparent")
        wbtns.pack(anchor="w", padx=16, pady=(0, 6))
        T.button(wbtns, "Open website", lambda: webbrowser.open(WEBSITE),
                 width=140).pack(side="left")
        T.button(wbtns, "Download latest version", lambda: webbrowser.open(DOWNLOAD),
                 width=200, fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="left", padx=(8, 0))
        self._end(get)

        # Row 2 — Finding this page
        find = self._card(grid, "Finding this page", 2, 0, colspan=2)
        for key, desc in [("Alt + 1", "Open Help from any screen"),
                          ("? Help", "Button in the top bar, on every screen"),
                          ("U › H › H", "Utilities › Support & Information › Help")]:
            self._key_row(find, key, desc)
        self._end(find)