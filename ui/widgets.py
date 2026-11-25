from tkinter import ttk, messagebox
import customtkinter as ctk
from ui import theme as T


class DataTable(ctk.CTkFrame):
    """columns: [(key, heading, width, anchor)].

    empty_text: message shown in the middle of the table when it has no rows.
    """
    DEFAULT_EMPTY = "No entries to show for this selection."

    def __init__(self, master, columns, height=10, empty_text=None):
        super().__init__(master, fg_color=T.CARD, border_width=1,
                         border_color=T.BORDER, corner_radius=14)
        T.style_tree()
        self.tree = ttk.Treeview(self, columns=[c[0] for c in columns],
                                 show="headings", style="Munim.Treeview",
                                 height=height)
        for key, head, width, anchor in columns:
            self.tree.heading(key, text=head, anchor=anchor)
            self.tree.column(key, width=width, anchor=anchor)
        self.tree.tag_configure("odd", background="#F8FAFD")
        self.tree.tag_configure("total", background="#EEF2F8",
                                font=(T.FONT, 11, "bold"))
        self.tree.tag_configure("head", background="#F1F5FB",
                                font=(T.FONT, 11, "bold"))
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview,
                           style="Munim.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        sb.pack(side="right", fill="y", pady=4)

        self.keys = {}
        self._empty = ctk.CTkLabel(self, text=empty_text or self.DEFAULT_EMPTY,
                                   font=T.f(12), text_color=T.MUTED,
                                   fg_color="transparent", justify="center",
                                   wraplength=460)
        self._sync_empty()

    def _sync_empty(self):
        """Show the empty-state message only when the table has no rows."""
        if self.tree.get_children():
            self._empty.place_forget()
        else:
            self._empty.place(relx=0.5, rely=0.55, anchor="center")
            self._empty.lift()

    def set_empty_text(self, text):
        self._empty.configure(text=text)
        self._sync_empty()

    def set_rows(self, rows):
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
        self._sync_empty()

    def selected_key(self):
        sel = self.tree.selection()
        return getattr(self, "keys", {}).get(sel[0]) if sel else None

    def on_open(self, callback):
        self._open_cb = callback
        self.tree.bind("<Double-1>", self.open_selected)
        self.tree.bind("<Return>", self.open_selected)

    def open_selected(self, _e=None):
        sel = self.tree.selection()
        cb = getattr(self, "_open_cb", None)
        if cb and sel and sel[0] in getattr(self, "keys", {}):
            cb(self.keys[sel[0]])


class ErrorPanel(ctk.CTkFrame):
    """Shown instead of a screen that failed to open."""

    def __init__(self, master, text):
        super().__init__(master, fg_color="transparent")
        T.title(self, "This screen hit a problem",
                "Press Esc to go back. Copy the details below and send them "
                "to your developer."
                ).pack(anchor="w", padx=28, pady=(24, 12))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(anchor="w", padx=28, pady=(0, 8))

        def _copy():
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("MUNIM", "Error details copied to clipboard.")

        T.button(bar, "Copy error details", _copy, width=180,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="left")
        box = ctk.CTkTextbox(self, font=("Consolas", 11), fg_color="white",
                             text_color=T.TEXT, border_width=1,
                             border_color=T.BORDER)
        box.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        box.insert("1.0", text)
        box.configure(state="disabled")
