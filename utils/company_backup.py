"""Portable, versioned full-company JSON backup and restore."""
import base64
import json
import os
from datetime import datetime

FORMAT = "MUNIM-COMPANY-BACKUP"
FORMAT_VERSION = 1


def _json_value(value):
    if isinstance(value, bytes):
        return {"__munim_blob__": base64.b64encode(value).decode("ascii")}
    return value


def _db_value(value):
    if isinstance(value, dict) and set(value) == {"__munim_blob__"}:
        return base64.b64decode(value["__munim_blob__"])
    return value


def export_company_backup(con, company_name, out_path, settings_override=None):
    from utils import settings
    tables = {}
    names = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    for name in names:
        # Table names are sourced from sqlite_master, and quoted defensively.
        qname = '"' + name.replace('"', '""') + '"'
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({qname})")]
        rows = []
        for row in con.execute(f"SELECT * FROM {qname}"):
            rows.append([_json_value(row[c]) for c in cols])
        tables[name] = {"columns": cols, "rows": rows}
    company_settings = settings_override if isinstance(settings_override, dict) else settings.load_settings()
    # Backups carry accounting/company configuration, never device/licence secrets.
    company_settings = {k: v for k, v in company_settings.items()
                       if k not in {"licence_key", "licence_user", "licence_expiry",
                                    "activation_token", "device_id", "machine_id"}}
    payload = {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "company_name": company_name,
        "company_settings": company_settings,
        "tables": tables,
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out_path


def restore_company_backup(con, json_path, expected_company=None):
    from utils import settings
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if payload.get("format") != FORMAT or payload.get("format_version") != FORMAT_VERSION:
        raise ValueError("This is not a supported MUNIM company backup.")
    tables = payload.get("tables")
    if not isinstance(tables, dict) or not {"accounts", "vouchers", "entries"}.issubset(tables):
        raise ValueError("Backup is incomplete: core accounting tables are missing.")
    backup_company = (payload.get("company_name") or "").strip()
    if expected_company and backup_company and backup_company.casefold() != expected_company.casefold():
        raise ValueError(f"Backup belongs to '{backup_company}', not '{expected_company}'.")

    current = {r[0]: r[1] for r in con.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    for table, data in tables.items():
        if table not in current:
            raise ValueError(f"Backup contains table '{table}' not supported by this version.")
        if not isinstance(data, dict) or not isinstance(data.get("columns"), list) or not isinstance(data.get("rows"), list):
            raise ValueError(f"Backup table '{table}' is malformed.")
        actual_cols = [r[1] for r in con.execute('PRAGMA table_info("' + table.replace('"','""') + '")')]
        if data["columns"] != actual_cols:
            raise ValueError(f"Backup table '{table}' has a different structure. Use a matching MUNIM version.")

    # Restore is intentionally a full replacement, not a silent merge.
    con.commit()
    con.execute("PRAGMA foreign_keys=OFF")
    try:
        con.execute("BEGIN")
        for table in current:
            q = '"' + table.replace('"', '""') + '"'
            con.execute(f"DELETE FROM {q}")
        for table, data in tables.items():
            q = '"' + table.replace('"', '""') + '"'
            cols = data["columns"]
            col_sql = ",".join('"' + c.replace('"','""') + '"' for c in cols)
            marks = ",".join("?" for _ in cols)
            sql = f"INSERT INTO {q} ({col_sql}) VALUES ({marks})"
            con.executemany(sql, [[_db_value(v) for v in row] for row in data["rows"]])
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.execute("PRAGMA foreign_keys=ON")
    st = payload.get("company_settings")
    if isinstance(st, dict):
        # Keep the currently activated licence on this device; it is not part
        # of a portable company backup.
        current_settings = settings.load_settings()
        for key in ("licence_key", "licence_user", "licence_expiry"):
            if current_settings.get(key):
                st[key] = current_settings[key]
        settings.save_settings(st)
    return {"company_name": backup_company, "tables_restored": len(tables),
            "records_restored": sum(len(t.get("rows", [])) for t in tables.values())}
