"""MUNIM Pro — Consultant Master (shared by TDS Pro, GST Pro and Tax Pro)."""
from tkinter import messagebox, simpledialog

import customtkinter as ctk

from ui import theme as T
from ui.ux import chain_enter, focus_later
from ui.pro_common import SecretEntry, ensure_vault, copy_for_a_while, open_portal
from db import pro_db
from utils import vault

SELECT = "— Select —"
STATE_VALUES = [SELECT] + [f"{c} - {n}" for c, n in pro_db.STATES]
ROLE_VALUES = [SELECT] + pro_db.CONTACT_ROLES

FIELDS_LEFT = [
    ("firm_name", "Firm name *"), ("firm_pan", "Firm PAN"),
    ("addr1", "Address"), ("addr2", ""), ("addr3", ""),
    ("city", "City"), ("state_code", "State"), ("pin", "PIN"),
    ("phone1", "Phone"), ("phone2", "Phone 2"), ("email", "E-mail"),
]
FIELDS_RIGHT = [
    ("contact_name", "Partner / Proprietor"), ("contact_role", "Role"),
    ("membership_no", "Membership No."), ("pan", "PAN"),
    ("firm_reg_no", "Firm Reg. No. (FRN)"), ("gstin", "GSTIN"),
    ("tagline", "Tagline on reports"),
]
LABEL_OF = {k: (v or "Address").rstrip(" *") for k, v in FIELDS_LEFT + FIELDS_RIGHT}

# (id, label, db field, vault portal)
CREDS = [
    ("itd", "Income-tax portal (CA login)", "itd_cred_ref", "ITD"),
    ("gstp", "GST portal (practitioner)", "gstp_cred_ref", "GST"),
]


