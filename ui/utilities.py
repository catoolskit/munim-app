import customtkinter as ctk
from tkinter import messagebox
from db import setup as s
from ui import theme as T
from utils import settings
from utils.fmt import inr
from ui.widgets import DataTable
from datetime import datetime, date
from utils.licence import validate_key, licence_status, days_remaining

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

        e = T.entry(card, "Your business name", width=560)
        e.insert(0, st.get("company_name", ""))
        self.w["company_name"] = e
        ctk.CTkLabel(card, text="Company name *", font=T.f(12),
                     text_color=T.MUTED).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(14, 2))
        e.grid(row=1, column=0, columnspan=3, sticky="ew", padx=20)

        addr = T.entry(card, "Street, area, city", width=560)
        addr.insert(0, st.get("address", ""))
        self.w["address"] = addr
        _field(card, "Address", addr, 2, 0, 3)

        gstin_e = T.entry(card, "03ABCDE1234F1Z5", width=200)
        gstin_e.insert(0, st.get("gstin", ""))
        self.w["gstin"] = gstin_e

        phone_e = T.entry(card, "Mobile / landline", width=200)
        phone_e.insert(0, st.get("phone", ""))
        self.w["phone"] = phone_e

        self.state_menu = T.option_menu(card, STATE_NAMES, width=220,
                                        command=lambda _v: None)
        saved_state = st.get("state_name", "-- Select state --")
        self.state_menu.set(saved_state if saved_state in STATE_NAMES
                            else "-- Select state --")

        for c, (h, w) in enumerate((("GSTIN", gstin_e), ("Phone", phone_e),
                                     ("State", self.state_menu))):
            ctk.CTkLabel(card, text=h, font=T.f(12), text_color=T.MUTED).grid(
                row=4, column=c, sticky="w", padx=20, pady=(14, 2))
            w.grid(row=5, column=c, padx=20, pady=(0, 4))

        self.gst_reg = ctk.CTkCheckBox(
            card, text="GST Registered", font=T.f(13), text_color=T.TEXT,
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            command=self._gst_toggle)
        if st.get("gst_registered", True):
            self.gst_reg.select()

        prefix_e = T.entry(card, "e.g. INV/ or leave blank", width=160)
        prefix_e.insert(0, st.get("invoice_prefix", ""))
        self.w["invoice_prefix"] = prefix_e

        self.roundoff = ctk.CTkCheckBox(
            card, text="Round off invoices to nearest rupee",
            font=T.f(13), text_color=T.TEXT,
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER)
        if st.get("round_off", False):
            self.roundoff.select()

        self.books_begin = T.entry(card, "e.g. 01-04-2026", width=160)
        self.books_begin.insert(0, st.get("books_begin", ""))

        for c, (h, w) in enumerate((("", self.gst_reg),
                                     ("Invoice prefix", prefix_e),
                                     ("Books begin date", self.books_begin))):
            if h:
                ctk.CTkLabel(card, text=h, font=T.f(12), text_color=T.MUTED).grid(
                    row=6, column=c, sticky="w", padx=20, pady=(14, 2))
            else:
                ctk.CTkLabel(card, text=" ", font=T.f(12)).grid(
                    row=6, column=c, sticky="w", padx=20, pady=(14, 2))
            w.grid(row=7, column=c, padx=20, pady=(0, 4), sticky="w")

        self.roundoff.grid(row=8, column=0, columnspan=2, sticky="w",
                           padx=20, pady=(10, 4))

        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.grid(row=9, column=0, columnspan=3, sticky="ew", padx=20, pady=18)
        T.button(bar, "Save", self.save, width=130).pack(side="left")
        self.msg = ctk.CTkLabel(bar, text="", font=T.f(13))
        self.msg.pack(side="left", padx=14)
        self._gst_toggle()

    def _gst_toggle(self):
        if self.gst_reg.get():
            self.w["gstin"].configure(state="normal", fg_color="white")
            self.state_menu.configure(state="normal")
        else:
            self.w["gstin"].configure(state="disabled", fg_color="#F0F0F0")
            self.state_menu.configure(state="disabled")

    def save(self):
        vals = {k: w.get().strip() for k, w in self.w.items()}
        vals["gstin"]          = vals.get("gstin", "").upper()
        vals["gst_registered"] = bool(self.gst_reg.get())
        vals["state_name"]     = self.state_menu.get()
        vals["round_off"]      = bool(self.roundoff.get())
        vals["books_begin"]    = self.books_begin.get().strip()
        if not vals["company_name"]:
            self.msg.configure(text="Company name is required", text_color=T.DANGER)
            return
        if vals["gst_registered"] and vals["gstin"] and not s.GSTIN_RE.match(vals["gstin"]):
            self.msg.configure(text="GSTIN format is invalid", text_color=T.DANGER)
            return
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
        self.cur  = T.entry(card, "Current password",                width=340, show="*")
        self.new  = T.entry(card, "New password (min 8 characters)", width=340, show="*")
        self.conf = T.entry(card, "Confirm new password",            width=340, show="*")
        for w, pad in ((self.cur, (24, 10)), (self.new, (0, 10)), (self.conf, (0, 6))):
            w.pack(padx=24, pady=pad)
        self.msg = ctk.CTkLabel(card, text="", font=T.f(13),
                                wraplength=340, justify="left")
        self.msg.pack(anchor="w", padx=24, pady=4)
        T.button(card, "Update password", self.save, width=340).pack(
            padx=24, pady=(6, 24))

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
    def __init__(self, master, con, opener=None):
        super().__init__(master, fg_color="transparent")
        self.con     = con
        self.opener  = opener
        T.title(self, "Audit Log",
                "Who created, edited or deleted what. Filter by type and date range."
                ).pack(anchor="w", padx=28, pady=(24, 12))

        ctrl  = T.card(self)
        ctrl.pack(fill="x", padx=28, pady=(0, 10))
        today = date.today()

        self.vtype_filter = T.option_menu(
            ctrl, ["All types", "Sales", "Purchase", "Journal",
                   "Receipt", "Payment", "Contra"], width=150)
        self.action_filter = T.option_menu(
            ctrl, ["All actions", "create", "edit", "delete"], width=130)
        self.d1 = T.entry(ctrl, width=120)
        self.d1.insert(0, today.replace(day=1).strftime("%d-%m-%Y"))
        self.d2 = T.entry(ctrl, width=120)
        self.d2.insert(0, today.strftime("%d-%m-%Y"))

        for c, (label, w) in enumerate((
            ("Voucher type", self.vtype_filter),
            ("Action",       self.action_filter),
            ("From date",    self.d1),
            ("To date",      self.d2),
        )):
            ctk.CTkLabel(ctrl, text=label, font=T.f(12), text_color=T.MUTED).grid(
                row=0, column=c, sticky="w",
                padx=(20 if c == 0 else 10, 10), pady=(12, 2))
            w.grid(row=1, column=c,
                   padx=(20 if c == 0 else 10, 10), pady=(0, 14))

        T.button(ctrl, "Show", self.refresh, width=80).grid(
            row=1, column=4, padx=10, pady=(0, 14))

        self.table = DataTable(self, [
            ("at", "When",        150, "w"),
            ("u",  "User",        110, "w"),
            ("a",  "Action",       90, "w"),
            ("v",  "Voucher",     160, "w"),
            ("m",  "Amount (Rs)", 130, "e"),
            ("ch", "Change",      200, "w"),
        ], height=12)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        if opener:
            self.table.on_open(lambda vid: opener(vid, self.refresh))
        self.refresh()

    def refresh(self):
        import json
        from utils.fmt import parse_date as pd

        try:
            d1 = pd(self.d1.get())
            d2 = pd(self.d2.get())
        except ValueError:
            return

        vtype_f  = self.vtype_filter.get()
        action_f = self.action_filter.get()

        rows_raw = self.con.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT 500"
        ).fetchall()

        rows = []
        for e in rows_raw:
            try:
                entry_date = date.fromisoformat(e["at"][:10])
                if not (d1 <= entry_date <= d2):
                    continue
            except Exception:
                continue
            if vtype_f  != "All types"   and e["vtype"]  != vtype_f:
                continue
            if action_f != "All actions" and e["action"] != action_f:
                continue

            change = ""
            try:
                import json as _json
                d      = _json.loads(e["detail"] or "{}")
                before = d.get("before")
                after  = d.get("after")
                if e["action"] == "edit" and before and after:
                    b_total = sum(l["dr"] for l in before.get("lines", []))
                    a_total = sum(l["dr"] for l in after.get("lines",  []))
                    if b_total != a_total:
                        from db.setup import to_rupees
                        change = (f"Amount: {to_rupees(b_total):,.2f} → "
                                  f"{to_rupees(a_total):,.2f}")
                    else:
                        change = "Details changed"
                elif e["action"] == "delete":
                    change = "Permanently deleted"
                elif e["action"] == "create":
                    change = "Created"
            except Exception:
                pass

            import json as _json2
            snap  = _json2.loads(e["detail"] or "{}")
            ref   = (snap.get("after") or snap.get("before") or {})
            total = sum(l["dr"] for l in ref.get("lines", []))
            from db.setup import to_rupees
            from utils.fmt import inr as _inr

            vid = None
            if e["vtype"] and e["vno"] and e["action"] != "delete":
                try:
                    r = self.con.execute(
                        "SELECT id FROM vouchers WHERE vtype=? AND vno=? AND fy=?",
                        (e["vtype"], e["vno"], e["fy"])).fetchone()
                    if r:
                        vid = r["id"]
                except Exception:
                    pass

            when = datetime.strptime(
                e["at"], "%Y-%m-%d %H:%M:%S").strftime("%d-%m-%Y %H:%M")
            row_data = (when, e["username"] or "-",
                        e["action"].capitalize(),
                        f"{e['vtype']} #{e['vno']}" if e["vtype"] else "-",
                        _inr(to_rupees(total)),
                        change)
            if vid:
                rows.append((row_data, None, vid))
            else:
                rows.append(row_data)
        self.table.set_rows(rows)


