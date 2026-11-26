"""About screen — MUNIM Books."""
import webbrowser

import customtkinter as ctk

from ui.theme import ACCENT, TEXT, MUTED, BG, f, card, button

APP_NAME = "MUNIM Books"
WEBSITE = "https://technicalmunim.vercel.app"
SUPPORT_PHONE = "+91 84276 51580"
SUPPORT_EMAIL = "sumitverma2880@gmail.com"


def _version():
    try:
        import __main__
        return getattr(__main__, "CURRENT_VERSION", "") or "—"
    except Exception:
        return "—"


def _data_folder():
    try:
        from db import setup as s
        return str(s.data_dir())
    except Exception:
        return "—"


def _licence():
    try:
        from utils import licence
        return licence.licence_status()
    except Exception:
        return "—"


class AboutFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG, **kwargs)
        self._build()

    def _build(self):
        col = ctk.CTkFrame(self, fg_color="transparent")
        col.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(col, text=APP_NAME, font=f(36, "bold"),
                     text_color=ACCENT).pack(pady=(0, 4))
        ctk.CTkLabel(col, text=f"Version {_version()}",
                     font=f(13), text_color=MUTED).pack(pady=(0, 6))
        ctk.CTkLabel(col, text="Accounting, GST billing and GST returns for Indian businesses",
                     font=f(14), text_color=TEXT).pack(pady=(0, 2))
        ctk.CTkLabel(col, text="Works offline · your data stays on your computer",
                     font=f(12), text_color=MUTED).pack(pady=(0, 24))

        c = card(col)
        c.pack(fill="x", padx=0, pady=(0, 18))
        rows = [
            ("Licence", _licence()),
            ("Data folder", _data_folder()),
            ("Website", WEBSITE.replace("https://", "")),
            ("Support", f"WhatsApp {SUPPORT_PHONE}  ·  {SUPPORT_EMAIL}"),
        ]
        for label, value in rows:
            row = ctk.CTkFrame(c, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(row, text=f"{label}:", font=f(12, "bold"),
                         text_color=MUTED, width=90, anchor="e").pack(side="left", padx=(0, 10))
            ctk.CTkLabel(row, text=value, font=f(12), text_color=TEXT,
                         anchor="w", justify="left", wraplength=460).pack(side="left")
        ctk.CTkFrame(c, fg_color="transparent", height=6).pack()

        btns = ctk.CTkFrame(col, fg_color="transparent")
        btns.pack(pady=(0, 18))
        button(btns, "Open website", lambda: webbrowser.open(WEBSITE), width=150).pack(side="left")

        ctk.CTkLabel(col, text="© 2026 MUNIM · Ludhiana, Punjab",
                     font=f(12), text_color=MUTED).pack(pady=(0, 4))