import customtkinter as ctk
from db import setup as s
from ui.party import PartyFrame

COMING = ["Journal Entry", "Ledger View", "Trial Balance", "Sales", "Purchase",
          "Cash Book", "Day Book", "Balance Sheet", "Profit & Loss", "GST Invoice", "Stock"]


class Shell(ctk.CTkFrame):
    def __init__(self, master, con, username, role, on_logout):
        super().__init__(master, fg_color="transparent")
        self.con = con
        self.current = None

        side = ctk.CTkScrollableFrame(self, width=190, corner_radius=0)
        side.pack(side="left", fill="y")
        ctk.CTkLabel(side, text="MUNIM", font=("Georgia", 24, "bold")).pack(pady=(12, 2))
        ctk.CTkLabel(side, text=f"{username} ({role})", text_color="gray").pack(pady=(0, 12))
        ctk.CTkButton(side, text="Dashboard", command=self.show_dashboard).pack(fill="x", pady=3)
        ctk.CTkButton(side, text="Party Master",
                      command=lambda: self.show(PartyFrame(self.body, con))).pack(fill="x", pady=3)
        for name in COMING:
            ctk.CTkButton(side, text=name, state="disabled").pack(fill="x", pady=3)
        ctk.CTkButton(side, text="Logout", fg_color="gray40", command=on_logout).pack(
            fill="x", pady=(16, 3))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(side="left", fill="both", expand=True)
        self.show_dashboard()

    def show(self, frame):
        if self.current is not None:
            self.current.destroy()
        self.current = frame
        frame.pack(fill="both", expand=True)

    def show_dashboard(self):
        f = ctk.CTkFrame(self.body, fg_color="transparent")
        ctk.CTkLabel(f, text="Dashboard", font=("Segoe UI", 22, "bold")).pack(
            anchor="w", padx=20, pady=(16, 8))
        c = s.counts(self.con)
        for label, key in (("Parties", "parties"), ("Ledger accounts", "accounts"),
                           ("Vouchers posted", "vouchers")):
            card = ctk.CTkFrame(f)
            card.pack(anchor="w", padx=20, pady=6, fill="x")
            ctk.CTkLabel(card, text=str(c[key]), font=("Segoe UI", 28, "bold")).pack(
                side="left", padx=20, pady=12)
            ctk.CTkLabel(card, text=label).pack(side="left")
        ctk.CTkLabel(f, text="More modules unlock in later releases (greyed out in the sidebar).",
                     text_color="gray").pack(anchor="w", padx=20, pady=12)
        self.show(f)
