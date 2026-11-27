"""MUNIM error log.
MUNIM Books: <Books data folder>\\error.log  (C:\\MUNIM by default)
MUNIM Pro:   C:\\MUNIM Pro\\error.log
"""
import datetime
import os
import traceback

from db.setup import data_dir

_log_dir = None   # optional override (set_log_dir)


def set_log_dir(path):
    """Optional: force a folder for the error log."""
    global _log_dir
    _log_dir = path


def _folder():
    if _log_dir:
        return _log_dir
    try:
        from utils import licence
        if licence.PRODUCT == "pro":
            return licence.DATA_DIR      # C:\MUNIM Pro (set in pro_main.py)
    except Exception:
        pass
    return data_dir()


def log_path():
    folder = _folder()
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        pass
    return os.path.join(folder, "error.log")


def log_exception(exc_type, exc, tb):
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    try:
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}")
    except OSError:
        pass
    return text