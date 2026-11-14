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
        M("Journal Entry", "J"), M("Sales", "S"), M("Purchase", "P"), M("GST Invoice", "G"),
    ]),
    "reports": ("Reports", [
        M("Ledger View", "L"), M("Trial Balance", "T"), M("Cash Book", "C"), M("Day Book", "D"),
        M("Balance Sheet", "B"), M("Profit & Loss", "P"), M("Stock Summary", "S"),
    ]),
    "utilities": ("Utilities", [
        M("Company Details", "C", ("page", "company")),
        M("Backup Data", "B", ("fn", "backup")),
        M("Change Password", "P", ("page", "password")),
    ]),
}
