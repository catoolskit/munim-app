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

def parse_date(text):
    t = (text or "").strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            pass
    raise ValueError("Date must be DD-MM-YYYY")

def today_str():
    return date.today().strftime("%d-%m-%Y")

def disp_date(iso):
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%d-%m-%Y")
