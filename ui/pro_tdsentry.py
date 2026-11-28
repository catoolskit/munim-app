"""MUNIM Pro — TDS / TCS Entry (TDS Pro). One row per payment or credit to a deductee.
The rate is suggested from Payment Codes and the deductee's type, PAN status and
lower-deduction certificate. Challans are linked in the next step."""
import datetime
from tkinter import messagebox

import customtkinter as ctk

from ui import theme as T
from ui.ux import chain_enter, focus_later, inner
from ui.widgets import DataTable
from ui.pro_common import bind_wheel
from db import pro_db

ALL_Q = "All quarters"
QUARTERS = [ALL_Q, "Q1 (Apr–Jun)", "Q2 (Jul–Sep)", "Q3 (Oct–Dec)", "Q4 (Jan–Mar)"]
CHOOSE = "— Choose payment code —"
REASON_VALUES = [n for _c, n in pro_db.TDS_REASONS]
REASON_CODE = {n: c for c, n in pro_db.TDS_REASONS}
LIGHT = dict(fg_color="#E7ECF5", text_color=T.TEXT, hover_color="#DCE3F0")

LABEL_OF = {
    "deductee": "Deductee", "pay_code": "Payment code", "paid_on": "Paid / credited on",
    "deducted_on": "Deducted on", "amount": "Amount", "rate": "Rate",
    "tds": "Tax deducted", "surcharge": "Surcharge", "cess": "Cess", "reason": "Reason",
}


def _num_text(v):
    if v is None:
        return ""
    v = float(v)
    return str(int(v)) if v.is_integer() else f"{v:g}"


def _inr(v):
    """1234567.5 → 12,34,567.50 (Indian grouping; paise only when present)."""
    if v is None:
        return ""
    neg = v < 0
    v = abs(float(v))
    whole = int(v)
    paise = int(round((v - whole) * 100))
    if paise == 100:
        whole, paise = whole + 1, 0
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if neg else "") + s + (f".{paise:02d}" if paise else "")


# ─────────────────────────────────────────────────────────────────────────────
class DeducteePicker(ctk.CTkToplevel):
    """Small search window to choose one deductee of the current deductor."""

    def __init__(self, master, con, deductor_id, on_pick):
        super().__init__(master)
        self.title("Choose deductee")
        self.geometry("640x480")
        self.transient(master.winfo_toplevel())
        self.con, self.deductor_id, self.on_pick = con, deductor_id, on_pick
        self.rows = {}

        self.search = T.entry(self, "Search by name, PAN or city…")
        self.search.pack(fill="x", padx=14, pady=(14, 8))
        self.table = DataTable(
            self, [("name", "Name", 260, "w"), ("pan", "PAN", 120, "w"),
                   ("type", "Type", 110, "w"), ("res", "Resident", 80, "w")],
            height=12, empty_text="No deductees found.\nAdd them in Deductee Master.")
        self.table.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.table.on_open(self._pick)
        inner(self.search).bind("<KeyRelease>", lambda _e: self.refresh())
        inner(self.search).bind("<Return>", self._enter)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.refresh()
        self.after(150, self._grab)

    def _grab(self):
        try:
            self.lift()
            self.grab_set()
            self.search.focus_set()
        except Exception:
            pass

    def refresh(self):
        text = self.search.get()
        rows = (pro_db.find_deductees(self.con, self.deductor_id, text) if text.strip()
                else pro_db.list_deductees(self.con, self.deductor_id))
        self.rows = {r["id"]: dict(r) for r in rows}
        self.table.set_rows([
            ((r["name"], r["pan"] or "—", pro_db.DEDUCTEE_TYPE_NAME.get(r["type"], ""),
              "Yes" if r["resident"] else "No"), None, r["id"]) for r in rows])

    def _enter(self, _e=None):
        if len(self.rows) == 1:
            self._pick(next(iter(self.rows)))
        return "break"

    def _pick(self, pid):
        row = self.rows.get(pid)
        if not row:
            return
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        self.on_pick(row)


