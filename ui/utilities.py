import customtkinter as ctk
from tkinter import messagebox
from db import setup as s
from ui import theme as T
from utils import settings
from utils.fmt import inr
from ui.widgets import DataTable
from datetime import datetime

# Indian state codes from GSTIN first 2 digits
STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana",
    "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh",
    "13": "Nagaland", "14": "Manipur", "15": "Mizoram",
    "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra & Nagar Haveli and Daman & Diu", "27": "Maharashtra",
    "28": "Andhra Pradesh", "29": "Karnataka", "30": "Goa",
    "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman & Nicobar Islands",
    "36": "Telangana", "37": "Andhra Pradesh (New)",
    "38": "Ladakh", "97": "Other Territory",
}
STATE_NAMES = ["-- Select state --"] + sorted(set(STATE_CODES.values()))


def _field(parent, label, widget, row, col=0, span=1):
    ctk.CTkLabel(parent, text=label, font=T.f(12), text_color=T.MUTED).grid(
        row=row, column=col, columnspan=span, sticky="w", padx=20, pady=(14, 2))
    widget.grid(row=row + 1, column=col, columnspan=span, sticky="ew", padx=20)


class CompanyFrame(ctk.CTkFrame):
    def __init__(self, master, on_saved):
        super().__init__(master, fg_color="transparent")
        self.on_saved = on_saved
        T.title(self, "Company Details",
                "Used on invoices and reports. GST registered toggle controls whether tax is charged."
                ).pack(anchor="w", padx=28, pady=(24, 14))
        card = T.card(self)
        card.pack(anchor="w", padx=28)
        card.grid_columnconfigure((0, 1, 2), weight=1, uniform="c")
        st = settings.load_settings()
        self.w = {}

        # Row 0-1: Company name (full width)
        e = T.entry(card, "Your business name", width=560)
        e.insert(0, st.get("company_name", ""))
        self.w["company_name"] = e
        ctk.CTkLabel(card, text="Company name *", font=T.f(12), text_color=T.MUTED).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(14, 2))
        e.grid(row=1, column=0, columnspan=3, sticky="ew", padx=20)

        # Row 2-3: Address (full width)
        addr = T.entry(card, "Street, area, city", width=560)
        addr.insert(0, st.get("address", ""))
        self.w["address"] = addr
        _field(card, "Address", addr, 2, 0, 3)

        # Row 4-5: GSTIN, Phone, State
        gstin_e = T.entry(card, "03ABCDE1234F1Z5", width=200)
        gstin_e.insert(0, st.get("gstin", ""))
        self.w["gstin"] = gstin_e

        phone_e = T.entry(card, "Mobile / landline", width=200)
        phone_e.insert(0, st.get("phone", ""))
        self.w["phone"] = phone_e

        self.state_menu = T.option_menu(card, STATE_NAMES, width=220,
                                        command=lambda _v: None)
        saved_state = st.get("state_name", "-- Select state --")
        self.state_menu.set(saved_state if saved_state in STATE_NAMES else "-- Select state --")

        for c, (h, w) in enumerate((("GSTIN", gstin_e), ("Phone", phone_e), ("State", self.state_menu))):
            ctk.CTkLabel(card, text=h, font=T.f(12), text_color=T.MUTED).grid(
                row=4, column=c, sticky="w", padx=20, pady=(14, 2))
            w.grid(row=5, column=c, padx=20, pady=(0, 4))

        # Row 6-7: GST registered toggle, Invoice prefix, Round-off
        self.gst_reg = ctk.CTkCheckBox(card, text="GST Registered",
                                       font=T.f(13), text_color=T.TEXT,
                                       fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                                       command=self._gst_toggle)
        if st.get("gst_registered", True):
            self.gst_reg.select()

        prefix_e = T.entry(card, "e.g. INV/ or leave blank", width=160)
        prefix_e.insert(0, st.get("invoice_prefix", ""))
        self.w["invoice_prefix"] = prefix_e

        self.roundoff = ctk.CTkCheckBox(card, text="Round off invoices to nearest rupee",
                                        font=T.f(13), text_color=T.TEXT,
                                        fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER)
        if st.get("round_off", False):
            self.roundoff.select()

        self.books_begin = T.entry(card, "e.g. 01-04-2026", width=160)
        self.books_begin.insert(0, st.get("books_begin", ""))

        for c, (h, w) in enumerate((("", self.gst_reg), ("Invoice prefix", prefix_e),
                                     ("Books begin date", self.books_begin))):
            if h:
                ctk.CTkLabel(card, text=h, font=T.f(12), text_color=T.MUTED).grid(
                    row=6, column=c, sticky="w", padx=20, pady=(14, 2))
            else:
                ctk.CTkLabel(card, text=" ", font=T.f(12)).grid(row=6, column=c, sticky="w", padx=20, pady=(14, 2))
            w.grid(row=7, column=c, padx=20, pady=(0, 4), sticky="w")

        self.roundoff.grid(row=8, column=0, columnspan=2, sticky="w", padx=20, pady=(10, 4))

        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.grid(row=9, column=0, columnspan=3, sticky="ew", padx=20, pady=18)
        T.button(bar, "Save", self.save, width=130).pack(side="left")
        self.msg = ctk.CTkLabel(bar, text="", font=T.f(13))
        self.msg.pack(side="left", padx=14)
        self._gst_toggle()

    def _gst_toggle(self):
        """Hide GSTIN and state fields when not GST registered."""
        if self.gst_reg.get():
            self.w["gstin"].configure(state="normal", fg_color="white")
            self.state_menu.configure(state="normal")
        else:
            self.w["gstin"].configure(state="disabled", fg_color="#F0F0F0")
            self.state_menu.configure(state="disabled")

    def save(self):
        vals = {k: w.get().strip() for k, w in self.w.items()}
        vals["gstin"] = vals.get("gstin", "").upper()
        vals["gst_registered"] = bool(self.gst_reg.get())
        vals["state_name"] = self.state_menu.get()
        vals["round_off"] = bool(self.roundoff.get())
        if not vals["company_name"]:
            self.msg.configure(text="Company name is required", text_color=T.DANGER)
            return
        if vals["gst_registered"] and vals["gstin"] and not s.GSTIN_RE.match(vals["gstin"]):
            self.msg.configure(text="GSTIN format is invalid", text_color=T.DANGER)
            return
        # Auto-fill state from GSTIN if not manually selected
        if vals["gst_registered"] and vals["gstin"] and len(vals["gstin"]) >= 2:
            code = vals["gstin"][:2]
            if code in STATE_CODES and vals["state_name"] == "-- Select state --":
                vals["state_name"] = STATE_CODES[code]
                self.state_menu.set(vals["state_name"])
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
        self.cur  = T.entry(card, "Current password", width=340, show="*")
        self.new  = T.entry(card, "New password (min 8 characters)", width=340, show="*")
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
        T.title(self, "Audit Log",
                "Who created, edited or deleted what. Newest first."
                ).pack(anchor="w", padx=28, pady=(24, 12))
        table = DataTable(self, [("at", "When", 150, "w"), ("u", "User", 110, "w"),
                                  ("a", "Action", 90, "w"), ("v", "Voucher", 160, "w"),
                                  ("m", "Amount (Rs)", 130, "e")], height=14)
        table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        rows = []
        for e in s.audit_entries(con):
            when = datetime.strptime(e["at"], "%Y-%m-%d %H:%M:%S").strftime("%d-%m-%Y %H:%M")
            rows.append((when, e["user"] or "-", e["action"].capitalize(),
                         f"{e['vtype']} #{e['vno']}", inr(e["amount"])))
        table.set_rows(rows)


