"""Admin screen: create, view and delete staff users."""
import customtkinter as ctk
from tkinter import messagebox
from db import setup as s
from ui import theme as T
from ui.ux import chain_enter, focus_later
from ui.widgets import DataTable


class UserMgmtFrame(ctk.CTkFrame):
    def __init__(self, master, con, current_username):
        super().__init__(master, fg_color="transparent")
        self.con = con
        self.current = current_username
        T.title(self, "User Management",
                "Create staff logins. Staff can enter transactions. "
                "Only admin can delete data or manage users."
                ).pack(anchor="w", padx=28, pady=(24, 12))
        card = T.card(self)
        card.pack(fill="x", padx=28)
        self.uname = T.entry(card, "Username (no spaces)", width=200)
        self.pw1   = T.entry(card, "Password (min 8 chars)", width=200, show="*")
        self.pw2   = T.entry(card, "Confirm password", width=200, show="*")
        self.role  = T.option_menu(card, ["staff", "admin"], width=120)
        for c, (h, w) in enumerate((("Username *", self.uname), ("Password *", self.pw1),
                                    ("Confirm *", self.pw2), ("Role", self.role))):
            ctk.CTkLabel(card, text=h, font=T.f(12), text_color=T.MUTED).grid(
                row=0, column=c, sticky="w", padx=(20 if c == 0 else 10, 10), pady=(14, 2))
            w.grid(row=1, column=c, padx=(20 if c == 0 else 10, 10), pady=(0, 14))
        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.grid(row=2, column=0, columnspan=4, sticky="ew", padx=20, pady=(0, 16))
        T.button(bar, "Create user", self.create, width=140).pack(side="left")
        self.msg = ctk.CTkLabel(bar, text="", font=T.f(13))
        self.msg.pack(side="left", padx=14)
        ctk.CTkLabel(self, text="All users", font=T.f(16, "bold"),
                     text_color=T.TEXT).pack(anchor="w", padx=28, pady=(14, 4))
        self.table = DataTable(self, [("u", "Username", 220, "w"),
                                      ("r", "Role", 110, "w"),
                                      ("m", "Status", 180, "w")], height=8)
        self.table.pack(fill="both", expand=True, padx=28, pady=(0, 10))
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=28, pady=(0, 20))
        T.button(foot, "Delete selected", self.delete, width=160,
                 fg_color=T.DANGER, hover_color="#A32F23").pack(side="left")
        T.button(foot, "Reset password", self.reset_pw, width=150,
                 fg_color="#E7ECF5", text_color=T.TEXT, hover_color="#DCE3F0").pack(side="left", padx=10)
        chain_enter([self.uname, self.pw1, self.pw2], self.create)
        focus_later(self.uname)
        self.refresh()

    def create(self):
        u = self.uname.get().strip()
        p1, p2 = self.pw1.get(), self.pw2.get()
        if not u:
            self.msg.configure(text="Username is required", text_color=T.DANGER); return
        if " " in u:
            self.msg.configure(text="No spaces in username", text_color=T.DANGER); return
        if p1 != p2:
            self.msg.configure(text="Passwords do not match", text_color=T.DANGER); return
        try:
            s.add_user(self.con, u, p1, self.role.get(), must_change=1)
        except Exception as e:
            self.msg.configure(text=str(e), text_color=T.DANGER); return
        for w in (self.uname, self.pw1, self.pw2):
            w.delete(0, "end")
        self.msg.configure(text=f"User '{u}' created", text_color=T.OK)
        self.refresh()
        focus_later(self.uname, 50)

    def delete(self):
        name = self.table.selected_key()
        if not name:
            self.msg.configure(text="Select a user first", text_color=T.DANGER); return
        if name == self.current:
            self.msg.configure(text="Cannot delete your own account", text_color=T.DANGER); return
        if not messagebox.askyesno("Delete user", f"Delete user '{name}'?\n\nThis cannot be undone."):
            return
        try:
            s.delete_user(self.con, name)
        except Exception as e:
            self.msg.configure(text=str(e), text_color=T.DANGER); return
        self.msg.configure(text=f"User '{name}' deleted", text_color=T.OK)
        self.refresh()

    def reset_pw(self):
        name = self.table.selected_key()
        if not name:
            self.msg.configure(text="Select a user first", text_color=T.DANGER); return
        _ResetPwDialog(self.winfo_toplevel(), self.con, name, self.refresh)

    def refresh(self):
        rows = []
        for r in s.list_users(self.con):
            status = "Must change password" if r["must_change"] else "Active"
            rows.append(((r["username"], r["role"].capitalize(), status), None, r["username"]))
        self.table.set_rows(rows)


class _ResetPwDialog(ctk.CTkToplevel):
    def __init__(self, master, con, username, on_done):
        super().__init__(master)
        self.con, self.username, self.on_done = con, username, on_done
        self.title(f"Reset password — {username}")
        self.geometry("400x270")
        self.resizable(False, False)
        self.configure(fg_color=T.BG)
        ctk.CTkLabel(self, text=f"New password for {username}", font=T.f(18, "bold"),
                     text_color=T.TEXT).pack(anchor="w", padx=24, pady=(20, 4))
        ctk.CTkLabel(self, text="User will be asked to change it on next login.",
                     font=T.f(12), text_color=T.MUTED).pack(anchor="w", padx=24)
        self.p1 = T.entry(self, "New password", width=350, show="*")
        self.p1.pack(padx=24, pady=(16, 8))
        self.p2 = T.entry(self, "Confirm password", width=350, show="*")
        self.p2.pack(padx=24)
        self.msg = ctk.CTkLabel(self, text="", font=T.f(12), text_color=T.DANGER, wraplength=350)
        self.msg.pack(anchor="w", padx=24, pady=6)
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=24, pady=16)
        T.button(bar, "Save", self.save, width=120).pack(side="left")
        T.button(bar, "Cancel", self.destroy, width=100, fg_color="#E7ECF5",
                 text_color=T.TEXT, hover_color="#DCE3F0").pack(side="left", padx=10)
        chain_enter([self.p1, self.p2], self.save)
        self.after(150, lambda: (self.lift(), self.focus_force(), self.grab_set(),
                                 self.p1._entry.focus_set()))

    def save(self):
        if self.p1.get() != self.p2.get():
            self.msg.configure(text="Passwords do not match"); return
        try:
            s.change_password(self.con, self.username, self.p1.get())
            self.con.execute("UPDATE users SET must_change=1 WHERE username=?", (self.username,))
            self.con.commit()
        except ValueError as e:
            self.msg.configure(text=str(e)); return
        self.destroy()
        self.on_done()