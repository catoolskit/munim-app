"""Tally XML importer for MUNIM — Masters only (Option A).

Reads a Tally XML export and imports:
  - Ledger accounts (with opening balances)
  - Parties (customers and suppliers) derived from ledger groups

Usage:
  from utils.tally_import import parse_tally_xml, import_masters
  data = parse_tally_xml(xml_path)
  result = import_masters(con, data)

How to export from Tally:
  Gateway > Display > Account Books > (any) > Export > XML
  OR: Gateway > Export Data > Masters > XML format
"""
import xml.etree.ElementTree as ET
from db import setup as s

CUSTOMER_GROUPS = {
    "sundry debtors", "debtors", "trade debtors",
    "accounts receivable", "customers",
}
SUPPLIER_GROUPS = {
    "sundry creditors", "creditors", "trade creditors",
    "accounts payable", "suppliers",
}
GROUP_MAP = {
    "bank accounts":           ("Bank Accounts",            "Asset"),
    "bank od a/c":             ("Bank Accounts",            "Asset"),
    "cash-in-hand":            ("Cash-in-hand",             "Asset"),
    "stock-in-trade":          ("Current Assets",           "Asset"),
    "loans & advances(asset)": ("Loans & Advances (Asset)", "Asset"),
    "loans(liability)":        ("Loans (Liability)",        "Liability"),
    "capital account":         ("Capital Account",          "Liability"),
    "current liabilities":     ("Current Liabilities",      "Liability"),
    "duties & taxes":          ("Duties & Taxes",           "Liability"),
    "direct expenses":         ("Direct Expenses",          "Expense"),
    "indirect expenses":       ("Indirect Expenses",        "Expense"),
    "direct incomes":          ("Direct Income",            "Income"),
    "indirect incomes":        ("Indirect Income",          "Income"),
    "sales accounts":          ("Sales Accounts",           "Income"),
    "purchase accounts":       ("Purchase Accounts",        "Expense"),
    "fixed assets":            ("Fixed Assets",             "Asset"),
    "current assets":          ("Current Assets",           "Asset"),
}

SKIP_NAMES = {
    "cash", "bank", "sales", "purchase", "capital",
    "sundry debtors", "sundry creditors", "stock-in-trade",
    "output cgst", "output sgst", "output igst",
    "input cgst", "input sgst", "input igst",
}


def _text(el, tag, default=""):
    child = el.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return default


def _amount(text):
    """Parse Tally amount string like '1,23,456.78 Dr' or '-5000.00 Cr'."""
    if not text:
        return 0.0, "Dr"
    text = text.strip()
    side = "Cr" if text.upper().endswith("CR") else "Dr"
    num_str = (text.upper()
               .replace("DR", "")
               .replace("CR", "")
               .replace(",", "")
               .strip())
    try:
        val = abs(float(num_str))
    except ValueError:
        val = 0.0
    return val, side


def parse_tally_xml(filepath):
    """Parse a Tally XML export file.

    Returns a dict:
      {
        "ledgers": [{"name", "group", "opening", "side", "gstin", "address"}, ...],
        "errors":  [str, ...]
      }
    """
    errors  = []
    ledgers = []

    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        return {"ledgers": [], "errors": [f"Could not read XML file: {e}"]}

    ledger_elements = (
        root.findall(".//LEDGER") or
        root.findall(".//Ledger") or
        root.findall(".//REQUESTDATA/TALLYMESSAGE/LEDGER")
    )

    if not ledger_elements:
        errors.append(
            "No ledger data found in this XML file. "
            "Make sure you exported Masters from Tally.")
        return {"ledgers": [], "errors": errors}

    for el in ledger_elements:
        name = (el.get("NAME") or
                _text(el, "NAME") or
                _text(el, "name", "")).strip()
        if not name:
            continue

        group_raw   = (_text(el, "PARENT") or
                       _text(el, "parent") or "").strip().lower()
        opening_raw = (_text(el, "OPENINGBALANCE") or
                       _text(el, "OpeningBalance") or "0").strip()
        gstin = (_text(el, "GSTREGISTRATIONDETAILS/GSTIN") or
                 _text(el, "gstin") or "").strip().upper()
        address_parts = el.findall(".//ADDRESS")
        address = ", ".join(
            p.text.strip()
            for p in address_parts
            if p.text and p.text.strip()
        )

        opening, side = _amount(opening_raw)

        ledgers.append({
            "name":    name,
            "group":   group_raw,
            "opening": opening,
            "side":    side,
            "gstin":   gstin,
            "address": address,
        })

    return {"ledgers": ledgers, "errors": errors}


def import_masters(con, data):
    """Import parsed Tally data into MUNIM.

    Returns:
      {
        "parties_added":  int,
        "accounts_added": int,
        "skipped":        [str],
        "errors":         [str],
      }
    """
    ledgers       = data.get("ledgers", [])
    parties_added = accounts_added = 0
    skipped       = []
    errors        = []

    for led in ledgers:
        name       = led["name"]
        group      = led["group"]
        name_lower = name.lower()

        if name_lower in SKIP_NAMES:
            skipped.append(f"{name} (system account)")
            continue

        if con.execute(
                "SELECT 1 FROM accounts WHERE name=? COLLATE NOCASE",
                (name,)).fetchone():
            skipped.append(f"{name} (already exists)")
            continue

        opening = led["opening"]
        side    = led["side"]
        gstin   = led["gstin"]
        address = led["address"]

        if group in CUSTOMER_GROUPS:
            try:
                s.add_party(con, name, "Customer", gstin, "", address, opening)
                parties_added += 1
            except ValueError as e:
                errors.append(f"{name}: {e}")
            continue

        if group in SUPPLIER_GROUPS:
            try:
                s.add_party(con, name, "Supplier", gstin, "", address, opening)
                parties_added += 1
            except ValueError as e:
                errors.append(f"{name}: {e}")
            continue

        munim_group, nature = GROUP_MAP.get(group, (None, None))
        if munim_group is None:
            for key, (mg, nat) in GROUP_MAP.items():
                if key in group:
                    munim_group, nature = mg, nat
                    break

        if munim_group is None:
            skipped.append(f"{name} (unknown group: {group})")
            continue

        try:
            s.add_ledger_account(con, name, munim_group, opening, side)
            accounts_added += 1
        except ValueError as e:
            errors.append(f"{name}: {e}")

    return {
        "parties_added":  parties_added,
        "accounts_added": accounts_added,
        "skipped":        skipped,
        "errors":         errors,
    }