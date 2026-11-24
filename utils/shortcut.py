"""First-run desktop shortcut for the built MUNIM.exe.
Asks once, remembers the answer, and re-points the shortcut if the .exe is moved."""
import json, os, subprocess, sys, threading
from utils import settings

PS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$exe = $env:MUNIM_EXE
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = Join-Path $desktop 'MUNIM.lnk'
$ws = New-Object -ComObject WScript.Shell
if (Test-Path $lnk) {
    $existing = $ws.CreateShortcut($lnk)
    if ($existing.TargetPath -eq $exe) { exit 0 }
}
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = $exe
$s.WorkingDirectory = Split-Path $exe
$s.IconLocation = "$exe,0"
$s.Description = 'MUNIM - Accounting for small business'
$s.Save()
"""

def create_shortcut(exe):
    """Creates or re-points %Desktop%\\MUNIM.lnk. Returns (ok, error_text)."""
    env = dict(os.environ, MUNIM_EXE=exe)
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", PS_SCRIPT],
            env=env, capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    if r.returncode != 0:
        return False, (r.stderr or r.stdout or "unknown error").strip()[:300]
    return True, ""

def setup(ask, notify, runner=create_shortcut, frozen=None, exe=None, is_windows=None):
    """ask() -> bool: first-run question. notify(msg): tell the user about a failure.
    Does nothing unless running as the built Windows .exe."""
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    is_windows = (os.name == "nt") if is_windows is None else is_windows
    if not (frozen and is_windows):
        return
    exe = exe or sys.executable
    st = settings.load_settings()
    choice = st.get("desktop_shortcut")
    if choice is None:
        choice = bool(ask())
        st["desktop_shortcut"] = choice
        settings.save_settings(st)
        if choice:
            ok, err = runner(exe)
            if not ok:
                st["desktop_shortcut"] = False
                settings.save_settings(st)
                notify("Could not create the desktop shortcut automatically.\n\n"
                       "You can make one yourself: right-click MUNIM.exe > Send to > Desktop "
                       f"(create shortcut).\n\nDetails: {err}")
        return
    if choice:  # already accepted earlier: quietly keep it pointing at this .exe
        threading.Thread(target=runner, args=(exe,), daemon=True).start()
