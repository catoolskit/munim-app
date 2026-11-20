"""Structured error logging for MUNIM (Road B foundation).

Uncaught exceptions are written to C:\\MUNIM\\logs\\error_YYYYMMDD.log.
Nothing is ever shown to the user from here — the caller decides that.
"""
import os
import sys
import traceback
from datetime import datetime

_DEFAULT_LOG_ROOT = r"C:\MUNIM\logs"


def _log_root() -> str:
    try:
        from utils import settings as _s
        st = _s.load_settings()
        root = (st.get("log_folder") or "").strip() or _DEFAULT_LOG_ROOT
    except Exception:
        root = _DEFAULT_LOG_ROOT
    os.makedirs(root, exist_ok=True)
    return root


def log_exception(exc_type, exc_value, exc_tb) -> str:
    """Write the exception to the daily log file. Returns a short user-facing message."""
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
    """Call once at app startup to catch all unhandled exceptions."""
    def _handler(exc_type, exc_value, exc_tb):
        log_exception(exc_type, exc_value, exc_tb)
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.excepthook = _handler