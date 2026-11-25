"""MUNIM's centralized visual system. Keep screen styling consistent here."""
from tkinter import ttk
import customtkinter as ctk

# Calm, high-contrast accounting UI: ink/navy, restrained blue accent, soft surfaces.
NAVY, NAVY_HOVER, NAVY_ACTIVE = "#14243F", "#203858", "#2B5DB5"
NAV_PANEL = "#14243F"
SURFACE_ALT = "#F8FAFD"
SURFACE_SELECTED = "#EAF0FC"
SUCCESS_BG = "#E8F5EF"
DANGER_BG = "#FCEDEC"
ACCENT, ACCENT_HOVER = "#2B5DB5", "#214A94"
BG, CARD, BORDER = "#F5F7FB", "#FFFFFF", "#E2E7F0"
TEXT, MUTED = "#1D293D", "#68758B"
OK, DANGER = "#16845B", "#C2413A"
SIDE_MUTED = "#8797B5"
FONT = "Segoe UI"


def f(size=13, weight="normal"):
    return (FONT, size, weight)


def card(master, **kw):
    """Create a consistent, restrained surface used across all screens."""
    kw.setdefault("corner_radius", 12)
    kw.setdefault("border_width", 1)
    kw.setdefault("border_color", BORDER)
    return ctk.CTkFrame(master, fg_color=CARD, **kw)


def entry(master, placeholder="", **kw):
    kw.setdefault("height", 38)
    kw.setdefault("border_width", 1)
    kw.setdefault("corner_radius", 8)
    kw.setdefault("font", f(13))
    return ctk.CTkEntry(master, placeholder_text=placeholder, fg_color="white",
                        border_color=BORDER, text_color=TEXT, **kw)


def button(master, text, command=None, **kw):
    kw.setdefault("height", 38)
    kw.setdefault("fg_color", ACCENT)
    kw.setdefault("hover_color", ACCENT_HOVER)
    kw.setdefault("corner_radius", 8)
    kw.setdefault("font", f(13, "bold"))
    return ctk.CTkButton(master, text=text, command=command, **kw)


def option_menu(master, values, **kw):
    kw.setdefault("height", 38)
    kw.setdefault("corner_radius", 8)
    kw.setdefault("dropdown_font", f(12))
    kw.setdefault("dropdown_hover_color", "#EAF0FC")
    kw.setdefault("font", f(13))
    return ctk.CTkOptionMenu(master, values=values, fg_color="white", text_color=TEXT,
                             button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                             dropdown_fg_color="white", dropdown_text_color=TEXT,
                             **kw)


def title(master, text, sub=None):
    box = ctk.CTkFrame(master, fg_color="transparent")
    ctk.CTkLabel(box, text=text, font=f(24, "bold"), text_color=TEXT).pack(anchor="w")
    if sub:
        ctk.CTkLabel(box, text=sub, font=f(13), text_color=MUTED).pack(anchor="w", pady=(3, 0))
    return box



def apply_global_theme():
    """Apply MUNIM design tokens to native CustomTkinter widgets app-wide."""
    theme = getattr(ctk.ThemeManager, "theme", {}) or {}
    def color_pair(value):
        return [value, value]
    updates = {
        "CTk": {"fg_color": BG},
        "CTkToplevel": {"fg_color": BG},
        "CTkLabel": {"text_color": TEXT},
        "CTkFrame": {"fg_color": BG, "border_color": BORDER},
        "CTkButton": {"fg_color": ACCENT, "hover_color": ACCENT_HOVER,
                      "text_color": "#FFFFFF", "border_color": ACCENT,
                      "corner_radius": 9},
        "CTkEntry": {"fg_color": CARD, "border_color": BORDER,
                     "text_color": TEXT, "placeholder_text_color": MUTED,
                     "corner_radius": 9},
        "CTkComboBox": {"fg_color": CARD, "border_color": BORDER,
                        "button_color": ACCENT, "button_hover_color": ACCENT_HOVER,
                        "text_color": TEXT, "corner_radius": 9},
        "CTkOptionMenu": {"fg_color": ACCENT, "button_color": ACCENT_HOVER,
                          "button_hover_color": ACCENT, "text_color": "#FFFFFF",
                          "corner_radius": 8, "dropdown_fg_color": CARD,
                          "dropdown_text_color": TEXT,
                          "dropdown_hover_color": "#EAF0FC"},
        "CTkCheckBox": {"fg_color": ACCENT, "hover_color": ACCENT_HOVER,
                        "border_color": ACCENT, "text_color": TEXT},
        "CTkRadioButton": {"fg_color": ACCENT, "hover_color": ACCENT_HOVER,
                           "border_color": ACCENT, "text_color": TEXT},
        "CTkSwitch": {"progress_color": ACCENT, "button_color": ACCENT,
                      "button_hover_color": ACCENT_HOVER, "text_color": TEXT},
        "CTkSegmentedButton": {"selected_color": ACCENT,
                               "selected_hover_color": ACCENT_HOVER,
                               "unselected_color": "#E8EDF5",
                               "unselected_hover_color": "#DCE4F0",
                               "text_color": TEXT},
        "CTkSlider": {"progress_color": ACCENT, "button_color": ACCENT,
                      "button_hover_color": ACCENT_HOVER},
        "CTkProgressBar": {"progress_color": ACCENT},
        "CTkScrollbar": {"button_color": "#C8D1E0",
                        "button_hover_color": "#AEBBD0"},
        "CTkTextbox": {"fg_color": CARD, "border_color": BORDER,
                       "text_color": TEXT, "corner_radius": 9},
    }
    for widget, values in updates.items():
        section = theme.get(widget)
        if not isinstance(section, dict):
            continue
        for key, value in values.items():
            if key in section:
                section[key] = color_pair(value) if isinstance(section[key], (list, tuple)) else value


def style_tree():
    st = ttk.Style()
    st.theme_use("clam")
    st.configure("Munim.Treeview", background="white", fieldbackground="white",
                 foreground=TEXT, rowheight=32, borderwidth=0, font=(FONT, 11))
    st.configure("Munim.Treeview.Heading", background="#EAF0F7", foreground=TEXT,
                 font=(FONT, 11, "bold"), relief="flat", padding=(10, 8))
    st.map("Munim.Treeview", background=[("selected", ACCENT)],
           foreground=[("selected", "white")])
    st.map("Munim.Treeview.Heading", background=[("active", "#DDE6F2")])
    st.configure("Munim.Vertical.TScrollbar", background="#C8D1E0", troughcolor="#F1F4F9",
                 bordercolor="#F1F4F9", lightcolor="#C8D1E0", darkcolor="#C8D1E0",
                 arrowcolor=TEXT, relief="flat")
    st.map("Munim.Vertical.TScrollbar", background=[("active", "#AEBBD0")])


def combo(master, values, **kw):
    kw.setdefault("height", 38)
    kw.setdefault("corner_radius", 8)
    kw.setdefault("dropdown_font", f(12))
    kw.setdefault("dropdown_hover_color", "#EAF0FC")
    kw.setdefault("font", f(13))
    return ctk.CTkComboBox(master, values=values, fg_color="white", border_color=BORDER,
                           border_width=1, button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                           dropdown_fg_color="white", dropdown_text_color=TEXT, **kw)
