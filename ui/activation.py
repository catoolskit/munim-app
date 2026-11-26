"""Activation screen — shown when this computer has no valid licence.
Needs internet once (username + password + licence key); after that MUNIM works offline."""
import threading
import webbrowser

import customtkinter as ctk

from ui import theme as T
from ui.ux import chain_enter, focus_later
from utils import settings
from utils import licence

HELP_URL = "https://wa.me/918427651580?text=Hi%2C%20I%20need%20help%20activating%20MUNIM"


class ActivationFrame(ctk.CTkFrame):
    """on_activated(user_row) is called on success."""
    def __init__(self, master, con, on_activated):
        super().__init__(master, fg_color="transparent")
        from db.setup import login, add_user
        self._login_fn = login
        self._add_user_fn = add_user
        self.con = con
        self.on_activated = on_activated
        self._busy = False
        name = licence.product_name()
        tagline = ("Simple books for small traders" if licence.PRODUCT == "books"
                   else "Tax · GST · TDS for professionals")

        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid_columnconfigure(0, weight=2, uniform="a")
        f.grid_columnconfigure(1, weight=3, uniform="a")
        f.grid_rowconfigure(0, weight=1)
        f.pack(fill="both", expand=True)

        left = ctk.CTkFrame(f, fg_color=T.NAVY, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(left, text=name, font=T.f(40, "bold"), text_color="white").place(
            relx=0.5, rely=0.42, anchor="center")
        ctk.CTkLabel(left, text=tagline, font=T.f(14),
                     text_color="#9FB3D9").place(relx=0.5, rely=0.50, anchor="center")
        ctk.CTkLabel(left, text="Activate your copy", font=T.f(13),
                     text_color="#7A9CC9").place(relx=0.5, rely=0.57, anchor="center")

        right = ctk.CTkFrame(f, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        card = T.card(right, width=380)
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(card, text=f"Activate {name}", font=T.f(22, "bold"),
                     text_color=T.TEXT).pack(anchor="w", padx=34, pady=(32, 2))
        ctk.CTkLabel(card, text="Enter the username, password and licence key\n"
                     "we sent you on WhatsApp.",
                     font=T.f(13), text_color=T.MUTED, justify="left").pack(
                     anchor="w", padx=34, pady=(0, 18))

        self.user = T.entry(card, "Username", width=330)
        self.user.pack(padx=34, pady=(0, 10))
        self.pw = T.entry(card, "Password", width=330, show="*")
        self.pw.pack(padx=34, pady=(0, 10))
        self.key_e = T.entry(card, "Licence key  (MNM-XXXX-XXXX-XXXX)", width=330)
        self.key_e.pack(padx=34, pady=(0, 6))
        self.msg = ctk.CTkLabel(card, text="", font=T.f(12), text_color=T.MUTED,
                                wraplength=330, justify="left")
        self.msg.pack(anchor="w", padx=34, pady=4)
        self.btn = T.button(card, "Activate", self.activate, width=330)
        self.btn.pack(padx=34, pady=(8, 8))
        ctk.CTkLabel(card, text="Internet is needed only for the first activation.\n"
                     "After that it works offline.",
                     font=T.f(11), text_color=T.MUTED, justify="left").pack(
                     anchor="w", padx=34, pady=(0, 4))
        help_lbl = ctk.CTkLabel(card, text=f"Need help? WhatsApp {licence.SUPPORT}",
                                font=T.f(12), text_color=T.ACCENT, cursor="hand2")
        help_lbl.pack(anchor="w", padx=34, pady=(0, 28))
        help_lbl.bind("<Button-1>", lambda _e: webbrowser.open(HELP_URL))

        chain_enter([self.user, self.pw, self.key_e], self.activate)
        focus_later(self.user)

        # Tell the user why activation is needed (expired / suspended / new company …)
        try:
            cur = licence.check(allow_network=False)
            self._say(f"This computer is already activated ({cur.get('u')}). Enter your username "
                      "and password to open this company — no key needed.", T.MUTED)
        except licence.LicenceError as e:
            if e.code != "not_activated":
                self._say(str(e), T.DANGER)
        saved_key = licence.stored_key()
        if saved_key:
            try:
                self.key_e.insert(0, saved_key)
            except Exception:
                pass

    # ── helpers ──────────────────────────────────────────────────────────────
    def _say(self, text, color):
        self.msg.configure(text=text, text_color=color)

    def _set_busy(self, busy):
        self._busy = busy
        try:
            self.btn.configure(state="disabled" if busy else "normal",
                               text="Activating…" if busy else "Activate")
        except Exception:
            pass

    # ── activation ───────────────────────────────────────────────────────────
    def activate(self):
        if self._busy:
            return
        typed = self.user.get().strip()
        uname = typed.lower()
        password = self.pw.get()
        key = self.key_e.get().strip().upper()
        if not typed or not password:
            self._say("Please enter your username and password", T.DANGER)
            return

        # Already licensed on this PC for this user (e.g. opening another company)?
        try:
            cur = licence.check(allow_network=False)
        except licence.LicenceError:
            cur = None
        if cur and cur.get("u") == uname:
            self._finish(cur, typed, password, key or licence.stored_key())
            return

        if not key:
            self._say("Please enter the licence key (MNM-XXXX-XXXX-XXXX)", T.DANGER)
            return
        self._set_busy(True)
        self._say("Checking your licence online…", T.MUTED)
        box = {}

        def work():
            try:
                box["lic"] = licence.activate(uname, password, key)
            except licence.LicenceError as e:
                box["err"] = str(e)
            except Exception as e:
                box["err"] = f"Activation failed: {e}"

        threading.Thread(target=work, daemon=True).start()
        self._wait(box, typed, password, key)

    def _wait(self, box, typed, password, key):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        if not box:
            self.after(150, lambda: self._wait(box, typed, password, key))
            return
        self._set_busy(False)
        if "err" in box:
            self._say(box["err"], T.DANGER)
            return
        self._finish(box["lic"], typed, password, key)

    def _finish(self, lic, typed, password, key):
        # Existing local account: authenticate its password. On a fresh company
        # database, create the licensed user and force a password change.
        row = self._login_fn(self.con, typed, password)
        if not row:
            existing = self.con.execute(
                "SELECT 1 FROM users WHERE username=?", (typed,)
            ).fetchone()
            if existing:
                self._say("Licence is active ✓  Now type your MUNIM login password (the one "
                          "you use every day) in the Password box and press Activate again.",
                          T.OK)
                try:
                    self.pw.delete(0, "end")
                    self.pw.focus_set()
                except Exception:
                    pass
                return
            try:
                self._add_user_fn(self.con, typed, password, "admin", must_change=1)
            except ValueError as e:
                self._say(str(e), T.DANGER)
                return
            except Exception as e:
                self._say(f"Could not create account: {e}", T.DANGER)
                return
            row = self._login_fn(self.con, typed, password)
            if not row:
                self._say("Activation failed — please try again", T.DANGER)
                return

        st = settings.load_settings()
        st["licence_key"] = key
        st["licence_user"] = typed
        settings.save_settings(st)
        self._say(f"Activated ✓  Valid until {licence.fmt_date(licence.expiry_of(lic))}", T.OK)
        self.after(900, lambda: self.on_activated(row))
