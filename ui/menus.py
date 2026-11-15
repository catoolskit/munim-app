"""Tally-style menu tree. go=None means 'not built yet' (shown dimmed, with a 'soon' tag)."""
def M(label, key, go=None):
    return {"label": label, "key": key, "go": go}

MENUS = {
    "gateway": ("Gateway of MUNIM", [
        M("Masters", "M", ("menu", "masters")),
        M("Transactions", "T", ("menu", "transactions")),
        M("Reports", "R", ("menu", "reports")),
        M("Utilities", "U", ("menu", "utilities")),
        M("Log out", "Q", ("quit",)),
    ]),
    "masters": ("Masters", [
        M("Party Master", "P", ("page", "party")),
        M("Stock Items", "S"),
    ]),
    "transactions": ("Transactions", [
        M("Voucher Entry", "V", ("page", "journal")), M("Sales Invoice", "S", ("page", "sales")),
        M("Purchase Bill", "P", ("page", "purchase")), M("GST Invoice (print)", "G"),
    ]),
    "reports": ("Reports", [
        M("Ledger View", "L", ("page", "ledger")), M("Trial Balance", "T", ("page", "trial")),
        M("Cash Book", "C", ("page", "cashbook")), M("Day Book", "D", ("page", "daybook")),
        M("Balance Sheet", "B", ("page", "bs")), M("Profit & Loss", "P", ("page", "pl")),
        M("Stock Summary", "S"),
    ]),
    "utilities": ("Utilities", [
        M("Company Details", "C", ("page", "company")),
        M("Backup Data", "B", ("fn", "backup")),
        M("Change Password", "P", ("page", "password")),
    ]),
}
