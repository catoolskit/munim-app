"""MUNIM password vault — portal credentials encrypted with Windows DPAPI
plus a master password (used as DPAPI entropy). Shared by Books and Pro.

Storage: tables vault_meta / vault_items in the caller's SQLite connection.
User IDs are stored plain (shown on screens); only passwords are encrypted.
A forgotten master password cannot be recovered: reset() wipes the secrets
(user IDs remain) and the user re-enters portal passwords.
"""
import sys
import time
import ctypes
import hashlib
import secrets
import datetime

AUTO_LOCK_MINUTES = 15
_CHECK = b"MUNIM-VAULT-OK"
_ITERATIONS = 200_000
_UI_FORBIDDEN = 0x01

_key = None
_last_used = 0.0


class VaultError(Exception):
    pass


class VaultLocked(VaultError):
    pass


# ---------------------------------------------------------------- DPAPI
if sys.platform == "win32":
    from ctypes import wintypes as wt

    class _BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_BLOB), wt.LPCWSTR, ctypes.POINTER(_BLOB),
        ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(_BLOB)]
    _crypt32.CryptProtectData.restype = wt.BOOL
    _crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_BLOB), ctypes.POINTER(wt.LPWSTR), ctypes.POINTER(_BLOB),
        ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(_BLOB)]
    _crypt32.CryptUnprotectData.restype = wt.BOOL
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    _kernel32.LocalFree.restype = ctypes.c_void_p


def _need_windows():
    if sys.platform != "win32":
        raise VaultError("The password vault works only on Windows.")


def _in_blob(data: bytes):
    buf = ctypes.create_string_buffer(data, max(1, len(data)))
    return _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _protect(data: bytes, entropy: bytes) -> bytes:
    _need_windows()
    din, _b1 = _in_blob(data)
    ent, _b2 = _in_blob(entropy)
    out = _BLOB()
    ok = _crypt32.CryptProtectData(ctypes.byref(din), "MUNIM", ctypes.byref(ent),
                                   None, None, _UI_FORBIDDEN, ctypes.byref(out))
    if not ok:
        raise VaultError(f"Encryption failed (Windows error {ctypes.get_last_error()})")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        _kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


def _unprotect(blob: bytes, entropy: bytes):
    _need_windows()
    din, _b1 = _in_blob(blob)
    ent, _b2 = _in_blob(entropy)
    out = _BLOB()
    ok = _crypt32.CryptUnprotectData(ctypes.byref(din), None, ctypes.byref(ent),
                                     None, None, _UI_FORBIDDEN, ctypes.byref(out))
    if not ok:
        return None
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        _kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


# ---------------------------------------------------------------- helpers
def ensure_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS vault_meta (key TEXT PRIMARY KEY, value BLOB);
        CREATE TABLE IF NOT EXISTS vault_items (
            ref TEXT PRIMARY KEY, portal TEXT NOT NULL, user_id TEXT,
            secret BLOB, updated_at TEXT);
    """)


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _derive(master: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", master.encode("utf-8"), salt, _ITERATIONS)


def _meta_get(conn, key):
    row = conn.execute("SELECT value FROM vault_meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def _meta_set(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO vault_meta(key, value) VALUES(?, ?)", (key, value))


def _open(key: bytes):
    global _key, _last_used
    _key, _last_used = key, time.monotonic()


def _require():
    global _last_used
    if not is_unlocked():
        raise VaultLocked("Vault is locked. Enter the master password.")
    _last_used = time.monotonic()


def strength_error(master: str):
    if len(master or "") < 8:
        return "Password must be at least 8 characters"
    if not any(c.isalpha() for c in master) or not any(c.isdigit() for c in master):
        return "Use both letters and numbers in the password"
    return None


# ---------------------------------------------------------------- public API
def is_setup(conn) -> bool:
    ensure_tables(conn)
    return _meta_get(conn, "salt") is not None


def setup(conn, master: str):
    if is_setup(conn):
        raise VaultError("Vault is already set up.")
    err = strength_error(master)
    if err:
        raise VaultError(err)
    salt = secrets.token_bytes(16)
    key = _derive(master, salt)
    _meta_set(conn, "salt", salt)
    _meta_set(conn, "check", _protect(_CHECK, key))
    conn.commit()
    _open(key)


def unlock(conn, master: str) -> bool:
    if not is_setup(conn):
        raise VaultError("Vault is not set up yet.")
    key = _derive(master, _meta_get(conn, "salt"))
    if _unprotect(_meta_get(conn, "check"), key) == _CHECK:
        _open(key)
        return True
    return False  # wrong password, or vault created under another Windows user


def lock():
    global _key
    _key = None


def is_unlocked() -> bool:
    if _key is None:
        return False
    if time.monotonic() - _last_used > AUTO_LOCK_MINUTES * 60:
        lock()
        return False
    return True


def put(conn, portal: str, user_id: str, password: str, ref: str = None) -> str:
    """Save or update a credential. Returns its ref (store it in *_cred_ref)."""
    _require()
    ref = ref or secrets.token_hex(8)
    secret = _protect(password.encode("utf-8"), _key) if password else None
    conn.execute("INSERT OR REPLACE INTO vault_items(ref, portal, user_id, secret, updated_at) "
                 "VALUES(?, ?, ?, ?, ?)", (ref, portal, (user_id or "").strip(), secret, _now()))
    conn.commit()
    return ref


def user_id(conn, ref: str) -> str:
    """User ID only — no unlock needed."""
    if not ref:
        return ""
    ensure_tables(conn)
    row = conn.execute("SELECT user_id FROM vault_items WHERE ref=?", (ref,)).fetchone()
    return row[0] if row else ""


def get(conn, ref: str):
    """Return (portal, user_id, password) or None."""
    _require()
    row = conn.execute("SELECT portal, user_id, secret FROM vault_items WHERE ref=?",
                       (ref,)).fetchone()
    if not row:
        return None
    password = ""
    if row[2]:
        plain = _unprotect(row[2], _key)
        if plain is None:
            raise VaultError("This password could not be decrypted on this PC / Windows user.")
        password = plain.decode("utf-8")
    return row[0], row[1], password


def delete(conn, ref: str):
    if ref:
        ensure_tables(conn)
        conn.execute("DELETE FROM vault_items WHERE ref=?", (ref,))
        conn.commit()


def change_master(conn, old: str, new: str):
    if not unlock(conn, old):
        raise VaultError("Current password is wrong.")
    err = strength_error(new)
    if err:
        raise VaultError(err)
    old_key = _key
    salt = secrets.token_bytes(16)
    new_key = _derive(new, salt)
    rows = conn.execute("SELECT ref, secret FROM vault_items WHERE secret IS NOT NULL").fetchall()
    try:
        for ref, blob in rows:
            plain = _unprotect(blob, old_key)
            if plain is not None:
                conn.execute("UPDATE vault_items SET secret=? WHERE ref=?",
                             (_protect(plain, new_key), ref))
        _meta_set(conn, "salt", salt)
        _meta_set(conn, "check", _protect(_CHECK, new_key))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    _open(new_key)


def reset(conn):
    """Forgot password: wipe all saved portal passwords (user IDs are kept)."""
    ensure_tables(conn)
    conn.execute("UPDATE vault_items SET secret=NULL")
    conn.execute("DELETE FROM vault_meta")
    conn.commit()
    lock()