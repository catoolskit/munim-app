"""MUNIM Pro — main window: top bar, module tiles, TDS menu bar + toolbar, F4 picker."""
import customtkinter as ctk

from ui import theme as T
from ui.pro_common import whatsapp
from ui.pro_deductee import DeducteePage
from ui.pro_picker import EntityPicker, LABELS
from ui.pro_consultant import ConsultantPage
from ui.pro_deductor import DeductorPage
from db import pro_db
from utils import licence

MODULES = [
    {"id": "tds", "name": "TDS Pro", "ready": True,
     "desc": "TDS / TCS statements (Forms 138, 140, 144, 143), challans, FVU and certificates."},
    {"id": "gst", "name": "GST Pro", "ready": False,
     "desc": "GSTR-1, IMS and GSTR-2B reconciliation, GSTR-3B and annual returns."},
    {"id": "tax", "name": "Tax Pro", "ready": False,
     "desc": "Income computation, old vs new regime, advance tax and returns under the new Act."},
]
MODULE_BY_ID = {m["id"]: m for m in MODULES}
MODULE_BY_NAME = {m["name"]: m for m in MODULES}

# TDS menu bar. Each menu: (title, [(label, action_or_None), ...]).
# action None → "coming in the next update".
TDS_MENUS = [
    ("Deductors", [("Deductor Master", "deductor")]),
    ("Deductees", [("Deductee Master", "deductee")]),
    ("TDS Entry", [("TDS / TCS Entry", None), ("Import 15G / 15H", None)]),
    ("Challans", [("Challans", None), ("Link Challans to Entries", None)]),
    ("Statements & FVU", [("Prepare Statement (138 / 140 / 144 / 143)", None),
                          ("Generate FVU", None), ("Form 27A", None),
                          ("Correction Statements", None)]),
    ("Certificates", [("Form 130 / 131 Import", None), ("Form 121 (15G / 15H)", None)]),
    ("Reports", [("TDS Reports", None), ("Payment Codes", None)]),
    ("Utilities", [("Consultant Master", "consultant")]),
]
# Toolbar: (label, action_or_None)
TDS_TOOLBAR = [("Deductors", "deductor"), ("Deductees", "deductee"),
               ("TDS Entry", None), ("Challans", None)]

SOON_FG, SOON_BG = "#8A5A00", "#FFF3D6"


