import customtkinter as ctk
from db.setup import init_db, db_path, login, change_password
from ui.shell import Shell
from ui import theme as T
from utils import shortcut, errlog
from tkinter import messagebox


class MunimApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        self.title("MUNIM")
        self.configure(fg_color=T.BG)
        self.geometry("1180x720")
        self.minsize(1000, 640)
        self.con = init_db()
        self.frame = None
        self.show_login()
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

    def _auth(self, heading, sub):
        """Split layout: brand panel on the left, form card on the right."""
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

    def show_login(self):
        f, card = self._auth("Welcome back", "Log in to your books.")
        user = T.entry(card, "Username", width=330)
        user.pack(padx=34, pady=(0, 10))
        pw = T.entry(card, "Password", width=330, show="*")
        pw.pack(padx=34, pady=(0, 6))
        msg = ctk.CTkLabel(card, text=f"Data: {db_path()}", font=T.f(11), text_color=T.MUTED)
        msg.pack(anchor="w", padx=34, pady=4)

        def go(_e=None):
            row = login(self.con, user.get(), pw.get())
            if not row:
                msg.configure(text="Wrong username or password", text_color=T.DANGER)
            elif row["must_change"]:
                self.show_change_password(row["username"], row["role"])
            else:
                self.show_shell(row["username"], row["role"])
        pw.bind("<Return>", go)
        T.button(card, "Log in", go, width=330).pack(padx=34, pady=(8, 32))
        self._swap(f)
        user.focus()

    def show_change_password(self, username, role):
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
        self._swap(Shell(self, self.con, username, role, self.show_login))


if __name__ == "__main__":
    MunimApp().mainloop()
