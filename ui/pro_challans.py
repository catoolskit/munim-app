"""MUNIM Pro — Challans (TDS Pro), ITNS 281N.
Add / edit: tick the TDS entries the challan paid → tax, surcharge and cess fill in per
payment code; type interest, fee and others per code; then the deposit details.
Challans tab: list, open, export. 'Check with CSI' goes live once the CSI layout is confirmed."""
import csv
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ui import theme as T
from ui.ux import focus_later
from ui.widgets import DataTable
from ui.pro_common import bind_wheel, attach_date_mask
from ui.pro_paycodes import section_text
from ui.pro_tdsentry import _inr
from db import pro_db
from utils import validate as V

LIGHT = dict(fg_color="#E7ECF5", text_color=T.TEXT, hover_color="#DCE3F0")
FORM_CHOICES = [(c, pro_db.PAY_FORM_NAME[c]) for c in pro_db.CHALLAN_FORMS]
FORM_VALUES = [n for _c, n in FORM_CHOICES]
FORM_CODE = {n: c for c, n in FORM_CHOICES}
MAJOR_VALUES = [n for _c, n in pro_db.CHALLAN_MAJOR]
MAJOR_CODE = {n: c for c, n in pro_db.CHALLAN_MAJOR}
MINOR_VALUES = [n for _c, n in pro_db.CHALLAN_MINOR]
MINOR_CODE = {n: c for c, n in pro_db.CHALLAN_MINOR}
EXTRA = (("interest", "Interest"), ("fee", "Fee"), ("others", "Others"))
TAB_EDIT, TAB_LIST = "Add / edit challan", "Challans"

ENT_COLS = [("", 30), ("Payee", 220), ("Paid on", 95), ("Deducted on", 95),
            ("Amount ₹", 110), ("Tax ₹", 90), ("PAN", 110), ("Last date", 105),
            ("Section", 130), ("Code", 60)]
CODE_COLS = [("Code", 60), ("Section", 130), ("Nature of payment", 260), ("Entries", 60),
             ("Tax ₹", 100), ("Surcharge ₹", 100), ("Cess ₹", 90), ("Interest ₹", 100),
             ("Fee ₹", 100), ("Others ₹", 100), ("Total ₹", 110)]

LABEL_OF = {
    "tax_year": "Tax year", "form": "Return form", "major_head": "Major head",
    "minor_head": "Minor head", "deposit_date": "Deposited on", "bsr_code": "BSR code",
    "serial_no": "Challan serial No.", "entries": "TDS entries", "lines": "Payment codes",
}


def _short(text, n):
    text = text or ""
    return text if len(text) <= n else text[:n - 1] + "…"


def _num(v):
    try:
        return pro_db.to_num(v) or 0.0
    except ValueError:
        return 0.0


