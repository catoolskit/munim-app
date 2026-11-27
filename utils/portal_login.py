"""MUNIM — portal auto-login (Income-tax e-filing, TRACES, GST).

Opens Chrome (or Edge), types the User ID and password and stops at the
captcha / OTP, which the user ALWAYS types. MUNIM never bypasses captcha or OTP.
The browser stays open after MUNIM finishes (detach mode).
Needs the 'selenium' package (bundled in MUNIMPro.exe).
"""
import os
import queue
import subprocess
import threading
import time

PORTAL_URLS = {
    "ITD": "https://eportal.incometax.gov.in/iec/foservices/#/login",
    "TRACES": "https://www.tdscpc.gov.in/app/login.xhtml",
    "GST": "https://services.gst.gov.in/services/login",
}
PORTAL_NAMES = {"ITD": "Income-tax portal", "TRACES": "TRACES", "GST": "GST portal"}

_drivers = []                      # keep references so browsers are not closed
_busy = threading.Lock()


class PortalError(Exception):
    def __init__(self, message, browser_open=False):
        super().__init__(message)
        self.browser_open = browser_open


# ---------------------------------------------------------------- browser
def _chrome_path():
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 os.environ.get("LOCALAPPDATA", "")):
        if base:
            p = os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")
            if os.path.isfile(p):
                return p
    return None


def _service(cls):
    kw = {"log_output": subprocess.DEVNULL}
    if os.name == "nt":
        kw["popen_kw"] = {"creationflags": subprocess.CREATE_NO_WINDOW}
    try:
        return cls(**kw)
    except TypeError:
        return cls()


def _new_driver():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.edge.service import Service as EdgeService
    except ImportError:
        raise PortalError("Auto-login is not available in this version of MUNIM.")

    chrome = _chrome_path()
    attempts = (["chrome"] if chrome else []) + ["edge"]
    errors = []
    for kind in attempts:
        try:
            if kind == "chrome":
                opts = webdriver.ChromeOptions()
                opts.binary_location = chrome
            else:
                opts = webdriver.EdgeOptions()
            opts.add_experimental_option("detach", True)
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_argument("--start-maximized")
            if kind == "chrome":
                driver = webdriver.Chrome(options=opts, service=_service(ChromeService))
            else:
                driver = webdriver.Edge(options=opts, service=_service(EdgeService))
            _drivers.append(driver)
            return driver
        except Exception as e:
            first = (str(e).strip().splitlines() or [type(e).__name__])[0]
            errors.append(f"{kind}: {first[:120]}")
    raise PortalError("Could not start Chrome or Edge. The first auto-login needs internet "
                      "to set up the browser driver. (" + "; ".join(errors) + ")")


# ---------------------------------------------------------------- page helpers
def _find(driver, selectors, timeout, need_enabled=True):
    from selenium.webdriver.common.by import By
    end = time.time() + timeout
    while time.time() < end:
        for css in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, css)
            except Exception:
                elements = []
            for el in elements:
                try:
                    if el.is_displayed() and (el.is_enabled() or not need_enabled):
                        return el
                except Exception:
                    pass
        time.sleep(0.3)
    return None


def _button(driver, texts, timeout):
    from selenium.webdriver.common.by import By
    xpath = " | ".join(f"//button[contains(normalize-space(.), '{t}')]" for t in texts)
    end = time.time() + timeout
    while time.time() < end:
        try:
            for el in driver.find_elements(By.XPATH, xpath):
                if el.is_displayed() and el.is_enabled():
                    return el
        except Exception:
            pass
        time.sleep(0.3)
    return None


def _type(el, text):
    el.clear()
    el.send_keys(text)


def _click(driver, el):
    driver.execute_script("arguments[0].click();", el)


def _changed(name):
    return PortalError(f"The {name} page looks different from what MUNIM expects. "
                       "Please finish the login in the browser window.", browser_open=True)


