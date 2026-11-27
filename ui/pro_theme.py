"""MUNIM Pro colours (emerald). Call apply() before any widget is created."""
from ui import theme as T

PRO_COLOURS = {
    "NAVY": "#0F3B2F",
    "NAVY_HOVER": "#18513F",
    "NAVY_ACTIVE": "#1F6B52",
    "NAV_PANEL": "#0F3B2F",
    "ACCENT": "#15805E",
    "ACCENT_HOVER": "#106A4D",
    "SURFACE_SELECTED": "#E4F3EC",
}


def apply():
    for name, value in PRO_COLOURS.items():
        setattr(T, name, value)