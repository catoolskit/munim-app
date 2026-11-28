"""MUNIM Pro — Payment Codes (TDS Pro → Utilities).
Old section → new section (Income-tax Act 2025) → 4-digit payment code, with
rates and thresholds. TDS Entry will use this table to suggest code and rate."""
from tkinter import messagebox

import customtkinter as ctk

from ui import theme as T
from ui.ux import chain_enter, focus_later, inner
from ui.widgets import DataTable
from ui.pro_common import bind_wheel
from db import pro_db

ALL_FORMS = "All forms"
FORM_VALUES = [name for _c, name in pro_db.PAY_FORMS]
FORM_CODE = {name: code for code, name in pro_db.PAY_FORMS}
FILTER_VALUES = [ALL_FORMS] + FORM_VALUES

LABEL_OF = {
    "code": "Payment code", "old_section": "Old section", "new_section": "New section",
    "sl_no": "Table Sl.", "nature": "Nature of payment", "form": "Return form",
    "rate_ind": "Rate (Ind / HUF)", "rate_company": "Rate (Company)",
    "rate_other": "Rate (Others)", "no_pan_rate": "No-PAN rate",
    "th_single": "Threshold per payment", "th_year": "Threshold per year",
    "th_month": "Threshold per month", "notes": "Notes",
}


def _num_text(v):
    if v is None:
        return ""
    v = float(v)
    return str(int(v)) if v.is_integer() else f"{v:g}"


def _rate_text(r):
    vals = [r["rate_ind"], r["rate_company"], r["rate_other"]]
    present = [v for v in vals if v is not None]
    if not present:
        return "per note"
    if len(set(present)) == 1:
        return f"{_num_text(present[0])}%"
    return " / ".join(_num_text(v) if v is not None else "–" for v in vals) + "%"


