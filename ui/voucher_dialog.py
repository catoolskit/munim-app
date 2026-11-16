from tkinter import messagebox
import customtkinter as ctk
from db import setup as s
from ui import theme as T
from ui.widgets import DataTable
from utils.fmt import inr, disp_date


def _num(text):
    f = float(text)
    return str(int(f)) if f == int(f) else str(f)


class VoucherDialog(ctk.CTkToplevel):
    """Shows one saved voucher or invoice, with Edit and Delete."""
    def __init__(self, master, con, vid, username, on_edit, on_changed):
        super().__init__(master)
        self.con, self.vid, self.username = con, vid, username
        self.on_edit, self.on_changed = on_edit, on_changed
        snap = s.voucher_snapshot(con, vid)
        self.snap, inv = snap, snap["invoice"]
        self.title(f"{snap['vtype']} #{snap['vno']}")
        self.geometry("820x700")
        self.minsize(760, 600)
        self.configure(fg_color=T.BG)

        editable = (bool(inv) or snap["vtype"] in s.MANUAL_TYPES) and not snap["applied_to"]
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=24, pady=16)
        if editable:
            T.button(bar, "Edit", self.edit, width=110).pack(side="left")
        else:
            why = ("It settles bills" if snap["applied_to"] else "Saved before item details were stored")
            ctk.CTkLabel(bar, text=f"{why}: delete and re-enter to change it.",
                         font=T.f(12), text_color=T.MUTED).pack(side="left")
        T.button(bar, "Delete", self.delete, width=110, fg_color=T.DANGER,
                 hover_color="#A32F23").pack(side="left", padx=10)
        T.button(bar, "Close", self.destroy, width=110, fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="right")

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=(20, 8))
        ctk.CTkLabel(head, text=f"{snap['vtype']} no. {snap['vno']}", font=T.f(22, "bold"),
                     text_color=T.TEXT).pack(anchor="w")
        sub = f"{disp_date(snap['vdate'])}   |   FY {snap['fy']}"
        if inv:
            sub += f"   |   {inv['party']}"
        ctk.CTkLabel(head, text=sub, font=T.f(13), text_color=T.MUTED).pack(anchor="w", pady=(2, 0))
        if snap["narration"]:
            ctk.CTkLabel(head, text=f"Narration: {snap['narration']}", font=T.f(13),
                         text_color=T.TEXT).pack(anchor="w", pady=(4, 0))

        if inv:
            ctk.CTkLabel(self, text="Items", font=T.f(14, "bold"), text_color=T.TEXT).pack(
                anchor="w", padx=24, pady=(8, 4))
            items = DataTable(self, [("d", "Item", 280, "w"), ("q", "Qty", 70, "e"), ("r", "Rate", 100, "e"),
                                     ("g", "GST %", 70, "e"), ("a", "Amount (Rs)", 120, "e")], height=3)
            items.pack(fill="x", padx=24)
            items.set_rows([(i["description"], _num(i["qty"]), inr(float(i["rate"])), _num(i["gst"]),
                             inr(i["amount"] / 100)) for i in inv["items"]])
            k = lambda v: inr(v / 100)
            tax = f"IGST {k(inv['igst'])}" if inv["interstate"] else f"CGST {k(inv['cgst'])}   SGST {k(inv['sgst'])}"
            ctk.CTkLabel(self, text=f"Taxable {k(inv['taxable'])}     {tax}     Total {k(inv['total'])}",
                         font=T.f(13, "bold"), text_color=T.TEXT).pack(anchor="e", padx=24, pady=6)

        if inv:
            done = sum(p["amount"] for p in snap["payments_in"])
            status = "Paid" if done >= inv["total"] else ("Partly paid" if done else "Unpaid")
            color = T.OK if status == "Paid" else "#B26A00"
            word = "received" if inv["kind"] == "Sales" and inv["party"] not in ("Cash", "Bank") else "settled"
            if inv["party"] in ("Cash", "Bank"):
                line = f"Paid in {inv['party']} at the time of sale"
            else:
                line = f"{status}: {word} Rs {inr(done / 100)}, balance Rs {inr(max(inv['total'] - done, 0) / 100)}"
            ctk.CTkLabel(self, text=line, font=T.f(13, "bold"), text_color=color).pack(anchor="e", padx=24)
            if snap["payments_in"]:
                txt = "Payments: " + "; ".join(f"{p['vtype']} #{p['vno']} ({disp_date(p['vdate'])}) Rs {inr(p['amount'] / 100)}"
                                               for p in snap["payments_in"])
                ctk.CTkLabel(self, text=txt, font=T.f(12), text_color=T.MUTED, wraplength=770,
                             justify="right").pack(anchor="e", padx=24)
        if snap["applied_to"]:
            txt = "Settles: " + "; ".join(f"{p['vtype']} #{p['vno']} Rs {inr(p['amount'] / 100)}" for p in snap["applied_to"])
            ctk.CTkLabel(self, text=txt, font=T.f(13, "bold"), text_color=T.OK, wraplength=770,
                         justify="left").pack(anchor="w", padx=24, pady=(6, 0))

        ctk.CTkLabel(self, text="Accounting entries", font=T.f(14, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=24, pady=(8, 4))
        lines = DataTable(self, [("a", "Account", 380, "w"), ("d", "Debit (Rs)", 150, "e"),
                                 ("c", "Credit (Rs)", 150, "e")], height=4)
        lines.pack(fill="x", padx=24)
        rows = [(l["account"], inr(l["dr"] / 100) if l["dr"] else "", inr(l["cr"] / 100) if l["cr"] else "")
                for l in snap["lines"]]
        td = sum(l["dr"] for l in snap["lines"]) / 100
        rows.append((("Total", inr(td), inr(td)), "total"))
        lines.set_rows(rows)

        self.after(150, self._front)

    def _front(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass

    def edit(self):
        self.destroy()
        self.on_edit(self.vid)

    def delete(self):
        v = self.snap
        extra = ""
        if v["payments_in"]:
            extra = "\n\nPayments already recorded against this bill will stay as unmatched money on account."
        elif v["applied_to"]:
            extra = "\n\nThe bills it settled will become unpaid again."
        if not messagebox.askyesno(
                "Delete voucher", f"Delete {v['vtype']} no. {v['vno']}?{extra}\n\nThis cannot be undone, "
                "but it will be recorded in the Audit Log.", parent=self):
            return
        try:
            s.delete_voucher(self.con, self.vid, self.username)
        except ValueError as e:
            messagebox.showerror("MUNIM", str(e), parent=self)
            return
        self.destroy()
        self.on_changed()
