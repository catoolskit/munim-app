import os
import subprocess
import sys
from datetime import date
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk
from db import setup as s, reports as r
from ui import theme as T
from ui.widgets import DataTable
from utils import settings
from utils.export import write_table
from utils.fmt import inr, parse_amount, parse_date, disp_date, today_str
from utils.pdf_reports import (generate_trial_balance_pdf, generate_balance_sheet_pdf,
                               generate_pl_pdf)

L, R = "w", "e"


def _amt(v):
    return inr(v) if v else ""


def _open_pdf(path):
    try:
        if sys.platform == "win32":    os.startfile(path)
        elif sys.platform == "darwin": subprocess.Popen(["open", path])
        else:                          subprocess.Popen(["xdg-open", path])
    except Exception as e:
        messagebox.showerror("MUNIM", f"Could not open PDF:\n{e}")


class ReportBase(ctk.CTkFrame):
    title_text, sub_text, with_fy = "", "", True

    def __init__(self, master, con):
        super().__init__(master, fg_color="transparent")
        self.con = con
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=28, pady=(24, 12))
        T.title(head, self.title_text, self.sub_text).pack(side="left")
        self.bar = ctk.CTkFrame(head, fg_color="transparent", width=1, height=1)
        self.bar.pack(side="right")
        if self.with_fy:
            self.fy = T.option_menu(self.bar, s.fy_choices(con), width=120,
                                    command=lambda _v: self.refresh())
            self.fy.set(s.fy_of(date.today()))
            self.fy.pack(side="right", padx=(10, 0))
        if hasattr(self, "export_data") and not getattr(self, "own_controls", False):
            T.button(self.bar, "Export Excel", self.export, width=120,
                     fg_color="#E7ECF5", text_color=T.TEXT,
                     hover_color="#DCE3F0").pack(side="right", padx=(10, 0))

    def export(self):
        try:
            title, headers, rows = self.export_data()
            path = filedialog.asksaveasfilename(
                title="Save report as", defaultextension=".xlsx",
                filetypes=[("Excel file", "*.xlsx")],
                initialfile=f"{title.replace(' ', '_')}.xlsx")
            if not path:
                return
            path = write_table(path, title, headers, rows)
        except Exception as e:
            messagebox.showerror("MUNIM", f"Could not save the report:\n{e}")
            return
        messagebox.showinfo("MUNIM", f"Report saved:\n{path}")

    def _period_label(self):
        if hasattr(self, "_d1") and hasattr(self, "_d2"):
            try:
                d1 = parse_date(self._d1.get())
                d2 = parse_date(self._d2.get())
                return f"{d1.strftime('%d-%m-%Y')} to {d2.strftime('%d-%m-%Y')}"
            except ValueError:
                pass
        return self.fy.get() if hasattr(self, "fy") else ""


# ── Trial Balance ─────────────────────────────────────────────────────────────
class TrialBalanceFrame(ReportBase):
    title_text = "Trial Balance"
    sub_text   = "Closing balances grouped by accounting head."

    def __init__(self, master, con):
        super().__init__(master, con)

        # Date range row
        dr = ctk.CTkFrame(self, fg_color="transparent")
        dr.pack(fill="x", padx=28, pady=(0, 4))
        ctk.CTkLabel(dr, text="From", font=T.f(12), text_color=T.MUTED).pack(side="left", padx=(0, 4))
        self._d1 = T.entry(dr, width=120)
        y = int(self.fy.get()[:4])
        self._d1.insert(0, f"01-04-{y}")
        self._d1.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(dr, text="to", font=T.f(12), text_color=T.MUTED).pack(side="left", padx=(0, 4))
        self._d2 = T.entry(dr, width=120)
        self._d2.insert(0, f"31-03-{y+1}")
        self._d2.pack(side="left", padx=(0, 8))
        T.button(dr, "Show", self.refresh, width=70,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="left")
        self._d1.bind("<Return>", lambda _e: self.refresh())
        self._d2.bind("<Return>", lambda _e: self.refresh())

        # Controls row
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.pack(fill="x", padx=28, pady=(4, 6))
        seg_kw = dict(selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER,
                      unselected_color="#E7ECF5", unselected_hover_color="#DCE3F0",
                      text_color=T.TEXT, font=T.f(13))
        self.view_mode = ctk.CTkSegmentedButton(
            ctrl, values=["Summary", "Detailed"],
            command=lambda _v: self.refresh(), **seg_kw)
        self.view_mode.set("Summary")
        self.view_mode.pack(side="left")
        T.button(ctrl, "Export PDF", self._export_pdf, width=100,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="right")
        T.button(ctrl, "Export Excel", self._export_excel, width=120,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="right", padx=(0, 8))

        self.period_lbl = ctk.CTkLabel(self, text="", font=T.f(11), text_color=T.MUTED)
        self.period_lbl.pack(anchor="w", padx=28, pady=(0, 4))

        self.table = DataTable(self, [
            ("p", "Particulars",  460, L),
            ("d", "Debit (Rs)",   160, R),
            ("c", "Credit (Rs)",  160, R),
        ], height=16,
            empty_text="No balances for this period. Record a voucher or widen the dates.")
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def _detailed(self):
        return self.view_mode.get() == "Detailed"

    def _dates(self):
        try:
            return parse_date(self._d1.get()), parse_date(self._d2.get())
        except ValueError:
            return None, None

    def refresh(self):
        d1, d2 = self._dates()
        rows, td, tc = s.trial_balance_grouped(
            self.con, self.fy.get(), detailed=self._detailed(),
            date_from=d1, date_to=d2)
        self.period_lbl.configure(text=f"Period: {self._period_label()}")
        out = []
        for row in rows:
            dr_txt = _amt(row["dr"]) if row["dr"] else ""
            cr_txt = _amt(row["cr"]) if row["cr"] else ""
            if row["kind"] == "group":
                out.append(((row["name"], dr_txt, cr_txt), "head"))
            elif row["kind"] == "total":
                out.append(((row["name"], _amt(row["dr"]), _amt(row["cr"])), "total"))
            else:
                out.append((row["name"], dr_txt, cr_txt))
        self.table.set_rows(out)

    def _export_pdf(self):
        st      = settings.load_settings()
        company = st.get("company_name", "Company")
        fy      = self.fy.get()
        d1, d2  = self._dates()
        rows, td, tc = s.trial_balance_grouped(self.con, fy,
                           detailed=self._detailed(), date_from=d1, date_to=d2)
        try:
            path = generate_trial_balance_pdf(company, fy, rows, td, tc,
                                              detailed=self._detailed(),
                                              period=self._period_label())
        except PermissionError:
            messagebox.showerror("MUNIM", "The PDF is open in another program. "
                                          "Close it and try again.")
            return
        except Exception as e:
            messagebox.showerror("MUNIM", f"Could not generate PDF:\n{e}")
            return
        _open_pdf(path)

    def _export_excel(self):
        d1, d2 = self._dates()
        rows, td, tc = s.trial_balance(self.con, self.fy.get(), d1, d2)
        title = f"Trial Balance {self._period_label()}"
        data  = [[n, dr, cr] for n, dr, cr in rows] + [["Total", td, tc]]
        try:
            path = filedialog.asksaveasfilename(
                title="Save Trial Balance", defaultextension=".xlsx",
                filetypes=[("Excel file", "*.xlsx")],
                initialfile=f"Trial_Balance_{self.fy.get()}.xlsx")
            if not path:
                return
            path = write_table(path, title, ["Particulars", "Debit (Rs)", "Credit (Rs)"], data)
        except Exception as e:
            messagebox.showerror("MUNIM", f"Could not save:\n{e}")
            return
        messagebox.showinfo("MUNIM", f"Saved:\n{path}")

    def export_data(self):
        d1, d2 = self._dates()
        rows, td, tc = s.trial_balance(self.con, self.fy.get(), d1, d2)
        return (f"Trial Balance {self._period_label()}",
                ["Particulars", "Debit (Rs)", "Credit (Rs)"],
                [[n, d, c] for n, d, c in rows] + [["Total", td, tc]])


# ── Ledger ────────────────────────────────────────────────────────────────────


