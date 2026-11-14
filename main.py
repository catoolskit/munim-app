import customtkinter as ctk
from db.setup import init_db, db_path, login, change_password
from ui.shell import Shell
from utils import shortcut
from tkinter import messagebox


class MunimApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        self.title("MUNIM")
        self.geometry("1100x680")
        self.minsize(900, 560)
        self.con = init_db()
        self.frame = None
        self.show_login()
        self.after(700, self._desktop_shortcut)

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

    def _card(self, title, subtitle):
        f = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(f, text=title, font=("Georgia", 32, "bold")).pack(pady=(60, 4))
        ctk.CTkLabel(f, text=subtitle).pack()
        return f

    def show_login(self):
        f = self._card("MUNIM", "Accounting for small business")
        user = ctk.CTkEntry(f, placeholder_text="Username", width=260)
        user.pack(pady=(24, 6))
        pw = ctk.CTkEntry(f, placeholder_text="Password", show="*", width=260)
        pw.pack(pady=6)
        msg = ctk.CTkLabel(f, text=f"Data: {db_path()}", text_color="gray")
        msg.pack(pady=4)

        def go(_e=None):
            row = login(self.con, user.get(), pw.get())
            if not row:
                msg.configure(text="Wrong username or password", text_color="red")
            elif row["must_change"]:
                self.show_change_password(row["username"], row["role"])
            else:
                self.show_shell(row["username"], row["role"])
        pw.bind("<Return>", go)
        ctk.CTkButton(f, text="Login", command=go, width=260).pack(pady=10)
        self._swap(f)
        user.focus()

    def show_change_password(self, username, role):
        f = self._card("Set a new password", "You must change the default password before continuing.")
        p1 = ctk.CTkEntry(f, placeholder_text="New password (min 8 characters)", show="*", width=300)
        p1.pack(pady=(24, 6))
        p2 = ctk.CTkEntry(f, placeholder_text="Confirm new password", show="*", width=300)
        p2.pack(pady=6)
        msg = ctk.CTkLabel(f, text="")
        msg.pack(pady=4)

        def save(_e=None):
            if p1.get() != p2.get():
                msg.configure(text="Passwords do not match", text_color="red")
                return
            try:
                change_password(self.con, username, p1.get())
            except ValueError as e:
                msg.configure(text=str(e), text_color="red")
                return
            self.show_shell(username, role)
        p2.bind("<Return>", save)
        ctk.CTkButton(f, text="Save and continue", command=save, width=300).pack(pady=10)
        self._swap(f)
        p1.focus()

    def show_shell(self, username, role):
        self._swap(Shell(self, self.con, username, role, self.show_login))


if __name__ == "__main__":
    MunimApp().mainloop()
