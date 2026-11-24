import customtkinter as ctk
from tkinter import messagebox
from db import setup as s
from ui import theme as T
from ui.dialogs import OpeningDialog
from ui.ux import chain_enter, focus_later
from ui.widgets import DataTable
from utils.fmt import inr


class AccountMasterFrame(ctk.CTkFrame):
    """Create ledger accounts (Electricity, Freight...), choose their group, set opening balances."""
    def __init__(self, master, con):
        super().__init__(master, fg_color="transparent")
        self.con = con
        T.title(self, "Ledger Accounts",
                "Create accounts such as Electricity or Freight and choose their group. Direct expenses and "
                "Sales/Purchase feed the Trading Account. Double-click an account to set its opening balance."
                ).pack(anchor="w", padx=28, pady=(24, 12))
        card = T.card(self)
        card.pack(fill="x", padx=28)
        self.name = T.entry(card, "e.g. Electricity", width=260)
        self.group = T.option_menu(card, [g for g, _n in s.ACCOUNT_GROUPS], width=230,
                                   command=lambda _v: self._side_default())
        self.group.set("Indirect Expenses")
        self.opening = T.entry(card, "0.00", width=150)
        self.side = T.option_menu(card, ["Dr", "Cr"], width=80)
        for c, (h, w) in enumerate((("Account name *", self.name), ("Group", self.group),
                                    ("Opening balance (Rs)", self.opening), ("Dr / Cr", self.side))):
            ctk.CTkLabel(card, text=h, font=T.f(12), text_color=T.MUTED).grid(
                row=0, column=c, sticky="w", padx=(20 if c == 0 else 8, 8), pady=(14, 2))
            w.grid(row=1, column=c, padx=(20 if c == 0 else 8, 8), pady=(0, 14))
        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.grid(row=2, column=0, columnspan=4, sticky="ew", padx=20, pady=(0, 16))
        T.button(bar, "Save account", self.save, width=150).pack(side="left")
        T.button(bar, "Delete selected", self.delete, width=140, fg_color=T.DANGER,
                 hover_color="#A32F23").pack(side="left", padx=10)
        self.msg = ctk.CTkLabel(bar, text="", font=T.f(13))
        self.msg.pack(side="left", padx=10)
        self.table = DataTable(self, [("n", "Account", 270, "w"), ("g", "Group", 210, "w"),
                                      ("t", "Type", 90, "w"), ("o", "Opening balance", 160, "e")], height=12)
        self.table.pack(fill="both", expand=True, padx=28, pady=(14, 24))
        self.table.on_open(self.edit_opening)
        chain_enter([self.name, self.opening], self.save)
        focus_later(self.name)
        self.refresh()

    def _side_default(self):
        nature = s.GROUP_NATURE.get(self.group.get(), "Expense")
        self.side.set("Dr" if nature in ("Asset", "Expense") else "Cr")

    def is_dirty(self):
        return bool(self.name.get().strip() or self.opening.get().strip())

    def save(self):
        try:
            s.add_ledger_account(self.con, self.name.get(), self.group.get(), self.opening.get() or 0,
                                 self.side.get())
        except ValueError as e:
            self.msg.configure(text=str(e), text_color=T.DANGER)
            return
        self.name.delete(0, "end"); self.opening.delete(0, "end")
        self.msg.configure(text="Account saved", text_color=T.OK)
        self.refresh()
        self.name._entry.focus_set()

    def delete(self):
        name = self.table.selected_key()
        if not name:
            self.msg.configure(text="Select an account in the list first", text_color=T.DANGER)
            return
        if not messagebox.askyesno("Delete account", f"Delete the account '{name}'?"):
            return
        try:
            s.delete_ledger_account(self.con, name)
        except ValueError as e:
            self.msg.configure(text=str(e), text_color=T.DANGER)
            return
        self.msg.configure(text="Account deleted", text_color=T.OK)
        self.refresh()

    def edit_opening(self, name):
        row = [a for a in s.list_accounts(self.con) if a["name"] == name][0]
        OpeningDialog(self.winfo_toplevel(), self.con, name, s.to_rupees(row["opening"]),
                      row["opening_side"], self.refresh)

    def refresh(self):
        rows = []
        for a in s.list_accounts(self.con):
            amt = f"{inr(s.to_rupees(a['opening']))} {a['opening_side']}" if a["opening"] else "-"
            rows.append(((a["name"], a["grp"], a["nature"], amt), None, a["name"]))
        self.table.set_rows(rows)
