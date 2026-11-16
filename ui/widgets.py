from tkinter import ttk
import customtkinter as ctk
from ui import theme as T


class DataTable(ctk.CTkFrame):
    """columns: [(key, heading, width, anchor)]. Rows: tuples, or (tuple, tag) with tag 'total'/'head'."""
    def __init__(self, master, columns, height=10):
        super().__init__(master, fg_color=T.CARD, border_width=1, border_color=T.BORDER,
                         corner_radius=12)
        T.style_tree()
        self.tree = ttk.Treeview(self, columns=[c[0] for c in columns], show="headings",
                                 style="Munim.Treeview", height=height)
        for key, head, width, anchor in columns:
            self.tree.heading(key, text=head, anchor=anchor)
            self.tree.column(key, width=width, anchor=anchor)
        self.tree.tag_configure("odd", background="#F8FAFD")
        self.tree.tag_configure("total", background="#EEF2F8", font=(T.FONT, 11, "bold"))
        self.tree.tag_configure("head", background="#F1F5FB", font=(T.FONT, 11, "bold"))
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview,
                           style="Munim.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
        sb.pack(side="right", fill="y", pady=2)

    def set_rows(self, rows):
        """Row forms: (values) | ((values), tag) | ((values), tag, key). Key marks an openable row."""
        self.tree.delete(*self.tree.get_children())
        self.keys = {}
        for i, row in enumerate(rows):
            if isinstance(row[0], tuple):
                values, tag = row[0], row[1]
                key = row[2] if len(row) > 2 else None
            else:
                values, tag, key = row, None, None
            tags = (tag,) if tag else (("odd",) if i % 2 else ())
            iid = self.tree.insert("", "end", values=values, tags=tags)
            if key is not None:
                self.keys[iid] = key

    def on_open(self, callback):
        """Double-click or Enter on a row that has a key calls callback(key)."""
        self._open_cb = callback
        self.tree.bind("<Double-1>", self.open_selected)
        self.tree.bind("<Return>", self.open_selected)

    def open_selected(self, _e=None):
        sel = self.tree.selection()
        cb = getattr(self, "_open_cb", None)
        if cb and sel and sel[0] in getattr(self, "keys", {}):
            cb(self.keys[sel[0]])


class ErrorPanel(ctk.CTkFrame):
    """Shown instead of a screen that failed to open, so the app keeps running."""
    def __init__(self, master, text):
        super().__init__(master, fg_color="transparent")
        T.title(self, "This screen hit a problem",
                "The details were saved to error.log. Press Esc to go back, and send these details to your developer."
                ).pack(anchor="w", padx=28, pady=(24, 12))
        box = ctk.CTkTextbox(self, font=("Consolas", 11), fg_color="white", text_color=T.TEXT,
                             border_width=1, border_color=T.BORDER)
        box.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        box.insert("1.0", text)
        box.configure(state="disabled")
