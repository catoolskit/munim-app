"""MUNIM Pro — F4 picker: choose a Deductor / GST Client / Assessee."""
import customtkinter as ctk

from ui import theme as T
from ui.ux import inner, focus_later
from ui.widgets import DataTable
from db import pro_db

LABELS = {
    "tds": ("Deductor", "TAN"),
    "gst": ("GST Client", "GSTIN"),
    "tax": ("Assessee", "PAN"),
}
_SKIP = {"Return", "Up", "Down", "Escape", "Tab"}


class EntityPicker(ctk.CTkToplevel):
    def __init__(self, master, con, module, on_pick):
        super().__init__(master)
        noun, key = LABELS[module]
        self.con, self.module, self.on_pick = con, module, on_pick
        self.rows = {}
        self.title(f"Select {noun}")
        self.geometry("660x480")
        self.configure(fg_color=T.BG)
        self.transient(master.winfo_toplevel())

        T.title(self, f"Select {noun}",
                f"Type to search by name, {key} or city. Enter to pick, Esc to close."
                ).pack(anchor="w", padx=22, pady=(18, 10))
        self.search = T.entry(self, f"Search {noun.lower()}…")
        self.search.pack(fill="x", padx=22, pady=(0, 10))
        self.table = DataTable(
            self, [("name", "Name", 320, "w"), ("key", key, 140, "w"),
                   ("city", "City", 140, "w")],
            height=10,
            empty_text=f"No {noun.lower()}s found.\nAdd one from Masters → {noun} Master.")
        self.table.pack(fill="both", expand=True, padx=22, pady=(0, 20))
        self.table.on_open(self._pick)

        e = inner(self.search)
        e.bind("<KeyRelease>", self._on_key)
        e.bind("<Return>", self._focus_table)
        e.bind("<Down>", self._focus_table)
        self.bind("<Escape>", lambda _e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.refresh()
        focus_later(self.search)
        self.after(150, self._grab)

    def _grab(self):
        try:
            self.grab_set()
        except Exception:
            pass

    def _on_key(self, event):
        if event.keysym not in _SKIP:
            self.refresh()

    def refresh(self):
        rows = pro_db.search_entities(self.con, self.module, self.search.get())
        self.rows = {r["id"]: dict(r) for r in rows}
        self.table.set_rows([((r["name"], r["key"], r["city"] or ""), None, r["id"])
                             for r in rows])

    def _focus_table(self, _e=None):
        kids = self.table.tree.get_children()
        if kids:
            self.table.tree.selection_set(kids[0])
            self.table.tree.focus(kids[0])
            self.table.tree.focus_set()
        return "break"

    def _pick(self, rid):
        row = self.rows.get(rid)
        self.close()
        if row:
            self.on_pick(row)

    def close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()