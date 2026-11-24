from datetime import date, datetime

def inr(x):
    """Indian digit grouping: 1234567.5 -> '12,34,567.50'."""
    neg = x < 0
    whole, frac = f"{abs(round(x, 2)):.2f}".split(".")
    if len(whole) > 3:
        head, tail, parts = whole[:-3], whole[-3:], []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return ("-" if neg else "") + whole + "." + frac

def parse_amount(text):
    t = (text or "").replace(",", "").strip()
    if not t:
        return 0.0
    try:
        v = float(t)
    except ValueError:
        raise ValueError(f"'{text.strip()}' is not a valid amount")
    if v < 0:
        raise ValueError("Amounts cannot be negative")
    return v

def parse_date(text, today=None):
    """DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD, DD-MM-YY, plus shortcuts: 't' (today), '15' (day this
    month), '1511' or '15-11' (day and month this year), '151126' (ddmmyy)."""
    today = today or date.today()
    t = (text or "").strip().lower()
    if t in ("t", "today"):
        return today
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            pass
    d = m = y = None
    if t.isdigit():
        if len(t) <= 2:
            d, m, y = int(t), today.month, today.year
        elif len(t) == 4:
            d, m, y = int(t[:2]), int(t[2:]), today.year
        elif len(t) == 6:
            d, m, y = int(t[:2]), int(t[2:4]), 2000 + int(t[4:])
    else:
        parts = [p for p in t.replace("/", "-").replace(".", "-").split("-")]
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            d, m, y = int(parts[0]), int(parts[1]), today.year
    if d is not None:
        try:
            return date(y, m, d)
        except ValueError:
            pass
    raise ValueError("Date must be DD-MM-YYYY (you can also type just 15, or 1511)")

def today_str():
    return date.today().strftime("%d-%m-%Y")

def disp_date(iso):
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%d-%m-%Y")
