"""Tally-style menu tree. go=None means 'not built yet' (shown dimmed, with a 'soon' tag)."""
def M(label, key, go=None):
    return {"label": label, "key": key, "go": go}

MENUS = {
    "gateway": ("Gateway of MUNIM", [
        M("Masters",      "M", ("menu", "masters")),
        M("Transactions", "T", ("menu", "transactions")),
        M("Reports",      "R", ("menu", "reports")),
        M("Utilities",    "U", ("menu", "utilities")),
        M("Log out",      "Q", ("quit",)),
    ]),
    "masters": ("Masters", [
        M("Party Master",    "P", ("page", "party")),
        M("Ledger Accounts", "L", ("page", "accounts")),
        M("Stock Items", "I", ("page", "stockitems")),
    ]),
    "transactions": ("Transactions", [
        M("Sales Invoice",               "S", ("page", "sales")),
        M("Sales Return / Credit Note",  "N", ("page", "salesreturn")),
        M("Daily Sales Summary",         "D", ("page", "summary")),
        M("Purchase Bill",               "P", ("page", "purchase")),
        M("Purchase Return / Debit Note","E", ("page", "purchasereturn")),
        M("Receipt / Payment",           "R", ("page", "payment")),
        M("Voucher Entry (journal etc.)", "V", ("page", "journal")),
        M("GST Invoice (print)",         "G"),
    ]),
    "reports": ("Reports", [
    M("Ledger View", "L", ("page", "ledger")), M("Trial Balance", "T", ("page", "trial")),
    M("Cash Book", "C", ("page", "cashbook")), M("Day Book", "D", ("page", "daybook")),
    M("Outstanding", "O", ("page", "outstanding")), M("Sales Register", "S", ("page", "salesreg")), M("Purchase Register", "U", ("page", "purchasereg")),
    M("Sales Return Register", "E", ("page", "salesreturnreg")),
    M("Purchase Return Register", "N", ("page", "purchasereturnreg")),
    M("Balance Sheet", "B", ("page", "bs")), M("Trading & P&L", "P", ("page", "pl")),
    M("Stock Summary", "K", ("page", "stocksummary")),
    M("Item-wise Profit", "I", ("page", "itemprofit")),
    ]),
    "utilities": ("Utilities", [
        M("Company Details",  "C", ("page", "company")),
        M("Backup Data",      "B", ("fn",   "backup")),
        M("Data Location", "D", ("page", "datalocation")),
        M("Audit Log",        "A", ("page", "audit")),
        M("Help & Shortcuts", "H", ("page", "help")),
        M("Change Password",  "P", ("page", "password")),
        M("Renew Licence",    "R", ("page", "renew")),
        M("Manage Companies", "M", ("page", "companies")),
        M("Reset All Data",   "X", ("page", "reset")),
    ]),
}
