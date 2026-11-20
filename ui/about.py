"""About dialog — version, licence expiry, support contact."""
import customtkinter as ctk
from ui import theme as T
from utils import settings

VERSION = "v0.16"
SUPPORT = "support@munim.in"


class AboutFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        st = settings.load_settings()
        licence = st.get("licence_key", "")
        expiry  = st.get("licence_expiry", "15-11-2028")

        T.title(self, "About MUNIM", "Version info, licence, and support.").pack(
            anchor="w", padx=28, pady=(24, 16))

        card = T.card(self)
        card.pack(fill="x", padx=28)

        def row(label, value, color=T.TEXT):
            f = ctk.CTkFrame(card, fg_color="transparent")
            f.pack(fill="x", padx=24, pady=(10, 0))
            ctk.CTkLabel(f, text=label, font=T.f(12), text_color=T.MUTED,
                         width=200, anchor="w").pack(side="left")
            ctk.CTkLabel(f, text=value, font=T.f(13, "bold"),
                         text_color=color).pack(side="left")

        ctk.CTkLabel(card, text="MUNIM", font=T.f(28, "bold"),
                     text_color=T.NAVY).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(card, text="GST Accounting for Indian Traders",
                     font=T.f(13), text_color=T.MUTED).pack(anchor="w", padx=24, pady=(0, 16))

        row("Version",         VERSION)
        row("Licence key",     licence[:28] + "…" if len(licence) > 28 else licence or "—")
        row("Licence valid to", expiry or "—")
        row("Support",         SUPPORT, T.ACCENT)
        row("Built with",      "Python 3.11 · CustomTkinter · SQLite")

        ctk.CTkFrame(card, fg_color=T.CARD, corner_radius=0, height=20).pack()

        note = ctk.CTkLabel(
            self,
            text="To renew your licence go to Utilities > Renew Licence.",
            font=T.f(12), text_color=T.MUTED)
        note.pack(anchor="w", padx=28, pady=(14, 0))