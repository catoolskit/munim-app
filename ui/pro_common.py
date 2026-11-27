"""MUNIM Pro — shared UI helpers: masked password box, vault prompt,
portal links, WhatsApp."""
import urllib.parse
import webbrowser
from tkinter import messagebox, simpledialog

import customtkinter as ctk

from ui import theme as T
from utils import vault

WHATSAPP_NO = "918427651580"
CLIPBOARD_SECONDS = 30

PORTALS = {
    "ITD": ("Income-tax e-filing", "https://eportal.incometax.gov.in/iec/foservices/#/login"),
    "TRACES": ("TRACES", "https://www.tdscpc.gov.in/app/login.xhtml"),
    "GST": ("GST portal", "https://services.gst.gov.in/services/login"),
}


def whatsapp(text):
    webbrowser.open(f"https://wa.me/{WHATSAPP_NO}?text={urllib.parse.quote(text)}")


def copy_for_a_while(widget, text, seconds=CLIPBOARD_SECONDS):
    """Copy to clipboard and clear it again after a few seconds (for passwords)."""
    root = widget.nametowidget(".")
    root.clipboard_clear()
    root.clipboard_append(text)

    def wipe():
        try:
            if root.clipboard_get() == text:
                root.clipboard_clear()
                root.clipboard_append("")
        except Exception:
            pass
    root.after(seconds * 1000, wipe)


def open_portal(widget, portal, user_id=""):
    """Open the portal's login page and copy the user ID. Returns a message."""
    name, url = PORTALS[portal]
    webbrowser.open(url)
    if user_id:
        root = widget.nametowidget(".")
        root.clipboard_clear()
        root.clipboard_append(user_id)
        return (f"{name} opened. User ID copied: paste it, then click 'Copy password'. "
                "Type the captcha / OTP yourself.")
    return f"{name} opened."


def ensure_vault(parent, con, username) -> bool:
    """Make sure saved passwords can be read/written. Asks for the MUNIM Pro
    password if needed. Returns True if the vault is ready."""
    try:
        if vault.is_unlocked():
            return True
        pw = simpledialog.askstring(
            "MUNIM Pro", "Enter your MUNIM Pro login password to use saved portal passwords:",
            show="*", parent=parent)
        if not pw:
            return False
        if not vault.is_setup(con):
            from db.setup import login
            if not login(con, username, pw):
                messagebox.showerror("MUNIM Pro", "Wrong password.", parent=parent)
                return False
            err = vault.strength_error(pw)
            if err:
                messagebox.showerror("MUNIM Pro", f"{err}. Please change your MUNIM Pro "
                                     "password first.", parent=parent)
                return False
            vault.setup(con, pw)
            return True
        if vault.unlock(con, pw):
            return True
        messagebox.showerror("MUNIM Pro", "Wrong password. If you changed your password "
                             "recently, try the old one.", parent=parent)
        return False
    except vault.VaultError as e:
        messagebox.showerror("MUNIM Pro", str(e), parent=parent)
        return False


class SecretEntry(ctk.CTkFrame):
    """Password box with a Show/Hide button. loader() may return a saved password
    to reveal when the box is empty (or None to do nothing)."""

    def __init__(self, master, placeholder="Password", loader=None, width=200):
        super().__init__(master, fg_color="transparent")
        self.loader = loader
        self._shown = False
        self.entry = T.entry(self, placeholder, width=width, height=34, show="•")
        self.entry.pack(side="left")
        self.eye = ctk.CTkButton(self, text="Show", width=56, height=34,
                                 fg_color="#E7ECF5", hover_color="#DCE3F0",
                                 text_color=T.TEXT, font=T.f(12), command=self.toggle)
        self.eye.pack(side="left", padx=(4, 0))

    def toggle(self):
        if not self._shown and not self.entry.get() and self.loader:
            pw = self.loader()
            if pw is None:
                return
            self.set(pw)
        self._shown = not self._shown
        self.entry.configure(show="" if self._shown else "•")
        self.eye.configure(text="Hide" if self._shown else "Show")

    def hide(self):
        self._shown = False
        self.entry.configure(show="•")
        self.eye.configure(text="Show")

    def get(self):
        return self.entry.get()

    def set(self, value):
        state = self.entry.cget("state")
        self.entry.configure(state="normal")
        self.entry.delete(0, "end")
        if value:
            self.entry.insert(0, value)
        self.entry.configure(state=state)

    def clear(self):
        self.set("")
        self.hide()

    def set_state(self, state):
        self.entry.configure(state=state)

    def set_placeholder(self, text):
        self.entry.configure(placeholder_text=text)