"""MUNIM Pro — entry point (TDS Pro · GST Pro · Tax Pro).
Built as MUNIMPro.exe from the same codebase as MUNIM Books."""
from utils import licence
licence.PRODUCT = "pro"          # must run before anything reads the licence

import threading
from tkinter import messagebox

import customtkinter as ctk

from ui import pro_theme
pro_theme.apply()                # emerald colours before any widget exists

from ui import theme as T
from ui.activation import ActivationFrame
from ui.pro_shell import ProShell
from db import pro_db
from db.setup import login, change_password
from utils import settings, errlog, vault

APP_NAME = "MUNIM Pro"
APP_TAGLINE = "Tax · GST · TDS for professionals"
CURRENT_VERSION = "pro-v0.1"


class ProApp(ctk.CTk):
    def __init__(self):
        ctk.set_default_color_theme("blue")
        T.apply_global_theme()
        super().__init__()
        ctk.set_appearance_mode("light")
        self.title(APP_NAME)
        self.configure(fg_color=T.BG)
        self.geometry("1180x720")
        self.minsize(1000, 640)
        self.frame = None
        self.con = pro_db.connect()
        settings.set_settings_file(pro_db.settings_file())
        self._show_wait("Checking your licence…")
        self.after(100, self._start)

    def report_callback_exception(self, exc, val, tb):
        errlog.log_exception(exc, val, tb)
        messagebox.showerror(APP_NAME, f"Something went wrong:\n{val}\n\n"
                             f"Details were saved to {errlog.log_path()}")

    # ── screens ───────────────────────────────────────────────────────────────
    def _swap(self, frame):
        if self.frame is not None:
            self.frame.destroy()
        self.frame = frame
        frame.pack(fill="both", expand=True)

    def _card_screen(self, heading, sub):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid_columnconfigure(0, weight=2, uniform="a")
        f.grid_columnconfigure(1, weight=3, uniform="a")
        f.grid_rowconfigure(0, weight=1)
        left = ctk.CTkFrame(f, fg_color=T.NAVY, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(left, text=APP_NAME, font=T.f(40, "bold"), text_color="white").place(
            relx=0.5, rely=0.44, anchor="center")
        ctk.CTkLabel(left, text=APP_TAGLINE, font=T.f(14), text_color="#A9D8C4").place(
            relx=0.5, rely=0.52, anchor="center")
        right = ctk.CTkFrame(f, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        card = T.card(right)
        card.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(card, text=heading, font=T.f(24, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=34, pady=(32, 2))
        ctk.CTkLabel(card, text=sub, font=T.f(13), text_color=T.MUTED, wraplength=330,
                     justify="left").pack(anchor="w", padx=34, pady=(0, 18))
        return f, card

    def _show_wait(self, text):
        f, card = self._card_screen(APP_NAME, text)
        ctk.CTkLabel(card, text="").pack(pady=(0, 20))
        self._swap(f)

    # ── start-up ──────────────────────────────────────────────────────────────
    def _start(self):
        box = {}

        def work():
            try:
                licence.check()          # online check (max ~4 s), offline fallback
                box["ok"] = True
            except Exception as e:       # LicenceError or anything unexpected
                box["err"] = e
        threading.Thread(target=work, daemon=True).start()
        self._wait_start(box)

    def _wait_start(self, box):
        if not box:
            self.after(150, lambda: self._wait_start(box))
            return
        if "err" in box or not pro_db.has_users(self.con):
            self.show_activation()
        else:
            self.show_login()

    def show_activation(self):
        def activated(row):
            if row["must_change"]:
                self.show_change_password(row["username"], row["role"], None)
            else:
                self.show_shell(row["username"], row["role"])
        self._swap(ActivationFrame(self, self.con, activated))

    def show_login(self):
        f, card = self._card_screen("Log in", "Use your MUNIM Pro password "
                                              "(not the activation password).")
        user = T.entry(card, "Username", width=330)
        user.pack(padx=34, pady=(0, 10))
        pw = T.entry(card, "Password", width=330, show="*")
        pw.pack(padx=34, pady=(0, 6))
        msg = ctk.CTkLabel(card, text="", font=T.f(12), text_color=T.MUTED,
                           wraplength=330, justify="left")
        msg.pack(anchor="w", padx=34, pady=4)

        def go(_e=None):
            typed, password = user.get().strip(), pw.get()
            row = login(self.con, typed, password)
            if not row:
                msg.configure(text="Wrong username or password.", text_color=T.DANGER)
                return
            try:
                licence.check(allow_network=False)
            except licence.LicenceError:
                self.show_activation()   # the activation screen shows the reason
                return
            self._open_vault(password)
            if row["must_change"]:
                self.show_change_password(row["username"], row["role"], password)
            else:
                self.show_shell(row["username"], row["role"])

        user.bind("<Return>", lambda _e: pw.focus_set())
        pw.bind("<Return>", go)
        T.button(card, "Log in", go, width=330).pack(padx=34, pady=(8, 32))
        self._swap(f)
        user.focus()

    def show_change_password(self, username, role, old_password):
        f, card = self._card_screen(
            "Set your password",
            "Choose your own MUNIM Pro password (at least 8 characters, letters and "
            "numbers). It also protects your saved portal passwords.")
        p1 = T.entry(card, "New password", width=330, show="*")
        p1.pack(padx=34, pady=(0, 10))
        p2 = T.entry(card, "Confirm new password", width=330, show="*")
        p2.pack(padx=34, pady=(0, 6))
        msg = ctk.CTkLabel(card, text="", font=T.f(12), wraplength=330, justify="left")
        msg.pack(anchor="w", padx=34, pady=4)

        def save(_e=None):
            a, b = p1.get(), p2.get()
            if a != b:
                msg.configure(text="Passwords do not match", text_color=T.DANGER)
                return
            err = vault.strength_error(a)
            if err:
                msg.configure(text=err, text_color=T.DANGER)
                return
            try:
                change_password(self.con, username, a)
            except ValueError as e:
                msg.configure(text=str(e), text_color=T.DANGER)
                return
            self._sync_vault(old_password, a)
            self.show_shell(username, role)

        p1.bind("<Return>", lambda _e: p2.focus_set())
        p2.bind("<Return>", save)
        T.button(card, "Save and continue", save, width=330).pack(padx=34, pady=(8, 32))
        self._swap(f)
        p1.focus()

    def show_shell(self, username, role):
        self._swap(ProShell(self, self.con, username, role, on_logout=self.logout))

    def logout(self):
        vault.lock()
        self.show_login()

    # ── vault follows the login password ──────────────────────────────────────
    def _open_vault(self, password):
        try:
            if vault.is_setup(self.con):
                vault.unlock(self.con, password)
            elif not vault.strength_error(password):
                vault.setup(self.con, password)
        except vault.VaultError:
            pass   # screens will ask again when a saved password is needed

    def _sync_vault(self, old_password, new_password):
        try:
            if not vault.is_setup(self.con):
                vault.setup(self.con, new_password)
            elif old_password:
                vault.change_master(self.con, old_password, new_password)
        except vault.VaultError:
            pass


if __name__ == "__main__":
    ProApp().mainloop()