class _LedgerDropdown(ctk.CTkFrame):
    """Searchable group/ledger picker with complete keyboard and mouse support."""
    def __init__(self, master, groups, command, width=270):
        super().__init__(master, fg_color="transparent", width=width)
        self.groups = groups
        self.command = command
        self.width = width
        self.selected_label = "Select group / ledger"
        self._expanded = {group for group, _accounts in groups}
        self.button = ctk.CTkButton(
            self, text=self.selected_label + "  ▾", command=self._open,
            width=width, height=38, corner_radius=8, font=T.f(13),
            anchor="w", fg_color="white", text_color=T.TEXT,
            hover_color="#F1F4F9", border_width=1, border_color=T.BORDER)
        self.button.pack(fill="x")

    def set_selection(self, label):
        self.selected_label = label or "Select group / ledger"
        self.button.configure(text=self.selected_label + "  ▾")

    def open(self):
        """Public keyboard/mouse entry point for opening the selector."""
        self._open()

    def focus_search(self):
        """Focus the search field when the selector is already open."""
        popup = getattr(self, "_popup", None)
        search = getattr(self, "_search_widget", None)
        if popup is not None and popup.winfo_exists() and search is not None:
            search.focus_set()
            search.select_range(0, "end")
            return True
        return False

    def _open(self):
        if getattr(self, "_popup", None) and self._popup.winfo_exists():
            self._popup.focus_force()
            return
        popup = ctk.CTkToplevel(self)
        self._popup = popup
        popup.title("Select group or ledger")
        popup.transient(self.winfo_toplevel())
        screen_w, screen_h = popup.winfo_screenwidth(), popup.winfo_screenheight()
        x = min(max(8, self.winfo_rootx()), max(8, screen_w - self.width - 8))
        h = min(420, max(260, screen_h - 100))
        y = self.winfo_rooty() + self.winfo_height()
        if y + h > screen_h - 8:
            y = max(8, self.winfo_rooty() - h)
        popup.geometry(f"{self.width}x{h}+{x}+{y}")
        popup.configure(fg_color="white")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()

        search = T.entry(popup, "Search groups or ledgers")
        self._search_widget = search
        search.pack(fill="x", padx=8, pady=8)
        listing = ctk.CTkScrollableFrame(
            popup, fg_color="white", scrollbar_button_color="#C5CEE0")
        listing.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        visible = []
        selected_index = 0

        def close():
            try:
                if popup.winfo_exists():
                    popup.grab_release()
                    popup.destroy()
            except Exception:
                pass
            self._popup = None
            self._search_widget = None
            self.button.focus_set()

        def choose(kind, value, label):
            self.set_selection(label)
            close()
            self.command(kind, value)

        def populate(_event=None):
            nonlocal visible, selected_index
            for child in listing.winfo_children():
                child.destroy()
            query = search.get().strip().casefold()
            visible = []
            for group, accounts in self.groups:
                matched = [
                    account for account in accounts
                    if query in (account[0] if isinstance(account, tuple) else account).casefold()
                    or (isinstance(account, tuple) and query in account[1].casefold())
                ]
                group_match = query in group.casefold()
                if query and not group_match and not matched:
                    continue
                visible.append(("group", group, group))
                if group in self._expanded or query:
                    for account in accounts:
                        name, display = account if isinstance(account, tuple) else (account, account)
                        if query and not group_match and query not in name.casefold() and query not in display.casefold():
                            continue
                        visible.append(("ledger", name, f"{group}  /  {display}"))
            if not visible:
                ctk.CTkLabel(listing, text="No matching groups or ledgers",
                             text_color=T.MUTED).pack(pady=12)
                selected_index = 0
                return
            selected_index = min(selected_index, len(visible) - 1)
            for index, (kind, value, label) in enumerate(visible):
                if kind == "group":
                    expanded = value in self._expanded or bool(query)
                    text = ("▾  " if expanded else "▸  ") + value
                    btn = ctk.CTkButton(
                        listing, text=text,
                        command=lambda v=value: choose("group", v, v),
                        height=30, corner_radius=7, font=T.f(12, "bold"),
                        fg_color="#EEF2F8", text_color=T.TEXT,
                        hover_color="#E0E7F2", anchor="w")
                else:
                    btn = ctk.CTkButton(
                        listing, text=f"     {label.split('  /  ', 1)[-1]}",
                        command=lambda v=value, lab=label: choose("ledger", v, lab),
                        height=28, corner_radius=7, font=T.f(12),
                        fg_color="white", text_color=T.TEXT,
                        hover_color="#F1F4F9", anchor="w")
                btn.pack(fill="x", pady=(2, 1) if kind == "group" else 1)
                if index == selected_index:
                    btn.configure(border_width=1, border_color="#9DB7E8")
            try:
                listing.update_idletasks()
                canvas = listing._parent_canvas
                canvas_height = max(1, canvas.winfo_height())
                row_height = 32
                visible_count = max(1, canvas_height // row_height)
                first_index = max(0, selected_index - visible_count // 2)
                fraction = first_index / max(1, len(visible))
                canvas.yview_moveto(min(1.0, fraction))
            except Exception:
                pass

        def move_selection(delta):
            nonlocal selected_index
            if visible:
                selected_index = (selected_index + delta) % len(visible)
                populate()

        def on_key(event):
            nonlocal selected_index
            key = event.keysym
            if key == "Escape":
                close()
                return "break"
            if key == "Down":
                move_selection(1)
                return "break"
            if key == "Up":
                move_selection(-1)
                return "break"
            if key == "Right" and visible:
                kind, value, _label = visible[selected_index]
                if kind == "group":
                    was_collapsed = value not in self._expanded
                    self._expanded.add(value)
                    populate()
                    # Right-arrow follows a tree convention: expand, then move
                    # to the first ledger inside the group.
                    if was_collapsed:
                        for index in range(selected_index + 1, len(visible)):
                            if visible[index][0] == "ledger":
                                selected_index = index
                                break
                        populate()
                    else:
                        for index in range(selected_index + 1, len(visible)):
                            if visible[index][0] == "ledger":
                                selected_index = index
                                populate()
                                break
                return "break"
            if key == "Left" and visible:
                kind, value, _label = visible[selected_index]
                if kind == "group" and value in self._expanded:
                    self._expanded.discard(value)
                    populate()
                elif kind == "ledger":
                    for group, accounts in self.groups:
                        if any((a[0] if isinstance(a, tuple) else a) == value for a in accounts):
                            self._expanded.discard(group)
                            populate()
                            break
                return "break"
            if key in ("Return", "KP_Enter") and visible:
                kind, value, label = visible[selected_index]
                choose(kind, value, label)
                return "break"
            return None

        search.bind("<KeyRelease>", populate)
        popup.bind("<KeyPress>", on_key)
        popup.protocol("WM_DELETE_WINDOW", close)
        populate()
        search.focus_set()


class LedgerFrame(ReportBase):
    def __init__(self, master, con, accounts=None, title="Ledger View",
                 sub="Every entry in one account, with a running balance.",
                 initial_account=None):
        self.title_text, self.sub_text = title, sub
        self._is_cashbook = accounts is not None
        self._initial_account = initial_account
        self._selected_group = None
        super().__init__(master, con)
        names = accounts or [x["name"] for x in con.execute(
            "SELECT name FROM accounts ORDER BY name COLLATE NOCASE")]
        selected = (self._initial_account if self._initial_account in names else
                    ("Cash" if "Cash" in names else (names[0] if names else "")))
        if self._is_cashbook:
            self.acct = T.option_menu(self.bar, names, width=160,
                                      command=lambda _v: self.refresh())
            self.acct.set(selected)
            self.acct.pack(side="right", padx=(10, 0))
        else:
            self.acct = ctk.StringVar(value=selected)
            rows = self.con.execute(
                "SELECT id, name, grp, opening FROM accounts "
                "ORDER BY grp COLLATE NOCASE, name COLLATE NOCASE"
            ).fetchall()
            by_group = {}
            for row in rows:
                name, group = row["name"], row["grp"]
                display = name
                if name == group and group in ("Sundry Debtors", "Sundry Creditors"):
                    has_entries = self.con.execute(
                        "SELECT 1 FROM entries WHERE account_id=? LIMIT 1",
                        (row["id"],)).fetchone() is not None
                    if not row["opening"] and not has_entries:
                        continue  # hide unused legacy group-named ledger
                    display = f"{group} · General Ledger (existing)"
                by_group.setdefault(group, []).append((name, display))
            ordered_groups = list(s.ACCOUNT_GROUPS)
            groups = [(group, by_group.pop(group, [])) for group, _nature in ordered_groups]
            groups.extend((group, ledgers) for group, ledgers in sorted(
                by_group.items(), key=lambda item: item[0].casefold()))
            groups = [(group, ledgers) for group, ledgers in groups if ledgers]
            self.picker = _LedgerDropdown(self.bar, groups, self._choose_ledger_item, width=270)
            self.picker.pack(side="right", padx=(10, 0))
            if selected:
                row = self.con.execute("SELECT grp FROM accounts WHERE name=?", (selected,)).fetchone()
                if row:
                    self.picker.set_selection(f"{row['grp']}  /  {selected}")
        today = date.today()
        self.d2 = T.entry(self.bar, width=120)
        self.d2.insert(0, today.strftime("%d-%m-%Y"))
        self.d1 = T.entry(self.bar, width=120)
        self.d1.insert(0, today.replace(day=1).strftime("%d-%m-%Y"))
        T.button(self.bar, "Show", self.refresh, width=70).pack(side="right")
        self.d2.pack(side="right", padx=6)
        ctk.CTkLabel(self.bar, text="to", text_color=T.MUTED).pack(side="right")
        self.d1.pack(side="right", padx=6)
        self.summary = ctk.CTkLabel(self, text="", font=T.f(13, "bold"), text_color=T.TEXT)
        self.summary.pack(anchor="w", padx=28, pady=(0, 8))
        table_frame = ctk.CTkFrame(self, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.table = DataTable(table_frame, [
            ("dt", "Date",        100, L), ("v",  "Voucher",    120, L),
            ("n",  "Narration",   300, L), ("d",  "Debit (Rs)", 130, R),
            ("c",  "Credit (Rs)", 130, R), ("b",  "Balance",    150, R)], height=14,
            empty_text="Choose a ledger and dates, then click Show.")
        self.table.pack(fill="both", expand=True)
        self.refresh()

    def _choose_ledger_item(self, kind, value):
        if kind == "group":
            self._show_group_summary(value)
            return
        self._selected_group = None
        self.acct.set(value)
        self.refresh()

    def _show_group_summary(self, group):
        """Show member ledger balances for a group as of the selected end date."""
        self._selected_group = group
        self.acct.set("")
        if hasattr(self, "picker"):
            self.picker.set_selection(f"Group summary  /  {group}")
        _fy_start, fy_end = s.fy_range(self.fy.get())
        try:
            as_of = parse_date(self.d2.get())
        except ValueError:
            as_of = date.today()
        as_of = min(as_of, date.fromisoformat(fy_end))
        states, _prior_pl = s.account_states(
            self.con, self.fy.get(), date_to=as_of)
        group_states = [st for st in states if st["grp"] == group]
        visible_states = []
        for st in group_states:
            if st["name"] == group and group in ("Sundry Debtors", "Sundry Creditors"):
                account = self.con.execute(
                    "SELECT id, opening FROM accounts WHERE name=?", (st["name"],)).fetchone()
                has_entries = bool(account and self.con.execute(
                    "SELECT 1 FROM entries WHERE account_id=? LIMIT 1",
                    (account["id"],)).fetchone())
                if not account or (not account["opening"] and not has_entries):
                    continue  # do not surface an unused legacy group-named ledger
                st = dict(st)
                st["display_name"] = f"{group} · General Ledger (existing)"
            visible_states.append(st)
        group_net = sum(st["bf"] + st["dr"] - st["cr"] for st in visible_states)
        rows = []
        for st in sorted(visible_states, key=lambda x: x["name"].casefold()):
            net = st["bf"] + st["dr"] - st["cr"]
            name = st.get("display_name", st["name"])
            rows.append((("", "", name,
                         inr(s.to_rupees(max(net, 0))) if net > 0 else "",
                         inr(s.to_rupees(max(-net, 0))) if net < 0 else "",
                         f"{inr(s.to_rupees(abs(net)))} {'Dr' if net >= 0 else 'Cr'}"), ""))
        rows.append((("", "", "Group total",
                     inr(s.to_rupees(max(group_net, 0))),
                     inr(s.to_rupees(max(-group_net, 0))),
                     f"{inr(s.to_rupees(abs(group_net)))} {'Dr' if group_net >= 0 else 'Cr'}"), "total"))
        self.table.set_rows(rows)
        self.summary.configure(
            text=(f"{group}   ·   Group summary ({len(visible_states)} ledgers)   |   "
                  f"As of {disp_date(as_of)}   |   "
                  f"Net balance: Rs {inr(s.to_rupees(abs(group_net)))} "
                  f"{'Dr' if group_net >= 0 else 'Cr'}"),
            text_color=T.TEXT)

    def refresh(self):
        if not self._is_cashbook and self._selected_group:
            self._show_group_summary(self._selected_group)
            return
        try:
            d1  = parse_date(self.d1.get())
            d2  = parse_date(self.d2.get())
            led = r.ledger_view(self.con, self.acct.get().strip(),
                                self.fy.get(), date_from=d1, date_to=d2)
        except ValueError as e:
            self.summary.configure(text=str(e), text_color=T.DANGER)
            self.table.set_rows([])
            return
        rows = [(("", "", "Opening balance", "", "",
                  f"{inr(led['opening'])} {led['opening_side']}"), "head")]
        for x in led["rows"]:
            rows.append((disp_date(x["date"]), f"{x['vtype']} #{x['vno']}", x["narration"],
                         _amt(x["dr"]), _amt(x["cr"]),
                         f"{inr(x['balance'])} {x['side']}"))
        rows.append((("", "", "Total", inr(led["total_dr"]), inr(led["total_cr"]),
                      f"{inr(led['closing'])} {led['closing_side']}"), "total"))
        self.table.set_rows(rows)
        self.summary.configure(
            text=(f"{led['account']}   |   "
                  f"Closing balance: Rs {inr(led['closing'])} {led['closing_side']}"),
            text_color=T.TEXT)

    def export_data(self):
        if self._selected_group and not self._is_cashbook:
            _fy_start, fy_end = s.fy_range(self.fy.get())
            try:
                as_of = parse_date(self.d2.get())
            except ValueError:
                as_of = date.today()
            as_of = min(as_of, date.fromisoformat(fy_end))
            states, _prior_pl = s.account_states(
                self.con, self.fy.get(), date_to=as_of)
            members = [st for st in states if st["grp"] == self._selected_group]
            data = []
            total = 0
            for st in members:
                net = st["bf"] + st["dr"] - st["cr"]
                if st["name"] == self._selected_group and self._selected_group in (
                        "Sundry Debtors", "Sundry Creditors"):
                    account = self.con.execute(
                        "SELECT id, opening FROM accounts WHERE name=?",
                        (st["name"],)).fetchone()
                    has_entries = bool(account and self.con.execute(
                        "SELECT 1 FROM entries WHERE account_id=? LIMIT 1",
                        (account["id"],)).fetchone())
                    if not account or (not account["opening"] and not has_entries):
                        continue
                total += net
                data.append(["", "", st["name"],
                            s.to_rupees(max(net, 0)),
                            s.to_rupees(max(-net, 0)),
                            s.to_rupees(net)])
            data.append(["", "", "Group total",
                         s.to_rupees(max(total, 0)),
                         s.to_rupees(max(-total, 0)), s.to_rupees(total)])
            return (f"{self._selected_group} Group {self.fy.get()}",
                    ["Date", "Voucher", "Narration", "Debit (Rs)",
                     "Credit (Rs)", "Balance (Rs)"], data)
        try:
            d1  = parse_date(self.d1.get())
            d2  = parse_date(self.d2.get())
            led = r.ledger_view(self.con, self.acct.get().strip(),
                                self.fy.get(), date_from=d1, date_to=d2)
        except ValueError:
            return "Ledger", ["Date", "Voucher", "Narration", "Debit (Rs)", "Credit (Rs)", "Balance"], []
        headers = ["Date", "Voucher", "Narration", "Debit (Rs)", "Credit (Rs)", "Balance"]
        rows = [[disp_date(x["date"]), f"{x['vtype']} #{x['vno']}", x["narration"],
                 x["dr"], x["cr"], x["balance"]] for x in led["rows"]]
        return f"Ledger {led['account']} {self.fy.get()}", headers, rows


# ── Day Book ──────────────────────────────────────────────────────────────────
class DayBookFrame(ReportBase):
    title_text, with_fy = "Day Book", False
    sub_text = "All vouchers between two dates. Double-click to open, edit or delete."

    def __init__(self, master, con, opener=None):
        super().__init__(master, con)
        self.opener = opener
        today = date.today()
        self.d1 = T.entry(self.bar, width=120)
        self.d1.insert(0, today.replace(day=1).strftime("%d-%m-%Y"))
        self.d2 = T.entry(self.bar, width=120)
        self.d2.insert(0, today.strftime("%d-%m-%Y"))
        T.button(self.bar, "Show", self.refresh, width=70).pack(side="right")
        self.d2.pack(side="right", padx=6)
        ctk.CTkLabel(self.bar, text="to", text_color=T.MUTED).pack(side="right")
        self.d1.pack(side="right", padx=6)
        self.msg = ctk.CTkLabel(self, text="", font=T.f(13), text_color=T.DANGER)
        self.msg.pack(anchor="w", padx=28)
        self.table = DataTable(self, [
            ("dt", "Date",         100, L), ("v",  "Voucher",    130, L),
            ("p",  "Particulars",  380, L), ("d",  "Debit (Rs)", 130, R),
            ("c",  "Credit (Rs)", 130, R)], height=14,
            empty_text="No vouchers between these dates. Change the dates and click Show.")
        self.table.pack(fill="both", expand=True, padx=28, pady=(4, 24))
        if opener:
            self.table.on_open(lambda vid: self.opener(vid, self.refresh))
        self.refresh()

    def refresh(self):
        try:
            book = r.day_book(self.con, parse_date(self.d1.get()),
                              parse_date(self.d2.get()))
        except ValueError as e:
            self.msg.configure(text=str(e))
            return
        self.msg.configure(text="")
        rows = []
        for v in book:
            rows.append(((disp_date(v["date"]), f"{v['vtype']} #{v['vno']}",
                          v["narration"], "", ""), "head", v["id"]))
            for name, dr, cr in v["lines"]:
                rows.append(("", "", "      " + name, _amt(dr), _amt(cr)))
        self.table.set_rows(rows)


# ── TwoSideReport base ────────────────────────────────────────────────────────
class TwoSideReport(ReportBase):
    def __init__(self, master, con):
        super().__init__(master, con)
        self.fy.configure(command=lambda _v: self.on_fy())
        self.extra_controls()
        self.footer = ctk.CTkLabel(self, text="", font=T.f(15, "bold"))
        self.footer.pack(side="bottom", anchor="w", padx=28, pady=(8, 16))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28)
        body.grid_columnconfigure((0, 1), weight=1, uniform="s")
        body.grid_rowconfigure(1, weight=1)
        cols = [("p", "Particulars", 260, L), ("a", "Amount (Rs)", 130, R)]
        self.ltitle = ctk.CTkLabel(body, text="", font=T.f(14, "bold"), text_color=T.TEXT)
        self.rtitle = ctk.CTkLabel(body, text="", font=T.f(14, "bold"), text_color=T.TEXT)
        self.ltitle.grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.rtitle.grid(row=0, column=1, sticky="w", padx=(10, 0), pady=(0, 6))
        self.left  = DataTable(body, cols, height=10)
        self.right = DataTable(body, cols, height=10)
        self.left.grid( row=1, column=0, sticky="nsew", padx=(0, 10))
        self.right.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        self.refresh()

    def extra_controls(self): pass
    def on_fy(self): self.refresh()

    def fill(self, ltitle, lrows, ltotal, rtitle, rrows, rtotal, footer, color):
        self.ltitle.configure(text=ltitle)
        self.rtitle.configure(text=rtitle)
        mk = lambda rows, total: [(n, inr(a)) for n, a in rows] + \
                                  [(("Total", inr(total)), "total")]
        self.left.set_rows(mk(lrows, ltotal))
        self.right.set_rows(mk(rrows, rtotal))
        self.footer.configure(text=footer, text_color=color)

    def _two_side_export(self, title, lrows, ltotal, rrows, rtotal, ltitle, rtitle):
        n = max(len(lrows), len(rrows))
        lrows = list(lrows) + [("", "")] * (n - len(lrows))
        rrows = list(rrows) + [("", "")] * (n - len(rrows))
        rows = [[a, b, c, d] for (a, b), (c, d) in zip(lrows, rrows)] + \
               [["Total", ltotal, "Total", rtotal]]
        return title, [ltitle, "Amount (Rs)", rtitle, "Amount (Rs)"], rows


# ── Profit & Loss ─────────────────────────────────────────────────────────────
class ProfitLossFrame(TwoSideReport):
    title_text = "Trading & Profit/Loss"
    sub_text   = "Trading Account gives gross profit; P&L carries it to net profit."

    def extra_controls(self):
        seg = dict(selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER,
                   unselected_color="#E7ECF5", unselected_hover_color="#DCE3F0",
                   text_color=T.TEXT, font=T.f(13))

        # Export PDF sits next to ReportBase's Export Excel in the header bar.
        T.button(self.bar, "Export PDF", self._export_pdf, width=110,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="right", padx=(10, 0))

        # Date range row
        dr_row = ctk.CTkFrame(self, fg_color="transparent")
        dr_row.pack(fill="x", padx=28, pady=(0, 6))
        ctk.CTkLabel(dr_row, text="Period:", font=T.f(12),
                     text_color=T.MUTED).pack(side="left", padx=(0, 8))
        self._d1 = T.entry(dr_row, width=120)
        self._d2 = T.entry(dr_row, width=120)
        today    = date.today()
        y = today.year if today.month >= 4 else today.year - 1
        self._d1.insert(0, f"01-04-{y}")
        self._d2.insert(0, f"31-03-{y+1}")
        self._d1.pack(side="left", padx=(0, 4))
        ctk.CTkLabel(dr_row, text="to", font=T.f(12),
                     text_color=T.MUTED).pack(side="left", padx=4)
        self._d2.pack(side="left", padx=(0, 8))
        T.button(dr_row, "Show", self.refresh, width=70,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="left")
        self._d1.bind("<Return>", lambda _e: self.refresh())
        self._d2.bind("<Return>", lambda _e: self.refresh())

        row = T.card(self)
        row.pack(fill="x", padx=28, pady=(0, 10))
        self.opening = T.entry(row, "0.00", width=150)
        self.closing = T.entry(row, "0.00", width=150)
        self.mode = ctk.CTkSegmentedButton(
            row, values=["Trading Account", "Profit & Loss"],
            command=lambda _v: self.refresh(), **seg)
        self.mode.set("Trading Account")
        for c, (label, w) in enumerate((("Show", self.mode),
                                        ("Opening stock (Rs)", self.opening),
                                        ("Closing stock (Rs)", self.closing))):
            if label != "Show":
                ctk.CTkLabel(row, text=label, font=T.f(12), text_color=T.MUTED).grid(
                    row=0, column=c, sticky="w",
                    padx=(18 if c == 0 else 10, 10), pady=(12, 2))
            w.grid(row=1, column=c, padx=(18 if c == 0 else 10, 10), pady=(0, 14))
        ctk.CTkLabel(row,
                     text="Opening stock follows last year's closing unless you change it.",
                     font=T.f(11), text_color=T.MUTED, wraplength=330,
                     justify="left").grid(row=1, column=3, padx=14, pady=(0, 14), sticky="w")
        for w in (self.closing, self.opening):
            w._entry.bind("<FocusOut>", lambda _e: self._save_stock(), add="+")
            w._entry.bind("<Return>",   lambda _e: self._save_stock(), add="+")
        self._load_stock()

    def _get_pl_dates(self):
        try:
            return parse_date(self._d1.get()), parse_date(self._d2.get())
        except (ValueError, AttributeError):
            return None, None

    @property
    def stock(self):
        return self.closing

    def _load_stock(self):
        o, c = s.get_stock(self.con, self.fy.get())
        for box, v in ((self.opening, o), (self.closing, c)):
            box.delete(0, "end")
            if v:
                box.insert(0, f"{v / 100:.2f}")

    def _save_stock(self):
        fy = self.fy.get()
        try:
            o_val = parse_amount(self.opening.get())
            c_val = parse_amount(self.closing.get())
        except ValueError:
            self.footer.configure(text="Stock values must be numbers", text_color=T.DANGER)
            return
        auto = s.get_stock(self.con, s.prev_fy(fy))[1] / 100
        s.set_stock(self.con, fy,
                    opening=None if abs(o_val - auto) < 0.005 else o_val,
                    closing=c_val)
        self.refresh()

    def on_fy(self):
        y = int(self.fy.get()[:4])
        self._d1.delete(0, "end"); self._d1.insert(0, f"01-04-{y}")
        self._d2.delete(0, "end"); self._d2.insert(0, f"31-03-{y+1}")
        self._load_stock()
        self.refresh()

    def _data(self):
        d1, d2 = self._get_pl_dates()
        return r.trading_and_pl(self.con, self.fy.get(), date_from=d1, date_to=d2)

    def refresh(self):
        ta  = self._data()
        t, p = ta["trading"], ta["pl"]
        gp, npf = t["gross_profit"], p["net_profit"]
        gp_pct  = ta.get("gross_pct", 0.0)
        np_pct  = ta.get("net_pct",   0.0)
        d1, d2  = self._get_pl_dates()
        period  = (f"{d1.strftime('%d-%m-%Y')} to {d2.strftime('%d-%m-%Y')}"
                   if d1 and d2 else self.fy.get())
        foot = (f"Period: {period}     |     "
                f"Gross {'Profit' if gp >= 0 else 'Loss'}: Rs {inr(abs(gp))} ({abs(gp_pct):.1f}%)     "
                f"Net {'Profit' if npf >= 0 else 'Loss'}: Rs {inr(abs(npf))} ({abs(np_pct):.1f}%)")
        color = T.OK if npf >= 0 else T.DANGER
        if self.mode.get() == "Trading Account":
            self.fill("Debit side", t["left"], t["left_total"],
                      "Credit side", t["right"], t["right_total"], foot, color)
        else:
            self.fill("Debit side", p["left"], p["left_total"],
                      "Credit side", p["right"], p["right_total"], foot, color)

    def _export_pdf(self):
        st = settings.load_settings()
        company = st.get("company_name") or "Company"
        try:
            path = generate_pl_pdf(company, self._period_label(), self._data())
        except PermissionError:
            messagebox.showerror("MUNIM", "The PDF is open in another program. "
                                          "Close it and try again.")
            return
        except Exception as e:
            messagebox.showerror("MUNIM", f"Could not generate PDF:\n{e}")
            return
        _open_pdf(path)

    def export_data(self):
        ta = self._data()
        out_rows, title = [], f"Trading and Profit Loss {self._period_label()}"
        _t, h, rows = self._two_side_export(
            "Trading Account", ta["trading"]["left"], ta["trading"]["left_total"],
            ta["trading"]["right"], ta["trading"]["right_total"], "Debit", "Credit")
        out_rows += [["TRADING ACCOUNT", "", "", ""]] + rows + [["", "", "", ""]]
        _t, h, rows = self._two_side_export(
            "Profit & Loss", ta["pl"]["left"], ta["pl"]["left_total"],
            ta["pl"]["right"], ta["pl"]["right_total"], "Debit", "Credit")
        out_rows += [["PROFIT & LOSS ACCOUNT", "", "", ""]] + rows
        return title, h, out_rows


# ── Balance Sheet ─────────────────────────────────────────────────────────────
class BalanceSheetFrame(TwoSideReport):
    title_text = "Balance Sheet"
    sub_text   = "What the business owns and owes."

    def extra_controls(self):
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.pack(fill="x", padx=28, pady=(0, 4))
        self.note = ctk.CTkLabel(ctrl, text="", font=T.f(12), text_color=T.MUTED)
        self.note.pack(side="left")

        # As-on date row
        as_on = ctk.CTkFrame(self, fg_color="transparent")
        as_on.pack(fill="x", padx=28, pady=(0, 4))
        ctk.CTkLabel(as_on, text="As on date:", font=T.f(12),
                     text_color=T.MUTED).pack(side="left", padx=(0, 6))
        self._d2 = T.entry(as_on, width=120)
        y = int(self.fy.get()[:4])
        self._d2.insert(0, f"31-03-{y+1}")
        self._d2.pack(side="left", padx=(0, 8))
        T.button(as_on, "Show", self.refresh, width=70,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="left")
        self._d2.bind("<Return>", lambda _e: self.refresh())

        # Buttons
        T.button(ctrl, "Export PDF", self._export_pdf, width=100,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="right", padx=(6, 0))
        T.button(ctrl, "Export Excel", self._export_excel, width=120,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="right", padx=(6, 0))
        seg_kw = dict(selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER,
                      unselected_color="#E7ECF5", unselected_hover_color="#DCE3F0",
                      text_color=T.TEXT, font=T.f(13))
        self.view_mode = ctk.CTkSegmentedButton(
            ctrl, values=["Summary", "Detailed"],
            command=lambda _v: self.refresh(), **seg_kw)
        self.view_mode.set("Detailed")
        self.view_mode.pack(side="right", padx=(6, 0))

    def _detailed(self):
        return self.view_mode.get() == "Detailed"

    def _as_on(self):
        try:
            return parse_date(self._d2.get())
        except Exception:
            return None

    def on_fy(self):
        y = int(self.fy.get()[:4])
        self._d2.delete(0, "end")
        self._d2.insert(0, f"31-03-{y+1}")
        self.refresh()

    def refresh(self):
        from db.reports import balance_sheet_grouped
        as_on = self._as_on()
        bs = balance_sheet_grouped(self.con, self.fy.get(),
                                   detailed=self._detailed(), date_to=as_on)
        cs = s.get_stock(self.con, self.fy.get())[1] / 100
        as_on_str = as_on.strftime("%d-%m-%Y") if as_on else "FY end"
        self.note.configure(
            text=f"As on: {as_on_str}   |   Closing stock: Rs {inr(cs)} (set under Trading & P&L)")

        def _flatten(sections):
            rows = []
            for sec in sections:
                rows.append((sec["head"], sec["total"]))
                for name, amt in sec["accounts"]:
                    rows.append((f"    {name}", amt))
            return rows

        liab_rows  = _flatten(bs["liabilities"])
        asset_rows = _flatten(bs["assets"])
        self.fill("Liabilities", liab_rows, bs["total_liabilities"],
                  "Assets",      asset_rows, bs["total_assets"],
                  f"Total: Rs {inr(bs['total_assets'])}", T.TEXT)

    def _export_pdf(self):
        from db.reports import balance_sheet_grouped
        st      = settings.load_settings()
        company = st.get("company_name", "Company")
        fy      = self.fy.get()
        as_on   = self._as_on()
        bs      = balance_sheet_grouped(self.con, fy, detailed=True, date_to=as_on)
        try:
            path = generate_balance_sheet_pdf(company, fy, bs)
        except PermissionError:
            messagebox.showerror("MUNIM", "The PDF is open in another program. "
                                          "Close it and try again.")
            return
        except Exception as e:
            messagebox.showerror("MUNIM", f"Could not generate PDF:\n{e}")
            return
        _open_pdf(path)

    def _export_excel(self):
        from db.reports import balance_sheet_grouped
        as_on = self._as_on()
        bs    = balance_sheet_grouped(self.con, self.fy.get(), detailed=True, date_to=as_on)
        title = f"Balance Sheet {self.fy.get()}"
        liab  = [(sec["head"], sec["total"]) for sec in bs["liabilities"]]
        for sec in bs["liabilities"]:
            liab += [(f"    {n}", a) for n, a in sec["accounts"]]
        asset = [(sec["head"], sec["total"]) for sec in bs["assets"]]
        for sec in bs["assets"]:
            asset += [(f"    {n}", a) for n, a in sec["accounts"]]
        n = max(len(liab), len(asset))
        liab  += [("", "")] * (n - len(liab))
        asset += [("", "")] * (n - len(asset))
        rows  = [[a, b, c, d] for (a, b), (c, d) in zip(liab, asset)]
        rows.append(["Total", bs["total_liabilities"], "Total", bs["total_assets"]])
        try:
            path = filedialog.asksaveasfilename(
                title="Save Balance Sheet", defaultextension=".xlsx",
                filetypes=[("Excel file", "*.xlsx")],
                initialfile=f"Balance_Sheet_{self.fy.get()}.xlsx")
            if not path:
                return
            path = write_table(path, title,
                               ["Liabilities", "Amount (Rs)", "Assets", "Amount (Rs)"], rows)
        except Exception as e:
            messagebox.showerror("MUNIM", f"Could not save Excel:\n{e}")
            return
        messagebox.showinfo("MUNIM", f"Saved:\n{path}")

    def export_data(self):
        from db.reports import balance_sheet
        bs = balance_sheet(self.con, self.fy.get())
        return self._two_side_export(
            f"Balance Sheet {self.fy.get()}",
            bs["liabilities"], bs["total_liabilities"],
            bs["assets"], bs["total_assets"], "Liabilities", "Assets")


# ── Invoice Register ──────────────────────────────────────────────────────────
class InvoiceRegisterFrame(ReportBase):
    own_controls = True

    def __init__(self, master, con, kind, opener=None):
        self.kind, self.opener = kind, opener
        self.title_text = f"{kind} Register"
        self.sub_text   = ("Every bill in the period, with payment status. "
                           "Double-click a bill to open, edit or delete it.")
        super().__init__(master, con)
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.pack(fill="x", padx=28, pady=(0, 8))
        today = date.today()
        self.d1 = T.entry(ctrl, width=120)
        self.d1.insert(0, today.replace(day=1).strftime("%d-%m-%Y"))
        self.d2 = T.entry(ctrl, width=120)
        self.d2.insert(0, today.strftime("%d-%m-%Y"))
        ctk.CTkLabel(ctrl, text="From", font=T.f(12),
                     text_color=T.MUTED).pack(side="left", padx=(0, 4))
        self.d1.pack(side="left", padx=(0, 4))
        ctk.CTkLabel(ctrl, text="to", font=T.f(12),
                     text_color=T.MUTED).pack(side="left", padx=4)
        self.d2.pack(side="left", padx=(0, 8))
        T.button(ctrl, "Show", self.refresh, width=70,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="left")
        T.button(ctrl, "Full FY", self._full_fy, width=80,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="left", padx=(8, 0))
        T.button(ctrl, "Export Excel", self.export, width=120,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="right")
        cols = [("dt", "Date",        90,  L), ("no", "No.",      50,  L),
                ("p",  "Party",      190,  L), ("tx", "Taxable", 110,  R),
                ("cg", "CGST",        85,  R), ("sg", "SGST",     85,  R),
                ("ig", "IGST",        85,  R), ("t",  "Total",   110,  R),
                ("b",  "Balance due", 110, R), ("st", "Status",   95,  L)]
        self.table = DataTable(
            self, cols, height=14,
            empty_text=f"No {kind.lower()} bills in this period. "
                       "Click Full FY or change the dates.")
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        if opener:
            self.table.on_open(lambda vid: self.opener(vid, self.refresh))
        self.refresh()

    def _full_fy(self):
        y = int(self.fy.get()[:4])
        self.d1.delete(0, "end"); self.d1.insert(0, f"01-04-{y}")
        self.d2.delete(0, "end"); self.d2.insert(0, f"31-03-{y+1}")
        self.refresh()

    def _dates(self):
        try:
            return parse_date(self.d1.get()), parse_date(self.d2.get())
        except Exception:
            return None, None

    def export_data(self):
        d1, d2 = self._dates()
        reg = r.invoice_register(self.con, self.fy.get(), self.kind, d1, d2)
        headers = ["Date", "No.", "Party", "Taxable", "CGST", "SGST", "IGST",
                   "Total", "Balance due", "Status"]
        rows = [[disp_date(x["date"]), x["vno"], x["party"],
                 x["taxable"], x["cgst"], x["sgst"], x["igst"],
                 x["total"], x["balance"], x["status"]] for x in reg]
        return f"{self.kind} Register {self._period_label()}", headers, rows

    def refresh(self):
        d1, d2 = self._dates()
        reg = r.invoice_register(self.con, self.fy.get(), self.kind, d1, d2)
        rows, tot = [], [0] * 6
        for x in reg:
            vals = [x["taxable"], x["cgst"], x["sgst"],
                    x["igst"], x["total"], x["balance"]]
            tot  = [a + b for a, b in zip(tot, vals)]
            rows.append(((disp_date(x["date"]), x["vno"], x["party"],
                          *[_amt(v) for v in vals], x["status"]), None, x["id"]))
        if reg:
            rows.append((("", "", f"Total ({len(reg)} bills)",
                          *[inr(v) for v in tot], ""), "total"))
        self.table.set_rows(rows)


# ── Outstanding ───────────────────────────────────────────────────────────────
class OutstandingFrame(ReportBase):
    title_text, with_fy = "Outstanding", False
    sub_text = "Unpaid bills and their ageing. Double-click a bill to open it."
    own_controls = True

    def __init__(self, master, con, opener=None):
        super().__init__(master, con)
        self.opener, self.table = opener, None
        st = settings.load_settings()
        self.edges = st.get("ageing_edges") or r.DEFAULT_EDGES
        ctrl = T.card(self)
        ctrl.pack(fill="x", padx=28, pady=(0, 10))
        seg = dict(selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER,
                   unselected_color="#E7ECF5", unselected_hover_color="#DCE3F0",
                   text_color=T.TEXT, font=T.f(13))
        self.which  = ctk.CTkSegmentedButton(ctrl, values=["Receivable", "Payable"],
                                              command=lambda _v: self.refresh(), **seg)
        self.which.set("Receivable")
        self.view   = ctk.CTkSegmentedButton(ctrl, values=["Bills", "Ageing"],
                                              command=lambda _v: self.refresh(), **seg)
        self.view.set("Ageing")
        self.basis  = T.option_menu(ctrl, ["Bill date", "Due date"], width=120,
                                    command=lambda _v: self.refresh())
        self.asof   = T.entry(ctrl, width=120)
        self.asof.insert(0, today_str())
        self.ranges = T.entry(ctrl, "30,60,90", width=150)
        self.ranges.insert(0, ",".join(str(e) for e in self.edges))
        items = (("Show", self.which), ("View", self.view),
                 ("Age from", self.basis), ("As on date", self.asof),
                 ("Ranges (days)", self.ranges))
        for c, (label, w) in enumerate(items):
            if label != "Show":
                ctk.CTkLabel(ctrl, text=label, font=T.f(12), text_color=T.MUTED).grid(
                    row=0, column=c, sticky="w",
                    padx=(18 if c == 0 else 8, 8), pady=(12, 2))
            w.grid(row=1, column=c, padx=(18 if c == 0 else 8, 8), pady=(0, 14))
        T.button(ctrl, "Refresh", self.refresh, width=90).grid(
            row=1, column=5, padx=8, pady=(0, 14))
        T.button(ctrl, "Export Excel", self.export, width=120,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").grid(row=1, column=6, padx=8, pady=(0, 14))
        self.summary = ctk.CTkLabel(self, text="", font=T.f(13, "bold"), text_color=T.TEXT)
        self.summary.pack(anchor="w", padx=28, pady=(0, 8))
        self.holder = ctk.CTkFrame(self, fg_color="transparent")
        self.holder.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def _inputs(self):
        edges = r.parse_edges(self.ranges.get())
        asof  = parse_date(self.asof.get())
        kind  = "Sales" if self.which.get() == "Receivable" else "Purchase"
        return kind, asof, ("due" if self.basis.get() == "Due date" else "bill"), edges

    def _report(self):
        kind, asof, basis, edges = self._inputs()
        rep = r.outstanding_report(self.con, kind, asof, basis, edges)
        return kind, rep

    def _set_table(self, columns):
        if self.table is not None:
            self.table.destroy()
        who = "customers" if self.which.get() == "Receivable" else "suppliers"
        self.table = DataTable(
            self.holder, columns, height=14,
            empty_text=f"Nothing outstanding from {who} as on this date.")
        self.table.pack(fill="both", expand=True)
        if self.opener:
            self.table.on_open(lambda vid: self.opener(vid, self.refresh))

    def refresh(self):
        try:
            kind, rep = self._report()
        except ValueError as e:
            self.summary.configure(text=str(e), text_color=T.DANGER)
            return
        st = settings.load_settings()
        st["ageing_edges"] = r.parse_edges(self.ranges.get())
        settings.save_settings(st)
        self.summary.configure(text_color=T.TEXT)
        due  = rep["basis"] == "due"
        word = "overdue" if due else "old"
        self.summary.configure(
            text=f"Total Rs {inr(rep['total'])}    |    " +
                 "    ".join(
                     f"{l}: {inr(rep['buckets'][l])}"
                     for l in rep["labels"]))
        has_parties = bool(rep["parties"])
        if self.view.get() == "Ageing":
            cols = ([("p", "Party", 250, L)] +
                    [(f"b{i}", l if l == "Not due" else f"{l} days", 105, R)
                     for i, l in enumerate(rep["labels"])] +
                    [("oa", "On account", 110, R), ("t", "Total", 120, R)])
            self._set_table(cols)
            rows = []
            for p in rep["parties"]:
                rows.append((p["party"],
                             *[_amt(p["bucket_amounts"][l]) for l in rep["labels"]],
                             _amt(p["on_account"]), inr(p["balance"])))
            if has_parties:
                on_acc = sum(p["on_account"] for p in rep["parties"])
                rows.append((("Total",
                              *[inr(rep["buckets"][l]) for l in rep["labels"]],
                              inr(on_acc), inr(rep["total"])), "total"))
        else:
            self._set_table([
                ("p",  "Party / bill",  270, L), ("dt", "Bill date",  95, L),
                ("du", "Due on",         95, L), ("t",  "Bill total", 120, R),
                ("s",  "Settled",       115, R), ("b",  "Balance",   125, R),
                ("d",  f"Days {word}" if due else "Days old", 90, R),
                ("k",  "Range", 90, L)])
            rows = []
            for p in rep["parties"]:
                rows.append(((p["party"], "", "", "", "",
                               inr(p["balance"]), "", ""), "head"))
                for b in p["bills"]:
                    rows.append(((
                        f"      {kind} #{b['vno']}",
                        disp_date(b["date"]), disp_date(b["due_date"]),
                        inr(b["total"]), _amt(b["settled"]), inr(b["balance"]),
                        b["days"] if not (due and b["days"] <= 0) else "-",
                        b["bucket"]), None, b["id"]))
                if p["on_account"]:
                    rows.append((("      On account / opening balance",
                                  "", "", "", "", inr(p["on_account"]),
                                  "", ""), None))
            if has_parties:
                rows.append((("Total outstanding", "", "", "", "",
                               inr(rep["total"]), "", ""), "total"))
        self.table.set_rows(rows)

    def export_data(self):
        kind, rep = self._report()
        who   = "Receivable" if kind == "Sales" else "Payable"
        basis = "from due date" if rep["basis"] == "due" else "from bill date"
        title = (f"{who} {'ageing' if self.view.get() == 'Ageing' else 'bills'} "
                 f"as on {disp_date(rep['as_of'])} ({basis})")
        if self.view.get() == "Ageing":
            headers = (["Party"] +
                       [l if l == "Not due" else f"{l} days" for l in rep["labels"]] +
                       ["On account", "Total"])
            rows = ([[p["party"]] +
                     [p["bucket_amounts"][l] for l in rep["labels"]] +
                     [p["on_account"], p["balance"]]
                     for p in rep["parties"]] +
                    [["Total"] + [rep["buckets"][l] for l in rep["labels"]] +
                     [sum(p["on_account"] for p in rep["parties"]), rep["total"]]])
        else:
            headers = ["Party", "Bill", "Bill date", "Due on", "Bill total",
                       "Settled", "Balance", "Days", "Range"]
            rows = []
            for p in rep["parties"]:
                for b in p["bills"]:
                    rows.append([p["party"], f"{kind} #{b['vno']}",
                                 disp_date(b["date"]), disp_date(b["due_date"]),
                                 b["total"], b["settled"], b["balance"],
                                 b["days"], b["bucket"]])
                if p["on_account"]:
                    rows.append([p["party"], "On account / opening",
                                 "", "", "", "", p["on_account"], "", ""])
            rows.append(["Total", "", "", "", "", "", rep["total"], "", ""])
        return title, headers, rows


# ── Returns Register ──────────────────────────────────────────────────────────
class ReturnsRegisterFrame(ReportBase):
    own_controls = True

    def __init__(self, master, con, kind, opener=None):
        self.kind, self.opener = kind, opener
        label = "Sales Return" if kind == "Sales Return" else "Purchase Return"
        self.title_text = f"{label} Register"
        self.sub_text   = ("Credit Notes issued to customers." if kind == "Sales Return"
                           else "Debit Notes raised on suppliers.")
        self.with_fy    = False
        super().__init__(master, con)
        today = date.today()
        self.d1 = T.entry(self.bar, width=120)
        self.d1.insert(0, today.replace(day=1).strftime("%d-%m-%Y"))
        self.d2 = T.entry(self.bar, width=120)
        self.d2.insert(0, today.strftime("%d-%m-%Y"))
        T.button(self.bar, "Show", self.refresh, width=70).pack(side="right")
        self.d2.pack(side="right", padx=6)
        ctk.CTkLabel(self.bar, text="to", text_color=T.MUTED).pack(side="right")
        self.d1.pack(side="right", padx=6)
        T.button(self.bar, "Export Excel", self.export, width=120,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="right", padx=(10, 0))
        self.msg = ctk.CTkLabel(self, text="", font=T.f(13), text_color=T.DANGER)
        self.msg.pack(anchor="w", padx=28)
        cols = [("dt", "Date",    90,  L), ("no", "No.",    50,  L),
                ("p",  "Party",  190,  L), ("tx", "Taxable",110, R),
                ("cg", "CGST",    85,  R), ("sg", "SGST",    85, R),
                ("ig", "IGST",    85,  R), ("t",  "Total",  110, R)]
        note = "credit notes" if kind == "Sales Return" else "debit notes"
        self.table = DataTable(
            self, cols, height=14,
            empty_text=f"No {note} between these dates. Change the dates and click Show.")
        self.table.pack(fill="both", expand=True, padx=28, pady=(4, 24))
        if opener:
            self.table.on_open(lambda vid: self.opener(vid, self.refresh))
        self.refresh()

    def _get_rows(self):
        try:
            d1 = parse_date(self.d1.get())
            d2 = parse_date(self.d2.get())
        except ValueError as e:
            self.msg.configure(text=str(e))
            return None, None, None
        self.msg.configure(text="")
        q = """SELECT v.id, v.vdate, v.vno, v.narration, i.party, i.taxable,
                      i.cgst, i.sgst, i.igst, i.total, i.customer_name
               FROM vouchers v LEFT JOIN invoices i ON i.voucher_id=v.id
               WHERE v.vtype=? AND v.vdate BETWEEN ? AND ?
               ORDER BY v.vdate, v.vno"""
        rows = self.con.execute(
            q, (self.kind, d1.isoformat(), d2.isoformat())).fetchall()
        return rows, d1, d2

    def refresh(self):
        rows, d1, d2 = self._get_rows()
        if rows is None:
            return
        from db.setup import to_rupees
        out, tot = [], [0] * 5
        for x in rows:
            has   = x["party"] is not None
            party = ((f"{x['party']} ({x['customer_name']})"
                      if x["customer_name"] else x["party"])
                     if has else "(details not stored)")
            vals = [to_rupees(x["taxable"]) if has else 0,
                    to_rupees(x["cgst"])    if has else 0,
                    to_rupees(x["sgst"])    if has else 0,
                    to_rupees(x["igst"])    if has else 0,
                    to_rupees(x["total"])   if has else 0]
            for i in range(5):
                tot[i] += vals[i]
            out.append(((disp_date(x["vdate"]), x["vno"], party,
                         *[_amt(v) for v in vals]), None, x["id"]))
        if rows:
            out.append((("", "", f"Total ({len(rows)} vouchers)",
                         inr(tot[0]), inr(tot[1]), inr(tot[2]), inr(tot[3]), inr(tot[4])),
                        "total"))
        self.table.set_rows(out)

    def export_data(self):
        rows, d1, d2 = self._get_rows()
        if rows is None:
            return f"{self.title_text}", [], []
        from db.setup import to_rupees
        label = "Sales Return" if self.kind == "Sales Return" else "Purchase Return"
        title = (f"{label} Register "
                 f"{disp_date(d1.isoformat())} to {disp_date(d2.isoformat())}")
        headers = ["Date", "No.", "Party", "Taxable", "CGST", "SGST", "IGST", "Total"]
        out = []
        for x in rows:
            has   = x["party"] is not None
            party = ((f"{x['party']} ({x['customer_name']})"
                      if x["customer_name"] else x["party"])
                     if has else "(details not stored)")
            out.append([disp_date(x["vdate"]), x["vno"], party,
                        to_rupees(x["taxable"]) if has else 0,
                        to_rupees(x["cgst"])    if has else 0,
                        to_rupees(x["sgst"])    if has else 0,
                        to_rupees(x["igst"])    if has else 0,
                        to_rupees(x["total"])   if has else 0])
        return title, headers, out


# ── Stock Summary ─────────────────────────────────────────────────────────────
class StockSummaryFrame(ReportBase):
    title_text = "Stock Summary"
    sub_text   = "Item-wise stock position and value for the financial year."

    def __init__(self, master, con):
        super().__init__(master, con)
        self.table = DataTable(self, [
            ("n", "Item",        200, L), ("h", "HSN",         80, L),
            ("u", "Unit",         60, L), ("o", "Opening",     90, "c"),
            ("p", "Purchased",  100, "c"), ("s", "Sold",        90, "c"),
            ("c", "Closing",    100, "c"), ("r", "Avg Rate",   110, R),
            ("v", "Stock Value",130, R)], height=14,
            empty_text="No stock items yet. Add items under Masters > Stock Items.")
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def _fmt(self, v):
        return f"{v:,.3f}".rstrip("0").rstrip(".")

    def refresh(self):
        from db.setup import stock_summary
        rows = stock_summary(self.con, self.fy.get())
        out = []
        totals      = [0.0] * 4
        total_value = 0.0
        for it in rows:
            vals = [it["opening"], it["purchased"], it["sold"], it["closing"]]
            for i, v in enumerate(vals):
                totals[i] += v
            total_value += it.get("stock_value", 0.0)
            out.append((it["name"], it["hsn"] or "-", it["unit"],
                        self._fmt(it["opening"]), self._fmt(it["purchased"]),
                        self._fmt(it["sold"]),    self._fmt(it["closing"]),
                        inr(it.get("avg_rate",    0.0)) if it.get("avg_rate")    else "",
                        inr(it.get("stock_value", 0.0)) if it.get("stock_value") else ""))
        if rows:
            out.append((("", "", "Total",
                         self._fmt(totals[0]), self._fmt(totals[1]),
                         self._fmt(totals[2]), self._fmt(totals[3]),
                         "", inr(total_value)), "total"))
        self.table.set_rows(out)

    def export_data(self):
        from db.setup import stock_summary
        rows = stock_summary(self.con, self.fy.get())
        headers = ["Item", "HSN", "Unit", "Opening", "Purchased", "Sold",
                   "Closing", "Avg Rate", "Stock Value"]
        data = [[it["name"], it["hsn"], it["unit"], it["opening"],
                 it["purchased"], it["sold"], it["closing"],
                 it.get("avg_rate", 0.0), it.get("stock_value", 0.0)]
                for it in rows]
        return f"Stock Summary {self.fy.get()}", headers, data


# ── Item-wise Profit ──────────────────────────────────────────────────────────
class ItemWiseProfitFrame(ReportBase):
    title_text = "Item-wise Profit"
    sub_text   = "Profit per item based on weighted-average cost of goods sold."

    def __init__(self, master, con):
        super().__init__(master, con)
        self.table = DataTable(self, [
            ("n", "Item",         200, L), ("u", "Unit",          60, L),
            ("q", "Sold Qty",     100, "e"), ("s", "Sale Value",  140, R),
            ("a", "Avg Cost",     120, R),  ("c", "Cost of Sold", 140, R),
            ("p", "Profit",       140, R),  ("m", "Margin %",      90, R)], height=14,
            empty_text="No item sales in this financial year yet.")
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def _fmt_qty(self, v):
        return f"{v:,.3f}".rstrip("0").rstrip(".")

    def refresh(self):
        from db.setup import item_wise_profit
        rows = item_wise_profit(self.con, self.fy.get())
        out = []
        tot_sale = tot_cost = tot_profit = 0.0
        for it in rows:
            tot_sale   += it["sale_value"]
            tot_cost   += it["cost_of_sold"]
            tot_profit += it["profit"]
            out.append((it["name"], it["unit"],
                        self._fmt_qty(it["sold_qty"]),
                        inr(it["sale_value"]),
                        inr(it["avg_cost"]) if it["avg_cost"] else "",
                        inr(it["cost_of_sold"]),
                        inr(it["profit"]),
                        f"{it['margin']:.2f}"))
        if rows:
            tot_margin = (tot_profit / tot_sale * 100) if tot_sale > 0 else 0.0
            out.append((("", "", "Total",
                         inr(tot_sale), "", inr(tot_cost),
                         inr(tot_profit), f"{tot_margin:.2f}"), "total"))
        self.table.set_rows(out)

    def export_data(self):
        from db.setup import item_wise_profit
        rows = item_wise_profit(self.con, self.fy.get())
        headers = ["Item", "Unit", "Sold Qty", "Sale Value",
                   "Avg Cost", "Cost of Sold", "Profit", "Margin %"]
        data = [[it["name"], it["unit"], it["sold_qty"], it["sale_value"],
                 it["avg_cost"], it["cost_of_sold"], it["profit"],
                 round(it["margin"], 2)] for it in rows]
        return f"Item-wise Profit {self.fy.get()}", headers, data


_MONTHS = ["April", "May", "June", "July", "August", "September",
           "October", "November", "December", "January", "February", "March"]


# ── GSTR-1 ────────────────────────────────────────────────────────────────────
class GSTR1Frame(ReportBase):
    title_text = "GSTR-1 (Outward)"
    sub_text   = "Monthly outward supply summary and invoice-wise detail."

    def __init__(self, master, con):
        super().__init__(master, con)
        from datetime import date as _d
        today = _d.today()
        default_month = (today.month - 3) % 12 or 12
        self.month = T.option_menu(self.bar, _MONTHS, width=130,
                                   command=lambda _v: self.refresh())
        self.month.set(_MONTHS[default_month - 1])
        self.month.pack(side="right", padx=(10, 0))
        T.button(self.bar, "Export JSON", self._export_json, width=120,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="right", padx=(10, 0))
        self.summary_lbl = ctk.CTkLabel(self, text="SUMMARY (by GST rate)",
                                        font=T.f(12, "bold"), text_color=T.MUTED)
        self.summary_lbl.pack(anchor="w", padx=28, pady=(4, 4))
        self.summary_tbl = DataTable(self, [
            ("k",  "Type",     70, L), ("r",  "Rate %",  70, R),
            ("tx", "Taxable", 140, R), ("cg", "CGST",   110, R),
            ("sg", "SGST",    110, R), ("ig", "IGST",   110, R),
            ("t",  "Total",   140, R)], height=6)
        self.summary_tbl.pack(fill="x", padx=28, pady=(0, 10))
        self.detail_lbl = ctk.CTkLabel(self, text="INVOICE DETAIL",
                                       font=T.f(12, "bold"), text_color=T.MUTED)
        self.detail_lbl.pack(anchor="w", padx=28, pady=(4, 4))
        self.detail_tbl = DataTable(self, [
            ("dt", "Date",    90, L), ("no", "No.",     50, L),
            ("p",  "Party",  170, L), ("g",  "GSTIN",  140, L),
            ("s",  "Supply",  70, L), ("tx", "Taxable",110, R),
            ("cg", "CGST",    90, R), ("sg", "SGST",    90, R),
            ("ig", "IGST",    90, R), ("t",  "Total",  110, R)], height=10)
        self.detail_tbl.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def _mnum(self):
        return _MONTHS.index(self.month.get()) + 1

    def refresh(self):
        from db.setup import gstr1_report
        rep   = gstr1_report(self.con, self.fy.get(), self._mnum())
        srows = [(s["kind"], s["rate"], inr(s["taxable"]), inr(s["cgst"]),
                  inr(s["sgst"]), inr(s["igst"]), inr(s["total"]))
                 for s in rep["summary"]]
        t = rep["totals"]
        srows.append((("", "Total", inr(t["taxable"]), inr(t["cgst"]),
                       inr(t["sgst"]), inr(t["igst"]), inr(t["total"])), "total"))
        self.summary_tbl.set_rows(srows)
        drows = [(disp_date(i["date"]), i["vno"],
                  (i["party"] + (" (CN)" if i["vtype"] == "Sales Return" else "")),
                  i["gstin"] or "-", i["supply"],
                  inr(i["taxable"]), _amt(i["cgst"]), _amt(i["sgst"]),
                  _amt(i["igst"]), inr(i["total"])) for i in rep["invoices"]]
        drows.append((("", "", f"Total ({len(rep['invoices'])} invoices)", "", "",
                       inr(t["taxable"]), inr(t["cgst"]), inr(t["sgst"]),
                       inr(t["igst"]), inr(t["total"])), "total"))
        self.detail_tbl.set_rows(drows)

    def _export_json(self):
        import json
        from db.setup import gstr1_json
        from utils import settings as _st
        st    = _st.load_settings()
        gstin = (st.get("gstin") or "GSTIN").strip().upper().replace("/", "")
        default_name = f"GSTR1_{gstin}_{self.month.get()}_{self.fy.get()}.json"
        path = filedialog.asksaveasfilename(
            title="Save GSTR-1 JSON",
            defaultextension=".json",
            filetypes=[("JSON file", "*.json")],
            initialfile=default_name)
        if not path:
            return
        try:
            data = gstr1_json(self.con, self.fy.get(), self._mnum())
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("MUNIM", f"Could not save JSON:\n{e}")
            return
        messagebox.showinfo("MUNIM",
                            f"GSTR-1 JSON saved:\n{path}\n\n"
                            "Upload this file in the GST portal offline tool.")

    def export_data(self):
        from db.setup import gstr1_report
        rep  = gstr1_report(self.con, self.fy.get(), self._mnum())
        rows = [["SUMMARY", "", "", "", "", "", ""]]
        rows.append(["Type", "Rate %", "Taxable", "CGST", "SGST", "IGST", "Total"])
        for s in rep["summary"]:
            rows.append([s["kind"], s["rate"], s["taxable"], s["cgst"],
                         s["sgst"], s["igst"], s["total"]])
        t = rep["totals"]
        rows.append(["", "Total", t["taxable"], t["cgst"], t["sgst"], t["igst"], t["total"]])
        rows.append(["", "", "", "", "", "", ""])
        rows.append(["INVOICE DETAIL", "", "", "", "", "", ""])
        rows.append(["Date", "No.", "Party", "GSTIN", "Supply", "Taxable", "Total"])
        for i in rep["invoices"]:
            rows.append([disp_date(i["date"]), i["vno"], i["party"],
                         i["gstin"] or "", i["supply"], i["taxable"], i["total"]])
        title = f"GSTR-1 {self.month.get()} {self.fy.get()}"
        return title, ["Col1", "Col2", "Col3", "Col4", "Col5", "Col6", "Col7"], rows


# ── GSTR-3B ───────────────────────────────────────────────────────────────────
class GSTR3BFrame(ReportBase):
    title_text = "GSTR-3B (Summary)"
    sub_text   = "Monthly GST: outward tax, ITC, net payable, and suggested payment breakdown."

    def __init__(self, master, con):
        super().__init__(master, con)
        from datetime import date as _d
        today = _d.today()
        default_month = (today.month - 3) % 12 or 12
        self.month = T.option_menu(self.bar, _MONTHS, width=130,
                                   command=lambda _v: self.refresh())
        self.month.set(_MONTHS[default_month - 1])
        self.month.pack(side="right", padx=(10, 0))
        self.table = DataTable(self, [
            ("s",  "Section",               380, L),
            ("tx", "Taxable / Amount (Rs)", 180, R),
            ("cg", "CGST (Rs)",             140, R),
            ("sg", "SGST (Rs)",             140, R),
            ("ig", "IGST (Rs)",             140, R)], height=26)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def _mnum(self):
        return _MONTHS.index(self.month.get()) + 1

    def refresh(self):
        from db.setup import gstr3b_report
        rep = gstr3b_report(self.con, self.fy.get(), self._mnum())
        o   = rep["outward"]
        i   = rep["net_itc"]
        ir  = rep["itc_reversed"]
        rcm = rep["rcm_liability"]
        n   = rep["net"]
        itc_used, cash, bal = rep["paid_by_itc"], rep["paid_by_cash"], rep["itc_balance"]
        rows = [
            (("3.1  OUTWARD SUPPLIES", "", "", "", ""), "head"),
            (("     (a) Outward taxable supplies (other than zero-rated, nil, exempted)",
              inr(o["taxable"]), inr(o["cgst"]), inr(o["sgst"]), inr(o["igst"])), None),
            (("     (b) Zero-rated / exports (not applicable)", "", "", "", ""), None),
            (("     (c) Other outward supplies (nil-rated, exempt)",
              inr(rep["nil_exempt"]), "", "", ""), None),
            (("     (d) Inward supplies liable to reverse charge (RCM)",
              inr(rcm["taxable"]), inr(rcm["cgst"]), inr(rcm["sgst"]), inr(rcm["igst"])), None),
            (("3.2  INTER-STATE SUPPLIES TO UNREGISTERED PERSONS",
              inr(rep["b2c_inter"]["taxable"]), "", "",
              inr(rep["b2c_inter"]["igst"])), "head"),
            (("4    ELIGIBLE ITC", "", "", "", ""), "head"),
            (("     (A) ITC available — normal purchases",
              "", inr(rep["itc"]["cgst"]), inr(rep["itc"]["sgst"]),
              inr(rep["itc"]["igst"])), None),
            (("     (B) ITC reversed — RCM (self-assessed)",
              "", inr(ir["cgst"]), inr(ir["sgst"]), inr(ir["igst"])), None),
            (("     (C) Net ITC available (A − B)",
              "", inr(i["cgst"]), inr(i["sgst"]), inr(i["igst"])), None),
            (("     (D) Ineligible ITC", "", "—", "—", "—"), None),
            (("     Net GST payable after cross-utilisation",
              "", inr(n["cgst"]), inr(n["sgst"]), inr(n["igst"])), "total"),
            (("     Total net payable", inr(n["total"]), "", "", ""), "total"),
            (("5    Exempt / nil-rated inward supplies", "", "—", "—", "—"), "head"),
            (("", "", "", "", ""), None),
            (("6.1  SUGGESTED PAYMENT BREAKDOWN (ITC cross-utilisation applied)",
              "", "", "", ""), "head"),
            (("     Paid through ITC",
              "", inr(itc_used["cgst"]), inr(itc_used["sgst"]),
              inr(itc_used["igst"])), None),
            (("     Paid in cash",
              "", inr(cash["cgst"]), inr(cash["sgst"]), inr(cash["igst"])), None),
            (("     Unused ITC balance (c/f)",
              "", inr(bal["cgst"]), inr(bal["sgst"]), inr(bal["igst"])), None),
            (("6.2  TDS / TCS credits", "", "—", "—", "—"), "head"),
            (("", "", "", "", ""), None),
            (("Closing stock value (reference, from Stock Summary)",
              inr(rep["stock_value"]), "", "", ""), "head"),
        ]
        self.table.set_rows(rows)

    def export_data(self):
        from db.setup import gstr3b_report
        rep = gstr3b_report(self.con, self.fy.get(), self._mnum())
        o   = rep["outward"]
        i   = rep["net_itc"]
        ir  = rep["itc_reversed"]
        rcm = rep["rcm_liability"]
        n   = rep["net"]
        itc_used, cash, bal = rep["paid_by_itc"], rep["paid_by_cash"], rep["itc_balance"]
        rows = [
            ["3.1  OUTWARD SUPPLIES",    "", "", "", ""],
            ["(a) Outward taxable",       o["taxable"], o["cgst"],  o["sgst"],  o["igst"]],
            ["(b) Zero-rated / exports",  0,            0,          0,          0],
            ["(c) Nil-rated, exempt",     rep["nil_exempt"], "",    "",         ""],
            ["(d) RCM inward",            rcm["taxable"], rcm["cgst"], rcm["sgst"], rcm["igst"]],
            ["3.2  Inter-state B2C",      rep["b2c_inter"]["taxable"], "", "",
                                          rep["b2c_inter"]["igst"]],
            ["4    ELIGIBLE ITC",         "", "", "", ""],
            ["(A) ITC available",         "",
             rep["itc"]["cgst"], rep["itc"]["sgst"], rep["itc"]["igst"]],
            ["(B) ITC reversed (RCM)",    "", ir["cgst"],  ir["sgst"],  ir["igst"]],
            ["(C) Net ITC",               "", i["cgst"],   i["sgst"],   i["igst"]],
            ["(D) Ineligible ITC",        "", 0,           0,           0],
            ["Net payable",               "", n["cgst"],   n["sgst"],   n["igst"]],
            ["Total net payable",         n["total"],      "", "",       ""],
            ["5    Exempt inward",        0,  0,           0,           0],
            ["6.1  Paid through ITC",     "",
             itc_used["cgst"], itc_used["sgst"], itc_used["igst"]],
            ["6.1  Paid in cash",         "",
             cash["cgst"],     cash["sgst"],     cash["igst"]],
            ["6.1  Unused ITC (c/f)",     "",
             bal["cgst"],      bal["sgst"],      bal["igst"]],
            ["6.2  TDS/TCS",             0, 0, 0, 0],
            ["Closing stock (reference)", rep["stock_value"], "", "", ""],
        ]
        headers = ["Section", "Amount (Rs)", "CGST", "SGST", "IGST"]
        title   = f"GSTR-3B {self.month.get()} {self.fy.get()}"
        return title, headers, rows


# ── Cash Flow ─────────────────────────────────────────────────────────────────
class CashFlowFrame(ReportBase):
    title_text = "Cash Flow Statement"
    sub_text   = ("Sources and uses of cash: operating, financing, "
                  "and investing activities.")

    def __init__(self, master, con):
        super().__init__(master, con)
        self.table = DataTable(self, [
            ("s", "Particulars", 400, L),
            ("a", "Amount (Rs)", 160, R)], height=18)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def refresh(self):
        from db.reports import cash_flow
        cf   = cash_flow(self.con, self.fy.get())
        rows = []

        def section(title, items, total):
            rows.append((("", ""), "head"))
            rows.append(((title, ""), "head"))
            for name, amt in items:
                rows.append((name, _amt(amt)))
            rows.append((("  Total", inr(total)), "total"))

        section("A. OPERATING ACTIVITIES",
                cf["operating"]["items"], cf["operating"]["total"])
        section("B. FINANCING ACTIVITIES",
                cf["financing"]["items"], cf["financing"]["total"])
        section("C. INVESTING ACTIVITIES",
                cf["investing"]["items"], cf["investing"]["total"])
        rows.append((("", ""), None))
        rows.append((("Net increase / (decrease) in cash",
                      inr(cf["net_change"])), "total"))
        rows.append((("Opening cash & bank balance",
                      inr(cf["opening_cash"])), None))
        rows.append((("Closing cash & bank balance",
                      inr(cf["closing_cash"])), "total"))
        self.table.set_rows(rows)

    def export_data(self):
        from db.reports import cash_flow
        cf   = cash_flow(self.con, self.fy.get())
        rows = []
        for section, key in (("Operating", "operating"),
                              ("Financing", "financing"),
                              ("Investing", "investing")):
            rows.append([section, ""])
            for name, amt in cf[key]["items"]:
                rows.append([name, amt])
            rows.append(["Total", cf[key]["total"]])
            rows.append(["", ""])
        rows.append(["Net change in cash",    cf["net_change"]])
        rows.append(["Opening cash & bank",   cf["opening_cash"]])
        rows.append(["Closing cash & bank",   cf["closing_cash"]])
        return (f"Cash Flow {self.fy.get()}",
                ["Particulars", "Amount (Rs)"], rows)


# ── Party Statement ───────────────────────────────────────────────────────────
class PartyStatementFrame(ReportBase):
    title_text = "Party Statement"
    sub_text   = ("Full account statement for one party — "
                  "opening, all transactions, closing.")
    with_fy    = True

    def __init__(self, master, con):
        super().__init__(master, con)
        names = [p["name"] for p in con.execute(
            "SELECT name FROM parties ORDER BY name COLLATE NOCASE")]
        self.party = T.combo(self.bar, names, width=240,
                             command=lambda _v: self.refresh())
        self.party.set(names[0] if names else "")
        self.party.pack(side="right", padx=(10, 0))
        T.button(self.bar, "Show", self.refresh, width=70).pack(
            side="right", padx=(10, 0))

        # Date range
        dr_row = ctk.CTkFrame(self, fg_color="transparent")
        dr_row.pack(fill="x", padx=28, pady=(0, 6))
        ctk.CTkLabel(dr_row, text="From", font=T.f(12),
                     text_color=T.MUTED).pack(side="left", padx=(0, 4))
        self._d1 = T.entry(dr_row, width=120)
        today    = date.today()
        y = today.year if today.month >= 4 else today.year - 1
        self._d1.insert(0, f"01-04-{y}")
        self._d1.pack(side="left", padx=(0, 4))
        ctk.CTkLabel(dr_row, text="to", font=T.f(12),
                     text_color=T.MUTED).pack(side="left", padx=4)
        self._d2 = T.entry(dr_row, width=120)
        self._d2.insert(0, today.strftime("%d-%m-%Y"))
        self._d2.pack(side="left", padx=(0, 8))
        T.button(dr_row, "Show", self.refresh, width=70,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="left")
        self._d1.bind("<Return>", lambda _e: self.refresh())
        self._d2.bind("<Return>", lambda _e: self.refresh())

        self.summary = ctk.CTkLabel(self, text="", font=T.f(13, "bold"),
                                    text_color=T.TEXT)
        self.summary.pack(anchor="w", padx=28, pady=(0, 8))
        self.table = DataTable(self, [
            ("dt", "Date",        100, L), ("v",  "Voucher",    140, L),
            ("n",  "Narration",   280, L), ("d",  "Debit (Rs)", 130, R),
            ("c",  "Credit (Rs)", 130, R), ("b",  "Balance",    150, R)],
            height=14,
            empty_text=("Choose a party to see its statement." if names else
                        "No parties yet. Add a customer or supplier under "
                        "Masters > Party Master."))
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.refresh()

    def _dates(self):
        try:
            return parse_date(self._d1.get()), parse_date(self._d2.get())
        except Exception:
            return None, None

    def refresh(self):
        from db.reports import party_statement
        name = self.party.get().strip()
        if not name:
            return
        d1, d2 = self._dates()
        try:
            ps = party_statement(self.con, name, self.fy.get(), d1, d2)
        except ValueError as e:
            self.summary.configure(text=str(e), text_color=T.DANGER)
            self.table.set_rows([])
            return
        rows = [(("", "", "Opening balance", "", "",
                  f"{inr(ps['opening'])} {ps['opening_side']}"), "head")]
        for x in ps["rows"]:
            rows.append((disp_date(x["date"]),
                         f"{x['vtype']} #{x['vno']}",
                         x["narration"],
                         _amt(x["dr"]), _amt(x["cr"]),
                         f"{inr(x['balance'])} {x['side']}"))
        rows.append((("", "", "Total",
                      inr(ps["total_dr"]), inr(ps["total_cr"]),
                      f"{inr(ps['closing'])} {ps['closing_side']}"), "total"))
        self.table.set_rows(rows)
        gstin = f"  |  GSTIN: {ps['gstin']}" if ps["gstin"] else ""
        self.summary.configure(
            text=(f"{name} ({ps['ptype']}){gstin}   |   "
                  f"Closing: Rs {inr(ps['closing'])} {ps['closing_side']}"),
            text_color=T.TEXT)

    def export_data(self):
        from db.reports import party_statement
        name = self.party.get().strip()
        if not name:
            return "Party Statement", [], []
        d1, d2 = self._dates()
        try:
            ps = party_statement(self.con, name, self.fy.get(), d1, d2)
        except ValueError:
            return "Party Statement", [], []
        headers = ["Date", "Voucher", "Narration",
                   "Debit (Rs)", "Credit (Rs)", "Balance"]
        rows = [[disp_date(x["date"]), f"{x['vtype']} #{x['vno']}",
                 x["narration"], x["dr"], x["cr"],
                 f"{x['balance']} {x['side']}"]
                for x in ps["rows"]]
        return (f"Party Statement {name} {self.fy.get()}", headers, rows)


# ── Bank Reconciliation ───────────────────────────────────────────────────────
class BankReconFrame(ReportBase):
    title_text = "Bank Reconciliation"
    sub_text   = ("Import your bank statement CSV and match entries to your books. "
                  "Unmatched items on either side need investigation.")
    with_fy    = False
    # Class attribute so ReportBase.__init__ sees it and skips its own
    # Export Excel button (this screen has one in its control card).
    own_controls = True

    def __init__(self, master, con):
        super().__init__(master, con)
        self._recon_rows   = []
        ctrl = T.card(self)
        ctrl.pack(fill="x", padx=28, pady=(0, 10))
        bank_names = [row["name"] for row in con.execute(
            "SELECT name FROM accounts "
            "WHERE grp IN ('Bank Accounts','Cash-in-hand') "
            "ORDER BY name")]
        if not bank_names:
            bank_names = ["Bank", "Cash"]
        self.account = T.option_menu(ctrl, bank_names, width=160,
                                     command=lambda _v: self.refresh())
        self.account.set("Bank" if "Bank" in bank_names else bank_names[0])
        ctk.CTkLabel(ctrl, text="Account", font=T.f(12),
                     text_color=T.MUTED).grid(
            row=0, column=0, sticky="w", padx=(20, 8), pady=(12, 2))
        self.account.grid(row=1, column=0, padx=(20, 8), pady=(0, 14))
        T.button(ctrl, "Import CSV", self._import_csv, width=120).grid(
            row=1, column=1, padx=8, pady=(0, 14))
        T.button(ctrl, "Clear all", self._clear, width=100,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").grid(row=1, column=2, padx=8, pady=(0, 14))
        T.button(ctrl, "Export Excel", self.export, width=120,
                 fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").grid(row=1, column=3, padx=8, pady=(0, 14))
        ctk.CTkLabel(ctrl,
                     text="CSV format: Date (DD-MM-YYYY), Description, Amount, Dr/Cr",
                     font=T.f(11), text_color=T.MUTED).grid(
            row=2, column=0, columnspan=4, sticky="w", padx=20, pady=(0, 10))
        self.summary_lbl = ctk.CTkLabel(self, text="", font=T.f(13, "bold"),
                                        text_color=T.TEXT)
        self.summary_lbl.pack(anchor="w", padx=28, pady=(0, 8))
        self.table = DataTable(self, [
            ("dt",  "Stmt Date",   100, L),
            ("dsc", "Description", 240, L),
            ("amt", "Amount",      110, R),
            ("typ", "Dr/Cr",        60, L),
            ("mat", "Best match",  200, L),
            ("sts", "Status",       90, L)], height=14,
            empty_text=("No statement loaded yet.\n"
                        "Click Import CSV and choose your bank statement "
                        "(Date DD-MM-YYYY, Description, Amount, Dr/Cr)."))
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 10))
        self.table.on_open(self._on_row_open)
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=28, pady=(0, 16))
        T.button(foot, "Mark selected as reconciled",
                 self._reconcile_selected, width=220).pack(side="left")
        self.foot_msg = ctk.CTkLabel(foot, text="", font=T.f(12),
                                     text_color=T.MUTED)
        self.foot_msg.pack(side="left", padx=12)
        self.refresh()

    def _import_csv(self):
        import csv
        from db.setup import import_bank_statement
        path = filedialog.askopenfilename(
            title="Open bank statement CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        rows = []
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                for line in reader:
                    if len(line) < 4:
                        continue
                    try:
                        d     = parse_date(line[0].strip())
                        desc  = line[1].strip()
                        amt   = float(line[2].strip().replace(",", ""))
                        dr_cr = line[3].strip().upper()
                        dr_cr = ("Dr" if dr_cr in ("DR", "D", "DEBIT") else "Cr")
                        rows.append((d.isoformat(), desc, amt, dr_cr))
                    except Exception:
                        continue
        except Exception as e:
            messagebox.showerror("MUNIM", f"Could not read CSV:\n{e}")
            return
        if not rows:
            messagebox.showwarning(
                "MUNIM",
                "No valid rows found.\n\n"
                "Expected format: Date, Description, Amount, Dr/Cr")
            return
        count = import_bank_statement(self.con, self.account.get(), rows)
        messagebox.showinfo("MUNIM", f"{count} rows imported.")
        self.refresh()

    def _clear(self):
        from db.setup import clear_recon
        if not messagebox.askyesno(
                "Clear reconciliation",
                "Remove all imported statement rows for this account?"):
            return
        clear_recon(self.con, self.account.get())
        self.refresh()

    def refresh(self):
        from db.setup import get_recon_rows, recon_summary
        account = self.account.get()
        rows    = get_recon_rows(self.con, account)
        summary = recon_summary(self.con, account)
        self.summary_lbl.configure(
            text=(f"Total: {summary['total']} rows  |  "
                  f"Matched: {summary['matched']}  |  "
                  f"Unmatched: {summary['unmatched']}  |  "
                  f"Statement balance: Rs {inr(summary['stmt_balance'])}"))
        self._recon_rows = rows
        out = []
        for row in rows:
            match_text = ""
            if row["matches"]:
                m = row["matches"][0]
                match_text = f"{m['vtype']} #{m['vno']}"
            status = ("✓ Matched"  if row["voucher_id"] else
                      "Suggested"  if row["matches"]    else
                      "Unmatched")
            out.append(((disp_date(row["date"]), row["desc"][:40],
                          inr(row["amount"]), row["type"],
                          match_text, status),
                         "total" if status == "✓ Matched" else None,
                         row["id"]))
        self.table.set_rows(out)

    def _on_row_open(self, recon_id):
        from db.setup import reconcile_row
        row = next((x for x in self._recon_rows if x["id"] == recon_id), None)
        if not row:
            return
        if row["matches"]:
            reconcile_row(self.con, recon_id, row["matches"][0]["id"])
            self.foot_msg.configure(
                text=(f"Matched to "
                      f"{row['matches'][0]['vtype']} #{row['matches'][0]['vno']}"),
                text_color=T.OK)
        else:
            reconcile_row(self.con, recon_id, None)
            self.foot_msg.configure(
                text="Marked reconciled (no voucher match)",
                text_color=T.MUTED)
        self.refresh()

    def _reconcile_selected(self):
        key = self.table.selected_key()
        if not key:
            self.foot_msg.configure(text="Select a row first",
                                    text_color=T.DANGER)
            return
        self._on_row_open(key)

    def export_data(self):
        from db.setup import get_recon_rows
        rows    = get_recon_rows(self.con, self.account.get())
        headers = ["Date", "Description", "Amount", "Dr/Cr",
                   "Best match", "Status"]
        data    = []
        for row in rows:
            match_text = ""
            if row["matches"]:
                m = row["matches"][0]
                match_text = f"{m['vtype']} #{m['vno']}"
            status = ("Matched"   if row["voucher_id"] else
                      "Suggested" if row["matches"]    else
                      "Unmatched")
            data.append([disp_date(row["date"]), row["desc"],
                          row["amount"], row["type"], match_text, status])
        return (f"Bank Reconciliation {self.account.get()}",
                headers, data)