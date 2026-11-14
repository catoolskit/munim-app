from tkinter import ttk
import customtkinter as ctk
from db import setup as s


class PartyFrame(ctk.CTkFrame):
    def __init__(self, master, con):
        super().__init__(master, fg_color="transparent")
        self.con = con
        ctk.CTkLabel(self, text="Party Master", font=("Segoe UI", 22, "bold")).pack(
            anchor="w", padx=20, pady=(16, 8))

        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=20, pady=6)
        form.grid_columnconfigure((1, 3), weight=1)

        self.name = ctk.CTkEntry(form, placeholder_text="Party name *")
        self.ptype = ctk.CTkOptionMenu(form, values=["Customer", "Supplier"])
        self.gstin = ctk.CTkEntry(form, placeholder_text="GSTIN (optional)")
        self.phone = ctk.CTkEntry(form, placeholder_text="Phone")
        self.address = ctk.CTkEntry(form, placeholder_text="Address")
        self.opening = ctk.CTkEntry(form, placeholder_text="Opening balance (Rs)")

        rows = [("Name", self.name, "Type", self.ptype),
                ("GSTIN", self.gstin, "Phone", self.phone),
                ("Address", self.address, "Opening Rs", self.opening)]
        for r, (l1, w1, l2, w2) in enumerate(rows):
            ctk.CTkLabel(form, text=l1).grid(row=r, column=0, padx=(12, 6), pady=6, sticky="e")
            w1.grid(row=r, column=1, padx=6, pady=6, sticky="ew")
            ctk.CTkLabel(form, text=l2).grid(row=r, column=2, padx=(12, 6), pady=6, sticky="e")
            w2.grid(row=r, column=3, padx=(6, 12), pady=6, sticky="ew")

        bar = ctk.CTkFrame(form, fg_color="transparent")
        bar.grid(row=3, column=0, columnspan=4, sticky="ew", padx=12, pady=(2, 10))
        ctk.CTkButton(bar, text="Save Party", width=140, command=self.save).pack(side="left")
        self.msg = ctk.CTkLabel(bar, text="")
        self.msg.pack(side="left", padx=14)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(10, 0))
        ctk.CTkLabel(top, text="Show:").pack(side="left")
        self.filter = ctk.CTkOptionMenu(top, values=["All", "Customer", "Supplier"],
                                        width=120, command=lambda _v: self.refresh())
        self.filter.pack(side="left", padx=8)

        cols = ("name", "type", "gstin", "phone", "address", "opening")
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=20, pady=8)
        self.tree = ttk.Treeview(box, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (200, 80, 150, 110, 220, 120)):
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=w, anchor="e" if c == "opening" else "w")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.refresh()

    def save(self):
        try:
            s.add_party(self.con, self.name.get(), self.ptype.get(), self.gstin.get(),
                        self.phone.get(), self.address.get(), self.opening.get() or 0)
        except ValueError as e:
            self.msg.configure(text=str(e), text_color="red")
            return
        for w in (self.name, self.gstin, self.phone, self.address, self.opening):
            w.delete(0, "end")
        self.msg.configure(text="Party saved", text_color="green")
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        f = self.filter.get()
        for p in s.list_parties(self.con, None if f == "All" else f):
            amt = f"{s.to_rupees(p['opening']):,.2f} {p['opening_side']}" if p["opening"] else "-"
            self.tree.insert("", "end", values=(p["name"], p["ptype"], p["gstin"],
                                                p["phone"], p["address"], amt))
