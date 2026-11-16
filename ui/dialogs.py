import customtkinter as ctk
from db import setup as s
from ui import theme as T
from ui.ux import chain_enter, focus_later


class PartyQuickDialog(ctk.CTkToplevel):
    """Add a customer or supplier without leaving the invoice screen."""
    def __init__(self, master, con, ptype, on_saved):
        super().__init__(master)
        self.con, self.ptype, self.on_saved = con, ptype, on_saved
        self.title(f"New {ptype.lower()}")
        self.geometry("420x360")
        self.resizable(False, False)
        self.configure(fg_color=T.BG)
        ctk.CTkLabel(self, text=f"New {ptype.lower()}", font=T.f(20, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=24, pady=(20, 10))
        self.name = T.entry(self, "Name *", width=370)
        self.gstin = T.entry(self, "GSTIN (optional)", width=370)
        self.phone = T.entry(self, "Mobile number (optional)", width=370)
        for w in (self.name, self.gstin, self.phone):
            w.pack(padx=24, pady=5)
        self.msg = ctk.CTkLabel(self, text="", font=T.f(12), text_color=T.DANGER, wraplength=360, justify="left")
        self.msg.pack(anchor="w", padx=24, pady=(4, 0))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=24, pady=18)
        T.button(bar, "Save", self.save, width=120).pack(side="left")
        T.button(bar, "Cancel", self.destroy, width=100, fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="left", padx=10)
        chain_enter([self.name, self.gstin, self.phone], self.save)
        self.after(150, self._front)

    def _front(self):
        try:
            self.lift(); self.focus_force(); self.grab_set()
            self.name._entry.focus_set()
        except Exception:
            pass

    def save(self):
        try:
            s.add_party(self.con, self.name.get(), self.ptype, self.gstin.get(), self.phone.get())
        except ValueError as e:
            self.msg.configure(text=str(e))
            return
        name = self.name.get().strip()
        self.destroy()
        self.on_saved(name)


class CreditDaysDialog(ctk.CTkToplevel):
    """Change how many days of credit a party gets (used for due-date ageing)."""
    def __init__(self, master, con, name, current, on_saved):
        super().__init__(master)
        self.con, self.name, self.on_saved = con, name, on_saved
        self.title("Credit days")
        self.geometry("380x230")
        self.resizable(False, False)
        self.configure(fg_color=T.BG)
        ctk.CTkLabel(self, text=name, font=T.f(18, "bold"), text_color=T.TEXT, wraplength=330,
                     justify="left").pack(anchor="w", padx=24, pady=(20, 2))
        ctk.CTkLabel(self, text="Credit days allowed for this party (0 = payable immediately)", font=T.f(12),
                     text_color=T.MUTED, wraplength=330, justify="left").pack(anchor="w", padx=24)
        self.days = T.entry(self, "0", width=120)
        self.days.insert(0, str(current))
        self.days.pack(anchor="w", padx=24, pady=12)
        self.msg = ctk.CTkLabel(self, text="", font=T.f(12), text_color=T.DANGER)
        self.msg.pack(anchor="w", padx=24)
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=24, pady=16)
        T.button(bar, "Save", self.save, width=110).pack(side="left")
        T.button(bar, "Cancel", self.destroy, width=100, fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="left", padx=10)
        chain_enter([self.days], self.save)
        self.after(150, self._front)

    def _front(self):
        try:
            self.lift(); self.focus_force(); self.grab_set(); self.days._entry.focus_set()
        except Exception:
            pass

    def save(self):
        try:
            s.set_credit_days(self.con, self.name, self.days.get())
        except ValueError as e:
            self.msg.configure(text=str(e))
            return
        self.destroy()
        self.on_saved()
