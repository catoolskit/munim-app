import customtkinter as ctk
from ui.theme import COLOURS, FONTS

VERSION = "v0.17"
BUILD_DATE = "November 2026"


class AboutFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLOURS["bg"], **kwargs)
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self,
            text="MUNIM",
            font=FONTS["heading"],
            text_color=COLOURS["accent"],
        ).pack(pady=(40, 4))

        ctk.CTkLabel(
            self,
            text=f"Version {VERSION}  •  {BUILD_DATE}",
            font=FONTS["sub"],
            text_color=COLOURS["muted"],
        ).pack(pady=(0, 24))

        ctk.CTkLabel(
            self,
            text="GST Accounting Software for Trading Businesses",
            font=FONTS["body"],
            text_color=COLOURS["fg"],
        ).pack(pady=(0, 8))

        ctk.CTkLabel(
            self,
            text="Designed for gold, silver & metals traders",
            font=FONTS["body"],
            text_color=COLOURS["muted"],
        ).pack(pady=(0, 32))

        info = [
            ("Stack",   "Python 3.11  •  CustomTkinter 5.2.2  •  SQLite"),
            ("Builder", "PyInstaller  •  GitHub Actions"),
            ("Licence", "Single-company perpetual licence"),
        ]
        for label, value in info:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(pady=2)
            ctk.CTkLabel(
                row,
                text=f"{label}:",
                font=FONTS["sub"],
                text_color=COLOURS["muted"],
                width=80,
                anchor="e",
            ).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(
                row,
                text=value,
                font=FONTS["body"],
                text_color=COLOURS["fg"],
                anchor="w",
            ).pack(side="left")

        ctk.CTkLabel(
            self,
            text="© 2026 Sumit Verma, Ludhiana",
            font=FONTS["sub"],
            text_color=COLOURS["muted"],
        ).pack(pady=(40, 8))

        ctk.CTkLabel(
            self,
            text="Built with ❤ for real-world Indian GST compliance",
            font=FONTS["sub"],
            text_color=COLOURS["muted"],
        ).pack(pady=(0, 40))
