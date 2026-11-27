"""MUNIM Pro — Deductor Master (TDS Pro).
A deductor is a TAN holder for whom TDS/TCS returns are filed."""
from tkinter import messagebox, simpledialog

import customtkinter as ctk

from ui import theme as T
from ui.ux import chain_enter, focus_later
from ui.pro_common import SecretEntry, ensure_vault, copy_for_a_while
from ui.pro_picker import EntityPicker
from db import pro_db
from utils import vault
from utils.portal_login import open_portal

SELECT = "— Select —"
STATE_VALUES = [SELECT] + [f"{c} - {n}" for c, n in pro_db.STATES]
TYPE_VALUES = [SELECT] + [name for _c, name in pro_db.DEDUCTOR_TYPES]
TYPE_CODE = {name: code for code, name in pro_db.DEDUCTOR_TYPES}

# (field, label) for the Details tab
DETAILS = [
    ("name", "Name *"), ("file_code", "File Code"), ("type", "Type"),
    ("tan", "TAN *"), ("pan", "PAN"),
    ("addr1", "Address"), ("addr2", ""), ("addr3", ""),
    ("city", "City"), ("state_code", "State"), ("pin", "PIN"),
    ("phone", "Phone"), ("email", "E-mail"),
]
# (field, label) for the Responsible Person tab
RP = [
    ("rp_name", "Name *"), ("rp_pan", "PAN"), ("rp_designation", "Designation"),
    ("rp_father", "Father's name"), ("rp_phone", "Phone"), ("rp_email", "E-mail"),
    ("rp_addr1", "Address"), ("rp_addr2", ""), ("rp_addr3", ""),
    ("rp_city", "City"), ("rp_state_code", "State"), ("rp_pin", "PIN"),
]
LABEL_OF = {f: (l or "Address").rstrip(" *") for f, l in DETAILS + RP}


