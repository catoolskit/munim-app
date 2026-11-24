"""About screen — MUNIM v0.17"""
import customtkinter as ctk
from ui.theme import ACCENT, TEXT, MUTED, BG, CARD, BORDER, f, card, button

VERSION = "v0.18"
BUILD_DATE = "November 2026"


class AboutFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG, **kwargs)
        self._build()

    def _build(self):
        # Centre column
        col = ctk.CTkFrame(self, fg_color="transparent")
        col.place(relx=0.5, rely=0.5, anchor="center")

        # Logo / app name
        ctk.CTkLabel(col, text="MUNIM", font=f(36, "bold"),
                     text_color=ACCENT).pack(pady=(0, 4))

        ctk.CTkLabel(col, text=f"Version {VERSION}  •  {BUILD_DATE}",
                     font=f(13), text_color=MUTED).pack(pady=(0, 6))

        ctk.CTkLabel(col, text="GST Accounting Software for Trading Businesses",
                     font=f(14), text_color=TEXT).pack(pady=(0, 2))

        ctk.CTkLabel(col, text="Designed for gold, silver & metals traders",
                     font=f(12), text_color=MUTED).pack(pady=(0, 28))

        # Info card
        c = card(col)
        c.pack(fill="x", padx=0, pady=(0, 24))

        rows = [
            ("Stack",    "Python 3.11  •  CustomTkinter 5.2.2  •  SQLite"),
            ("Builder",  "PyInstaller  •  GitHub Actions"),
            ("Data",     "D:\\MUNIM\\  (per-company SQLite)"),
            ("Licence",  "Single-company perpetual licence"),
        ]
        for label, value in rows:
            row = ctk.CTkFrame(c, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(row, text=f"{label}:", font=f(12, "bold"),
                         text_color=MUTED, width=70, anchor="e").pack(side="left", padx=(0, 10))
            ctk.CTkLabel(row, text=value, font=f(12),
                         text_color=TEXT, anchor="w").pack(side="left")

        # Footer
        ctk.CTkLabel(col, text="© 2026 Sumit Verma, Ludhiana",
                     font=f(12), text_color=MUTED).pack(pady=(0, 4))

        ctk.CTkLabel(col, text="Built with ❤ for real-world Indian GST compliance",
                     font=f(11), text_color=MUTED).pack()
