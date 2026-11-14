from tkinter import ttk
import customtkinter as ctk
from db import setup as s
from ui import theme as T


class PartyFrame(ctk.CTkFrame):
    def __init__(self, master, con):
        super().__init__(master, fg_color="transparent")
        self.con = con
        T.style_tree()
        T.title(self, "Party Master", "Customers and suppliers. Each party gets its own ledger account."
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
        grid = [(("Party name *", self.name), ("Type", self.ptype), ("GSTIN", self.gstin)),
                (("Phone", self.phone), ("Address", self.address), ("Opening balance (Rs)", self.opening))]
        for r, row in enumerate(grid):
            for c, (label, w) in enumerate(row):
                ctk.CTkLabel(form, text=label, font=T.f(12), text_color=T.MUTED).grid(
                    row=r * 2, column=c, sticky="w", padx=(18, 9), pady=(14, 2))
                w.grid(row=r * 2 + 1, column=c, sticky="ew", padx=(18 if c == 0 else 9, 18 if c == 2 else 9))
        bar = ctk.CTkFrame(form, fg_color="transparent")
        bar.grid(row=4, column=0, columnspan=3, sticky="ew", padx=18, pady=16)
        T.button(bar, "Save party", self.save, width=150).pack(side="left")
        self.msg = ctk.CTkLabel(bar, text="", font=T.f(13))
        self.msg.pack(side="left", padx=16)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=28, pady=(18, 8))
        ctk.CTkLabel(top, text="All parties", font=T.f(16, "bold"), text_color=T.TEXT).pack(side="left")
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
        cols = ("name", "type", "gstin", "phone", "address", "opening")
        self.tree = ttk.Treeview(box, columns=cols, show="headings", style="Munim.Treeview")
        heads = {"name": "Party", "type": "Type", "gstin": "GSTIN", "phone": "Phone",
                 "address": "Address", "opening": "Opening balance"}
        for c, w in zip(cols, (220, 90, 170, 120, 220, 140)):
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=w, anchor="e" if c == "opening" else "w")
        self.tree.tag_configure("odd", background="#F8FAFD")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
        sb.pack(side="right", fill="y", pady=2)
        self.refresh()

    def save(self):
        try:
            s.add_party(self.con, self.name.get(), self.ptype.get(), self.gstin.get(),
                        self.phone.get(), self.address.get(), self.opening.get() or 0)
        except ValueError as e:
            self.msg.configure(text=str(e), text_color=T.DANGER)
            return
        for w in (self.name, self.gstin, self.phone, self.address, self.opening):
            w.delete(0, "end")
        self.msg.configure(text="Party saved", text_color=T.OK)
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        f = self.filter.get()
        rows = s.list_parties(self.con, None if f == "All" else f)
        for i, p in enumerate(rows):
            amt = f"{s.to_rupees(p['opening']):,.2f} {p['opening_side']}" if p["opening"] else "-"
            self.tree.insert("", "end", tags=("odd",) if i % 2 else (),
                             values=(p["name"], p["ptype"], p["gstin"], p["phone"], p["address"], amt))
        self.count.configure(text=f"{len(rows)} shown")
