import customtkinter as ctk
from db.setup import init_db, login, change_password, list_companies, create_company, company_db_path
from ui.shell import Shell
from ui import theme as T
from utils import shortcut, errlog, settings
from tkinter import messagebox, simpledialog


class MunimApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        self.title("MUNIM")
        self.configure(fg_color=T.BG)
        self.geometry("1180x720")
        self.minsize(1000, 640)
        self.con = None
        self.frame = None
        self.show_company_picker()
        self.after(700, self._desktop_shortcut)

    def report_callback_exception(self, exc, val, tb):
        errlog.log_exception(exc, val, tb)
        messagebox.showerror("MUNIM", f"Something went wrong:\n{val}\n\nDetails were saved to {errlog.log_path()}")

    def _desktop_shortcut(self):
        shortcut.setup(
            ask=lambda: messagebox.askyesno(
                "MUNIM", "Create a MUNIM shortcut on your desktop?\n\n"
                "Keep MUNIM.exe in a permanent folder first. If you move it later, "
                "the shortcut updates itself the next time you open MUNIM."),
            notify=lambda m: messagebox.showinfo("MUNIM", m))

    def _swap(self, frame):
        if self.frame is not None:
            self.frame.destroy()
        self.frame = frame
        frame.pack(fill="both", expand=True)

    def show_company_picker(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid_columnconfigure(0, weight=2, uniform="a")
        f.grid_columnconfigure(1, weight=3, uniform="a")
        f.grid_rowconfigure(0, weight=1)

        # left brand panel
        left = ctk.CTkFrame(f, fg_color=T.NAVY, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(left, text="MUNIM", font=T.f(44, "bold"), text_color="white").place(
            relx=0.5, rely=0.44, anchor="center")
        ctk.CTkLabel(left, text="Simple books for small traders", font=T.f(14),
                     text_color="#9FB3D9").place(relx=0.5, rely=0.52, anchor="center")

        # right picker card
        right = ctk.CTkFrame(f, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        card = T.card(right)
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(card, text="Select Company", font=T.f(24, "bold"),
                     text_color=T.TEXT).pack(anchor="w", padx=34, pady=(32, 2))
        ctk.CTkLabel(card, text="Choose a company to open, or create a new one.",
                     font=T.f(13), text_color=T.MUTED).pack(anchor="w", padx=34, pady=(0, 18))

        self._company_list_frame = ctk.CTkScrollableFrame(card, fg_color="transparent",
                                                           width=330, height=200)
        self._company_list_frame.pack(padx=20, pady=(0, 10), fill="x")
        self._refresh_company_list(card)

        msg = ctk.CTkLabel(card, text="", font=T.f(12), text_color=T.DANGER)
        msg.pack(anchor="w", padx=34, pady=(0, 4))

        def new_company():
            name = simpledialog.askstring("New Company", "Enter company name:", parent=self)
            if not name:
                return
            try:
                create_company(name.strip())
            except ValueError as e:
                msg.configure(text=str(e))
                return
            self._refresh_company_list(card)

        T.button(card, "+ New Company", new_company, width=330).pack(padx=34, pady=(4, 32))
        self._swap(f)

    def _refresh_company_list(self, card):
        for w in self._company_list_frame.winfo_children():
            w.destroy()
        companies = list_companies()
        if not companies:
            ctk.CTkLabel(self._company_list_frame, text="No companies yet. Create one below.",
                         font=T.f(13), text_color=T.MUTED).pack(pady=10)
            return
        for co in companies:
            row = ctk.CTkFrame(self._company_list_frame, fg_color="#EEF2FA", corner_radius=8)
            row.pack(fill="x", pady=3, padx=4)
            ctk.CTkLabel(row, text=co["name"], font=T.f(14), text_color=T.TEXT,
                         anchor="w").pack(side="left", padx=14, pady=10)
            T.button(row, "Open", lambda c=co: self._open_company(c["name"]),
                     width=70, height=30).pack(side="right", padx=8, pady=6)

    def _open_company(self, name):
        settings.set_active_company(name)
        from db.setup import connect, init_db
        self.con = init_db(company_db_path(name))
        self.show_login(name)

    def _auth(self, heading, sub):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid_columnconfigure(0, weight=2, uniform="a")
        f.grid_columnconfigure(1, weight=3, uniform="a")
        f.grid_rowconfigure(0, weight=1)
        left = ctk.CTkFrame(f, fg_color=T.NAVY, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(left, text="MUNIM", font=T.f(44, "bold"), text_color="white").place(
            relx=0.5, rely=0.44, anchor="center")
        ctk.CTkLabel(left, text="Simple books for small traders", font=T.f(14),
                     text_color="#9FB3D9").place(relx=0.5, rely=0.52, anchor="center")
        right = ctk.CTkFrame(f, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        card = T.card(right)
        card.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(card, text=heading, font=T.f(24, "bold"), text_color=T.TEXT).pack(
            anchor="w", padx=34, pady=(32, 2))
        ctk.CTkLabel(card, text=sub, font=T.f(13), text_color=T.MUTED, wraplength=330,
                     justify="left").pack(anchor="w", padx=34, pady=(0, 18))
        return f, card

    def show_login(self, company_name):
        f, card = self._auth(company_name, "Log in to continue.")
        user = T.entry(card, "Username", width=330)
        user.pack(padx=34, pady=(0, 10))
        pw = T.entry(card, "Password", width=330, show="*")
        pw.pack(padx=34, pady=(0, 6))
        msg = ctk.CTkLabel(card, text="", font=T.f(12), text_color=T.MUTED)
        msg.pack(anchor="w", padx=34, pady=4)

        # Switch company link
        def switch(_e=None):
            self.show_company_picker()
        sw = ctk.CTkLabel(card, text="← Switch company", font=T.f(12),
                          text_color=T.ACCENT, cursor="hand2")
        sw.pack(anchor="w", padx=34, pady=(0, 4))
        sw.bind("<Button-1>", switch)

        def go(_e=None):
            row = login(self.con, user.get(), pw.get())
            if not row:
                msg.configure(text="Wrong username or password", text_color=T.DANGER)
            elif row["must_change"]:
                self.show_change_password(company_name, row["username"], row["role"])
            else:
                self.show_shell(row["username"], row["role"])
        pw.bind("<Return>", go)
        T.button(card, "Log in", go, width=330).pack(padx=34, pady=(8, 32))
        self._swap(f)
        user.focus()

    def show_change_password(self, company_name, username, role):
        f, card = self._auth("Set a new password",
                             "You must change the default password before continuing.")
        p1 = T.entry(card, "New password (min 8 characters)", width=330, show="*")
        p1.pack(padx=34, pady=(0, 10))
        p2 = T.entry(card, "Confirm new password", width=330, show="*")
        p2.pack(padx=34, pady=(0, 6))
        msg = ctk.CTkLabel(card, text="", font=T.f(12), wraplength=330, justify="left")
        msg.pack(anchor="w", padx=34, pady=4)

        def save(_e=None):
            if p1.get() != p2.get():
                msg.configure(text="Passwords do not match", text_color=T.DANGER)
                return
            try:
                change_password(self.con, username, p1.get())
            except ValueError as e:
                msg.configure(text=str(e), text_color=T.DANGER)
                return
            self.show_shell(username, role)
        p2.bind("<Return>", save)
        T.button(card, "Save and continue", save, width=330).pack(padx=34, pady=(8, 32))
        self._swap(f)
        p1.focus()

    def show_shell(self, username, role):
        self._swap(Shell(self, self.con, username, role, self.show_company_picker))


if __name__ == "__main__":
    MunimApp().mainloop()