class ResetDataFrame(ctk.CTkFrame):
    def __init__(self, master, con, on_done=None):
        super().__init__(master, fg_color="transparent")
        self.con     = con
        self.on_done = on_done
        T.title(self, "Reset / Clear All Data",
                "Deletes all vouchers, parties and accounts. Keeps your login. Cannot be undone."
                ).pack(anchor="w", padx=28, pady=(24, 12))
        card = T.card(self)
        card.pack(anchor="w", padx=28)

        ctk.CTkLabel(card,
                     text="⚠  This will permanently delete all your business data.",
                     font=T.f(14, "bold"), text_color=T.DANGER).pack(
            anchor="w", padx=24, pady=(20, 4))
        ctk.CTkLabel(card,
                     text="All vouchers, parties and ledger accounts will be removed.\n"
                          "Your login password will NOT change.\n"
                          "Take a Backup first if you want to keep a copy.",
                     font=T.f(13), text_color=T.TEXT, justify="left").pack(
            anchor="w", padx=24, pady=(0, 16))

        ctk.CTkLabel(card, text="Enter admin password to confirm:",
                     font=T.f(13), text_color=T.MUTED).pack(anchor="w", padx=24)
        self.pw = T.entry(card, "Admin password", width=300, show="*")
        self.pw.pack(anchor="w", padx=24, pady=(6, 4))
        self.msg = ctk.CTkLabel(card, text="", font=T.f(13),
                                text_color=T.DANGER, wraplength=400)
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
        st = settings.load_settings()
        for k in ("last_backup",):
            st.pop(k, None)
        settings.save_settings(st)
        messagebox.showinfo("MUNIM", "All data has been cleared.")
        if self.on_done:
            self.on_done()


class RenewLicenceFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        st          = settings.load_settings()
        current_key = st.get("licence_key", "")
        status      = licence_status(current_key)
        days        = days_remaining(current_key)

        T.title(self, "Renew Licence",
                "Enter a new licence key to extend your subscription.").pack(
            anchor="w", padx=28, pady=(24, 14))

        card = T.card(self)
        card.pack(anchor="w", padx=28)
        card.grid_columnconfigure(0, weight=1)

        status_color = T.DANGER if days <= 7 else T.OK
        ctk.CTkLabel(card, text="Current licence status", font=T.f(12),
                     text_color=T.MUTED).grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 2))
        ctk.CTkLabel(card, text=status, font=T.f(14, "bold"),
                     text_color=status_color).grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 14))

        ctk.CTkLabel(card, text="New licence key", font=T.f(12),
                     text_color=T.MUTED).grid(
            row=2, column=0, sticky="w", padx=20, pady=(4, 2))
        self.key_entry = T.entry(card, "MNM-…", width=500)
        self.key_entry.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 4))

        self.msg = ctk.CTkLabel(card, text="", font=T.f(13),
                                wraplength=480, justify="left")
        self.msg.grid(row=4, column=0, sticky="w", padx=20, pady=(4, 4))

        T.button(card, "Activate new key", self._activate, width=200).grid(
            row=5, column=0, sticky="w", padx=20, pady=(6, 24))

    def _activate(self):
        key = self.key_entry.get().strip()
        if not key:
            self.msg.configure(text="Please enter a licence key.",
                               text_color=T.DANGER)
            return
        try:
            username, expiry = validate_key(key)
        except ValueError as e:
            self.msg.configure(text=str(e), text_color=T.DANGER)
            return
        st = settings.load_settings()
        st["licence_key"] = key
        settings.save_settings(st)
        self.msg.configure(
            text=f"✓  Licence activated for {username}. "
                 f"Valid until {expiry.strftime('%d-%m-%Y')}.",
            text_color=T.OK)
        self.key_entry.delete(0, "end")


class ManageCompaniesFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        from db.setup import list_companies
        from utils.settings import get_active_company
        self._active = get_active_company()
        T.title(self, "Manage Companies",
                "Rename or delete companies. The currently open company cannot be deleted.").pack(
            anchor="w", padx=28, pady=(24, 12))
        self.card = T.card(self)
        self.card.pack(fill="x", padx=28)
        self.msg = ctk.CTkLabel(self, text="", font=T.f(12), text_color=T.DANGER)
        self.msg.pack(anchor="w", padx=28, pady=(8, 0))
        self._refresh()

    def _refresh(self):
        from db.setup import list_companies
        for w in self.card.winfo_children():
            w.destroy()
        companies = list_companies()
        if not companies:
            ctk.CTkLabel(self.card, text="No companies found.",
                         font=T.f(13), text_color=T.MUTED).pack(padx=24, pady=16)
            return
        for co in companies:
            row = ctk.CTkFrame(self.card, fg_color="#EEF2FA", corner_radius=8)
            row.pack(fill="x", padx=16, pady=4)
            is_active = co["name"] == self._active
            ctk.CTkLabel(row,
                         text=co["name"] + (" (current)" if is_active else ""),
                         font=T.f(13, "bold" if is_active else "normal"),
                         text_color=T.ACCENT if is_active else T.TEXT,
                         anchor="w").pack(side="left", padx=14, pady=10)
            if not is_active:
                T.button(row, "Delete", lambda n=co["name"]: self._delete(n),
                         width=70, height=28,
                         fg_color="#FDECEA", text_color=T.DANGER,
                         hover_color="#FAD7D3").pack(side="right", padx=6, pady=6)
            T.button(row, "Rename", lambda n=co["name"]: self._rename(n),
                     width=70, height=28).pack(side="right", padx=6, pady=6)

    def _rename(self, name):
        from tkinter import simpledialog
        from db.setup import rename_company
        new = simpledialog.askstring(
            "Rename Company", f"New name for '{name}':",
            initialvalue=name, parent=self.winfo_toplevel())
        if not new or new.strip() == name:
            return
        try:
            rename_company(name, new.strip())
            self.msg.configure(text=f"Renamed to '{new.strip()}'", text_color=T.OK)
            self._refresh()
        except ValueError as e:
            self.msg.configure(text=str(e), text_color=T.DANGER)

    def _delete(self, name):
        from db.setup import delete_company
        if not messagebox.askyesno(
                "Delete Company",
                f"Permanently delete '{name}' and all its data?\n\n"
                "This cannot be undone."):
            return
        try:
            delete_company(name)
            self.msg.configure(text=f"'{name}' deleted.", text_color=T.OK)
            self._refresh()
        except ValueError as e:
            self.msg.configure(text=str(e), text_color=T.DANGER)


class DataLocationFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        from db.setup import data_dir
        import os
        self._current = data_dir()
        self._default = (r"C:\MUNIM" if os.name == "nt"
                         else os.path.join(os.path.expanduser("~"), "MUNIM"))
        self._pointer = os.path.join(self._default, "data_location.txt")

        T.title(self, "Data Location",
                "Move your MUNIM data folder to a new drive or folder.").pack(
            anchor="w", padx=28, pady=(24, 12))

        card = T.card(self)
        card.pack(fill="x", padx=28, pady=(0, 16))

        ctk.CTkLabel(card, text="Current data location",
                     font=T.f(12), text_color=T.MUTED).pack(
            anchor="w", padx=24, pady=(18, 2))
        self.current_lbl = ctk.CTkLabel(
            card, text=self._current, font=T.f(13, "bold"),
            text_color=T.TEXT, wraplength=700, justify="left")
        self.current_lbl.pack(anchor="w", padx=24, pady=(0, 16))

        ctk.CTkLabel(
            card,
            text="New location (choose a folder — a MUNIM subfolder will be created inside it)",
            font=T.f(12), text_color=T.MUTED).pack(anchor="w", padx=24, pady=(0, 4))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(0, 18))
        self.path_entry = T.entry(row, width=500)
        self.path_entry.pack(side="left", padx=(0, 10))
        T.button(row, "Browse…", self._browse, width=100).pack(side="left")

        self.msg = ctk.CTkLabel(card, text="", font=T.f(12),
                                text_color=T.DANGER, wraplength=700)
        self.msg.pack(anchor="w", padx=24, pady=(0, 4))

        T.button(card, "Move Data", self._move, width=140).pack(
            anchor="w", padx=24, pady=(0, 18))

    def _browse(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(
            title="Choose a parent folder for MUNIM data")
        if folder:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder)

    def _move(self):
        import shutil, os
        dest_parent = self.path_entry.get().strip()
        if not dest_parent:
            self.msg.configure(
                text="Please choose a destination folder first.",
                text_color=T.DANGER)
            return
        if not os.path.isdir(dest_parent):
            self.msg.configure(
                text="That folder does not exist. Please choose an existing folder.",
                text_color=T.DANGER)
            return
        dest    = os.path.join(dest_parent, "MUNIM")
        current = self._current
        if os.path.normcase(dest) == os.path.normcase(current):
            self.msg.configure(text="Data is already at that location.",
                               text_color=T.MUTED)
            return
        if not messagebox.askyesno(
                "Move Data",
                f"MUNIM will copy all data to:\n\n{dest}\n\n"
                "Then delete the old location.\n\n"
                "Make sure you have a backup first! Continue?"):
            return
        try:
            if os.path.exists(dest):
                messagebox.showerror(
                    "MUNIM",
                    f"Folder already exists:\n{dest}\n\n"
                    "Choose a different location or rename it.")
                return
            shutil.copytree(current, dest)
            os.makedirs(self._default, exist_ok=True)
            with open(self._pointer, "w", encoding="utf-8") as f:
                f.write(dest)
            if os.path.normcase(current) != os.path.normcase(self._default):
                shutil.rmtree(current, ignore_errors=True)
            messagebox.showinfo(
                "MUNIM",
                f"Data moved to:\n{dest}\n\nRestart MUNIM to use the new location.")
            self.current_lbl.configure(text=dest)
            self.msg.configure(text="Done! Please restart MUNIM.", text_color=T.OK)
        except Exception as e:
            self.msg.configure(text=f"Error: {e}", text_color=T.DANGER)


# ── NEW v0.17: Tally Import ───────────────────────────────────────────────────

