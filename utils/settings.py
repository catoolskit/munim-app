import json, os

_active_company = None   # set by main.py when user picks a company

def set_active_company(name):
    global _active_company
    _active_company = name

def get_active_company():
    return _active_company

def settings_path():
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
    with open(settings_path(), "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2)