class ChallansPage(ctk.CTkFrame):
    def __init__(self, master, con, deductor, on_back=None):
        super().__init__(master, fg_color="transparent")
        self.con, self.deductor = con, deductor
        self.on_back = on_back or (lambda: None)
        self.editing_id = None
        self.cands, self.tick = {}, {}
        self.extra_w, self.extra_vals = {}, {}
        self.row_total_lbl, self._groups = {}, {}
        self.list_rows = {}
        self.w = {}

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=(16, 4))
        T.title(head, "Challans (ITNS 281N)",
                f"Tax deposited by {deductor['name']} (TAN {deductor['tan']}). Tick the TDS "
                "entries a challan paid; tax fills in per payment code.").pack(side="left")
        self.msg = ctk.CTkLabel(head, text="", font=T.f(12), text_color=T.MUTED)
        self.msg.pack(side="right", anchor="s")

        ybar = ctk.CTkFrame(self, fg_color="transparent")
        ybar.pack(fill="x", padx=24, pady=(0, 4))
        ctk.CTkLabel(ybar, text="Tax year", font=T.f(12), text_color=T.MUTED).pack(side="left")
        years = pro_db.tax_years_available()
        self.year_menu = T.option_menu(ybar, years, width=120)
        self.year_menu.pack(side="left", padx=8)
        self.year_menu.set(years[0])
        self.year_menu.configure(command=lambda _v: self._year_changed())

        self.tabs = ctk.CTkTabview(self, fg_color=T.CARD, border_width=1,
                                   border_color=T.BORDER, segmented_button_fg_color=T.BG,
                                   segmented_button_selected_color=T.ACCENT,
                                   segmented_button_selected_hover_color=T.ACCENT_HOVER)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        self.tabs.add(TAB_EDIT)
        self.tabs.add(TAB_LIST)
        self._build_editor(self.tabs.tab(TAB_EDIT))
        self._build_list(self.tabs.tab(TAB_LIST))

        self.refresh_list()
        self._new()

    # ── editor layout ─────────────────────────────────────────────────────────
    def _section(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=T.f(14, "bold")).pack(
            anchor="w", padx=12, pady=(12, 4))

    def _build_editor(self, tab):
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=12, pady=(6, 8))
        self.save_btn = T.button(bar, "Save challan", self.save, width=160)
        self.save_btn.pack(side="left", padx=(0, 8))
        T.button(bar, "New", self._new, width=90, **LIGHT).pack(side="left", padx=(0, 8))
        self.del_btn = T.button(bar, "Delete", self.delete, width=90, fg_color=T.DANGER,
                                hover_color="#A32F23")
        self.del_btn.pack(side="left")
        self.ed_title = ctk.CTkLabel(bar, text="", font=T.f(12, "bold"), text_color=T.MUTED)
        self.ed_title.pack(side="right")

        body = ctk.CTkScrollableFrame(tab, fg_color="transparent", corner_radius=0)
        body.pack(fill="both", expand=True)
        bind_wheel(body)

        # 1 — entries
        self._section(body, "1.  Tick the TDS entries this challan paid")
        f = ctk.CTkFrame(body, fg_color="transparent")
        f.pack(fill="x", padx=12, pady=(0, 6))
        self.form_menu = T.option_menu(f, FORM_VALUES, width=280)
        self.form_menu.pack(side="left")
        self.form_menu.configure(command=lambda _v: self._load_candidates())
        self.major_menu = T.option_menu(f, MAJOR_VALUES, width=330)
        self.major_menu.pack(side="left", padx=8)
        self.major_menu.configure(command=lambda _v: self._load_candidates())
        self.skip_bad = ctk.CTkCheckBox(f, text="Skip entries without a valid PAN",
                                        font=T.f(12), command=self._load_candidates)
        self.skip_bad.pack(side="left", padx=8)
        for text, mode in (("Select all", "all"), ("Inverse", "invert"),
                           ("Unselect all", "none")):
            T.button(f, text, lambda m=mode: self._select(m), width=100, **LIGHT).pack(
                side="left", padx=(6, 0))
        self.sel_lbl = ctk.CTkLabel(f, text="", font=T.f(12, "bold"))
        self.sel_lbl.pack(side="right")

        self.ent_box = ctk.CTkScrollableFrame(body, height=230, fg_color=T.BG,
                                              border_width=1, border_color=T.BORDER)
        self.ent_box.pack(fill="x", padx=12)
        bind_wheel(self.ent_box)

        # 2 — codes
        self._section(body, "2.  Payment codes on this challan  (tax fills in from the ticked "
                            "entries; type interest, fee and others)")
        self.codes_box = ctk.CTkFrame(body, fg_color=T.BG, border_width=1, border_color=T.BORDER)
        self.codes_box.pack(fill="x", padx=12)
        self.grand_lbl = ctk.CTkLabel(body, text="", font=T.f(14, "bold"), anchor="w")
        self.grand_lbl.pack(fill="x", padx=14, pady=(6, 0))

        # 3 — deposit details
        self._section(body, "3.  Deposit details")
        g = ctk.CTkFrame(body, fg_color="transparent")
        g.pack(fill="x", padx=12, pady=(0, 10))

        def lab(text, r, c):
            lbl = ctk.CTkLabel(g, text=text, font=T.f(12), text_color=T.MUTED, width=170,
                               anchor="e")
            lbl.grid(row=r, column=c, sticky="e", padx=(0, 10), pady=4)
            return lbl

        lab("Deposited on *", 0, 0)
        self.w["deposit_date"] = T.entry(g, "DD/MM/YYYY", width=150)
        self.w["deposit_date"].grid(row=0, column=1, sticky="w", pady=4)
        lab("Minor head", 0, 2)
        self.minor_menu = T.option_menu(g, MINOR_VALUES, width=330)
        self.minor_menu.grid(row=0, column=3, sticky="w", pady=4)

        self.bsr_lbl = lab("BSR code *", 1, 0)
        self.w["bsr_code"] = T.entry(g, "7 digits", width=150)
        self.w["bsr_code"].grid(row=1, column=1, sticky="w", pady=4)
        lab("CRN", 1, 2)
        self.w["crn"] = T.entry(g, "optional", width=240)
        self.w["crn"].grid(row=1, column=3, sticky="w", pady=4)

        self.serial_lbl = lab("Challan serial No. *", 2, 0)
        self.w["serial_no"] = T.entry(g, "5 digits", width=150)
        self.w["serial_no"].grid(row=2, column=1, sticky="w", pady=4)
        self.book_cb = ctk.CTkCheckBox(g, text="Book entry (government — transfer voucher)",
                                       font=T.f(12), command=self._book_changed)
        self.book_cb.grid(row=2, column=3, sticky="w", pady=4)

        lab("Notes", 3, 0)
        self.w["notes"] = T.entry(g, width=420)
        self.w["notes"].grid(row=3, column=1, columnspan=3, sticky="w", pady=4)

        attach_date_mask(self.w["deposit_date"], self._year_for)
        from ui.ux import inner
        inner(self.w["deposit_date"]).bind("<FocusOut>",
                                           lambda _e: self._load_candidates(), add="+")

    # ── list layout ───────────────────────────────────────────────────────────
    def _build_list(self, tab):
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=12, pady=(6, 8))
        self.list_totals = ctk.CTkLabel(bar, text="", font=T.f(12, "bold"), anchor="w")
        self.list_totals.pack(side="left")
        T.button(bar, "Check with CSI (soon)", lambda: None, width=190, state="disabled",
                 **LIGHT).pack(side="right", padx=(8, 0))
        T.button(bar, "Export to Excel", self.export, width=150, **LIGHT).pack(side="right")

        ctk.CTkLabel(tab, text="Double-click a challan to open it for editing.", font=T.f(11),
                     text_color=T.MUTED).pack(anchor="w", padx=14, pady=(6, 2))
        self.table = DataTable(
            tab, [("date", "Deposited", 100, "w"), ("serial", "Serial", 80, "w"),
                  ("bsr", "BSR code", 90, "w"), ("form", "Form", 60, "w"),
                  ("minor", "Minor", 60, "w"), ("codes", "Codes", 220, "w"),
                  ("amt", "Amount ₹", 120, "e"), ("lnk", "Entries tax ₹", 120, "e"),
                  ("n", "Entries", 70, "e"), ("csi", "CSI", 90, "w")],
            height=16, empty_text="No challans for this tax year yet.\n"
                                  f"Use '{TAB_EDIT}'.")
        self.table.pack(fill="both", expand=True, padx=12)
        self.table.on_open(self._open_challan)

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

    def _year_for(self, _day, month):
        start = int(self.year_menu.get()[:4])
        return start if month >= 4 else start + 1

    def _dep_date(self):
        try:
            return pro_db.parse_date(self.w["deposit_date"].get())
        except ValueError:
            return None

    def _reset_borders(self):
        for w in self.w.values():
            w.configure(border_color=T.BORDER)

    def _book_changed(self):
        if self.book_cb.get():
            self.bsr_lbl.configure(text="Form 137 receipt No. *")
            self.serial_lbl.configure(text="DDO serial No. *")
        else:
            self.bsr_lbl.configure(text="BSR code *")
            self.serial_lbl.configure(text="Challan serial No. *")

    def _year_changed(self):
        self.refresh_list()
        self._new()

    # ── entries list ──────────────────────────────────────────────────────────
    def _selected_ids(self):
        return [i for i, v in self.tick.items() if v.get()]

    def _load_candidates(self, selected=None):
        selected = set(self._selected_ids() if selected is None else selected)
        rows = pro_db.challan_candidates(
            self.con, self.deductor["id"], self.year_menu.get(),
            FORM_CODE[self.form_menu.get()], MAJOR_CODE[self.major_menu.get()], self.editing_id)
        if self.skip_bad.get():
            rows = [r for r in rows if r["pan_status"] == "active" and V.is_pan(r["dee_pan"])]
        self.cands = {r["id"]: dict(r) for r in rows}

        for w in self.ent_box.winfo_children():
            w.destroy()
        self.tick = {}
        for c, (h, wd) in enumerate(ENT_COLS):
            ctk.CTkLabel(self.ent_box, text=h, font=T.f(11, "bold"), text_color=T.MUTED,
                         width=wd, anchor="w").grid(row=0, column=c, padx=(0, 6), sticky="w")
        if not rows:
            ctk.CTkLabel(self.ent_box, text="No unlinked TDS entries for this tax year, form and "
                         "major head.", font=T.f(12), text_color=T.MUTED).grid(
                row=1, column=0, columnspan=len(ENT_COLS), sticky="w", pady=8)
        dep = self._dep_date()
        for i, r in enumerate(rows, start=1):
            v = ctk.IntVar(value=1 if r["id"] in selected else 0)
            self.tick[r["id"]] = v
            ctk.CTkCheckBox(self.ent_box, text="", width=24, variable=v,
                            command=self._sel_changed).grid(row=i, column=0, sticky="w")
            ded = pro_db.parse_date(r["deducted_on"] or r["paid_on"])
            due = pro_db.deposit_due_date(ded)
            late = bool(dep and due and dep > due)
            pan_ok = r["pan_status"] == "active" and V.is_pan(r["dee_pan"])
            vals = [_short(r["dee_name"], 30), pro_db.date_text(r["paid_on"]),
                    pro_db.date_text(r["deducted_on"]), _inr(r["amount"]),
                    _inr(r["total"]) or "0", r["dee_pan"] or "—",
                    pro_db.date_text(due) + ("  ⚠" if late else ""),
                    section_text(r), r["pay_code"] or "—"]
            for c, (val, (_h, wd)) in enumerate(zip(vals, ENT_COLS[1:]), start=1):
                color = T.TEXT
                if (c == 6 and not pan_ok) or (c == 7 and late):
                    color = T.DANGER
                ctk.CTkLabel(self.ent_box, text=val, font=T.f(12), text_color=color, width=wd,
                             anchor="w").grid(row=i, column=c, padx=(0, 6), sticky="w")
        self._sel_changed()

    def _select(self, mode):
        for v in self.tick.values():
            v.set(1 if mode == "all" else 0 if mode == "none" else 1 - v.get())
        self._sel_changed()

    def _sel_changed(self):
        ids = self._selected_ids()
        tax = sum(self.cands[i]["total"] or 0 for i in ids if i in self.cands)
        self.sel_lbl.configure(text=f"{len(ids)} selected  ·  Tax ₹{_inr(tax) or '0'}")
        self._render_codes()

    # ── codes table ───────────────────────────────────────────────────────────
    def _sync_extras(self):
        for pid, ws in self.extra_w.items():
            try:
                self.extra_vals[pid] = {f: e.get() for f, e in ws.items()}
            except Exception:
                pass

    def _render_codes(self):
        self._sync_extras()
        for w in self.codes_box.winfo_children():
            w.destroy()
        self.extra_w, self.row_total_lbl = {}, {}
        groups = {}
        for i in self._selected_ids():
            c = self.cands.get(i)
            if not c:
                continue
            g = groups.setdefault(c["pay_code_id"], {"row": c, "n": 0, "tax": 0.0,
                                                     "surcharge": 0.0, "cess": 0.0})
            g["n"] += 1
            g["tax"] += c["tds"] or 0
            g["surcharge"] += c["surcharge"] or 0
            g["cess"] += c["cess"] or 0
        self._groups = groups

        for c, (h, wd) in enumerate(CODE_COLS):
            ctk.CTkLabel(self.codes_box, text=h, font=T.f(11, "bold"), text_color=T.MUTED,
                         width=wd, anchor="w").grid(row=0, column=c, padx=(8 if c == 0 else 0, 6),
                                                    pady=(6, 2), sticky="w")
        if not groups:
            ctk.CTkLabel(self.codes_box, text="Tick at least one entry above.", font=T.f(12),
                         text_color=T.MUTED).grid(row=1, column=0, columnspan=len(CODE_COLS),
                                                  sticky="w", padx=8, pady=(2, 8))
        ordered = sorted(groups.items(), key=lambda kv: kv[1]["row"]["pay_code"] or "")
        for i, (pid, g) in enumerate(ordered, start=1):
            r = g["row"]
            vals = [r["pay_code"] or "—", section_text(r), _short(r["nature"], 38), str(g["n"]),
                    _inr(g["tax"]) or "0", _inr(g["surcharge"]) or "0", _inr(g["cess"]) or "0"]
            for c, val in enumerate(vals):
                ctk.CTkLabel(self.codes_box, text=val, font=T.f(12), width=CODE_COLS[c][1],
                             anchor="w").grid(row=i, column=c, padx=(8 if c == 0 else 0, 6),
                                              pady=2, sticky="w")
            ws = {}
            for k, (f, _n) in enumerate(EXTRA):
                e = T.entry(self.codes_box, width=CODE_COLS[7 + k][1] - 6)
                e.grid(row=i, column=7 + k, padx=(0, 6), pady=2, sticky="w")
                self._set(e, self.extra_vals.get(pid, {}).get(f, ""))
                from ui.ux import inner
                inner(e).bind("<KeyRelease>", lambda _e: self._update_grand(), add="+")
                ws[f] = e
            self.extra_w[pid] = ws
            lbl = ctk.CTkLabel(self.codes_box, text="", font=T.f(12, "bold"),
                               width=CODE_COLS[10][1], anchor="w")
            lbl.grid(row=i, column=10, padx=(0, 6), pady=2, sticky="w")
            self.row_total_lbl[pid] = lbl
        if len(groups) > pro_db.MAX_CHALLAN_CODES:
            ctk.CTkLabel(self.codes_box, text=f"A challan can carry at most "
                         f"{pro_db.MAX_CHALLAN_CODES} payment codes — untick some entries.",
                         font=T.f(12, "bold"), text_color=T.DANGER).grid(
                row=len(groups) + 1, column=0, columnspan=len(CODE_COLS), sticky="w", padx=8)
        ctk.CTkFrame(self.codes_box, height=6, fg_color="transparent").grid(
            row=len(groups) + 2, column=0)
        self._update_grand()

    def _update_grand(self):
        self._sync_extras()
        totals = {k: 0.0 for k in pro_db.CHALLAN_LINE_AMOUNTS}
        for pid, g in self._groups.items():
            ex = {f: _num(self.extra_vals.get(pid, {}).get(f)) for f, _n in EXTRA}
            row_total = g["tax"] + g["surcharge"] + g["cess"] + sum(ex.values())
            lbl = self.row_total_lbl.get(pid)
            if lbl:
                lbl.configure(text=_inr(row_total) or "0")
            for k in ("tax", "surcharge", "cess"):
                totals[k] += g[k]
            for f in ex:
                totals[f] += ex[f]
        grand = sum(totals.values())
        names = (("tax", "Tax"), ("surcharge", "Surcharge"), ("cess", "Cess"),
                 ("interest", "Interest"), ("fee", "Fee"), ("others", "Others"))
        parts = [f"{n} ₹{_inr(totals[k])}" for k, n in names if totals[k]]
        self.grand_lbl.configure(text=f"Challan total ₹{_inr(grand) or '0'}" +
                                 (f"     ({'  ·  '.join(parts)})" if parts else ""))

    # ── form state ────────────────────────────────────────────────────────────
    def _new(self):
        self.editing_id = None
        self._reset_borders()
        self.form_menu.set(FORM_VALUES[0])
        self.major_menu.set(MAJOR_VALUES[0])
        self.minor_menu.set(MINOR_VALUES[0])
        self.book_cb.deselect()
        self._book_changed()
        for w in self.w.values():
            self._set(w, "")
        self.extra_vals, self.extra_w = {}, {}
        self.tick = {}
        self._load_candidates(selected=[])
        self.save_btn.configure(text="Save challan")
        self.del_btn.configure(state="disabled")
        self.ed_title.configure(text="New challan")
        self.tabs.set(TAB_EDIT)
        focus_later(self.w["deposit_date"])

    def _open_challan(self, cid):
        ch = pro_db.get_challan(self.con, cid)
        if not ch:
            return
        if ch["tax_year"] != self.year_menu.get() and \
                ch["tax_year"] in pro_db.tax_years_available():
            self.year_menu.set(ch["tax_year"])
            self.refresh_list()
        self.editing_id = ch["id"]
        self._reset_borders()
        self.form_menu.set(pro_db.PAY_FORM_NAME.get(ch["form"], FORM_VALUES[0]))
        self.major_menu.set(pro_db.CHALLAN_MAJOR_NAME.get(ch["major_head"], MAJOR_VALUES[0]))
        self.minor_menu.set(pro_db.CHALLAN_MINOR_NAME.get(ch["minor_head"], MINOR_VALUES[0]))
        self.book_cb.select() if ch["book_entry"] else self.book_cb.deselect()
        self._book_changed()
        self._set(self.w["deposit_date"], pro_db.date_text(ch["deposit_date"]))
        self._set(self.w["bsr_code"], ch["bsr_code"])
        self._set(self.w["serial_no"], ch["serial_no"])
        self._set(self.w["crn"], ch["crn"])
        self._set(self.w["notes"], ch["notes"])
        self.extra_w = {}
        self.extra_vals = {
            ln["pay_code_id"]: {f: (f"{ln[f]:g}" if ln[f] else "") for f, _n in EXTRA}
            for ln in pro_db.challan_lines(self.con, cid)}
        linked = [e["id"] for e in pro_db.linked_entries(self.con, cid)]
        self._load_candidates(selected=linked)
        self.save_btn.configure(text="Save changes")
        self.del_btn.configure(state="normal")
        self.ed_title.configure(text=f"Editing challan {ch['serial_no']} of "
                                     f"{pro_db.date_text(ch['deposit_date'])}")
        self.tabs.set(TAB_EDIT)

    # ── actions ───────────────────────────────────────────────────────────────
    def save(self):
        self._sync_extras()
        ids = self._selected_ids()
        extras = {pid: self.extra_vals.get(pid, {}) for pid in self._groups}
        data = {
            "tax_year": self.year_menu.get(),
            "form": FORM_CODE[self.form_menu.get()],
            "major_head": MAJOR_CODE[self.major_menu.get()],
            "minor_head": MINOR_CODE[self.minor_menu.get()],
            "book_entry": self.book_cb.get(),
            **{k: w.get() for k, w in self.w.items()},
        }
        self._reset_borders()
        try:
            cid = pro_db.save_challan(self.con, self.deductor["id"], data, ids, extras,
                                      self.editing_id)
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
        self.refresh_list()
        self._open_challan(cid)
        self._say(f"Saved ✓  —  {len(ids)} entr{'y' if len(ids) == 1 else 'ies'} linked", T.OK)

    def delete(self):
        if not self.editing_id:
            return
        if not messagebox.askyesno(
                "Delete challan",
                "Delete this challan?\n\nIts TDS entries are not deleted — they become "
                "unlinked and can be ticked on another challan.", parent=self):
            return
        pro_db.delete_challan(self.con, self.editing_id)
        self.refresh_list()
        self._new()
        self._say("Deleted.")

    # ── list ──────────────────────────────────────────────────────────────────
    def refresh_list(self):
        rows = pro_db.list_challans(self.con, self.deductor["id"], self.year_menu.get())
        self.list_rows = {r["id"]: dict(r) for r in rows}
        self.table.set_rows([
            ((pro_db.date_text(r["deposit_date"]),
              r["serial_no"] + ("  (BE)" if r["book_entry"] else ""), r["bsr_code"], r["form"],
              r["minor_head"], r["codes"] or "—", _inr(r["total"]) or "0",
              _inr(r["linked_tax"]) or "0", str(r["linked_count"]), r["csi_status"] or "—"),
             None, r["id"]) for r in rows])
        amt = sum(r["total"] for r in rows)
        n_un, tax_un = pro_db.unlinked_summary(self.con, self.deductor["id"],
                                               self.year_menu.get())
        text = (f"{len(rows)} challan{'s' if len(rows) != 1 else ''}  ·  "
                f"Deposited ₹{_inr(amt) or '0'}")
        if n_un:
            text += f"   ·   {n_un} TDS entr{'y' if n_un == 1 else 'ies'} not yet on a challan " \
                    f"(tax ₹{_inr(tax_un) or '0'})"
        self.list_totals.configure(text=text,
                                   text_color=T.DANGER if n_un else T.TEXT)

    def export(self):
        if not self.list_rows:
            self._say("No challans to export for this tax year.", T.DANGER)
            return
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".csv",
            filetypes=[("CSV — opens in Excel", "*.csv")],
            initialfile=f"Challans_{self.deductor['tan']}_{self.year_menu.get()}.csv")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                wr = csv.writer(fh)
                wr.writerow(["Deposited on", "BSR code", "Serial No.", "Book entry", "Form",
                             "Major head", "Minor head", "Codes", "Amount", "Entries tax",
                             "Entries", "CRN", "CSI"])
                for r in self.list_rows.values():
                    wr.writerow([pro_db.date_text(r["deposit_date"]), r["bsr_code"],
                                 r["serial_no"], "Yes" if r["book_entry"] else "No", r["form"],
                                 r["major_head"], r["minor_head"], r["codes"] or "",
                                 f"{r['total']:.2f}", f"{r['linked_tax']:.2f}",
                                 r["linked_count"], r["crn"] or "", r["csi_status"] or ""])
        except OSError as e:
            self._say(f"Could not save: {e}", T.DANGER)
            return
        self._say("Exported ✓", T.OK)

    def on_escape(self):
        if self.editing_id is not None:
            self._new()
            return True
        return False