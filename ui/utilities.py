import customtkinter as ctk
from db import setup as s
from ui import theme as T
from utils import settings
from utils.fmt import inr
from ui.widgets import DataTable
from datetime import datetime


def _field(parent, label, widget, row, col=0, span=1):
    ctk.CTkLabel(parent, text=label, font=T.f(12), text_color=T.MUTED).grid(
        row=row, column=col, columnspan=span, sticky="w", padx=20, pady=(14, 2))
    widget.grid(row=row + 1, column=col, columnspan=span, sticky="ew", padx=20)


class CompanyFrame(ctk.CTkFrame):
    def __init__(self, master, on_saved):
        super().__init__(master, fg_color="transparent")
        self.on_saved = on_saved
        T.title(self, "Company Details", "Used on invoices and reports.").pack(
            anchor="w", padx=28, pady=(24, 14))
        card = T.card(self)
        card.pack(anchor="w", padx=28)
        card.grid_columnconfigure((0, 1), weight=1, uniform="c")
        st = settings.load_settings()
        self.w = {}
        spec = [("company_name", "Company name *", 0, 0, 2), ("address", "Address", 2, 0, 2),
                ("gstin", "GSTIN", 4, 0, 1), ("phone", "Phone", 4, 1, 1)]
        for key, label, r, c, span in spec:
            e = T.entry(card, width=420 if span == 2 else 200)
            e.insert(0, st.get(key, ""))
            self.w[key] = e
            _field(card, label, e, r, c, span)
        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.grid(row=6, column=0, columnspan=2, sticky="ew", padx=20, pady=18)
        T.button(bar, "Save", self.save, width=130).pack(side="left")
        self.msg = ctk.CTkLabel(bar, text="", font=T.f(13))
        self.msg.pack(side="left", padx=14)

    def save(self):
        vals = {k: w.get().strip() for k, w in self.w.items()}
        vals["gstin"] = vals["gstin"].upper()
        if not vals["company_name"]:
            self.msg.configure(text="Company name is required", text_color=T.DANGER)
            return
        if vals["gstin"] and not s.GSTIN_RE.match(vals["gstin"]):
            self.msg.configure(text="GSTIN format is invalid", text_color=T.DANGER)
            return
        st = settings.load_settings()
        st.update(vals)
        settings.save_settings(st)
        self.msg.configure(text="Saved", text_color=T.OK)
        self.on_saved()


class PasswordFrame(ctk.CTkFrame):
    def __init__(self, master, con, username):
        super().__init__(master, fg_color="transparent")
        self.con, self.username = con, username
        T.title(self, "Change Password", f"Signed in as {username}.").pack(
            anchor="w", padx=28, pady=(24, 14))
        card = T.card(self)
        card.pack(anchor="w", padx=28)
        self.cur = T.entry(card, "Current password", width=340, show="*")
        self.new = T.entry(card, "New password (min 8 characters)", width=340, show="*")
        self.conf = T.entry(card, "Confirm new password", width=340, show="*")
        for w, pad in ((self.cur, (24, 10)), (self.new, (0, 10)), (self.conf, (0, 6))):
            w.pack(padx=24, pady=pad)
        self.msg = ctk.CTkLabel(card, text="", font=T.f(13), wraplength=340, justify="left")
        self.msg.pack(anchor="w", padx=24, pady=4)
        T.button(card, "Update password", self.save, width=340).pack(padx=24, pady=(6, 24))

    def save(self):
        if not s.login(self.con, self.username, self.cur.get()):
            self.msg.configure(text="Current password is wrong", text_color=T.DANGER)
        elif self.new.get() != self.conf.get():
            self.msg.configure(text="New passwords do not match", text_color=T.DANGER)
        else:
            try:
                s.change_password(self.con, self.username, self.new.get())
            except ValueError as e:
                self.msg.configure(text=str(e), text_color=T.DANGER)
                return
            for w in (self.cur, self.new, self.conf):
                w.delete(0, "end")
            self.msg.configure(text="Password updated", text_color=T.OK)


class AuditFrame(ctk.CTkFrame):
    """Every voucher created, edited or deleted, newest first."""
    def __init__(self, master, con):
        super().__init__(master, fg_color="transparent")
        T.title(self, "Audit Log", "Who created, edited or deleted what. Newest first.").pack(
            anchor="w", padx=28, pady=(24, 12))
        table = DataTable(self, [("at", "When", 150, "w"), ("u", "User", 110, "w"), ("a", "Action", 90, "w"),
                                 ("v", "Voucher", 160, "w"), ("m", "Amount (Rs)", 130, "e")], height=14)
        table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        rows = []
        for e in s.audit_entries(con):
            when = datetime.strptime(e["at"], "%Y-%m-%d %H:%M:%S").strftime("%d-%m-%Y %H:%M")
            rows.append((when, e["user"] or "-", e["action"].capitalize(),
                         f"{e['vtype']} #{e['vno']}", inr(e["amount"])))
        table.set_rows(rows)
