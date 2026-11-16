"""First-run activation screen shown when no valid licence is stored."""
import customtkinter as ctk
from ui import theme as T
from ui.ux import chain_enter, focus_later
from utils import settings
from utils.licence import validate_key
from utils.fmt import disp_date


class ActivationFrame(ctk.CTkFrame):
    """on_activated(user_row) is called on success."""
    def __init__(self, master, con, on_activated):
        super().__init__(master, fg_color="transparent")
        from db.setup import login
        self._login_fn = login
        self.con = con
        self.on_activated = on_activated

        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid_columnconfigure(0, weight=2, uniform="a")
        f.grid_columnconfigure(1, weight=3, uniform="a")
        f.grid_rowconfigure(0, weight=1)
        f.pack(fill="both", expand=True)

        left = ctk.CTkFrame(f, fg_color=T.NAVY, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(left, text="MUNIM", font=T.f(44, "bold"), text_color="white").place(
            relx=0.5, rely=0.42, anchor="center")
        ctk.CTkLabel(left, text="Simple books for small traders", font=T.f(14),
                     text_color="#9FB3D9").place(relx=0.5, rely=0.50, anchor="center")
        ctk.CTkLabel(left, text="Activate your copy", font=T.f(13),
                     text_color="#7A9CC9").place(relx=0.5, rely=0.57, anchor="center")

        right = ctk.CTkFrame(f, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        card = T.card(right, width=380)
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(card, text="Activate MUNIM", font=T.f(22, "bold"),
                     text_color=T.TEXT).pack(anchor="w", padx=34, pady=(32, 2))
        ctk.CTkLabel(card, text="Enter the username, password and licence key\n"
                     "provided by your software provider.",
                     font=T.f(13), text_color=T.MUTED, justify="left").pack(
                     anchor="w", padx=34, pady=(0, 18))

        self.user = T.entry(card, "Username", width=330)
        self.user.pack(padx=34, pady=(0, 10))
        self.pw = T.entry(card, "Password", width=330, show="*")
        self.pw.pack(padx=34, pady=(0, 10))
        self.key_e = T.entry(card, "Licence key  (MNM-...)", width=330)
        self.key_e.pack(padx=34, pady=(0, 6))
        self.msg = ctk.CTkLabel(card, text="", font=T.f(12), text_color=T.MUTED,
                                wraplength=330, justify="left")
        self.msg.pack(anchor="w", padx=34, pady=4)
        T.button(card, "Activate", self.activate, width=330).pack(padx=34, pady=(8, 32))

        chain_enter([self.user, self.pw, self.key_e], self.activate)
        focus_later(self.user)

    def activate(self):
        username = self.user.get().strip()
        password = self.pw.get()
        key = self.key_e.get().strip()
        if not username or not password or not key:
            self.msg.configure(text="Please fill all three fields", text_color=T.DANGER)
            return
        try:
            lic_user, expiry = validate_key(key)
        except ValueError as e:
            self.msg.configure(text=str(e), text_color=T.DANGER)
            return
        if lic_user.lower() != username.lower():
            self.msg.configure(text="This licence key does not belong to this username",
                               text_color=T.DANGER)
            return
        row = self._login_fn(self.con, username, password)
        if not row:
            self.msg.configure(text="Wrong username or password", text_color=T.DANGER)
            return
        st = settings.load_settings()
        st["licence_key"] = key
        st["licence_user"] = username
        settings.save_settings(st)
        self.msg.configure(
            text=f"Activated! Valid until {expiry.strftime('%d-%m-%Y')}",
            text_color=T.OK)
        self.after(900, lambda: self.on_activated(row))