class ResetDataFrame(ctk.CTkFrame):
    """Wipe all business data — vouchers, parties, accounts. Keeps logins."""
    def __init__(self, master, con):
        super().__init__(master, fg_color="transparent")
        self.con = con
        T.title(self, "Reset / Clear All Data",
                "Deletes all vouchers, parties and accounts. Keeps your login. Cannot be undone."
                ).pack(anchor="w", padx=28, pady=(24, 12))
        card = T.card(self)
        card.pack(anchor="w", padx=28)

        ctk.CTkLabel(card, text="⚠  This will permanently delete all your business data.",
                     font=T.f(14, "bold"), text_color=T.DANGER).pack(anchor="w", padx=24, pady=(20, 4))
        ctk.CTkLabel(card,
                     text="All vouchers, parties and ledger accounts will be removed.\n"
                          "Your login password will NOT change.\n"
                          "Take a Backup first if you want to keep a copy.",
                     font=T.f(13), text_color=T.TEXT, justify="left").pack(anchor="w", padx=24, pady=(0, 16))

        ctk.CTkLabel(card, text="Enter admin password to confirm:", font=T.f(13),
                     text_color=T.MUTED).pack(anchor="w", padx=24)
        self.pw = T.entry(card, "Admin password", width=300, show="*")
        self.pw.pack(anchor="w", padx=24, pady=(6, 4))
        self.msg = ctk.CTkLabel(card, text="", font=T.f(13), text_color=T.DANGER, wraplength=400)
        self.msg.pack(anchor="w", padx=24, pady=4)

        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.pack(fill="x", padx=24, pady=(4, 20))
        T.button(bar, "DELETE ALL DATA", self.reset, width=200,
                 fg_color=T.DANGER, hover_color="#A32F23").pack(side="left")

    def reset(self):
        pw = self.pw.get()
        if not pw:
            self.msg.configure(text="Enter your admin password first")
            return
        if not messagebox.askyesno(
                "Delete all data",
                "This will permanently delete ALL vouchers, parties and accounts.\n\n"
                "This cannot be undone. Are you absolutely sure?"):
            return
        try:
            s.reset_all_data(self.con, pw)
        except ValueError as e:
            self.msg.configure(text=str(e))
            return
        # Also clear settings data fields
        st = settings.load_settings()
        for k in ("last_backup",):
            st.pop(k, None)
        settings.save_settings(st)
        messagebox.showinfo("MUNIM", "All data has been cleared.\nThe app will now restart.")
        self.winfo_toplevel().destroy()