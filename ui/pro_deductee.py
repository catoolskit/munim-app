"""MUNIM Pro — Deductee (Payee) Master. Deductees belong to one deductor."""
from tkinter import messagebox

import customtkinter as ctk

from ui import theme as T
from ui.ux import chain_enter, focus_later
from ui.widgets import DataTable
from db import pro_db

SELECT = "— Select —"
STATE_VALUES = [SELECT] + [f"{c} - {n}" for c, n in pro_db.STATES]
TYPE_VALUES = [name for _c, name in pro_db.DEDUCTEE_TYPES]
TYPE_CODE = {name: code for code, name in pro_db.DEDUCTEE_TYPES}
PAN_STATUS_VALUES = [name for _c, name in pro_db.PAN_STATUS]
PAN_STATUS_CODE = {name: code for code, name in pro_db.PAN_STATUS}
FREQ_VALUES = [SELECT] + pro_db.FORM16A_FREQ


class DeducteePage(ctk.CTkFrame):
    def __init__(self, master, con, username, deductor, on_back=None):
        super().__init__(master, fg_color="transparent")
        self.con, self.username, self.deductor = con, username, deductor
        self.on_back = on_back or (lambda: None)
        self.editing_id = None
        self.w = {}

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=(16, 6))
        T.title(head, "Deductee Master",
                f"Payees of {deductor['name']} (TAN {deductor['tan']}). "
                "Each deductor has its own list.").pack(side="left")
        self.msg = ctk.CTkLabel(head, text="", font=T.f(12), text_color=T.MUTED)
        self.msg.pack(side="right", anchor="s")

        split = ctk.CTkFrame(self, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=20, pady=(2, 16))
        split.grid_columnconfigure(0, weight=2, uniform="d")
        split.grid_columnconfigure(1, weight=3, uniform="d")
        split.grid_rowconfigure(0, weight=1)

        # left: list + search
        left = ctk.CTkFrame(split, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.search = T.entry(left, "Search by name, PAN or city…")
        self.search.pack(fill="x", pady=(0, 8))
        from ui.ux import inner
        inner(self.search).bind("<KeyRelease>", lambda _e: self.refresh_list())
        self.table = DataTable(
            left, [("name", "Name", 200, "w"), ("pan", "PAN", 120, "w"),
                   ("tag", "Type", 90, "w")],
            height=16, empty_text="No deductees yet.\nAdd one using the form on the right.")
        self.table.pack(fill="both", expand=True)
        self.table.on_open(self._edit)

        # right: form in a scrollable card
        right = ctk.CTkScrollableFrame(split, fg_color=T.CARD, border_width=1,
                                       border_color=T.BORDER, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew")
        self._build_form(right)

        self.rows = {}
        self.refresh_list()
        self._clear_form()

    # ── form ──────────────────────────────────────────────────────────────────
    def _row(self, parent, label):
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x", padx=18, pady=3)
        ctk.CTkLabel(r, text=label, font=T.f(12), text_color=T.MUTED, width=130,
                     anchor="e").pack(side="left", padx=(0, 10))
        return r

    def _build_form(self, p):
        ctk.CTkLabel(p, text="Deductee details", font=T.f(16, "bold")).pack(
            anchor="w", padx=18, pady=(14, 6))

        r = self._row(p, "Name *")
        self.w["name"] = T.entry(r, width=300); self.w["name"].pack(side="left")

        r = self._row(p, "PAN")
        self.w["pan"] = T.entry(r, width=150); self.w["pan"].pack(side="left")
        self.w["pan_status"] = T.option_menu(r, PAN_STATUS_VALUES, width=150)
        self.w["pan_status"].pack(side="left", padx=(8, 0))

        r = self._row(p, "Type")
        self.w["type"] = T.option_menu(r, TYPE_VALUES, width=180); self.w["type"].pack(side="left")

        r = self._row(p, "")
        self.w["is_employee"] = ctk.CTkCheckBox(r, text="Employee (salary / 392)", font=T.f(12))
        self.w["is_employee"].pack(side="left")
        r = self._row(p, "")
        self.w["resident"] = ctk.CTkCheckBox(r, text="Resident in India", font=T.f(12))
        self.w["resident"].pack(side="left")
        r = self._row(p, "")
        self.w["higher_rate"] = ctk.CTkCheckBox(
            r, text="Higher TDS rate — non-filer (206AB / 206CCA)", font=T.f(12))
        self.w["higher_rate"].pack(side="left")

        ctk.CTkLabel(p, text="Lower-deduction certificate (if any)", font=T.f(13, "bold"),
                     text_color=T.MUTED).pack(anchor="w", padx=18, pady=(10, 2))
        r = self._row(p, "Certificate No.")
        self.w["lower_cert_no"] = T.entry(r, width=180); self.w["lower_cert_no"].pack(side="left")
        self.w["lower_rate"] = T.entry(r, "Rate %", width=90); self.w["lower_rate"].pack(
            side="left", padx=(8, 0))
        r = self._row(p, "Valid from / to")
        self.w["lower_valid_from"] = T.entry(r, "DD-MM-YYYY", width=130)
        self.w["lower_valid_from"].pack(side="left")
        self.w["lower_valid_to"] = T.entry(r, "DD-MM-YYYY", width=130)
        self.w["lower_valid_to"].pack(side="left", padx=(8, 0))

        ctk.CTkLabel(p, text="Other", font=T.f(13, "bold"), text_color=T.MUTED).pack(
            anchor="w", padx=18, pady=(10, 2))
        r = self._row(p, "Father's name")
        self.w["father_name"] = T.entry(r, width=300); self.w["father_name"].pack(side="left")
        r = self._row(p, "Designation")
        self.w["designation"] = T.entry(r, width=300); self.w["designation"].pack(side="left")
        r = self._row(p, "Date of birth")
        self.w["dob"] = T.entry(r, "DD-MM-YYYY", width=150); self.w["dob"].pack(side="left")
        r = self._row(p, "Form 16A every")
        self.w["form16a_freq"] = T.option_menu(r, FREQ_VALUES, width=180)
        self.w["form16a_freq"].pack(side="left")

        r = self._row(p, "Address")
        self.w["addr1"] = T.entry(r, width=300); self.w["addr1"].pack(side="left")
        r = self._row(p, "")
        self.w["addr2"] = T.entry(r, width=300); self.w["addr2"].pack(side="left")
        r = self._row(p, "City / State")
        self.w["city"] = T.entry(r, "City", width=150); self.w["city"].pack(side="left")
        self.w["state_code"] = T.option_menu(r, STATE_VALUES, width=140)
        self.w["state_code"].pack(side="left", padx=(8, 0))
        r = self._row(p, "PIN / Phone")
        self.w["pin"] = T.entry(r, "PIN", width=120); self.w["pin"].pack(side="left")
        self.w["phone"] = T.entry(r, "Phone", width=170); self.w["phone"].pack(
            side="left", padx=(8, 0))
        r = self._row(p, "E-mail")
        self.w["email"] = T.entry(r, width=300); self.w["email"].pack(side="left")

        bar = ctk.CTkFrame(p, fg_color="transparent")
        bar.pack(fill="x", padx=18, pady=(14, 18))
        self.save_btn = T.button(bar, "Add deductee", self.save, width=150)
        self.save_btn.pack(side="left", padx=(0, 8))
        T.button(bar, "Clear", self._clear_form, width=90, fg_color="#E7ECF5",
                 text_color=T.TEXT, hover_color="#DCE3F0").pack(side="left", padx=(0, 8))
        self.del_btn = T.button(bar, "Delete", self.delete, width=90, fg_color=T.DANGER,
                                hover_color="#A32F23")
        self.del_btn.pack(side="left")

        order = [self.w[k] for k in ("name", "pan", "lower_cert_no", "lower_rate",
                                     "father_name", "designation", "dob", "addr1",
                                     "addr2", "city", "pin", "phone", "email")]
        chain_enter(order, self.save)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _say(self, text, color=None):
        try:
            self.msg.configure(text=text, text_color=color or T.MUTED)
        except Exception:
            pass

    @staticmethod
    def _set(entry, value):
        entry.delete(0, "end")
        if value:
            entry.insert(0, str(value))

    def _clear_form(self):
        self.editing_id = None
        for key, w in self.w.items():
            if isinstance(w, ctk.CTkEntry):
                self._set(w, "")
            elif isinstance(w, ctk.CTkCheckBox):
                w.deselect()
        self.w["type"].set("Individual")
        self.w["pan_status"].set(pro_db.PAN_STATUS[0][1])
        self.w["state_code"].set(SELECT)
        self.w["form16a_freq"].set("Quarterly")
        self.w["resident"].select()
        self.save_btn.configure(text="Add deductee")
        self.del_btn.configure(state="disabled")
        focus_later(self.w["name"])

    def _fill(self, row):
        self.editing_id = row["id"]
        for key, w in self.w.items():
            if isinstance(w, ctk.CTkEntry):
                self._set(w, row[key])
        self.w["type"].set(pro_db.DEDUCTEE_TYPE_NAME.get(row["type"], "Individual"))
        self.w["pan_status"].set(pro_db.PAN_STATUS_NAME.get(row["pan_status"],
                                                            pro_db.PAN_STATUS[0][1]))
        sc = row["state_code"]
        self.w["state_code"].set(f"{sc} - {pro_db.STATE_NAME[sc]}"
                                 if sc in pro_db.STATE_NAME else SELECT)
        self.w["form16a_freq"].set(row["form16a_freq"] or "Quarterly")
        for flag in ("is_employee", "resident", "higher_rate"):
            self.w[flag].select() if row[flag] else self.w[flag].deselect()
        self.save_btn.configure(text="Save changes")
        self.del_btn.configure(state="normal")

    def _collect(self):
        d = {}
        for key, w in self.w.items():
            if isinstance(w, ctk.CTkEntry):
                d[key] = w.get()
            elif isinstance(w, ctk.CTkCheckBox):
                d[key] = 1 if w.get() else 0
        d["type"] = TYPE_CODE.get(self.w["type"].get(), "individual")
        d["pan_status"] = PAN_STATUS_CODE.get(self.w["pan_status"].get(), "active")
        sv = self.w["state_code"].get()
        d["state_code"] = "" if sv == SELECT else sv[:2]
        fv = self.w["form16a_freq"].get()
        d["form16a_freq"] = "" if fv == SELECT else fv
        return d

    # ── list ──────────────────────────────────────────────────────────────────
    def refresh_list(self):
        text = self.search.get()
        rows = (pro_db.find_deductees(self.con, self.deductor["id"], text) if text.strip()
                else pro_db.list_deductees(self.con, self.deductor["id"]))
        self.rows = {r["id"]: dict(r) for r in rows}
        self.table.set_rows([
            ((r["name"], r["pan"] or "—", pro_db.DEDUCTEE_TYPE_NAME.get(r["type"], "")),
             None, r["id"]) for r in rows])
        self._say(f"{len(rows)} deductee(s)")

    # ── actions ───────────────────────────────────────────────────────────────
    def _edit(self, pid):
        row = self.rows.get(pid)
        if row:
            self._fill(row)

    def save(self):
        d = self._collect()
        try:
            pid = pro_db.save_deductee(self.con, self.deductor["id"], d, self.editing_id)
        except ValueError as e:
            arg = e.args[0] if e.args else {}
            if isinstance(arg, dict):
                field, err = next(iter(arg.items()))
                self._say(f"{field}: {err}", T.DANGER)
            else:
                self._say(str(e), T.DANGER)
            return
        self._say("Saved ✓", T.OK)
        self.refresh_list()
        self._clear_form()
        # keep focus flowing for fast entry of the next payee
        focus_later(self.w["name"])

    def delete(self):
        if not self.editing_id:
            return
        row = self.rows.get(self.editing_id)
        name = row["name"] if row else "this deductee"
        if not messagebox.askyesno("Delete deductee", f"Delete “{name}”?", parent=self):
            return
        pro_db.delete_deductee(self.con, self.editing_id)
        self.refresh_list()
        self._clear_form()
        self._say("Deleted.")

    def on_escape(self):
        if self.editing_id is not None:
            self._clear_form()
            return True
        return False