# ─────────────────────────────────────────────────────────────────────────────
class TdsEntryPage(ctk.CTkFrame):
    def __init__(self, master, con, deductor, on_back=None):
        super().__init__(master, fg_color="transparent")
        self.con, self.deductor = con, deductor
        self.on_back = on_back or (lambda: None)
        self.editing_id = None
        self.deductee = None
        self.code_map = {}
        self.rows = {}
        self.w = {}
        self._paid_last = ""

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=(16, 6))
        T.title(head, "TDS / TCS Entry",
                f"Payments by {deductor['name']} (TAN {deductor['tan']}). The rate is "
                "suggested from Payment Codes and the deductee's PAN and certificate."
                ).pack(side="left")
        self.msg = ctk.CTkLabel(head, text="", font=T.f(12), text_color=T.MUTED)
        self.msg.pack(side="right", anchor="s")

        split = ctk.CTkFrame(self, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=20, pady=(2, 16))
        split.grid_columnconfigure(0, weight=3, uniform="t")
        split.grid_columnconfigure(1, weight=2, uniform="t")
        split.grid_rowconfigure(0, weight=1)

        # left: period filter + list + totals
        left = ctk.CTkFrame(split, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        bar = ctk.CTkFrame(left, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        years = pro_db.tax_years_available()
        self.year_menu = T.option_menu(bar, years, width=120)
        self.year_menu.pack(side="left")
        self.year_menu.set(years[0])
        self.year_menu.configure(command=lambda _v: self.refresh_list())
        self.q_menu = T.option_menu(bar, QUARTERS, width=160)
        self.q_menu.pack(side="left", padx=8)
        self.q_menu.set(ALL_Q)
        self.q_menu.configure(command=lambda _v: self.refresh_list())
        self.search = T.entry(bar, "Search deductee, PAN or code…")
        self.search.pack(side="left", fill="x", expand=True)
        inner(self.search).bind("<KeyRelease>", lambda _e: self.refresh_list())

        self.table = DataTable(
            left, [("date", "Paid / credited", 110, "w"), ("dee", "Deductee", 230, "w"),
                   ("code", "Code", 70, "w"), ("amt", "Amount ₹", 120, "e"),
                   ("rate", "Rate", 60, "e"), ("tax", "Tax ₹", 110, "e")],
            height=16, empty_text="No entries for this period yet.\n"
                                  "Add one using the form on the right.")
        self.table.pack(fill="both", expand=True)
        self.table.on_open(self._edit)
        self.totals = ctk.CTkLabel(left, text="", font=T.f(12, "bold"), text_color=T.TEXT,
                                   anchor="w")
        self.totals.pack(fill="x", pady=(8, 0))

        # right: scrollable form + pinned buttons
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

    def _note(self, parent):
        r = self._row(parent, "")
        lbl = ctk.CTkLabel(r, text="", font=T.f(11), text_color=T.MUTED, anchor="w",
                           justify="left", wraplength=380)
        lbl.pack(side="left")
        return lbl

    def _build_buttons(self, card):
        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=18, pady=(8, 12))
        ctk.CTkFrame(card, height=1, fg_color=T.BORDER).pack(side="bottom", fill="x", padx=12)
        self.save_btn = T.button(bar, "Add entry", self.save, width=150)
        self.save_btn.pack(side="left", padx=(0, 8))
        T.button(bar, "New", lambda: self._clear_form(), width=90, **LIGHT).pack(
            side="left", padx=(0, 8))
        self.del_btn = T.button(bar, "Delete", self.delete, width=90, fg_color=T.DANGER,
                                hover_color="#A32F23")
        self.del_btn.pack(side="left")

    def _build_form(self, p):
        ctk.CTkLabel(p, text="Entry details", font=T.f(16, "bold")).pack(
            anchor="w", padx=18, pady=(14, 6))

        r = self._row(p, "Deductee *")
        self.dee_btn = T.button(r, "Choose…", self.choose_deductee, width=100, **LIGHT)
        self.dee_btn.pack(side="left")
        self.dee_lbl = ctk.CTkLabel(r, text="", font=T.f(13, "bold"), anchor="w")
        self.dee_lbl.pack(side="left", padx=10)
        self.dee_info = self._note(p)

        r = self._row(p, "Payment code *")
        self.code_menu = T.option_menu(r, [CHOOSE], width=360)
        self.code_menu.pack(side="left")
        self.code_menu.configure(command=self._code_changed)
        self.code_info = self._note(p)

        r = self._row(p, "Paid / credited on *")
        self.w["paid_on"] = T.entry(r, "DD-MM-YYYY", width=140)
        self.w["paid_on"].pack(side="left")
        ctk.CTkLabel(r, text="earlier of payment or credit", font=T.f(11),
                     text_color=T.MUTED).pack(side="left", padx=(8, 0))
        r = self._row(p, "Deducted on")
        self.w["deducted_on"] = T.entry(r, "DD-MM-YYYY", width=140)
        self.w["deducted_on"].pack(side="left")
        r = self._row(p, "Amount ₹ *")
        self.w["amount"] = T.entry(r, width=160)
        self.w["amount"].pack(side="left")

        ctk.CTkLabel(p, text="Tax", font=T.f(13, "bold"), text_color=T.MUTED).pack(
            anchor="w", padx=18, pady=(10, 2))
        r = self._row(p, "Rate %")
        self.w["rate"] = T.entry(r, width=90)
        self.w["rate"].pack(side="left")
        self.rate_hint = ctk.CTkLabel(r, text="", font=T.f(11), text_color=T.MUTED,
                                      anchor="w", justify="left", wraplength=270)
        self.rate_hint.pack(side="left", padx=(8, 0))
        r = self._row(p, "Tax deducted ₹")
        self.w["tds"] = T.entry(r, width=140)
        self.w["tds"].pack(side="left")
        r = self._row(p, "Surcharge / Cess ₹")
        self.w["surcharge"] = T.entry(r, "Surcharge", width=110)
        self.w["surcharge"].pack(side="left")
        self.w["cess"] = T.entry(r, "Cess", width=110)
        self.w["cess"].pack(side="left", padx=(8, 0))
        r = self._row(p, "Total tax ₹")
        self.total_lbl = ctk.CTkLabel(r, text="0", font=T.f(14, "bold"), anchor="w")
        self.total_lbl.pack(side="left")
        r = self._row(p, "Reason")
        self.reason_menu = T.option_menu(r, REASON_VALUES, width=360)
        self.reason_menu.pack(side="left")
        r = self._row(p, "Certificate No.")
        self.w["cert_no"] = T.entry(r, "if lower / nil rate", width=200)
        self.w["cert_no"].pack(side="left")
        r = self._row(p, "Notes")
        self.w["notes"] = T.entry(r, width=360)
        self.w["notes"].pack(side="left")
        ctk.CTkFrame(p, height=10, fg_color="transparent").pack(fill="x")

        # live updates
        inner(self.w["paid_on"]).bind("<FocusOut>", lambda _e: self._paid_changed(), add="+")
        for key in ("amount", "rate"):
            inner(self.w[key]).bind("<KeyRelease>", lambda _e: self._recalc(), add="+")
        for key in ("tds", "surcharge", "cess"):
            inner(self.w[key]).bind("<KeyRelease>", lambda _e: self._update_total(), add="+")

        order = [self.w[k] for k in ("paid_on", "deducted_on", "amount", "rate", "tds",
                                     "surcharge", "cess", "cert_no", "notes")]
        chain_enter(order, self.save)

    # ── small helpers ─────────────────────────────────────────────────────────
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

    def _num(self, key):
        try:
            return pro_db.to_num(self.w[key].get())
        except ValueError:
            return None

    def _date(self, key):
        try:
            return pro_db.parse_date(self.w[key].get())
        except ValueError:
            return None

    def _reset_borders(self):
        for w in self.w.values():
            w.configure(border_color=T.BORDER)

    def _code_row(self):
        return self.code_map.get(self.code_menu.get())

    def _label_for_id(self, pid):
        if pid is None:
            return None
        for label, row in self.code_map.items():
            if row["id"] == pid:
                return label
        return None

    def _quarter(self):
        q = self.q_menu.get()
        return None if q == ALL_Q else q[:2]

    # ── deductee + codes ──────────────────────────────────────────────────────
    def choose_deductee(self):
        DeducteePicker(self, self.con, self.deductor["id"], self._picked_deductee)

    def _picked_deductee(self, row):
        self._set_deductee(row)
        if self._code_row():
            self._code_changed(self.code_menu.get())
        focus_later(self.w["paid_on"])

    def _set_deductee(self, row):
        self.deductee = dict(row)
        self.dee_lbl.configure(text=f"{row['name']}  ({row['pan'] or 'no PAN'})")
        info = [pro_db.DEDUCTEE_TYPE_NAME.get(row["type"], ""),
                "Resident" if row["resident"] else "Non-resident (Form 144)",
                "PAN " + pro_db.PAN_STATUS_NAME.get(row["pan_status"], "")]
        if (row["lower_cert_no"] or "").strip():
            info.append(f"Lower-deduction cert {row['lower_cert_no']} @ "
                        f"{row['lower_rate'] or '?'}%")
        self.dee_info.configure(text="  ·  ".join(i for i in info if i))
        prev = self._code_row()
        self._load_codes(keep_id=prev["id"] if prev else None)

    def _load_codes(self, keep_id=None):
        resident = self.deductee is None or self.deductee["resident"]
        form = "140" if resident else "144"
        rows = pro_db.list_pay_codes(self.con, form=form, include_inactive=False)
        self.code_map = {}
        for r in rows:
            self._add_code(r)
        if keep_id and self._label_for_id(keep_id) is None:
            old = pro_db.get_pay_code(self.con, keep_id)
            if old and old["form"] == form:          # inactive code on an old entry
                self._add_code(old, suffix="  (off)")
        self.code_menu.configure(values=[CHOOSE] + list(self.code_map))
        self.code_menu.set(self._label_for_id(keep_id) or CHOOSE)

    def _add_code(self, r, suffix=""):
        label = f"{r['code'] or '—'} · {r['old_section'] or ''} · {r['nature']}"
        if len(label) > 64:
            label = label[:63] + "…"
        label += suffix
        if label in self.code_map:
            label += f"  #{r['id']}"
        self.code_map[label] = dict(r)

    def _code_changed(self, label):
        row = self.code_map.get(label)
        if not row:
            self.code_info.configure(text="")
            return
        if self.deductee:
            alt = pro_db.contractor_code_for(self.con, row, self.deductee)
            if alt:
                alt_label = self._label_for_id(alt["id"])
                if alt_label:
                    self.code_menu.set(alt_label)
                    self._say(f"Switched to code {alt['code']}: it matches the deductee's type.",
                              T.OK)
        self._suggest_rate()
        self._update_threshold_info()

    # ── rate / amounts ────────────────────────────────────────────────────────
    def _paid_changed(self):
        text = self.w["paid_on"].get().strip()
        if text == self._paid_last:
            return
        self._paid_last = text
        d = self._date("paid_on")
        if d and not self.w["deducted_on"].get().strip():
            self._set(self.w["deducted_on"], d.strftime("%d-%m-%Y"))
        self._suggest_rate()
        self._update_threshold_info()

    def _suggest_rate(self):
        row = self._code_row()
        if not (self.deductee and row):
            return
        on = self._date("paid_on") or datetime.date.today()
        rate, reason, cert, note = pro_db.suggest_rate(self.deductee, row, on)
        if rate is None:
            self.rate_hint.configure(text=note, text_color=T.DANGER)
            return
        self._set(self.w["rate"], _num_text(rate))
        self.reason_menu.set(pro_db.TDS_REASON_NAME.get(reason, REASON_VALUES[0]))
        self._set(self.w["cert_no"], cert)
        self.rate_hint.configure(text=note, text_color=T.MUTED)
        self._recalc()

    def _recalc(self):
        amt, rate = self._num("amount"), self._num("rate")
        if amt is not None and rate is not None:
            self._set(self.w["tds"], _num_text(pro_db.round_rupee(amt * rate / 100)))
        self._update_total()
        self._update_threshold_info()

    def _update_total(self):
        total = sum(self._num(k) or 0 for k in ("tds", "surcharge", "cess"))
        self.total_lbl.configure(text=f"₹ {_inr(total) or '0'}")

    def _update_threshold_info(self):
        row = self._code_row()
        if not (self.deductee and row):
            self.code_info.configure(text="")
            return
        parts = []
        if row["th_single"]:
            parts.append(f"₹{_inr(row['th_single'])} per payment")
        if row["th_year"]:
            parts.append(f"₹{_inr(row['th_year'])} per year")
        if row["th_month"]:
            parts.append(f"₹{_inr(row['th_month'])} per month")
        text = ("Threshold: " + ", ".join(parts)) if parts else "No threshold"
        paid = self._date("paid_on")
        if paid:
            ty = pro_db.tax_year_of(paid)
            amt = self._num("amount") or 0
            total = pro_db.year_total(self.con, self.deductor["id"], self.deductee["id"],
                                      row["id"], ty, self.editing_id) + amt
            text += f".  This payee, this code, TY {ty}: ₹{_inr(total) or '0'} incl. this entry."
            if row["th_year"] and total <= row["th_year"] and \
                    (not row["th_single"] or amt <= row["th_single"]):
                text += "  Below threshold so far — check whether TDS applies."
        self.code_info.configure(text=text)

    # ── form state ────────────────────────────────────────────────────────────
    def _clear_form(self, keep=False):
        """keep=True: after adding an entry, keep deductee / code / dates / rate
        so the next payment to the same payee is quick to enter."""
        self.editing_id = None
        self._reset_borders()
        if keep:
            for key in ("amount", "tds", "surcharge", "cess", "notes"):
                self._set(self.w[key], "")
        else:
            self.deductee = None
            self.dee_lbl.configure(text="")
            self.dee_info.configure(text="No deductee chosen.")
            for w in self.w.values():
                self._set(w, "")
            self._load_codes()
            self.reason_menu.set(REASON_VALUES[0])
            self.rate_hint.configure(text="")
            self.code_info.configure(text="")
            self._paid_last = ""
        self._update_total()
        self.save_btn.configure(text="Add entry")
        self.del_btn.configure(state="disabled")
        focus_later(self.w["amount"] if keep else self.dee_btn)

    def _fill(self, row):
        self.editing_id = row["id"]
        self._reset_borders()
        dee = pro_db.get_deductee(self.con, row["deductee_id"])
        self._set_deductee(dee)
        self._load_codes(keep_id=row["pay_code_id"])
        self._set(self.w["paid_on"], pro_db.date_text(row["paid_on"]))
        self._set(self.w["deducted_on"], pro_db.date_text(row["deducted_on"]))
        self._paid_last = self.w["paid_on"].get().strip()
        for key in ("amount", "rate", "tds", "surcharge", "cess"):
            v = row[key]
            self._set(self.w[key], "" if (key in ("surcharge", "cess") and not v)
                      else _num_text(v))
        self._set(self.w["cert_no"], row["cert_no"])
        self._set(self.w["notes"], row["notes"])
        self.reason_menu.set(pro_db.TDS_REASON_NAME.get(row["reason"] or "", REASON_VALUES[0]))
        self.rate_hint.configure(text="")
        self._update_total()
        self._update_threshold_info()
        self.save_btn.configure(text="Save changes")
        self.del_btn.configure(state="normal")

    def _collect(self):
        row = self._code_row()
        d = {k: w.get() for k, w in self.w.items()}
        d.update(deductee_id=self.deductee["id"] if self.deductee else None,
                 pay_code_id=row["id"] if row else None,
                 reason=REASON_CODE.get(self.reason_menu.get(), ""))
        return d

    # ── list ──────────────────────────────────────────────────────────────────
    def refresh_list(self):
        rows = pro_db.list_tds_entries(self.con, self.deductor["id"], self.year_menu.get(),
                                       self._quarter(), self.search.get())
        self.rows = {r["id"]: dict(r) for r in rows}
        self.table.set_rows([
            ((pro_db.date_text(r["paid_on"]), r["dee_name"],
              r["pay_code"] or r["old_section"] or "—", _inr(r["amount"]),
              f"{_num_text(r['rate'])}%", _inr(r["total"]) or "0"), None, r["id"])
            for r in rows])
        amt = sum(r["amount"] for r in rows)
        tax = sum(r["total"] for r in rows)
        self.totals.configure(text=f"{len(rows)} entr{'y' if len(rows) == 1 else 'ies'}   ·   "
                                   f"Amount ₹{_inr(amt) or '0'}   ·   Tax ₹{_inr(tax) or '0'}")

    # ── actions ───────────────────────────────────────────────────────────────
    def _edit(self, eid):
        row = self.rows.get(eid)
        if row:
            self._fill(row)

    def save(self):
        d = self._collect()
        self._reset_borders()
        try:
            eid = pro_db.save_tds_entry(self.con, self.deductor["id"], d, self.editing_id)
        except ValueError as e:
            arg = e.args[0] if e.args else {}
            if isinstance(arg, dict):
                for key in arg:
                    w = self.w.get(key)
                    if w is not None:
                        w.configure(border_color=T.DANGER)
                key, err = next(iter(arg.items()))
                self._say(f"{LABEL_OF.get(key, key)}: {err}", T.DANGER)
            else:
                self._say(str(e), T.DANGER)
            return
        was_edit = self.editing_id is not None
        saved = pro_db.get_tds_entry(self.con, eid)
        if saved and saved["tax_year"] in pro_db.tax_years_available():
            self.year_menu.set(saved["tax_year"])
        self.refresh_list()
        if was_edit and eid in self.rows:
            self._fill(self.rows[eid])
        else:
            self._clear_form(keep=True)
        self._say("Saved ✓", T.OK)

    def delete(self):
        row = self.rows.get(self.editing_id)
        if not row:
            return
        if not messagebox.askyesno(
                "Delete entry",
                f"Delete this entry?\n\n{row['dee_name']} · ₹{_inr(row['amount'])} on "
                f"{pro_db.date_text(row['paid_on'])}", parent=self):
            return
        pro_db.delete_tds_entry(self.con, row["id"])
        self.refresh_list()
        self._clear_form()
        self._say("Deleted.")

    def on_escape(self):
        if self.editing_id is not None or self.deductee is not None:
            self._clear_form()
            return True
        return False