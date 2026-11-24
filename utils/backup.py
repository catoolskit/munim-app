"""Auto-backup and backup-nag logic for MUNIM.

Auto-backup: called on clean exit. Silently copies the active company's
SQLite file to data_dir()\\backups\\ (or the configured folder).

Nag: returns True when the last backup is more than NAG_DAYS old,
so the gateway can show a warning.
"""
import os
import sqlite3
from datetime import date, datetime

NAG_DAYS = 7          # warn if no backup in this many days
_BACKUP_SUBDIR = "backups"


def backup_root(st: dict) -> str:
    """Return the configured backup folder, creating it if needed."""
    from db.setup import data_dir
    folder = (st.get("backup_folder") or "").strip()
    if not folder:
        folder = os.path.join(data_dir(), _BACKUP_SUBDIR)
    os.makedirs(folder, exist_ok=True)
    return folder


def auto_backup(con, company_name: str, st: dict) -> str | None:
    """Copy the active DB to the backup folder.

    Returns the destination path on success, None on any error
    (silent — backup failure must never crash the app on exit).
    """
    try:
        folder = backup_root(st)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c for c in (company_name or "company") if c.isalnum() or c in "-_")
        dest_path = os.path.join(folder, f"{safe}_{ts}.db")
        dest = sqlite3.connect(dest_path)
        try:
            con.backup(dest)
        finally:
            dest.close()
        return dest_path
    except Exception:
        return None


def should_nag(st: dict, threshold_days: int | None = None) -> bool:
    """Return True when the last backup is older than threshold_days (default NAG_DAYS)."""
    days = threshold_days if threshold_days is not None else st.get("backup_nag_days", NAG_DAYS)
    last = st.get("last_backup")
    if not last:
        return True
    try:
        delta = (date.today() - date.fromisoformat(last)).days
        return delta > int(days)
    except (ValueError, TypeError):
        return True


def record_backup(st: dict) -> dict:
    """Stamp today's date as the last backup in the settings dict (caller must save)."""
    st["last_backup"] = date.today().isoformat()
    return st
