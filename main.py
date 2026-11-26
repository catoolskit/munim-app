import customtkinter as ctk
from db.setup import init_db, login, change_password, list_companies, create_company, company_db_path
from ui.shell import Shell
from ui.activation import ActivationFrame
from ui import theme as T
from utils import shortcut, errlog, settings
from utils.licence import validate_key
from tkinter import messagebox, simpledialog

APP_NAME = "MUNIM Books"
APP_TAGLINE = "Simple books for small traders"
CURRENT_VERSION = "v0.18"
GITHUB_API = "https://api.github.com/repos/catoolskit/munim-app/releases/latest"
DOWNLOAD_PAGE = "technicalmunim.vercel.app/download.html"
DELETE_COUNTDOWN = 5   # seconds before "Delete permanently" can be clicked


class MunimApp(ctk.CTk):
    def __init__(self):
        # Apply the shared MUNIM theme before any screen/widget is constructed.
        ctk.set_default_color_theme("blue")
        T.apply_global_theme()
        super().__init__()
        ctk.set_appearance_mode("light")
        self.title(APP_NAME)
        self.configure(fg_color=T.BG)
        self.geometry("1180x720")
        self.minsize(1000, 640)
        self.con = None
        self.frame = None
        self._version_banner = None
        self._picker_msg = None
        self.show_company_picker()
        self.after(700, self._desktop_shortcut)
        self.after(3000, self._check_version)  # check after UI settles

    def report_callback_exception(self, exc, val, tb):
        errlog.log_exception(exc, val, tb)
        messagebox.showerror(APP_NAME, f"Something went wrong:\n{val}\n\nDetails were saved to {errlog.log_path()}")

    def _desktop_shortcut(self):
        shortcut.setup(
            ask=lambda: messagebox.askyesno(
                APP_NAME, f"Create a {APP_NAME} shortcut on your desktop?\n\n"
                "Keep MUNIM.exe in a permanent folder first. If you move it later, "
                "the shortcut updates itself the next time you open MUNIM Books."),
            notify=lambda m: messagebox.showinfo(APP_NAME, m))

    # ── Version check ─────────────────────────────────────────────────────────
    def _check_version(self):
        import threading
        threading.Thread(target=self._fetch_latest, daemon=True).start()

    def _fetch_latest(self):
        try:
            import urllib.request, json
            req = urllib.request.Request(
                GITHUB_API,
                headers={"User-Agent": "MUNIM-app",
                         "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            latest = data.get("tag_name", "")
            if latest and latest != CURRENT_VERSION:
                self.after(0, lambda: self._show_version_banner(latest))
        except Exception:
            pass  # no internet — silently skip

    def _show_version_banner(self, latest_version):
        if self._version_banner:
            return
        banner = ctk.CTkFrame(self, fg_color="#1D4ED8", corner_radius=0, height=28)
        banner.place(relx=0, rely=0, relwidth=1, anchor="nw")
        banner.lift()
        ctk.CTkLabel(
            banner,
            text=f"⬆ New version {latest_version} available — {DOWNLOAD_PAGE}",
            font=T.f(11), text_color="white"
        ).pack(side="left", padx=16, pady=4)
        ctk.CTkButton(
            banner, text="✕", width=28, height=20,
            fg_color="transparent", hover_color="#2563EB",
            text_color="white", font=T.f(11),
            command=self._dismiss_banner
        ).pack(side="right", padx=8, pady=4)
        self._version_banner = banner

    def _dismiss_banner(self):
        if self._version_banner:
            self._version_banner.destroy()
            self._version_banner = None

    # ── App flow ──────────────────────────────────────────────────────────────
    def _swap(self, frame):
        if self.frame is not None:
            self.frame.destroy()
        self.frame = frame
        frame.pack(fill="both", expand=True)

    def _brand_panel(self, parent):
        left = ctk.CTkFrame(parent, fg_color=T.NAVY, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(left, text=APP_NAME, font=T.f(40, "bold"), text_color="white").place(
            relx=0.5, rely=0.44, anchor="center")
        ctk.CTkLabel(left, text=APP_TAGLINE, font=T.f(14),
                     text_color="#9FB3D9").place(relx=0.5, rely=0.52, anchor="center")
        return left

    def show_company_picker(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid_columnconfigure(0, weight=2, uniform="a")
        f.grid_columnconfigure(1, weight=3, uniform="a")
        f.grid_rowconfigure(0, weight=1)

        self._brand_panel(f)

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

        msg = ctk.CTkLabel(card, text="", font=T.f(12), text_color=T.DANGER,
                           wraplength=330, justify="left")
        msg.pack(anchor="w", padx=34, pady=(0, 4))
        self._picker_msg = msg

        def new_company():
            name = simpledialog.askstring("New Company", "Enter company name:", parent=self)
            if not name:
                return
            try:
                create_company(name.strip())
            except ValueError as e:
                msg.configure(text=str(e), text_color=T.DANGER)
                return
            msg.configure(text="")
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
                     width=70, height=30).pack(side="right", padx=(4, 8), pady=6)
            T.button(row, "Delete", lambda c=co: self._confirm_delete_company(c["name"], card),
                     width=64, height=30, fg_color="#FDECEA", text_color=T.DANGER,
                     hover_color="#FAD7D3").pack(side="right", padx=(0, 2), pady=6)

    # ── Delete a company (5-second countdown + safety copy) ───────────────────
    def _confirm_delete_company(self, name, card):
        win = ctk.CTkToplevel(self)
        win.title(f"Delete company — {APP_NAME}")
        win.geometry("480x270")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text=f"Delete “{name}”?", font=T.f(19, "bold"),
                     text_color=T.TEXT).pack(anchor="w", padx=24, pady=(22, 6))
        ctk.CTkLabel(win,
                     text="All entries, parties and reports of this company will be removed "
                          "from this computer.\n\nA safety copy is kept in the "
                          "“Deleted companies” folder inside your MUNIM data folder.",
                     font=T.f(12), text_color=T.MUTED, justify="left",
                     wraplength=430).pack(anchor="w", padx=24)

        bar = ctk.CTkFrame(win, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=24, pady=(16, 22))

        def close():
            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()

        def do_delete():
            close()
            self._delete_company(name, card)

        T.button(bar, "Cancel", close, width=110, fg_color="#E7ECF5", text_color=T.TEXT,
                 hover_color="#DCE3F0").pack(side="right")
        del_btn = T.button(bar, f"Delete ({DELETE_COUNTDOWN})", do_delete, width=180,
                           fg_color=T.DANGER, hover_color="#A32F23")
        del_btn.pack(side="right", padx=(0, 10))
        del_btn.configure(state="disabled")

        def tick(n):
            try:
                if not win.winfo_exists():
                    return
            except Exception:
                return
            if n > 0:
                del_btn.configure(text=f"Delete ({n})")
                win.after(1000, lambda: tick(n - 1))
            else:
                del_btn.configure(text="Delete permanently", state="normal")

        tick(DELETE_COUNTDOWN)
        win.bind("<Escape>", lambda _e: close())
        win.protocol("WM_DELETE_WINDOW", close)

    def _delete_company(self, name, card):
        import gc
        import os
        import shutil
        import time
        from datetime import datetime
        from db.setup import data_dir, delete_company

        msg = self._picker_msg

        def say(text, color):
            try:
                if msg is not None:
                    msg.configure(text=text, text_color=color)
            except Exception:
                pass

        # Close any open database connection so Windows can remove the file.
        if self.con is not None:
            try:
                self.con.close()
            except Exception:
                pass
            self.con = None
        gc.collect()   # also releases connections still held by screens that were closed

        # Safety copy first — if this fails, nothing is deleted.
        backup_folder = ""
        try:
            src = company_db_path(name)
            if src and os.path.exists(src):
                backup_folder = os.path.join(str(data_dir()), "Deleted companies")
                os.makedirs(backup_folder, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in name).strip()
                ext = os.path.splitext(str(src))[1] or ".db"
                shutil.copy2(src, os.path.join(backup_folder, f"{safe or 'company'} {stamp}{ext}"))
        except Exception as e:
            say(f"Could not make a safety copy, so nothing was deleted.\n{e}", T.DANGER)
            return

        # Windows may hold the file for a moment after logging out — retry briefly.
        last_err = None
        for _attempt in range(5):
            try:
                delete_company(name)
                last_err = None
                break
            except PermissionError as e:      # WinError 32: file still in use
                last_err = e
                gc.collect()
                time.sleep(0.4)
            except Exception as e:
                last_err = e
                break
        if last_err is not None:
            say(f"Could not delete “{name}” because the file is still in use. "
                f"Close {APP_NAME}, open it again and delete it from this screen.", T.DANGER)
            return

        self._refresh_company_list(card)
        note = f" Safety copy: {backup_folder}" if backup_folder else ""
        say(f"“{name}” deleted.{note}", T.OK)

    def _open_company(self, name):
        settings.set_active_company(name)
        from db.setup import connect, init_db
        self.con = init_db(company_db_path(name))
        # Require activation for each company database until a valid licence
        # has been stored in that company's settings.
        st = settings.load_settings()
        try:
            licensed_user, _expiry = validate_key(st.get("licence_key", ""))
            saved_user = st.get("licence_user", "")
            if not saved_user or licensed_user.lower() != saved_user.lower():
                raise ValueError("Stored licence/user mismatch")
        except ValueError:
            self.show_activation(name)
        else:
            self.show_login(name)

    def show_activation(self, company_name):
        def activated(row):
            if row["must_change"]:
                self.show_change_password(company_name, row["username"], row["role"])
            else:
                self.show_shell(row["username"], row["role"])
        self._swap(ActivationFrame(self, self.con, activated))

    def _auth(self, heading, sub):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid_columnconfigure(0, weight=2, uniform="a")
        f.grid_columnconfigure(1, weight=3, uniform="a")
        f.grid_rowconfigure(0, weight=1)

        self._brand_panel(f)

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
        f, card = self._auth(company_name, "Log in with your MUNIM Books password.")
        user = T.entry(card, "Username", width=330)
        user.pack(padx=34, pady=(0, 10))
        pw = T.entry(card, "Password", width=330, show="*")
        pw.pack(padx=34, pady=(0, 6))
        msg = ctk.CTkLabel(card, text="", font=T.f(12), text_color=T.MUTED,
                           wraplength=330, justify="left")
        msg.pack(anchor="w", padx=34, pady=4)

        def switch(_e=None):
            self.show_company_picker()
        sw = ctk.CTkLabel(card, text="← Switch company", font=T.f(12),
                          text_color=T.ACCENT, cursor="hand2")
        sw.pack(anchor="w", padx=34, pady=(0, 4))
        sw.bind("<Button-1>", switch)

        def go(_e=None):
            row = login(self.con, user.get(), pw.get())
            if not row:
                msg.configure(text="Wrong username or password. Use the password you set "
                                   "in MUNIM Books (not the activation password).",
                              text_color=T.DANGER)
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
                             "Choose your own MUNIM Books password. You will use it to log in "
                             "from now on.")
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