class PayCodesPage(ctk.CTkFrame):
    def __init__(self, master, con, on_back=None):
        super().__init__(master, fg_color="transparent")
        self.con = con
        self.on_back = on_back or (lambda: None)
        self.editing_id = None
        self.rows = {}
        self.w = {}

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=(16, 6))
        T.title(head, "Payment Codes",
                "Old section → new section (Income-tax Act 2025) → 4-digit payment code, "
                "with rates and thresholds. TDS Entry uses this table.").pack(side="left")
        self.msg = ctk.CTkLabel(head, text="", font=T.f(12), text_color=T.MUTED)
        self.msg.pack(side="right", anchor="s")

        split = ctk.CTkFrame(self, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=20, pady=(2, 16))
        split.grid_columnconfigure(0, weight=3, uniform="p")
        split.grid_columnconfigure(1, weight=2, uniform="p")
        split.grid_rowconfigure(0, weight=1)

        # left: search + form filter + list
        left = ctk.CTkFrame(split, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        bar = ctk.CTkFrame(left, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        self.search = T.entry(bar, "Search by code, section or nature…")
        self.search.pack(side="left", fill="x", expand=True)
        inner(self.search).bind("<KeyRelease>", lambda _e: self.refresh_list())
        self.filter = T.option_menu(bar, FILTER_VALUES, width=250)
        self.filter.pack(side="left", padx=(8, 0))
        self.filter.set(ALL_FORMS)
        self.filter.configure(command=lambda _v: self.refresh_list())

        self.table = DataTable(
            left, [("code", "Code", 60, "w"), ("old", "Old §", 80, "w"),
                   ("new", "New § / Sl.", 130, "w"), ("nature", "Nature of payment", 320, "w"),
                   ("rate", "Rate", 90, "w"), ("ok", "Checked", 70, "center")],
            height=16, empty_text="No payment codes match.")
        self.table.pack(fill="both", expand=True)
        self.table.on_open(self._edit)

        foot = ctk.CTkFrame(left, fg_color="transparent")
        foot.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(foot, text="Rate shown as Ind·HUF / Company / Others when they differ. "
                     "'Checked' = code confirmed against Protean's file format.",
                     font=T.f(11), text_color=T.MUTED, wraplength=560,
                     justify="left").pack(side="left")
        T.button(foot, "Reset built-in rows", self.reset_defaults, width=170,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="right")

        # right: scrollable form + pinned button bar
        card = ctk.CTkFrame(split, fg_color=T.CARD, border_width=1,
                            border_color=T.BORDER, corner_radius=12)
        card.grid(row=0, column=1, sticky="nsew")
        self._build_buttons(card)
        form = ctk.CTkScrollableFrame(card, fg_color="transparent", corner_radius=0)
        form.pack(fill="both", expand=True, padx=3, pady=(3, 0))
        self._build_form(form)
        bind_wheel(form)

        self.refresh_list()
        self._clear_form()

    # ── layout ────────────────────────────────────────────────────────────────
    def _row(self, parent, label):
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x", padx=18, pady=3)
        ctk.CTkLabel(r, text=label, font=T.f(12), text_color=T.MUTED, width=150,
                     anchor="e").pack(side="left", padx=(0, 10))
        return r

    def _small_heads(self, parent, names):
        r = self._row(parent, "")
        for n in names:
            ctk.CTkLabel(r, text=n, font=T.f(11), text_color=T.MUTED, width=110,
                         anchor="w").pack(side="left", padx=(0, 8))

    def _section(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=T.f(13, "bold"), text_color=T.MUTED).pack(
            anchor="w", padx=18, pady=(10, 2))

    def _build_buttons(self, card):
        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=18, pady=(8, 12))
        ctk.CTkFrame(card, height=1, fg_color=T.BORDER).pack(side="bottom", fill="x", padx=12)
        self.save_btn = T.button(bar, "Add code", self.save, width=150)
        self.save_btn.pack(side="left", padx=(0, 8))
        T.button(bar, "New", self._clear_form, width=90, fg_color="#E7ECF5",
                 text_color=T.TEXT, hover_color="#DCE3F0").pack(side="left", padx=(0, 8))
        self.del_btn = T.button(bar, "Delete", self.delete, width=90, fg_color=T.DANGER,
                                hover_color="#A32F23")
        self.del_btn.pack(side="left")

    def _build_form(self, p):
        top = ctk.CTkFrame(p, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(14, 0))
        ctk.CTkLabel(top, text="Payment code details", font=T.f(16, "bold")).pack(side="left")
        self.kind_lbl = ctk.CTkLabel(top, text="", font=T.f(11, "bold"), corner_radius=8)
        self.kind_lbl.pack(side="left", padx=10)
        ctk.CTkLabel(p, text="Codes come from published charts. Tick 'Checked' after comparing "
                     "with Protean's file format (Forms 140 / 144, Annexure 2).",
                     font=T.f(11), text_color=T.MUTED, wraplength=440,
                     justify="left").pack(anchor="w", padx=18, pady=(2, 8))

        r = self._row(p, "Payment code")
        self.w["code"] = T.entry(r, "e.g. 1023", width=110); self.w["code"].pack(side="left")
        self.w["code_checked"] = ctk.CTkCheckBox(r, text="Checked", font=T.f(12))
        self.w["code_checked"].pack(side="left", padx=(12, 0))

        r = self._row(p, "Old section")
        self.w["old_section"] = T.entry(r, "e.g. 194C", width=140)
        self.w["old_section"].pack(side="left")
        r = self._row(p, "New section / Sl.")
        self.w["new_section"] = T.entry(r, "393(1)", width=110)
        self.w["new_section"].pack(side="left")
        self.w["sl_no"] = T.entry(r, "6(i) D(a)", width=130)
        self.w["sl_no"].pack(side="left", padx=(8, 0))
        r = self._row(p, "Nature of payment *")
        self.w["nature"] = T.entry(r, width=320); self.w["nature"].pack(side="left")
        r = self._row(p, "Return form")
        self.w["form"] = T.option_menu(r, FORM_VALUES, width=320)
        self.w["form"].pack(side="left")

        self._section(p, "Rates (%)")
        self._small_heads(p, ("Ind / HUF", "Company", "Others"))
        r = self._row(p, "Rate %")
        for key in ("rate_ind", "rate_company", "rate_other"):
            self.w[key] = T.entry(r, width=110)
            self.w[key].pack(side="left", padx=(0, 8))
        r = self._row(p, "No-PAN rate %")
        self.w["no_pan_rate"] = T.entry(r, width=110); self.w["no_pan_rate"].pack(side="left")
        ctk.CTkLabel(r, text="used if higher than the normal rate", font=T.f(11),
                     text_color=T.MUTED).pack(side="left", padx=(8, 0))

        self._section(p, "Threshold (₹) — leave blank if none")
        self._small_heads(p, ("Per payment", "Per year", "Per month"))
        r = self._row(p, "Threshold ₹")
        for key in ("th_single", "th_year", "th_month"):
            self.w[key] = T.entry(r, width=110)
            self.w[key].pack(side="left", padx=(0, 8))

        self._section(p, "Other")
        r = self._row(p, "Notes")
        self.w["notes"] = T.entry(r, width=320); self.w["notes"].pack(side="left")
        r = self._row(p, "")
        self.w["active"] = ctk.CTkCheckBox(r, text="Active (show in TDS Entry)", font=T.f(12))
        self.w["active"].pack(side="left")
        ctk.CTkFrame(p, height=10, fg_color="transparent").pack(fill="x")

        order = [self.w[k] for k in ("code", "old_section", "new_section", "sl_no", "nature",
                                     "rate_ind", "rate_company", "rate_other", "no_pan_rate",
                                     "th_single", "th_year", "th_month", "notes")]
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
        if value not in (None, ""):
            entry.insert(0, str(value))

    def _reset_borders(self):
        for w in self.w.values():
            if isinstance(w, ctk.CTkEntry):
                w.configure(border_color=T.BORDER)

    def _set_kind(self, text, fg, bg):
        self.kind_lbl.configure(text=f"  {text}  " if text else "", text_color=fg,
                                fg_color=bg if text else "transparent")

    def _clear_form(self):
        self.editing_id = None
        self._reset_borders()
        for w in self.w.values():
            if isinstance(w, ctk.CTkEntry):
                self._set(w, "")
        self.w["form"].set(pro_db.PAY_FORM_NAME["140"])
        self._set(self.w["no_pan_rate"], "20")
        self.w["code_checked"].deselect()
        self.w["active"].select()
        self._set_kind("New row", T.OK, T.SUCCESS_BG)
        self.save_btn.configure(text="Add code")
        self.del_btn.configure(state="disabled")
        focus_later(self.w["code"])

    def _fill(self, row):
        self.editing_id = row["id"]
        self._reset_borders()
        for key in ("code", "old_section", "new_section", "sl_no", "nature", "notes"):
            self._set(self.w[key], row[key])
        for key in ("rate_ind", "rate_company", "rate_other", "no_pan_rate",
                    "th_single", "th_year", "th_month"):
            self._set(self.w[key], _num_text(row[key]))
        self.w["form"].set(pro_db.PAY_FORM_NAME.get(row["form"], pro_db.PAY_FORM_NAME["140"]))
        self.w["code_checked"].select() if row["code_checked"] else self.w["code_checked"].deselect()
        self.w["active"].select() if row["active"] else self.w["active"].deselect()
        if row["seed_key"]:
            self._set_kind("Built-in", T.MUTED, "#E7ECF5")
        else:
            self._set_kind("Your own", T.OK, T.SUCCESS_BG)
        self.save_btn.configure(text="Save changes")
        self.del_btn.configure(state="normal")

    def _collect(self):
        d = {k: w.get() for k, w in self.w.items() if isinstance(w, ctk.CTkEntry)}
        d["form"] = FORM_CODE.get(self.w["form"].get(), "140")
        d["code_checked"] = self.w["code_checked"].get()
        d["active"] = self.w["active"].get()
        return d

    # ── list ──────────────────────────────────────────────────────────────────
    def refresh_list(self):
        fname = self.filter.get()
        form = None if fname == ALL_FORMS else FORM_CODE.get(fname)
        rows = pro_db.list_pay_codes(self.con, form=form, text=self.search.get())
        self.rows = {r["id"]: dict(r) for r in rows}
        self.table.set_rows([
            ((r["code"] or "—", r["old_section"] or "",
              f"{r['new_section'] or ''} {r['sl_no'] or ''}".strip(),
              r["nature"] + ("  (off)" if not r["active"] else ""),
              _rate_text(r), "✓" if r["code_checked"] else ""),
             None, r["id"]) for r in rows])
        checked = sum(1 for r in rows if r["code_checked"])
        self._say(f"{len(rows)} code(s) · {checked} checked")

    # ── actions ───────────────────────────────────────────────────────────────
    def _edit(self, pid):
        row = self.rows.get(pid)
        if row:
            self._fill(row)

    def save(self):
        d = self._collect()
        self._reset_borders()
        try:
            pid = pro_db.save_pay_code(self.con, d, self.editing_id)
        except ValueError as e:
            arg = e.args[0] if e.args else {}
            if isinstance(arg, dict):
                for key in arg:
                    w = self.w.get(key)
                    if isinstance(w, ctk.CTkEntry):
                        w.configure(border_color=T.DANGER)
                key, err = next(iter(arg.items()))
                self._say(f"{LABEL_OF.get(key, key)}: {err}", T.DANGER)
            else:
                self._say(str(e), T.DANGER)
            return
        was_edit = self.editing_id is not None
        self.refresh_list()
        if was_edit and pid in self.rows:
            self._fill(self.rows[pid])
        else:
            self._clear_form()
        self._say("Saved ✓", T.OK)

    def delete(self):
        row = self.rows.get(self.editing_id)
        if not row:
            return
        if row["seed_key"]:
            messagebox.showinfo("Built-in code",
                                "Built-in codes can't be deleted.\n\n"
                                "Untick 'Active' to hide it from TDS Entry.", parent=self)
            return
        if not messagebox.askyesno("Delete payment code",
                                   f"Delete “{row['nature']}”?", parent=self):
            return
        try:
            pro_db.delete_pay_code(self.con, row["id"])
        except ValueError as e:
            self._say(str(e), T.DANGER)
            return
        self.refresh_list()
        self._clear_form()
        self._say("Deleted.")

    def reset_defaults(self):
        if not messagebox.askyesno(
                "Reset built-in rows",
                "Put all built-in rows back to MUNIM's default codes, rates and thresholds?\n\n"
                "Rows you added yourself are not touched. 'Checked' ticks on built-in rows "
                "will be cleared.", parent=self):
            return
        pro_db.restore_pay_code_defaults(self.con)
        self.refresh_list()
        self._clear_form()
        self._say("Built-in rows reset ✓", T.OK)

    def on_escape(self):
        if self.editing_id is not None:
            self._clear_form()
            return True
        return False