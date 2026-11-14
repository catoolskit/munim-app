import json, os
from db.setup import data_dir

def settings_path():
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
