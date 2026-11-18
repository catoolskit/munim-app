"""Stock Items Master — add, edit, delete stock items."""
import customtkinter as ctk
from db import setup as s
from ui import theme as T
from ui.ux import chain_enter, focus_later

L = "w"

GST_RATES = ["0", "0.25", "1.5", "3", "5", "12", "18", "28", "40"]
UNITS = ["pcs", "kg", "g", "mtr", "cm", "ltr", "ml", "box", "bag", "set", "pair", "doz"]


class StockItemsFrame(ctk.CTkFrame):
    """Stock Items Master."""

    def __init__(self, master, con):
        super().__init__(master, fg_color="transparent")
        self.con = con
        T.title(self, "Stock Items", "Manage your item master. Items appear in Sales and Purchase invoices.").pack(
            anchor="w", padx=28, pady=(24, 12))

        # ---- entry card ----
        self.card = T.card(self)
        self.card.pack(fill="x", padx=28, pady=(0, 12))
        self._editing_id = None
        self._build_form()

        # ---- table ----
        from ui.widgets import DataTable
        self.table = DataTable(self, [
            ("n", "Item Name", 280, L), ("h", "HSN", 100, L),
            ("u", "Unit", 80, L), ("g", "GST %", 70, L),
            ("o", "Opening Qty", 100, "e")], height=14)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.table.on_open(self._on_select)
        self._refresh()

    def _build_form(self):
        for w in self.card.winfo_children():
            w.destroy()
        g = self.card
        g.grid_columnconfigure((0, 1, 2, 3, 4), weight=0)

        def lbl(text, row, col):
            ctk.CTkLabel(g, text=text, font=T.f(12), text_color=T.MUTED).grid(
                row=row, column=col, sticky="w", padx=(20 if col == 0 else 8, 8), pady=(12, 2))

        lbl("Item Name *", 0, 0)
        lbl("HSN / SAC", 0, 1)
        lbl("Unit", 0, 2)
        lbl("GST %", 0, 3)
        lbl("Opening Qty", 0, 4)

        self.f_name = T.entry(g, width=260)
        self.f_hsn = T.entry(g, width=120)
        self.f_unit = T.combo(g, UNITS, width=100)
        self.f_unit.set("pcs")
        self.f_gst = T.option_menu(g, GST_RATES, width=90)
        self.f_gst.set("18")
        self.f_qty = T.entry(g, "0", width=110)

        self.f_name.grid(row=1, column=0, padx=(20, 8), pady=(0, 4))
        self.f_hsn.grid(row=1, column=1, padx=8, pady=(0, 4))
        self.f_unit.grid(row=1, column=2, padx=8, pady=(0, 4))
        self.f_gst.grid(row=1, column=3, padx=8, pady=(0, 4))
        self.f_qty.grid(row=1, column=4, padx=8, pady=(0, 4))

        bar = ctk.CTkFrame(g, fg_color="transparent")
        bar.grid(row=2, column=0, columnspan=6, sticky="w", padx=20, pady=(4, 14))
        self.save_btn = T.button(bar, "Add Item", self._save, width=120)
        self.save_btn.pack(side="left")
        self.cancel_btn = T.button(bar, "Cancel", self._cancel, width=90,
                                   fg_color="#E7ECF5", text_color=T.TEXT, hover_color="#DCE3F0")
        self.msg = ctk.CTkLabel(bar, text="", font=T.f(12), text_color=T.DANGER)
        self.msg.pack(side="left", padx=12)
        chain_enter([self.f_name, self.f_hsn, self.f_qty], self._save)
        focus_later(self.f_name)

    def _refresh(self):
        rows = []
        for it in s.list_stock_items(self.con):
            rows.append(((it["name"], it["hsn"] or "-", it["unit"],
                          it["gst_rate"] + "%", it["opening_qty"]), None, it["id"]))
        self.table.set_rows(rows)

    def _on_select(self, item_id):
        it = self.con.execute(
            "SELECT * FROM stock_items WHERE id=?", (item_id,)).fetchone()
        if not it:
            return
        self._editing_id = item_id
        self.f_name.delete(0, "end"); self.f_name.insert(0, it["name"])
        self.f_hsn.delete(0, "end"); self.f_hsn.insert(0, it["hsn"] or "")
        self.f_unit.set(it["unit"] or "pcs")
        self.f_gst.set(str(it["gst_rate"] or "18"))
        self.f_qty.delete(0, "end"); self.f_qty.insert(0, str(it["opening_qty"] or "0"))
        self.save_btn.configure(text="Update Item")
        self.cancel_btn.pack(side="left", padx=(8, 0))
        self.msg.configure(text="Editing — double-click a row to edit", text_color=T.MUTED)
        focus_later(self.f_name)

    def _cancel(self):
        self._editing_id = None
        self.f_name.delete(0, "end")
        self.f_hsn.delete(0, "end")
        self.f_unit.set("pcs"); self.f_gst.set("18")
        self.f_qty.delete(0, "end"); self.f_qty.insert(0, "0")
        self.save_btn.configure(text="Add Item")
        self.cancel_btn.pack_forget()
        self.msg.configure(text="")
        focus_later(self.f_name)

    def _save(self):
        try:
            if self._editing_id:
                s.update_stock_item(self.con, self._editing_id,
                                    self.f_name.get(), self.f_hsn.get(),
                                    self.f_unit.get(), self.f_gst.get(), self.f_qty.get())
                self.msg.configure(text="Updated", text_color=T.OK)
            else:
                s.add_stock_item(self.con, self.f_name.get(), self.f_hsn.get(),
                                 self.f_unit.get(), self.f_gst.get(), self.f_qty.get())
                self.msg.configure(text="Item added", text_color=T.OK)
            self._cancel()
            self._refresh()
        except ValueError as e:
            self.msg.configure(text=str(e), text_color=T.DANGER)

    def _delete(self, item_id):
        from tkinter import messagebox
        it = self.con.execute("SELECT name FROM stock_items WHERE id=?", (item_id,)).fetchone()
        if not it:
            return
        if not messagebox.askyesno("Delete Item", f"Delete '{it['name']}'?"):
            return
        try:
            s.delete_stock_item(self.con, item_id)
            self._cancel()
            self._refresh()
        except ValueError as e:
            self.msg.configure(text=str(e), text_color=T.DANGER)
