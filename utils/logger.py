"""Structured error logging for MUNIM."""
import os
import sys
import traceback
from datetime import datetime

_LOG_SUBDIR = "logs"


def _log_root() -> str:
    try:
        from db.setup import data_dir
        from utils import settings as _s
        st = _s.load_settings()
        root = (st.get("log_folder") or "").strip()
        if not root:
            root = os.path.join(data_dir(), _LOG_SUBDIR)
    except Exception:
        root = os.path.join(os.path.expanduser("~"), "MUNIM", "logs")
    os.makedirs(root, exist_ok=True)
    return root


def log_exception(exc_type, exc_value, exc_tb) -> str:
    try:
        root = _log_root()
        fname = os.path.join(root, f"error_{datetime.now():%Y%m%d}.log")
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        line = (f"\n{'─' * 60}\n"
                f"{datetime.now():%Y-%m-%d %H:%M:%S}\n"
                f"{tb_str}")
        with open(fname, "a", encoding="utf-8") as f:
            f.write(line)
        return (f"{exc_type.__name__}: {exc_value}\n\n"
                f"Details saved to:\n{fname}")
    except Exception:
        return f"{exc_type.__name__}: {exc_value}"


def install_global_handler():
    def _handler(exc_type, exc_value, exc_tb):
        log_exception(exc_type, exc_value, exc_tb)
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.excepthook = _handler