class ConsultantPage(ctk.CTkFrame):
    def __init__(self, master, con, username, on_change=None, on_back=None):
        super().__init__(master, fg_color="transparent")
        self.con, self.username = con, username
        self.on_change = on_change or (lambda: None)
        self.on_back = on_back or (lambda: None)
        self.rows, self.idx, self.mode = [], -1, "view"
        self.w, self.cred_w = {}, {}

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=28, pady=(20, 8))
        T.title(head, "Consultant Master",
                "Your firm's details print on returns, certificates and reports. "
                "Shared by TDS Pro, GST Pro and Tax Pro.").pack(side="left")
        self.pos_lbl = ctk.CTkLabel(head, text="", font=T.f(12), text_color=T.MUTED)
        self.pos_lbl.pack(side="right", anchor="s")

        holder = ctk.CTkFrame(self, fg_color="transparent")
        holder.pack(side="bottom", fill="x", padx=28, pady=(6, 18))
        self.msg = ctk.CTkLabel(self, text="", font=T.f(12), wraplength=900, justify="left")
        self.msg.pack(side="bottom", anchor="w", padx=30)

        self.view_bar = ctk.CTkFrame(holder, fg_color="transparent")
        for text, cmd, primary in (("Top", self.first, False), ("Prev", self.prev, False),
                                   ("Next", self.next, False), ("Bottom", self.last, False),
                                   ("Find", self.find, False), ("Add", self.start_add, True),
                                   ("Edit", self.start_edit, True),
                                   ("Set as default", self.make_default, False),
                                   ("Delete", self.delete, False)):
            self._btn(self.view_bar, text, cmd, primary).pack(side="left", padx=(0, 6))
        self.edit_bar = ctk.CTkFrame(holder, fg_color="transparent")
        self._btn(self.edit_bar, "Save", self.save, True).pack(side="left", padx=(0, 6))
        self._btn(self.edit_bar, "Cancel", self.cancel).pack(side="left")

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20)
        self._build_form(body)
        self._build_creds(body)

        order = [self.w[k] for k, _ in FIELDS_LEFT + FIELDS_RIGHT
                 if isinstance(self.w[k], ctk.CTkEntry)]
        for user_e, sec in self.cred_w.values():
            order += [user_e, sec.entry]
        chain_enter(order, self.save)
        self.load()

    # ── layout ────────────────────────────────────────────────────────────────
    def _btn(self, parent, text, cmd, primary=False):
        kw = {} if primary else dict(fg_color="#E7ECF5", text_color=T.TEXT,
                                     hover_color="#DCE3F0")
        return T.button(parent, text, cmd, width=max(76, 9 * len(text) + 28), height=34, **kw)

    def _build_form(self, body):
        form = T.card(body)
        form.pack(fill="x", padx=8, pady=6)
        for col, fields in ((0, FIELDS_LEFT), (2, FIELDS_RIGHT)):
            for r, (key, label) in enumerate(fields):
                ctk.CTkLabel(form, text=label, font=T.f(12), text_color=T.MUTED,
                             anchor="e").grid(row=r, column=col, sticky="e",
                                              padx=(18, 8), pady=(12 if r == 0 else 3, 3))
                if key == "state_code":
                    w = T.option_menu(form, STATE_VALUES, width=260, height=34)
                elif key == "contact_role":
                    w = T.option_menu(form, ROLE_VALUES, width=260, height=34)
                else:
                    w = T.entry(form, width=260, height=34)
                w.grid(row=r, column=col + 1, sticky="w", padx=(0, 18),
                       pady=(12 if r == 0 else 3, 3))
                self.w[key] = w
        cb = ctk.CTkCheckBox(form, text="Tax auditor (signs tax audit reports)",
                             font=T.f(12))
        cb.grid(row=len(FIELDS_RIGHT), column=3, sticky="w", pady=6)
        self.w["is_tax_auditor"] = cb

    def _build_creds(self, body):
        cc = T.card(body)
        cc.pack(fill="x", padx=8, pady=(10, 6))
        ctk.CTkLabel(cc, text="Portal logins", font=T.f(15, "bold")).grid(
            row=0, column=0, columnspan=5, sticky="w", padx=18, pady=(14, 0))
        ctk.CTkLabel(cc, text="Passwords are encrypted on this computer. MUNIM opens the "
                     "portal and fills nothing you have to verify: you type the captcha / OTP.",
                     font=T.f(12), text_color=T.MUTED).grid(
            row=1, column=0, columnspan=5, sticky="w", padx=18, pady=(0, 8))
        for i, (cid, label, _field, portal) in enumerate(CREDS, start=2):
            ctk.CTkLabel(cc, text=label, font=T.f(12), text_color=T.MUTED).grid(
                row=i, column=0, sticky="e", padx=(18, 8), pady=4)
            user_e = T.entry(cc, "User ID", width=190, height=34)
            user_e.grid(row=i, column=1, sticky="w", pady=4)
            sec = SecretEntry(cc, "Password", width=170,
                              loader=lambda c=cid: self._saved_password(c))
            sec.grid(row=i, column=2, sticky="w", padx=8, pady=4)
            self._btn(cc, "Open portal", lambda c=cid: self._open_portal(c)).grid(
                row=i, column=3, padx=(0, 6), pady=4)
            self._btn(cc, "Copy password", lambda c=cid: self._copy_password(c)).grid(
                row=i, column=4, padx=(0, 18), pady=4)
            self.cred_w[cid] = (user_e, sec)
        ctk.CTkLabel(cc, text="").grid(row=len(CREDS) + 2, column=0, pady=2)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _say(self, text, color=None):
        self.msg.configure(text=text, text_color=color or T.MUTED)

    @staticmethod
    def _set_text(entry, value):
        state = entry.cget("state")
        entry.configure(state="normal")
        entry.delete(0, "end")
        if value:
            entry.insert(0, str(value))
        entry.configure(state=state)

    def _current(self):
        return self.rows[self.idx] if 0 <= self.idx < len(self.rows) else None

    def _reset_borders(self):
        for w in self.w.values():
            if isinstance(w, ctk.CTkEntry):
                w.configure(border_color=T.BORDER)

    def _set_mode(self, mode):
        self.mode = mode
        editable = mode in ("add", "edit")
        state = "normal" if editable else "disabled"
        for w in self.w.values():
            w.configure(state=state)
        for user_e, sec in self.cred_w.values():
            user_e.configure(state=state)
            sec.set_state(state)
        if editable:
            self.view_bar.pack_forget()
            self.edit_bar.pack(fill="x")
        else:
            self.edit_bar.pack_forget()
            self.view_bar.pack(fill="x")

    def _fill(self, row):
        self._reset_borders()
        for key, w in self.w.items():
            val = row[key] if row else None
            if key == "state_code":
                w.set(f"{val} - {pro_db.STATE_NAME[val]}" if val in pro_db.STATE_NAME else SELECT)
            elif key == "contact_role":
                w.set(val if val in pro_db.CONTACT_ROLES else SELECT)
            elif key == "is_tax_auditor":
                w.select() if val else w.deselect()
            else:
                self._set_text(w, val)
        for cid, _label, field, _portal in CREDS:
            user_e, sec = self.cred_w[cid]
            ref = row[field] if row else None
            self._set_text(user_e, vault.user_id(self.con, ref) if ref else "")
            sec.clear()
            sec.set_placeholder("Saved: type to change" if ref else "Password")

    def _collect(self):
        d = {}
        for key, w in self.w.items():
            v = w.get()
            if key == "state_code":
                d[key] = "" if v == SELECT else v[:2]
            elif key == "contact_role":
                d[key] = "" if v == SELECT else v
            else:
                d[key] = v
        return d

    def _update_pos(self):
        row = self._current()
        if self.mode == "add":
            self.pos_lbl.configure(text="New consultant")
        elif row:
            extra = "  ·  Default" if row["is_default"] else ""
            self.pos_lbl.configure(text=f"Consultant {self.idx + 1} of {len(self.rows)}{extra}")
        else:
            self.pos_lbl.configure(text="")

    # ── records ───────────────────────────────────────────────────────────────
    def load(self, select_id=None):
        self.rows = pro_db.list_consultants(self.con)
        if not self.rows:
            self.idx = -1
            self.start_add(first=True)
            return
        idx = 0
        for i, r in enumerate(self.rows):
            if (select_id and r["id"] == select_id) or (not select_id and r["is_default"]):
                idx = i
                break
        self.show(idx)

    def show(self, i):
        self.idx = i
        self._set_mode("edit")          # widgets must be editable while filling
        self._fill(self.rows[i])
        self._set_mode("view")
        self._update_pos()

    def first(self):
        if self.rows:
            self.show(0)

    def prev(self):
        if self.idx > 0:
            self.show(self.idx - 1)

    def next(self):
        if self.idx < len(self.rows) - 1:
            self.show(self.idx + 1)

    def last(self):
        if self.rows:
            self.show(len(self.rows) - 1)

    def find(self):
        text = simpledialog.askstring("Find consultant", "Name, partner, M.No. or city:",
                                      parent=self)
        if not text:
            return
        hits = pro_db.find_consultants(self.con, text)
        if not hits:
            self._say("No match found.", T.DANGER)
            return
        for i, r in enumerate(self.rows):
            if r["id"] == hits[0]["id"]:
                self.show(i)
                self._say(f"{len(hits)} match(es). Showing the first.")
                return

    def start_add(self, first=False):
        self._set_mode("add")
        self._fill(None)
        self._update_pos()
        focus_later(self.w["firm_name"])
        self._say("Add your firm's details to get started." if first else "")

    def start_edit(self):
        if self._current():
            self._set_mode("edit")
            self._update_pos()
            focus_later(self.w["firm_name"])
            self._say("")

    def cancel(self):
        if self.rows:
            self.show(self.idx if self.idx >= 0 else 0)
            self._say("")
        else:
            self.on_back()

    def on_escape(self):
        """Called by the shell when Esc is pressed. True = handled here."""
        if self.mode in ("add", "edit"):
            self.cancel()
            return True
        return False

    def save(self):
        if self.mode not in ("add", "edit"):
            return
        d = self._collect()
        errors = pro_db.validate_consultant(d)
        self._reset_borders()
        if errors:
            for key in errors:
                w = self.w.get(key)
                if isinstance(w, ctk.CTkEntry):
                    w.configure(border_color=T.DANGER)
            key, err = next(iter(errors.items()))
            self._say(f"{LABEL_OF.get(key, key)}: {err}", T.DANGER)
            return
        row = self._current() if self.mode == "edit" else None
        try:
            refs = self._save_creds(row)
        except vault.VaultError as e:
            self._say(str(e), T.DANGER)
            return
        if refs is None:
            self._say("Not saved: the password vault was not opened.", T.DANGER)
            return
        d.update(refs)
        try:
            cid = pro_db.save_consultant(self.con, d, row["id"] if row else None)
        except ValueError as e:
            self._say(str(e), T.DANGER)
            return
        self.load(select_id=cid)
        self.on_change()
        self._say("Saved ✓", T.OK)

    def _save_creds(self, row):
        """Returns {field: ref or None}, or None if the vault could not be opened."""
        out = {}
        for cid, _label, field, portal in CREDS:
            user_e, sec = self.cred_w[cid]
            user, pw = user_e.get().strip(), sec.get()
            ref = row[field] if row else None
            old_user = vault.user_id(self.con, ref) if ref else ""
            if not user and not pw:
                if ref:
                    vault.delete(self.con, ref)
                out[field] = None
                continue
            if ref and not pw and user == old_user:
                out[field] = ref
                continue
            if not ensure_vault(self, self.con, self.username):
                return None
            if not pw and ref:
                saved = vault.get(self.con, ref)
                pw = saved[2] if saved else ""
            out[field] = vault.put(self.con, portal, user, pw, ref=ref)
        return out

    def make_default(self):
        row = self._current()
        if row:
            pro_db.set_default_consultant(self.con, row["id"])
            self.load(select_id=row["id"])
            self.on_change()
            self._say(f"“{row['firm_name']}” is now the default consultant.", T.OK)

    def delete(self):
        row = self._current()
        if not row:
            return
        if not messagebox.askyesno(
                "Delete consultant",
                f"Delete “{row['firm_name']}”?\n\nIts saved portal passwords will also be removed.",
                parent=self):
            return
        pro_db.delete_consultant(self.con, row["id"])
        self.load()
        self.on_change()
        self._say("Deleted.")

    # ── portal buttons ────────────────────────────────────────────────────────
    def _cred_field(self, cid):
        return next(c for c in CREDS if c[0] == cid)

    def _saved_password(self, cid):
        row = self._current()
        field = self._cred_field(cid)[2]
        ref = row[field] if (row and self.mode != "add") else None
        if not ref:
            return None
        if not ensure_vault(self, self.con, self.username):
            return None
        try:
            saved = vault.get(self.con, ref)
        except vault.VaultError as e:
            self._say(str(e), T.DANGER)
            return None
        return saved[2] if saved and saved[2] else None

    def _open_portal(self, cid):
        user_e, _sec = self.cred_w[cid]
        portal = self._cred_field(cid)[3]
        self._say(open_portal(self, portal, user_e.get().strip()), T.OK)

    def _copy_password(self, cid):
        _user_e, sec = self.cred_w[cid]
        pw = sec.get() or self._saved_password(cid)
        if not pw:
            self._say("No password saved for this login.", T.DANGER)
            return
        copy_for_a_while(self, pw)
        self._say("Password copied. It will be cleared from the clipboard in 30 seconds.", T.OK)