# ---------------------------------------------------------------- portals
def _itd(driver, user_id, password, extra, say):
    driver.get(PORTAL_URLS["ITD"])
    say("Typing your User ID…")
    uid = _find(driver, ["#panAdhaarUserId", "input[name='panAdhaarUserId']",
                         "input[placeholder*='USER ID' i]"], 40)
    if not uid:
        raise _changed("Income-tax")
    _type(uid, user_id)
    btn = _button(driver, ["Continue"], 15)
    if not btn:
        raise _changed("Income-tax")
    _click(driver, btn)

    say("Typing your password…")
    pwd = _find(driver, ["#loginPasswordField", "input[type='password']"], 40,
                need_enabled=False)
    if not pwd:
        raise PortalError("The portal did not show the password box. Check the User ID in "
                          "the browser window.", browser_open=True)
    from selenium.webdriver.common.by import By
    for cb in driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
        try:
            if not cb.is_selected():
                _click(driver, cb)
            break
        except Exception:
            pass
    pwd = _find(driver, ["#loginPasswordField", "input[type='password']"], 10) or pwd
    _type(pwd, password)
    btn = _button(driver, ["Continue", "Login"], 15)
    if not btn:
        raise _changed("Income-tax")
    _click(driver, btn)
    say("Details filled. If the portal asks for an OTP, type it in the browser.")


def _gst(driver, user_id, password, extra, say):
    driver.get(PORTAL_URLS["GST"])
    say("Typing your username…")
    uid = _find(driver, ["#username", "input[name='user_name']", "input[name='username']"], 40)
    if not uid:
        raise _changed("GST")
    _type(uid, user_id)
    pwd = _find(driver, ["#user_pass", "input[type='password']"], 15)
    if not pwd:
        raise _changed("GST")
    _type(pwd, password)
    cap = _find(driver, ["#captcha", "input[name='captcha']"], 10)
    if cap:
        cap.click()
    say("Type the captcha shown in the browser, then click LOGIN.")


def _traces(driver, user_id, password, extra, say):
    driver.get(PORTAL_URLS["TRACES"])
    say("Typing your TRACES details…")
    uid = _find(driver, ["#userId", "input[name='userId']"], 40)
    if not uid:
        raise _changed("TRACES")
    _type(uid, user_id)
    pwd = _find(driver, ["#psw", "input[type='password']"], 15)
    if not pwd:
        raise _changed("TRACES")
    _type(pwd, password)
    tan = (extra or {}).get("tan")
    if tan:
        box = _find(driver, ["#tanpan", "input[name='tanpan']"], 10)
        if box:
            _type(box, tan)
    cap = _find(driver, ["#captcha", "input[name='captcha']"], 10)
    if cap:
        cap.click()
    say("Type the captcha shown in the browser, then click Go.")


_FLOWS = {"ITD": _itd, "GST": _gst, "TRACES": _traces}


# ---------------------------------------------------------------- public API
def run(portal, user_id, password, extra=None, say=lambda _m: None):
    """Blocking. Call from a background thread (use start() from the UI)."""
    if portal not in _FLOWS:
        raise PortalError(f"Unknown portal: {portal}")
    if not _busy.acquire(blocking=False):
        raise PortalError("A portal login is already in progress.")
    try:
        say("Opening the browser… (the first time can take a minute)")
        driver = _new_driver()
        try:
            _FLOWS[portal](driver, user_id, password, extra or {}, say)
        except PortalError:
            raise
        except Exception as e:
            raise PortalError(f"Auto-login stopped: {str(e).splitlines()[0][:150] if str(e) else e}. "
                              "Please finish the login in the browser window.",
                              browser_open=True)
    finally:
        _busy.release()


def start(widget, portal, user_id, password, extra=None, on_status=None, on_done=None):
    """Run the login in the background. on_status(msg) for progress;
    on_done(error_message_or_None, browser_open) when finished. Both run on the UI thread."""
    q = queue.Queue()
    on_status = on_status or (lambda _m: None)
    on_done = on_done or (lambda _e, _b: None)

    def work():
        try:
            run(portal, user_id, password, extra, lambda m: q.put(("status", m)))
            q.put(("done", (None, True)))
        except PortalError as e:
            q.put(("done", (str(e), e.browser_open)))
        except Exception as e:
            q.put(("done", (f"Auto-login failed: {e}", False)))

    threading.Thread(target=work, daemon=True).start()
    root = widget.nametowidget(".")

    def poll():
        try:
            while True:
                kind, payload = q.get_nowait()
                try:
                    if kind == "status":
                        on_status(payload)
                    else:
                        on_done(*payload)
                        return
                except Exception:
                    if kind == "done":
                        return
        except queue.Empty:
            pass
        root.after(200, poll)

    root.after(200, poll)