class ProShell(ctk.CTkFrame):
    def __init__(self, master, con, username, role, on_logout):
        super().__init__(master, fg_color=T.BG)
        self.con, self.username, self.role, self.on_logout = con, username, role, on_logout
        try:
            lic = licence.check(allow_network=False)
            self.licensed = set(lic.get("m") or []) if lic.get("p") in ("pro", "both") else set()
        except licence.LicenceError:
            self.licensed = set()
        self.module = None
        self.entity = {}
        self.page, self.page_name = None, ""
        self._open_menu = None

        self._build_topbar()
        self.menubar = ctk.CTkFrame(self, fg_color="#0C3327", corner_radius=0, height=38)
        self.toolbar = ctk.CTkFrame(self, fg_color="#113B2D", corner_radius=0, height=46)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)

        top = self.winfo_toplevel()
        top.bind("<F4>", self._on_f4)
        top.bind("<Escape>", self._on_escape)
        top.bind("<Button-1>", self._close_dropdown, add="+")
        self.show_home()

    def destroy(self):
        try:
            top = self.winfo_toplevel()
            for seq in ("<F4>", "<Escape>", "<Button-1>"):
                top.unbind(seq)
        except Exception:
            pass
        super().destroy()

    # ── top bar (MUNIM green) ──────────────────────────────────────────────────
    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color=T.NAVY, corner_radius=0, height=54)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        ctk.CTkButton(bar, text="MUNIM Pro", width=120, height=36, font=T.f(17, "bold"),
                      fg_color="transparent", hover_color=T.NAVY_HOVER, text_color="white",
                      command=self.show_home).pack(side="left", padx=(12, 8))
        self.switch = ctk.CTkSegmentedButton(
            bar, values=[m["name"] for m in MODULES], command=self._on_switch, height=34,
            font=T.f(12, "bold"), fg_color=T.NAVY_HOVER, selected_color=T.ACCENT,
            selected_hover_color=T.ACCENT_HOVER, unselected_color=T.NAVY_HOVER,
            unselected_hover_color=T.NAVY_ACTIVE, text_color="white")
        self.switch.pack(side="left", padx=8)
        self.entity_lbl = ctk.CTkLabel(bar, text="", font=T.f(12), text_color="#CFE7DC",
                                       cursor="hand2")
        self.entity_lbl.pack(side="left", padx=14)
        self.entity_lbl.bind("<Button-1>", lambda _e: self._on_f4())

        ctk.CTkButton(bar, text="Log out", width=80, height=32, fg_color="transparent",
                      border_width=1, border_color="#5E8F7C", hover_color=T.NAVY_HOVER,
                      text_color="white", font=T.f(12),
                      command=self.on_logout).pack(side="right", padx=(6, 12))
        ctk.CTkLabel(bar, text=self.username, font=T.f(12),
                     text_color="#CFE7DC").pack(side="right", padx=8)
        self.cons_btn = ctk.CTkButton(bar, text="", height=32, fg_color="transparent",
                                      hover_color=T.NAVY_HOVER, text_color="#CFE7DC",
                                      font=T.f(12), command=self.show_consultant)
        self.cons_btn.pack(side="right", padx=6)
        self._refresh_consultant_label()

    def _refresh_consultant_label(self):
        c = pro_db.get_default_consultant(self.con)
        name = c["firm_name"] if c else "Add your firm details"
        self.cons_btn.configure(text=name if len(name) <= 34 else name[:32] + "…")

    def _refresh_entity(self):
        if not self.module:
            self.entity_lbl.configure(text="")
            return
        noun = LABELS[self.module][0]
        e = self.entity.get(self.module)
        self.entity_lbl.configure(
            text=f"{noun}: {e['name']} ({e['key']})" if e else f"{noun}: none selected · F4")

    # ── TDS menu bar + toolbar ─────────────────────────────────────────────────
    def _show_tds_bars(self):
        self._close_dropdown()
        self.menubar.pack(fill="x", after=self._topbar_ref(), before=self.body) \
            if False else None
        # pack menubar and toolbar right under the top bar, above the body
        self.menubar.pack(fill="x")
        self.toolbar.pack(fill="x")
        # re-stack body last
        self.body.pack_forget()
        self.body.pack(fill="both", expand=True)
        self._build_menubar()
        self._build_toolbar()

    def _hide_tds_bars(self):
        self._close_dropdown()
        self.menubar.pack_forget()
        self.toolbar.pack_forget()

    def _topbar_ref(self):
        return self.winfo_children()[0]

    def _build_menubar(self):
        for w in self.menubar.winfo_children():
            w.destroy()
        for title, items in TDS_MENUS:
            b = ctk.CTkButton(self.menubar, text=title, height=30, width=1,
                              fg_color="transparent", hover_color="#154A38",
                              text_color="white", font=T.f(12),
                              command=lambda t=title, it=items: self._toggle_menu(t, it))
            b.pack(side="left", padx=2, pady=4)

    def _build_toolbar(self):
        for w in self.toolbar.winfo_children():
            w.destroy()
        for label, action in TDS_TOOLBAR:
            enabled = action is not None
            ctk.CTkButton(
                self.toolbar, text=label, height=34, width=104,
                fg_color=T.ACCENT if enabled else "#245244",
                hover_color=T.ACCENT_HOVER if enabled else "#245244",
                text_color="white" if enabled else "#8FB6A6", font=T.f(12, "bold"),
                command=(lambda a=action: self._run_action(a)) if enabled else None
            ).pack(side="left", padx=(8 if label == TDS_TOOLBAR[0][0] else 4), pady=6)
        ctk.CTkLabel(self.toolbar, text="F4 = select deductor", font=T.f(11),
                     text_color="#8FB6A6").pack(side="right", padx=14)

    def _toggle_menu(self, title, items):
        if self._open_menu and self._open_menu.winfo_exists() \
                and getattr(self._open_menu, "_title", None) == title:
            self._close_dropdown()
            return
        self._close_dropdown()
        # find the button to anchor under
        btn = next((w for w in self.menubar.winfo_children()
                    if isinstance(w, ctk.CTkButton) and w.cget("text") == title), None)
        if not btn:
            return
        top = self.winfo_toplevel()
        x = btn.winfo_rootx() - top.winfo_rootx()
        y = (self.menubar.winfo_rooty() - top.winfo_rooty()) + self.menubar.winfo_height()
        menu = ctk.CTkFrame(top, fg_color=T.CARD, border_width=1, border_color=T.BORDER,
                            corner_radius=6)
        menu._title = title
        for label, action in items:
            enabled = action is not None
            ctk.CTkButton(
                menu, text=label if enabled else f"{label}  (soon)",
                anchor="w", height=30, fg_color="transparent",
                hover_color=T.SURFACE_SELECTED if enabled else T.CARD,
                text_color=T.TEXT if enabled else T.MUTED, font=T.f(12),
                command=(lambda a=action: self._run_action(a)) if enabled else None
            ).pack(fill="x", padx=4, pady=1)
        menu.place(x=x, y=y)
        menu.lift()
        self._open_menu = menu

    def _close_dropdown(self, _e=None):
        if self._open_menu is not None:
            try:
                if self._open_menu.winfo_exists():
                    self._open_menu.destroy()
            except Exception:
                pass
            self._open_menu = None

    def _run_action(self, action):
        self._close_dropdown()
        if action == "deductor":
            self.show_deductor()
        elif action == "deductee":
            self.show_deductee()
        elif action == "consultant":
            self.show_consultant()
            
    # ── navigation ────────────────────────────────────────────────────────────
    def state_of(self, m):
        if not m["ready"]:
            return "soon"
        return "open" if m["id"] in self.licensed else "locked"

    def _show(self, page, name):
        keep = {page, getattr(page, "_parent_frame", page)}
        for w in list(self.body.winfo_children()):
            if w not in keep:
                w.destroy()
        self.page, self.page_name = page, name
        page.pack(fill="both", expand=True)

    def _on_switch(self, name):
        self.open_module(MODULE_BY_NAME[name]["id"])

    def open_module(self, mid):
        m = MODULE_BY_ID[mid]
        state = self.state_of(m)
        self.module = mid if state == "open" else None
        self.switch.set(m["name"])
        self._refresh_entity()
        if state == "open" and mid == "tds":
            self._show_tds_bars()
            self._show(self._tds_welcome(m), "module")
        else:
            self._hide_tds_bars()
            self._show(self._locked_page(m, state), "locked")

    def show_home(self):
        self.module = None
        self.switch.set("")
        self._refresh_entity()
        self._hide_tds_bars()
        page = ctk.CTkFrame(self.body, fg_color="transparent")
        info = licence.info() or {}
        who = info.get("firm") or info.get("username", "")
        T.title(page, "Choose a module",
                f"Licensed to {who}  ·  valid till {info.get('expires', '—')}"
                ).pack(anchor="w", padx=28, pady=(24, 14))

        if not pro_db.get_default_consultant(self.con):
            nb = T.card(page)
            nb.pack(fill="x", padx=28, pady=(0, 12))
            ctk.CTkLabel(nb, text="First, add your firm's details in Consultant Master. "
                         "They print on every return and report.", font=T.f(13),
                         wraplength=700, justify="left").pack(side="left", padx=18, pady=14)
            T.button(nb, "Open Consultant Master", self.show_consultant,
                     width=210).pack(side="right", padx=18, pady=10)

        tiles = ctk.CTkFrame(page, fg_color="transparent")
        tiles.pack(fill="x", padx=20)
        for i, m in enumerate(MODULES):
            tiles.grid_columnconfigure(i, weight=1, uniform="t")
            self._tile(tiles, m).grid(row=0, column=i, padx=8, pady=8, sticky="nsew")

        foot = ctk.CTkFrame(page, fg_color="transparent")
        foot.pack(fill="x", padx=28, pady=(12, 0))
        T.button(foot, "Consultant Master", self.show_consultant, width=180,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="left")
        self._show(page, "home")

    def show_consultant(self):
        self._close_dropdown()
        self.module = None
        self.switch.set("")
        self._refresh_entity()
        self._hide_tds_bars()
        page = ConsultantPage(self.body, self.con, self.username,
                              on_change=self._refresh_consultant_label,
                              on_back=self.show_home)
        self._show(page, "consultant")

    def show_deductor(self, start_id=None):
        self.module = "tds"
        self.switch.set("TDS Pro")
        self._refresh_entity()
        self._show_tds_bars()
        page = DeductorPage(self.body, self.con, self.username,
                            on_back=lambda: self.open_module("tds"), start_id=start_id)
        self._show(page, "deductor")

    def show_deductee(self):
        ded = self.entity.get("tds")
        if not ded:
            self.module = "tds"
            self.switch.set("TDS Pro")
            self._show_tds_bars()
            self._on_f4()   # ask the user to pick a deductor first
            return
        full = pro_db.get_deductor(self.con, ded["id"])
        self.module = "tds"
        self.switch.set("TDS Pro")
        self._refresh_entity()
        self._show_tds_bars()
        page = DeducteePage(self.body, self.con, self.username, full,
                            on_back=lambda: self.open_module("tds"))
        self._show(page, "deductee")
        
    # ── pages ─────────────────────────────────────────────────────────────────
    def _tile(self, parent, m):
        state = self.state_of(m)
        c = T.card(parent)
        ctk.CTkLabel(c, text=m["name"], font=T.f(20, "bold")).pack(anchor="w", padx=22,
                                                                  pady=(22, 2))
        ctk.CTkLabel(c, text=m["desc"], font=T.f(12), text_color=T.MUTED, wraplength=280,
                     justify="left").pack(anchor="w", padx=22)
        pill = {"open": ("Ready", T.OK, T.SUCCESS_BG),
                "locked": ("Not in your licence", T.DANGER, T.DANGER_BG),
                "soon": ("Coming soon", SOON_FG, SOON_BG)}[state]
        ctk.CTkLabel(c, text=f"  {pill[0]}  ", font=T.f(11, "bold"), text_color=pill[1],
                     fg_color=pill[2], corner_radius=10).pack(anchor="w", padx=22, pady=(12, 0))
        if state == "open":
            btn = T.button(c, "Open", lambda: self.open_module(m["id"]))
        elif state == "locked":
            btn = T.button(c, "Contact to unlock", lambda: whatsapp(self._wa_text(m, state)),
                           fg_color="#E7ECF5", text_color=T.TEXT, hover_color="#DCE3F0")
        else:
            btn = T.button(c, "Get early access", lambda: whatsapp(self._wa_text(m, state)),
                           fg_color="#E7ECF5", text_color=T.TEXT, hover_color="#DCE3F0")
        btn.pack(fill="x", padx=22, pady=(16, 22))
        return c

    def _wa_text(self, m, state):
        user = (licence.info() or {}).get("username", "")
        want = "early access to" if state == "soon" else "to unlock"
        return f"Hi, I want {want} {m['name']} in MUNIM Pro. Username: {user}"

    def _locked_page(self, m, state):
        page = ctk.CTkFrame(self.body, fg_color="transparent")
        c = T.card(page)
        c.place(relx=0.5, rely=0.42, anchor="center")
        ctk.CTkLabel(c, text=m["name"], font=T.f(24, "bold")).pack(anchor="w", padx=34,
                                                                  pady=(30, 6))
        text = (f"{m['name']} is being built. Message us on WhatsApp for early access."
                if state == "soon" else
                f"{m['name']} is not in your licence. Contact us to add it; "
                "your data and settings stay as they are.")
        ctk.CTkLabel(c, text=text, font=T.f(13), text_color=T.MUTED, wraplength=420,
                     justify="left").pack(anchor="w", padx=34)
        bar = ctk.CTkFrame(c, fg_color="transparent")
        bar.pack(anchor="w", padx=34, pady=(18, 30))
        T.button(bar, "WhatsApp us", lambda: whatsapp(self._wa_text(m, state)),
                 width=150).pack(side="left", padx=(0, 8))
        T.button(bar, "Back", self.show_home, width=100, fg_color="#E7ECF5",
                 text_color=T.TEXT, hover_color="#DCE3F0").pack(side="left")
        return page

    def _tds_welcome(self, m):
        page = ctk.CTkFrame(self.body, fg_color="transparent")
        e = self.entity.get("tds")
        card = T.card(page)
        card.place(relx=0.5, rely=0.4, anchor="center")
        ctk.CTkLabel(card, text="TDS Pro", font=T.f(26, "bold")).pack(
            anchor="w", padx=40, pady=(34, 6))
        if e:
            ctk.CTkLabel(card, text=f"Working on: {e['name']}  (TAN {e['key']})",
                         font=T.f(14), text_color=T.OK).pack(anchor="w", padx=40)
        else:
            ctk.CTkLabel(card, text="Pick a deductor (press F4) or open Deductors from "
                         "the menu above to begin.", font=T.f(13), text_color=T.MUTED,
                         wraplength=460, justify="left").pack(anchor="w", padx=40)
        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.pack(anchor="w", padx=40, pady=(20, 34))
        T.button(bar, "Open Deductors", self.show_deductor, width=170).pack(side="left",
                                                                            padx=(0, 8))
        T.button(bar, "Select Deductor (F4)", self._on_f4, width=200,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="left")
        return page

    # ── keys ──────────────────────────────────────────────────────────────────
    def _on_f4(self, _e=None):
        if self.module:
            EntityPicker(self, self.con, self.module, self._picked)
        return "break"

    def _picked(self, row):
        if not self.module:
            return
        self.entity[self.module] = row
        self._refresh_entity()
        if self.page_name == "module":
            self.open_module(self.module)

    def _on_escape(self, _e=None):
        if self._open_menu is not None:
            self._close_dropdown()
            return "break"
        handler = getattr(self.page, "on_escape", None)
        if handler and handler():
            return "break"
        if self.page_name != "home":
            self.show_home()
        return "break"