class TallyImportFrame(ctk.CTkFrame):
    """Utilities → Import from Tally.
    Reads a Tally XML export and imports parties + ledger accounts
    with opening balances (Masters only).
    """

    def __init__(self, master, con):
        super().__init__(master, fg_color="transparent")
        self.con = con

        T.title(self, "Import from Tally",
                "Import your parties and ledger accounts from a Tally XML export. "
                "Historical vouchers are not imported — you start entering new "
                "transactions in MUNIM."
                ).pack(anchor="w", padx=28, pady=(24, 14))

        # How-to card
        how = T.card(self)
        how.pack(fill="x", padx=28, pady=(0, 14))
        ctk.CTkLabel(how, text="How to export from Tally",
                     font=T.f(13, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=20, pady=(14, 6))
        for step in [
            "1.  Open Tally and select your company.",
            "2.  Go to Gateway of Tally > Export Data.",
            "3.  Choose Masters > XML format.",
            "4.  Save the file and select it below.",
        ]:
            ctk.CTkLabel(how, text=step, font=T.f(12), text_color=T.MUTED,
                         anchor="w").pack(anchor="w", padx=20, pady=1)
        ctk.CTkFrame(how, fg_color=T.CARD, height=12).pack()

        # File picker
        file_card = T.card(self)
        file_card.pack(fill="x", padx=28, pady=(0, 14))
        ctk.CTkLabel(file_card, text="Tally XML file",
                     font=T.f(12), text_color=T.MUTED).pack(
            anchor="w", padx=20, pady=(14, 4))
        row = ctk.CTkFrame(file_card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 14))
        self.path_entry = T.entry(row, "Select file…", width=460)
        self.path_entry.pack(side="left", padx=(0, 10))
        T.button(row, "Browse…", self._browse, width=100).pack(side="left")

        # Import button
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(anchor="w", padx=28, pady=(0, 10))
        T.button(btn_row, "Import Masters", self._import, width=160).pack(side="left")
        self.msg = ctk.CTkLabel(btn_row, text="", font=T.f(13))
        self.msg.pack(side="left", padx=14)

        # Results area
        self.results = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                              height=300)
        self.results.pack(fill="both", expand=True, padx=28, pady=(0, 16))

    def _browse(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select Tally XML export",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")])
        if path:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, path)

    def _import(self):
        from utils.tally_import import parse_tally_xml, import_masters

        path = self.path_entry.get().strip()
        if not path:
            self.msg.configure(text="Choose a file first.", text_color=T.DANGER)
            return

        import os
        if not os.path.exists(path):
            self.msg.configure(text="File not found.", text_color=T.DANGER)
            return

        for w in self.results.winfo_children():
            w.destroy()

        self.msg.configure(text="Reading file…", text_color=T.MUTED)
        self.update()

        try:
            data   = parse_tally_xml(path)
            result = import_masters(self.con, data)
        except Exception as e:
            self.msg.configure(text=f"Error: {e}", text_color=T.DANGER)
            return

        pa = result["parties_added"]
        aa = result["accounts_added"]
        self.msg.configure(
            text=f"Done — {pa} parties, {aa} accounts imported.",
            text_color=T.OK)

        def _section(title, items, color):
            if not items:
                return
            ctk.CTkLabel(self.results, text=title,
                         font=T.f(13, "bold"), text_color=color).pack(
                anchor="w", pady=(10, 2))
            for item in items:
                ctk.CTkLabel(self.results, text=f"  • {item}",
                             font=T.f(12), text_color=T.TEXT,
                             anchor="w", wraplength=700).pack(anchor="w", pady=1)

        _section(f"✓  Imported ({pa + aa})",
                 ([f"{pa} parties (customers/suppliers)",
                   f"{aa} ledger accounts"] if (pa + aa) else []),
                 T.OK)
        _section("⚠  Skipped", result["skipped"], T.MUTED)
        _section("✗  Errors",  result["errors"],  T.DANGER)

        if result["errors"]:
            self.msg.configure(
                text=f"Done with {len(result['errors'])} errors — see below.",
                text_color="#B26A00")

# ── NEW v0.18: Mobile Config Export ──────────────────────────────────────────

