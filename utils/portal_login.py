"""MUNIM — portal login helper (Income-tax e-filing, TRACES, GST).

MUNIM opens the portal in the user's normal browser and copies the User ID.
The user pastes it, then uses 'Copy password' to paste the password, and types
the captcha / OTP. MUNIM never bypasses captcha, OTP or any login check, and
does not drive the browser (the portals block automated browsers).
"""
import webbrowser

PORTAL_URLS = {
    "ITD": "https://eportal.incometax.gov.in/iec/foservices/#/login",
    "TRACES": "https://www.tdscpc.gov.in/app/login.xhtml",
    "GST": "https://services.gst.gov.in/services/login",
}
PORTAL_NAMES = {"ITD": "Income-tax portal", "TRACES": "TRACES", "GST": "GST portal"}


def open_portal(widget, portal, user_id=""):
    """Open the portal's login page in the normal browser and copy the User ID.
    Returns a short message for the status line."""
    name = PORTAL_NAMES.get(portal, "portal")
    url = PORTAL_URLS.get(portal)
    if not url:
        return f"No login page known for {name}."
    webbrowser.open(url)
    if user_id:
        try:
            root = widget.nametowidget(".")
            root.clipboard_clear()
            root.clipboard_append(user_id)
        except Exception:
            pass
        return (f"{name} opened. User ID copied — paste it, click Continue, then use "
                "'Copy password'. Type the captcha / OTP yourself.")
    return f"{name} opened."