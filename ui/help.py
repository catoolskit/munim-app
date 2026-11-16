import customtkinter as ctk
from ui import theme as T

SECTIONS = [
    ("Getting started", [
        "1.  Utilities > Company Details: enter your business name and GSTIN.",
        "2.  Masters > Party Master: add your customers and suppliers (you can also add one while billing with the + New button).",
        "3.  Transactions > Sales Invoice or Purchase Bill: record your first bill.",
        "4.  Utilities > Backup Data: save a copy of your books to a pen drive or cloud folder. Do this regularly.",
    ]),
    ("Keyboard shortcuts", [
        "Menus:  ↑ ↓ and Enter, or press the letter shown on the right of an item.",
        "Esc:  go back one screen.        Ctrl+S:  save the entry you are on.",
        "Enter:  move to the next box on any entry screen.",
        "Dates:  type 15 (this month), 1511 (15 Nov this year) or the full 15-11-2026.",
        "Account / party boxes:  type part of the name, then press Enter to complete it.",
        "Reports:  double-click a voucher or bill to open it, then edit or delete it.",
    ]),
    ("How do I record...", [
        "A credit sale:  Sales Invoice. Pick the customer, add items, Save. The invoice posts to the ledger by itself, so do not also make a journal.",
        "A part payment at the time of sale:  type the amount in 'Received now' before saving. The rest stays as the customer's outstanding.",
        "Money received later:  Receipt / Payment. It settles the oldest bills first. See who still owes you under Reports > Outstanding.",
        "Counter sales for a day:  Daily Sales Summary (amount per GST rate). Use it only for customers who do not need a GST invoice.",
        "A mistake:  open the entry from the Day Book or a Register, then Edit or Delete. Every change is kept in Utilities > Audit Log.",
    ]),
    ("Good to know", [
        "GST law needs a tax invoice for every sale to a registered business. A monthly lump entry is fine for your books but does not replace invoices. Ask your CA if unsure.",
        "Sales returns (credit notes), stock and invoice printing are not in this version yet.",
        "Your data is stored on this computer in C:\\MUNIM. Back it up.",
    ]),
]


class HelpFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        T.title(self, "Help & Shortcuts", "The quick way around MUNIM.").pack(anchor="w", padx=28, pady=(24, 12))
        box = ctk.CTkScrollableFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        for head, lines in SECTIONS:
            card = T.card(box)
            card.pack(fill="x", padx=8, pady=8)
            ctk.CTkLabel(card, text=head, font=T.f(16, "bold"), text_color=T.TEXT).pack(
                anchor="w", padx=22, pady=(16, 6))
            for ln in lines:
                ctk.CTkLabel(card, text=ln, font=T.f(13), text_color=T.TEXT, wraplength=900,
                             justify="left", anchor="w").pack(anchor="w", padx=22, pady=3)
            ctk.CTkFrame(card, fg_color=T.CARD, corner_radius=0, height=10).pack()