class MobileExportFrame(ctk.CTkFrame):
    """Utilities → Export Mobile Config.
    Creates a JSON file the mobile APK reads to know your company,
    parties and stock items."""

    def __init__(self, master, con):
        super().__init__(master, fg_color="transparent")
        self.con = con

        T.title(self, "Export Mobile Config",
                "Create a config file for the MUNIM mobile app. "
                "Send this file to your phone once — the app reads your company, "
                "parties and stock items from it."
                ).pack(anchor="w", padx=28, pady=(24, 14))

        how = T.card(self)
        how.pack(fill="x", padx=28, pady=(0, 14))
        ctk.CTkLabel(how, text="How to set up the mobile app",
                     font=T.f(13, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=20, pady=(14, 6))
        for step in [
            "1.  Click Export Config below — saves a munim_config.json file.",
            "2.  Send that file to your phone via WhatsApp or USB.",
            "3.  Open the MUNIM mobile app and import the config file.",
            "4.  The app now knows your company, parties and items.",
            "5.  After creating invoices on mobile, export an invoices JSON.",
            "6.  Come back here → Import Mobile Invoices to bring them in.",
        ]:
            ctk.CTkLabel(how, text=step, font=T.f(12), text_color=T.MUTED,
                         anchor="w").pack(anchor="w", padx=20, pady=1)
        ctk.CTkFrame(how, fg_color=T.CARD, height=12).pack()

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(anchor="w", padx=28, pady=(0, 14))
        T.button(btn_row, "Export Config", self._export, width=160).pack(side="left")
        self.msg = ctk.CTkLabel(btn_row, text="", font=T.f(13))
        self.msg.pack(side="left", padx=14)

        # Info card
        info = T.card(self)
        info.pack(fill="x", padx=28, pady=(0, 16))
        st = settings.load_settings()
        parties_count = con.execute("SELECT COUNT(*) FROM parties").fetchone()[0]
        items_count   = con.execute("SELECT COUNT(*) FROM stock_items").fetchone()[0]
        for label, value in [
            ("Company",      st.get("company_name", "Not set")),
            ("Parties",      f"{parties_count} active"),
            ("Stock items",  f"{items_count} items"),
            ("Financial year", s.fy_of(date.today())),
        ]:
            row = ctk.CTkFrame(info, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(row, text=label + ":", font=T.f(12),
                         text_color=T.MUTED, width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, font=T.f(12, "bold"),
                         text_color=T.TEXT).pack(side="left")
        ctk.CTkFrame(info, fg_color=T.CARD, height=8).pack()

    def _export(self):
        from tkinter import filedialog
        from utils.mobile_export import export_mobile_config
        st = settings.load_settings()
        company = st.get("company_name", "company").replace(" ", "_")
        path = filedialog.asksaveasfilename(
            title="Save Mobile Config",
            initialfile=f"munim_config_{company}.json",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=s.data_dir())
        if not path:
            return
        try:
            export_mobile_config(self.con, path)
            self.msg.configure(
                text=f"✓ Saved — send this file to your phone",
                text_color=T.OK)
        except Exception as e:
            self.msg.configure(text=f"Error: {e}", text_color=T.DANGER)


class MobileImportFrame(ctk.CTkFrame):
    """Utilities → Import Mobile Invoices.
    Reads a JSON file from the mobile APK and creates Sales invoices."""

    def __init__(self, master, con):
        super().__init__(master, fg_color="transparent")
        self.con = con

        T.title(self, "Import Mobile Invoices",
                "Import sales invoices created on the MUNIM mobile app. "
                "New parties are created automatically. Duplicates are skipped."
                ).pack(anchor="w", padx=28, pady=(24, 14))

        file_card = T.card(self)
        file_card.pack(fill="x", padx=28, pady=(0, 14))
        ctk.CTkLabel(file_card, text="Mobile invoices JSON file",
                     font=T.f(12), text_color=T.MUTED).pack(
            anchor="w", padx=20, pady=(14, 4))
        row = ctk.CTkFrame(file_card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 14))
        self.path_entry = T.entry(row, "Select file…", width=460)
        self.path_entry.pack(side="left", padx=(0, 10))
        T.button(row, "Browse…", self._browse, width=100).pack(side="left")

        # Preview area
        self.preview_card = T.card(self)
        self.preview_card.pack(fill="x", padx=28, pady=(0, 14))
        self.preview_lbl = ctk.CTkLabel(
            self.preview_card,
            text="Select a file and click Preview to see invoices before importing.",
            font=T.f(12), text_color=T.MUTED)
        self.preview_lbl.pack(anchor="w", padx=20, pady=14)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(anchor="w", padx=28, pady=(0, 10))
        T.button(btn_row, "Preview", self._preview, width=120).pack(side="left")
        T.button(btn_row, "Import All", self._import, width=120,
                 fg_color=T.OK, hover_color="#166b44").pack(side="left", padx=10)
        self.msg = ctk.CTkLabel(btn_row, text="", font=T.f(13))
        self.msg.pack(side="left", padx=10)

        self.results = ctk.CTkScrollableFrame(self, fg_color="transparent", height=260)
        self.results.pack(fill="both", expand=True, padx=28, pady=(0, 16))
        self._pending = None

    def _browse(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select mobile invoices JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if path:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, path)
            self._preview()

    def _load_file(self):
        import json
        path = self.path_entry.get().strip()
        if not path or not os.path.exists(path):
            self.msg.configure(text="File not found.", text_color=T.DANGER)
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _preview(self):
        data = self._load_file()
        if not data:
            return
        for w in self.preview_card.winfo_children():
            w.destroy()
        for w in self.results.winfo_children():
            w.destroy()
        invoices = data.get("invoices", [])
        if not invoices:
            self.preview_lbl = ctk.CTkLabel(
                self.preview_card, text="No invoices found in this file.",
                font=T.f(12), text_color=T.MUTED)
            self.preview_lbl.pack(anchor="w", padx=20, pady=14)
            return
        ctk.CTkLabel(self.preview_card,
                     text=f"{len(invoices)} invoice(s) ready to import:",
                     font=T.f(13, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=20, pady=(14, 6))
        for inv in invoices:
            items     = inv.get("items", [])
            total_val = sum(float(it.get("qty", 0)) * float(it.get("rate", 0))
                            for it in items)
            ctk.CTkLabel(self.preview_card,
                         text=f"  • {inv.get('inv_no','?')}  —  "
                              f"{inv.get('party','?')}  —  "
                              f"Rs {total_val:,.2f}  —  {inv.get('date','')}",
                         font=T.f(12), text_color=T.TEXT, anchor="w").pack(
                anchor="w", padx=20, pady=1)
        ctk.CTkFrame(self.preview_card, fg_color=T.CARD, height=10).pack()
        self._pending = data
        self.msg.configure(text="", text_color=T.TEXT)

    def _import(self):
        if not self._pending:
            self._preview()
            if not self._pending:
                return
        from utils.mobile_export import import_mobile_invoices
        path = self.path_entry.get().strip()
        self.msg.configure(text="Importing…", text_color=T.MUTED)
        self.update()
        try:
            result = import_mobile_invoices(self.con, path)
        except Exception as e:
            self.msg.configure(text=f"Error: {e}", text_color=T.DANGER)
            return
        for w in self.results.winfo_children():
            w.destroy()

        def _section(title, items, color):
            if not items:
                return
            ctk.CTkLabel(self.results, text=title,
                         font=T.f(13, "bold"), text_color=color).pack(
                anchor="w", pady=(10, 2))
            for item in items:
                ctk.CTkLabel(self.results, text=f"  • {item}",
                             font=T.f(12), text_color=T.TEXT,
                             anchor="w", wraplength=700).pack(anchor="w", pady=1)

        _section(f"✓ Imported ({len(result['imported'])})", result["imported"], T.OK)
        _section(f"⚠ Skipped ({len(result['skipped'])})",  result["skipped"],  T.MUTED)
        _section(f"✗ Errors ({len(result['errors'])})",    result["errors"],   T.DANGER)

        n = len(result["imported"])
        self.msg.configure(
            text=f"✓ {n} imported, {len(result['skipped'])} skipped, "
                 f"{len(result['errors'])} errors",
            text_color=T.OK if n else T.MUTED)
        self._pending = None
