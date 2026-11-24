"""Pure helpers for safe application-level keyboard shortcuts."""


def is_text_input_widget(widget):
    """Return True for widgets where single-letter shortcuts must not fire."""
    if widget is None:
        return False
    try:
        cls = str(widget.winfo_class()).casefold()
    except Exception:
        cls = widget.__class__.__name__.casefold()
    return any(token in cls for token in ("entry", "text", "combobox", "spinbox"))


def alt_shortcut_action(keysym):
    """Map Alt shortcuts: H=Home, 1=Help, G=Go To."""
    key = (keysym or "").casefold()
    return {"h": "home", "1": "help", "g": "goto"}.get(key)


def single_key_action(keysym, text_input_focused=False):
    """Map unmodified single-letter shortcuts to routed page keys safely."""
    if text_input_focused:
        return None
    key = (keysym or "").casefold()
    return {"r": "payment", "p": "purchase"}.get(key)
