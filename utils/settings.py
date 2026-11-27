import json, os

_active_company = None   # set by main.py when user picks a company
_fixed_path = None       # MUNIM Pro: one settings file (no companies)


def set_settings_file(path):
    """MUNIM Pro calls this once at start-up. MUNIM Books never calls it."""
    global _fixed_path
    _fixed_path = path


def set_active_company(name):
    global _active_company
    _active_company = name


def get_active_company():
    return _active_company


def settings_path():
    if _fixed_path:
        return _fixed_path
    if _active_company:
        from db.setup import company_settings_path
        return company_settings_path(_active_company)
    # fallback to legacy path (used before company is selected)
    from db.setup import data_dir
    return os.path.join(data_dir(), "settings.json")


def load_settings():
    try:
        with open(settings_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(st):
    path = settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2)


def is_gst_registered():
    """Returns True (default) if the company is GST registered."""
    return load_settings().get("gst_registered", True)


def set_gst_registered(value: bool):
    st = load_settings()
    st["gst_registered"] = bool(value)
    save_settings(st)