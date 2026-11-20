import customtkinter as ctk
from ui import theme as T

SECTIONS = [
    ("Getting started", [
        "1.  Utilities > Company Details — enter your business name, GSTIN, address and state. This appears on every invoice.",
        "2.  Masters > Stock Items — add the goods you buy and sell (Gold, Silver etc). Set HSN code, GST rate and opening stock quantity and rate.",
        "3.  Masters > Party Master — add your customers and suppliers. You can also add one while billing using the + New button.",
        "4.  Transactions > Sales Invoice or Purchase Bill — record your first bill. GST is calculated automatically.",
        "5.  Utilities > Backup Data — save a copy to a pen drive or cloud folder. Do this every day you enter data.",
    ]),
    ("Keyboard shortcuts", [
        "Menus:  ↑ ↓ and Enter to navigate, or press the letter shown on the right of an item.",
        "Esc:  go back one screen from anywhere.",
        "Ctrl+S:  save the entry you are currently on.",
        "Enter:  move to the next field on any entry screen.",
        "Dates:  type 15 (this month's 15th), 1511 (15 Nov this year) or the full 15-11-2026.",
        "Account / party boxes:  type a few letters, then press Enter or click to pick from the dropdown.",
        "Reports:  double-click any voucher or bill row to open, edit or delete it.",
    ]),
    ("Sales & invoicing", [
        "Sales Invoice:  for every sale to a registered business or any customer who needs a GST invoice. Pick the customer, add items (HSN and GST auto-fill from Stock Items), save.",
        "Save PDF:  after saving an invoice, click 'Save PDF' to generate and open a printable A4 invoice. PDFs are saved to the MUNIM\\Invoices\\ folder.",
        "Share:  after saving a PDF, click 'Share' to send via WhatsApp Web or Email. The party's phone number is pre-filled if set in Party Master.",
        "Inter-state sales:  tick 'Inter-state (IGST)' — MUNIM auto-detects this from the buyer's GSTIN state code, but you can override it.",
        "Part payment at sale time:  enter the amount in 'Received now'. The rest stays as the customer's outstanding balance.",
        "Walk-in / cash customer:  choose Cash as the customer. If they want a named bill, type their name in 'Customer name on bill'.",
        "Daily Sales Summary:  use this for counter sales where individual invoices are not needed. Enter total sales per GST rate for the day.",
        "Sales Return / Credit Note:  Transactions > Sales Return. Select the customer, pick the original invoice, enter returned items.",
    ]),
    ("Purchases & expenses", [
        "Purchase Bill:  record every bill from a supplier. Items, HSN and GST auto-fill from Stock Items master.",
        "Reverse Charge (RCM):  tick the RCM checkbox on a purchase bill if the supply attracts reverse charge. This populates section 3.1(d) in GSTR-3B automatically.",
        "Purchase Return / Debit Note:  Transactions > Purchase Return. Select the supplier, pick the original bill, enter returned items.",
        "Expenses (electricity, rent etc):  create the ledger account first under Masters > Ledger Accounts (pick Direct or Indirect Expenses group), then record it via Transactions > Voucher Entry.",
    ]),
    ("Payments & receipts", [
        "Receipt / Payment:  Transactions > Receipt / Payment. Select the customer or supplier, then type the amount against each open bill to settle it.",
        "On-account payment:  if you pay more than a bill's balance, the excess is held as an on-account credit and shown in Outstanding.",
        "Outstanding report:  Reports > Outstanding. Switch between Receivable (customers) and Payable (suppliers). Set ageing ranges to see overdue amounts.",
        "Party Statement:  Reports > Accounting > Party Statement. Full transaction history for one party with opening and closing balance. Exportable to Excel.",
    ]),
    ("GST reports & filing", [
        "GSTR-1:  Reports > GST > GSTR-1. Shows outward supplies by rate and invoice. Use 'Export JSON' to download a portal-ready JSON file for upload to the GST offline tool.",
        "GSTR-3B:  Reports > GST > GSTR-3B. Full monthly summary including RCM, ITC cross-utilisation, net payable, and suggested payment breakdown.",
        "ITC cross-utilisation:  MUNIM applies IGST ITC first against IGST liability, then uses any remaining IGST ITC to offset CGST and SGST — matching the GST Act order.",
        "B2B vs B2C:  invoices to parties with a GSTIN are classified B2B; all others are B2C. Add GSTIN to a party in Party Master to move them to B2B.",
        "Filing tip:  enter all transactions for the month, check GSTR-1 and GSTR-3B in MUNIM, then upload the JSON to the GST portal. Ask your CA to verify before submitting.",
    ]),
    ("Stock & valuation", [
        "Stock Items Master:  Masters > Stock Items. Set HSN, unit, GST rate, opening quantity and opening rate for each item.",
        "Stock Summary:  Reports > Stock > Stock Summary. Shows opening, purchased, sold and closing quantity, plus weighted-average cost and total stock value.",
        "Item-wise Profit:  Reports > Stock > Item-wise Profit. Shows sale value, cost of goods sold (at weighted-average rate), profit and margin % per item.",
        "Weighted-average cost:  MUNIM calculates average cost as (opening stock value + purchases − purchase returns) ÷ total quantity. This feeds both Stock Summary and Item-wise Profit so the two reports always agree.",
    ]),
    ("Accounting & reports", [
        "Trial Balance:  Reports > Accounting > Trial Balance. All account closing balances for the year.",
        "Ledger View:  Reports > Accounting > Ledger View. Every entry in one account with a running balance. Use the Cash Book shortcut for cash and bank entries.",
        "Day Book:  Reports > Accounting > Day Book. All vouchers between two dates.",
        "Cash Flow:  Reports > Financial > Cash Flow. Sources and uses of cash — operating, financing and investing activities.",
        "Trading & P&L:  Reports > Financial > Trading & P&L. Enter opening and closing stock to get gross and net profit.",
        "Balance Sheet:  Reports > Financial > Balance Sheet. Assets and liabilities as at year end.",
        "Export Excel:  most reports have an 'Export Excel' button that saves an .xlsx file.",
        "Dashboard:  Reports > Dashboard. Business snapshot — monthly sales chart, top customers, GST payable trend, stock value summary.",
    ]),
    ("Bank reconciliation", [
        "Reports > Accounting > Bank Reconciliation. Import your bank statement as a CSV file and match the entries to your MUNIM books.",
        "CSV format:  Date (DD-MM-YYYY), Description, Amount, Dr/Cr — four columns, one row per transaction.",
        "Matching:  MUNIM finds ledger entries on the same date with the same amount and suggests them. Double-click a row to accept the match.",
        "Unmatched rows:  entries in your bank statement with no match in MUNIM usually mean a missing voucher. Enter it and re-run.",
    ]),
    ("Utilities & data", [
        "Backup Data:  Utilities > Backup Data. Always back up to a different drive or cloud folder — not the same disk as your data.",
        "Auto-backup:  MUNIM automatically backs up to the MUNIM\\backups\\ folder every time you close the app. The gateway shows a warning if no backup has been taken in over 7 days.",
        "Import from Tally:  Utilities > Import from Tally. Bring in party names, ledger accounts and opening balances from a Tally XML export. Historical vouchers are not imported.",
        "Data Location:  Utilities > Data Location. Move your MUNIM data folder to a different drive (e.g. D:).",
        "Audit Log:  Utilities > Audit Log. Every voucher created, edited or deleted — with who did it and when.",
        "Manage Companies:  Utilities > Manage Companies. Rename or delete companies. Use the company picker at login to switch between companies.",
        "Reset All Data:  Utilities > Reset All Data. Wipes all vouchers, parties and accounts. Requires admin password. Cannot be undone.",
    ]),
    ("Good to know", [
        "GST law requires a tax invoice for every sale to a registered business. A monthly lump entry covers your books but does not replace individual invoices. Ask your CA if unsure.",
        "Your data is stored as a single SQLite file inside the MUNIM data folder. It is small and easy to back up.",
        "If MUNIM crashes, check the MUNIM\\logs\\ folder for an error log. Share it with support when reporting a problem.",
        "Support: support@munim.in     Licence renewal: Utilities > Renew Licence.",
    ]),
]


class HelpFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        T.title(self, "Help & Shortcuts",
                "Everything you need to use MUNIM.").pack(
            anchor="w", padx=28, pady=(24, 12))
        box = ctk.CTkScrollableFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        for head, lines in SECTIONS:
            card = T.card(box)
            card.pack(fill="x", padx=8, pady=8)
            ctk.CTkLabel(card, text=head, font=T.f(16, "bold"),
                         text_color=T.TEXT).pack(
                anchor="w", padx=22, pady=(16, 6))
            for ln in lines:
                ctk.CTkLabel(card, text=ln, font=T.f(13), text_color=T.TEXT,
                             wraplength=900, justify="left",
                             anchor="w").pack(anchor="w", padx=22, pady=3)
            ctk.CTkFrame(card, fg_color=T.CARD, corner_radius=0,
                         height=10).pack()