class DeductorPage(ctk.CTkFrame):
    def __init__(self, master, con, username, on_back=None, start_id=None):
        super().__init__(master, fg_color="transparent")
        self.con, self.username = con, username
        self.on_back = on_back or (lambda: None)
        self.rows, self.idx, self.mode = [], -1, "view"
        self.w = {}

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=28, pady=(18, 6))
        T.title(head, "Deductor Master",
                "The TAN holders for whom you file TDS / TCS returns. "
                "Press F4 anywhere in TDS Pro to pick one quickly.").pack(side="left")
        self.pos_lbl = ctk.CTkLabel(head, text="", font=T.f(12), text_color=T.MUTED)
        self.pos_lbl.pack(side="right", anchor="s")

        holder = ctk.CTkFrame(self, fg_color="transparent")
        holder.pack(side="bottom", fill="x", padx=28, pady=(6, 16))
        self.msg = ctk.CTkLabel(self, text="", font=T.f(12), wraplength=900, justify="left")
        self.msg.pack(side="bottom", anchor="w", padx=30)

        self.view_bar = ctk.CTkFrame(holder, fg_color="transparent")
        for text, cmd, primary in (("Top", self.first, False), ("Prev", self.prev, False),
                                   ("Next", self.next, False), ("Bottom", self.last, False),
                                   ("Find", self.find, False), ("Add", self.start_add, True),
                                   ("Edit", self.start_edit, True),
                                   ("Delete", self.delete, False)):
            self._btn(self.view_bar, text, cmd, primary).pack(side="left", padx=(0, 6))
        self.edit_bar = ctk.CTkFrame(holder, fg_color="transparent")
        self._btn(self.edit_bar, "Save", self.save, True).pack(side="left", padx=(0, 6))
        self._btn(self.edit_bar, "Cancel", self.cancel).pack(side="left")

        self.tabs = ctk.CTkTabview(self, fg_color=T.CARD, border_width=1,
                                   border_color=T.BORDER, segmented_button_fg_color=T.BG,
                                   segmented_button_selected_color=T.ACCENT,
                                   segmented_button_selected_hover_color=T.ACCENT_HOVER)
        self.tabs.pack(fill="both", expand=True, padx=22, pady=(4, 2))
        self.tabs.add("Details")
        self.tabs.add("Responsible Person")
        self._build_grid(self.tabs.tab("Details"), DETAILS)
        self._build_rp(self.tabs.tab("Responsible Person"))
        self._build_creds()

        order = [self.w[f] for f, _ in DETAILS + RP if isinstance(self.w[f], ctk.CTkEntry)]
        order.append(self.trace_user)
        order.append(self.trace_sec.entry)
        chain_enter(order, self.save)
        self.load(select_id=start_id)

    # ── layout ────────────────────────────────────────────────────────────────
    def _btn(self, parent, text, cmd, primary=False):
        kw = {} if primary else dict(fg_color="#E7ECF5", text_color=T.TEXT,
                                     hover_color="#DCE3F0")
        return T.button(parent, text, cmd, width=max(72, 9 * len(text) + 26), height=34, **kw)

    def _field(self, parent, key, row, col):
        if key == "state_code" or key == "rp_state_code":
            w = T.option_menu(parent, STATE_VALUES, width=240, height=34)
        elif key == "type":
            w = T.option_menu(parent, TYPE_VALUES, width=240, height=34)
        else:
            w = T.entry(parent, width=240, height=34)
        w.grid(row=row, column=col + 1, sticky="w", padx=(0, 18),
               pady=(12 if row == 0 else 3, 3))
        self.w[key] = w

    def _build_grid(self, parent, fields):
        half = (len(fields) + 1) // 2
        left, right = fields[:half], fields[half:]
        for col, chunk in ((0, left), (2, right)):
            for r, (key, label) in enumerate(chunk):
                ctk.CTkLabel(parent, text=label, font=T.f(12), text_color=T.MUTED,
                             anchor="e").grid(row=r, column=col, sticky="e",
                                              padx=(18, 8), pady=(12 if r == 0 else 3, 3))
                self._field(parent, key, r, col)

    def _build_rp(self, parent):
        self.same_cb = ctk.CTkCheckBox(
            parent, text="Responsible person's address is the same as the deductor's",
            font=T.f(12), command=self._toggle_same)
        self.same_cb.grid(row=0, column=0, columnspan=4, sticky="w", padx=18, pady=(14, 4))
        fields = RP
        half = (len(fields) + 1) // 2
        left, right = fields[:half], fields[half:]
        for col, chunk in ((0, left), (2, right)):
            for r, (key, label) in enumerate(chunk):
                ctk.CTkLabel(parent, text=label, font=T.f(12), text_color=T.MUTED,
                             anchor="e").grid(row=r + 1, column=col, sticky="e",
                                              padx=(18, 8), pady=3)
                self._field(parent, key, r + 1, col)

    def _build_creds(self):
        cc = T.card(self)
        cc.pack(fill="x", padx=22, pady=(2, 2))
        ctk.CTkLabel(cc, text="TRACES login", font=T.f(14, "bold")).grid(
            row=0, column=0, columnspan=5, sticky="w", padx=18, pady=(12, 0))
        ctk.CTkLabel(cc, text="Password is encrypted on this computer. 'Open portal' opens "
                     "TRACES and copies the User ID; you type the captcha yourself.",
                     font=T.f(11), text_color=T.MUTED).grid(
            row=1, column=0, columnspan=5, sticky="w", padx=18, pady=(0, 6))
        ctk.CTkLabel(cc, text="User ID", font=T.f(12), text_color=T.MUTED).grid(
            row=2, column=0, sticky="e", padx=(18, 8), pady=(0, 12))
        self.trace_user = T.entry(cc, "TRACES User ID", width=180, height=34)
        self.trace_user.grid(row=2, column=1, sticky="w", pady=(0, 12))
        self.trace_sec = SecretEntry(cc, "Password", width=160, loader=self._saved_password)
        self.trace_sec.grid(row=2, column=2, sticky="w", padx=8, pady=(0, 12))
        self._btn(cc, "Open portal", self._open_traces, primary=True).grid(
            row=2, column=3, padx=(0, 6), pady=(0, 12))
        self._btn(cc, "Copy password", self._copy_password).grid(
            row=2, column=4, padx=(0, 18), pady=(0, 12))

    # ── helpers ───────────────────────────────────────────────────────────────
    def _say(self, text, color=None):
        try:
            self.msg.configure(text=text, text_color=color or T.MUTED)
        except Exception:
            pass

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

    def _editable(self):
        return self.mode in ("add", "edit")

    def _set_mode(self, mode):
        self.mode = mode
        state = "normal" if self._editable() else "disabled"
        for w in self.w.values():
            w.configure(state=state)
        self.same_cb.configure(state=state)
        self.trace_user.configure(state=state)
        self.trace_sec.set_state(state)
        self._toggle_same()
        if self._editable():
            self.view_bar.pack_forget()
            self.edit_bar.pack(fill="x")
        else:
            self.edit_bar.pack_forget()
            self.view_bar.pack(fill="x")

    def _toggle_same(self):
        """When 'same address' is ticked, hide/disable the RP address fields."""
        same = bool(self.same_cb.get())
        state = "disabled" if (same or not self._editable()) else "normal"
        for key in ("rp_addr1", "rp_addr2", "rp_addr3", "rp_city", "rp_state_code", "rp_pin"):
            self.w[key].configure(state=state)

    def _fill(self, row):
        self._reset_borders()
        for key, w in self.w.items():
            val = row[key] if row else None
            if key in ("state_code", "rp_state_code"):
                w.set(f"{val} - {pro_db.STATE_NAME[val]}" if val in pro_db.STATE_NAME else SELECT)
            elif key == "type":
                w.set(pro_db.DEDUCTOR_TYPE_NAME.get(val, SELECT) if val else SELECT)
            else:
                self._set_text(w, val)
        same = 1 if (row is None or row["rp_same_addr"]) else 0
        self.same_cb.select() if same else self.same_cb.deselect()
        ref = row["traces_cred_ref"] if row else None
        self._set_text(self.trace_user, vault.user_id(self.con, ref) if ref else "")
        self.trace_sec.clear()
        self.trace_sec.set_placeholder("Saved: type to change" if ref else "Password")

    def _collect(self):
        d = {}
        for key, w in self.w.items():
            v = w.get()
            if key in ("state_code", "rp_state_code"):
                d[key] = "" if v == SELECT else v[:2]
            elif key == "type":
                d[key] = TYPE_CODE.get(v, "")
            else:
                d[key] = v
        d["rp_same_addr"] = 1 if self.same_cb.get() else 0
        if d["rp_same_addr"]:          # copy deductor address into RP fields
            for s, t in (("addr1", "rp_addr1"), ("addr2", "rp_addr2"), ("addr3", "rp_addr3"),
                         ("city", "rp_city"), ("state_code", "rp_state_code"), ("pin", "rp_pin")):
                d[t] = d.get(s, "")
        return d

    def _update_pos(self):
        if self.mode == "add":
            self.pos_lbl.configure(text="New deductor")
        elif self._current():
            self.pos_lbl.configure(text=f"Deductor {self.idx + 1} of {len(self.rows)}")
        else:
            self.pos_lbl.configure(text="")

    # ── records ───────────────────────────────────────────────────────────────
    def load(self, select_id=None):
        self.rows = pro_db.list_deductors(self.con)
        if not self.rows:
            self.idx = -1
            self.start_add(first=True)
            return
        idx = 0
        if select_id:
            for i, r in enumerate(self.rows):
                if r["id"] == select_id:
                    idx = i
                    break
        self.show(idx)

    def show(self, i):
        self.idx = i
        self._set_mode("edit")          # editable while filling
        self._fill(self.rows[i])
        self._set_mode("view")
        self.tabs.set("Details")
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
        EntityPicker(self, self.con, "tds", self._picked)

    def _picked(self, row):
        for i, r in enumerate(self.rows):
            if r["id"] == row["id"]:
                self.show(i)
                return
        self.load(select_id=row["id"])

    def start_add(self, first=False):
        self._set_mode("add")
        self._fill(None)
        self.tabs.set("Details")
        self._update_pos()
        focus_later(self.w["name"])
        self._say("Add your first deductor." if first else "")

    def start_edit(self):
        if self._current():
            self._set_mode("edit")
            self._update_pos()
            focus_later(self.w["name"])
            self._say("")

    def cancel(self):
        if self.rows:
            self.show(self.idx if self.idx >= 0 else 0)
            self._say("")
        else:
            self.on_back()

    def on_escape(self):
        if self._editable():
            self.cancel()
            return True
        return False

    def save(self):
        if not self._editable():
            return
        d = self._collect()
        errors = pro_db.validate_deductor(d)
        self._reset_borders()
        if errors:
            # jump to the tab that holds the first error
            first_key = next(iter(errors))
            self.tabs.set("Responsible Person" if first_key.startswith("rp_") else "Details")
            for key in errors:
                w = self.w.get(key)
                if isinstance(w, ctk.CTkEntry):
                    w.configure(border_color=T.DANGER)
            self._say(f"{LABEL_OF.get(first_key, first_key)}: {errors[first_key]}", T.DANGER)
            return
        row = self._current() if self.mode == "edit" else None
        try:
            d["traces_cred_ref"] = self._save_cred(row)
        except vault.VaultError as e:
            self._say(str(e), T.DANGER)
            return
        if d["traces_cred_ref"] == "__abort__":
            self._say("Not saved: the password vault was not opened.", T.DANGER)
            return
        try:
            did = pro_db.save_deductor(self.con, d, row["id"] if row else None)
        except ValueError as e:
            arg = e.args[0] if e.args else {}
            if isinstance(arg, dict):
                first_key = next(iter(arg))
                self.tabs.set("Responsible Person" if first_key.startswith("rp_") else "Details")
                w = self.w.get(first_key)
                if isinstance(w, ctk.CTkEntry):
                    w.configure(border_color=T.DANGER)
                self._say(f"{LABEL_OF.get(first_key, first_key)}: {arg[first_key]}", T.DANGER)
            else:
                self._say(str(e), T.DANGER)
            return
        self.load(select_id=did)
        self._say("Saved ✓", T.OK)

    def _save_cred(self, row):
        """Returns the TRACES cred ref, '' if none, or '__abort__' if vault not opened."""
        user, pw = self.trace_user.get().strip(), self.trace_sec.get()
        ref = row["traces_cred_ref"] if row else None
        old_user = vault.user_id(self.con, ref) if ref else ""
        if not user and not pw:
            if ref:
                vault.delete(self.con, ref)
            return ""
        if ref and not pw and user == old_user:
            return ref
        if not ensure_vault(self, self.con, self.username):
            return "__abort__"
        if not pw and ref:
            saved = vault.get(self.con, ref)
            pw = saved[2] if saved else ""
        return vault.put(self.con, "TRACES", user, pw, ref=ref)

    def delete(self):
        row = self._current()
        if not row:
            return
        if not messagebox.askyesno(
                "Delete deductor",
                f"Delete “{row['name']}” (TAN {row['tan']})?\n\n"
                "Its saved TRACES password will also be removed.",
                parent=self):
            return
        pro_db.delete_deductor(self.con, row["id"])
        self.load()
        self._say("Deleted.")

    # ── TRACES buttons ────────────────────────────────────────────────────────
    def _saved_password(self):
        row = self._current()
        ref = row["traces_cred_ref"] if (row and self.mode != "add") else None
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

    def _open_traces(self):
        self._say(open_portal(self, "TRACES", self.trace_user.get().strip()), T.OK)

    def _copy_password(self):
        pw = self.trace_sec.get() or self._saved_password()
        if not pw:
            self._say("No TRACES password saved.", T.DANGER)
            return
        copy_for_a_while(self, pw)
        self._say("Password copied. Cleared from the clipboard in 30 seconds.", T.OK)