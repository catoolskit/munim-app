"""One place for MUNIM's look. Every screen imports this, so later modules match automatically."""
from tkinter import ttk
import customtkinter as ctk

NAVY, NAVY_HOVER, NAVY_ACTIVE = "#0F1F3D", "#1B3156", "#1856A0"
ACCENT, ACCENT_HOVER = "#1856A0", "#134581"
BG, CARD, BORDER = "#F4F6FA", "#FFFFFF", "#E1E6EF"
TEXT, MUTED = "#1B2438", "#6B7690"
OK, DANGER = "#1E8E5A", "#C0392B"
SIDE_MUTED = "#6F82A8"
FONT = "Segoe UI"


def f(size=13, weight="normal"):
    return (FONT, size, weight)


def card(master, **kw):
    return ctk.CTkFrame(master, fg_color=CARD, border_width=1, border_color=BORDER,
                        corner_radius=12, **kw)


def entry(master, placeholder="", **kw):
    kw.setdefault("height", 38)
    return ctk.CTkEntry(master, placeholder_text=placeholder, fg_color="white",
                        border_color=BORDER, border_width=1, corner_radius=8,
                        text_color=TEXT, font=f(13), **kw)


def button(master, text, command=None, **kw):
    kw.setdefault("height", 38)
    kw.setdefault("fg_color", ACCENT)
    kw.setdefault("hover_color", ACCENT_HOVER)
    return ctk.CTkButton(master, text=text, command=command, corner_radius=8,
                         font=f(13, "bold"), **kw)


def option_menu(master, values, **kw):
    kw.setdefault("height", 38)
    return ctk.CTkOptionMenu(master, values=values, fg_color="white", text_color=TEXT,
                             button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                             dropdown_fg_color="white", dropdown_text_color=TEXT,
                             corner_radius=8, font=f(13), **kw)


def title(master, text, sub=None):
    box = ctk.CTkFrame(master, fg_color="transparent")
    ctk.CTkLabel(box, text=text, font=f(24, "bold"), text_color=TEXT).pack(anchor="w")
    if sub:
        ctk.CTkLabel(box, text=sub, font=f(13), text_color=MUTED).pack(anchor="w", pady=(2, 0))
    return box


def style_tree():
    st = ttk.Style()
    st.theme_use("clam")
    st.configure("Munim.Treeview", background="white", fieldbackground="white",
                 foreground=TEXT, rowheight=32, borderwidth=0, font=(FONT, 11))
    st.configure("Munim.Treeview.Heading", background="#EEF2F8", foreground=TEXT,
                 font=(FONT, 11, "bold"), relief="flat", padding=(8, 8))
    st.map("Munim.Treeview", background=[("selected", ACCENT)],
           foreground=[("selected", "white")])
    st.map("Munim.Treeview.Heading", background=[("active", "#E3E9F4")])
    st.configure("Munim.Vertical.TScrollbar", background="#C5CEE0", troughcolor="#F1F4F9",
                 bordercolor="#F1F4F9", lightcolor="#C5CEE0", darkcolor="#C5CEE0",
                 arrowcolor=TEXT, relief="flat")
    st.map("Munim.Vertical.TScrollbar", background=[("active", "#A9B6D0")])


def combo(master, values, **kw):
    kw.setdefault("height", 38)
    return ctk.CTkComboBox(master, values=values, fg_color="white", border_color=BORDER,
                           border_width=1, button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                           dropdown_fg_color="white", dropdown_text_color=TEXT, text_color=TEXT,
                           corner_radius=8, font=f(13), **kw)
