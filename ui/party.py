from tkinter import ttk
import customtkinter as ctk
from db import setup as s
from ui import theme as T
from ui.ux import chain_enter, focus_later
from ui.dialogs import CreditDaysDialog


class PartyFrame(ctk.CTkFrame):
    def __init__(self, master, con):
        super().__init__(master, fg_color="transparent")
        self.con = con
        T.style_tree()
        T.title(self, "Party Master", "Customers and suppliers. Each party gets its own ledger account. Enter moves to the next box, Ctrl+S saves."
                ).pack(anchor="w", padx=28, pady=(24, 14))

        form = T.card(self)
        form.pack(fill="x", padx=28)
        for c in range(3):
            form.grid_columnconfigure(c, weight=1, uniform="col")
        self.name = T.entry(form, "e.g. Ram Traders")
        self.ptype = T.option_menu(form, ["Customer", "Supplier"])
        self.gstin = T.entry(form, "03ABCDE1234F1Z5 (optional)")
        self.phone = T.entry(form, "Mobile number")
        self.address = T.entry(form, "City / address")
        self.opening = T.entry(form, "0.00")
        self.credit = T.entry(form, "0")
        grid = [(("Party name *", self.name), ("Type", self.ptype), ("GSTIN", self.gstin)),
                (("Phone", self.phone), ("Address", self.address), ("Opening balance (Rs)", self.opening)),
                (("Credit days (for due-date ageing)", self.credit), None, None)]
        for r, row in enumerate(grid):
            for c, spec in enumerate(row):
                if spec is None:
                    continue
                label, w = spec
                ctk.CTkLabel(form, text=label, font=T.f(12), text_color=T.MUTED).grid(
                    row=r * 2, column=c, sticky="w", padx=(18, 9), pady=(14, 2))
                w.grid(row=r * 2 + 1, column=c, sticky="ew", padx=(18 if c == 0 else 9, 18 if c == 2 else 9))
        bar = ctk.CTkFrame(form, fg_color="transparent")
        bar.grid(row=6, column=0, columnspan=3, sticky="ew", padx=18, pady=16)
        T.button(bar, "Save party", self.save, width=150).pack(side="left")
        self.msg = ctk.CTkLabel(bar, text="", font=T.f(13))
        self.msg.pack(side="left", padx=16)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=28, pady=(18, 8))
        ctk.CTkLabel(top, text="All parties", font=T.f(16, "bold"), text_color=T.TEXT).pack(side="left")
        ctk.CTkLabel(top, text="(double-click a party to edit)", font=T.f(11), text_color=T.MUTED).pack(side="left", padx=10)
        self.count = ctk.CTkLabel(top, text="", font=T.f(12), text_color=T.MUTED)
        self.count.pack(side="left", padx=10)
        self.filter = ctk.CTkSegmentedButton(
            top, values=["All", "Customer", "Supplier"], command=lambda _v: self.refresh(),
            selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER,
            unselected_color="#E7ECF5", unselected_hover_color="#DCE3F0",
            text_color=T.TEXT, font=T.f(12))
        self.filter.set("All")
        self.filter.pack(side="right")

        box = T.card(self)
        box.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        cols = ("name", "type", "gstin", "phone", "address", "opening", "credit")
        self.tree = ttk.Treeview(box, columns=cols, show="headings", style="Munim.Treeview")
        heads = {"name": "Party", "type": "Type", "gstin": "GSTIN", "phone": "Phone",
                 "address": "Address", "opening": "Opening balance", "credit": "Credit days"}
        for c, w in zip(cols, (210, 80, 160, 110, 190, 130, 90)):
            self.tree.heading(c, text=heads[c], anchor="e" if c in ("opening", "credit") else "w")
            self.tree.column(c, width=w, anchor="e" if c in ("opening", "credit") else "w")
        self.tree.tag_configure("odd", background="#F8FAFD")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview,
                           style="Munim.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
        sb.pack(side="right", fill="y", pady=2)
        chain_enter([self.name, self.gstin, self.phone, self.address, self.opening, self.credit], self.save)
        self.tree.bind("<Double-1>", self.edit_party)
        focus_later(self.name)
        self.refresh()

    def edit_party(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.tree.item(sel[0])["values"]
        EditPartyDialog(self.winfo_toplevel(), self.con,
                        old_name=str(v[0]), ptype=str(v[1]), gstin=str(v[2]),
                        phone=str(v[3]), address=str(v[4]), credit_days=str(v[6]),
                        on_saved=self.refresh)

    def is_dirty(self):
        return any(w.get().strip() for w in (self.name, self.gstin, self.phone, self.address, self.opening))

    def save(self):
        try:
            s.add_party(self.con, self.name.get(), self.ptype.get(), self.gstin.get(),
                        self.phone.get(), self.address.get(), self.opening.get() or 0, self.credit.get() or 0)
        except ValueError as e:
            self.msg.configure(text=str(e), text_color=T.DANGER)
            return
        for w in (self.name, self.gstin, self.phone, self.address, self.opening, self.credit):
            w.delete(0, "end")
        self.msg.configure(text="Party saved", text_color=T.OK)
        self.refresh()
        self.name._entry.focus_set()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        f = self.filter.get()
        rows = s.list_parties(self.con, None if f == "All" else f)
        for i, p in enumerate(rows):
            amt = f"{s.to_rupees(p['opening']):,.2f} {p['opening_side']}" if p["opening"] else "-"
            self.tree.insert("", "end", tags=("odd",) if i % 2 else (),
                             values=(p["name"], p["ptype"], p["gstin"], p["phone"], p["address"], amt, p["credit_days"]))
        self.count.configure(text=f"{len(rows)} shown")


class EditPartyDialog(ctk.CTkToplevel):
    """Edit an existing party's details (name, type, GSTIN, phone, address, credit days)."""

    def __init__(self, master, con, old_name, ptype, gstin, phone, address, credit_days, on_saved):
        super().__init__(master)
        self.title(f"Edit {old_name}")
        self.con = con
        self.old_name = old_name
        self.on_saved = on_saved
        self.geometry("460x480")
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=T.BG if hasattr(T, "BG") else "#F5F7FB")

        ctk.CTkLabel(self, text=old_name, font=T.f(18, "bold"),
                     text_color=T.TEXT).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(self, text="Edit the party's details below.",
                     font=T.f(12), text_color=T.MUTED).pack(anchor="w", padx=22, pady=(0, 14))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=22)

        self.name = T.entry(body, "")
        self.name.insert(0, old_name)
        self.ptype = T.option_menu(body, ["Customer", "Supplier"])
        self.ptype.set(ptype if ptype in ("Customer", "Supplier") else "Customer")
        self.gstin = T.entry(body, "03ABCDE1234F1Z5 (optional)")
        if gstin:
            self.gstin.insert(0, gstin)
        self.phone = T.entry(body, "Mobile number")
        if phone:
            self.phone.insert(0, phone)
        self.address = T.entry(body, "City / address")
        if address:
            self.address.insert(0, address)
        self.credit = T.entry(body, "0")
        if credit_days:
            self.credit.insert(0, str(credit_days))

        fields = [("Party name *", self.name), ("Type", self.ptype),
                  ("GSTIN", self.gstin), ("Phone", self.phone),
                  ("Address", self.address), ("Credit days", self.credit)]
        for i, (label, w) in enumerate(fields):
            ctk.CTkLabel(body, text=label, font=T.f(12), text_color=T.MUTED).grid(
                row=i * 2, column=0, sticky="w", pady=(8, 2))
            w.grid(row=i * 2 + 1, column=0, sticky="ew")
        body.grid_columnconfigure(0, weight=1)

        self.msg = ctk.CTkLabel(self, text="", font=T.f(13))
        self.msg.pack(anchor="w", padx=22, pady=(10, 0))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=22, pady=(10, 20))
        T.button(bar, "Save changes", self.save, width=150).pack(side="left")
        T.button(bar, "Cancel", self.destroy, width=110,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="left", padx=10)

        chain_enter([self.name, self.gstin, self.phone, self.address, self.credit], self.save)
        focus_later(self.name)

    def save(self):
        try:
            s.update_party(self.con, self.old_name,
                           self.name.get(), self.ptype.get(), self.gstin.get(),
                           self.phone.get(), self.address.get(), self.credit.get() or 0)
        except ValueError as e:
            self.msg.configure(text=str(e), text_color=T.DANGER)
            return
        self.on_saved()
        self.destroy()
