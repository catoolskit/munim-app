import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import setup as s, billing as b
from unittest.mock import patch
from utils.pdf_reports import generate_trial_balance_pdf
from pypdf import PdfReader


class MoneyAndReportTests(unittest.TestCase):
    def setUp(self):
        self.con = s.init_db(os.path.join(tempfile.mkdtemp(), "munim-test.db"))
        self.day = date(2026, 11, 14)
        s.add_party(self.con, "GST Customer", "Customer", "03ABCDE1234F1Z5")

    def tearDown(self):
        self.con.close()

    def test_to_paise_decimal_half_up_and_blank_values(self):
        self.assertEqual(s.to_paise("1.005"), 101)
        self.assertEqual(s.to_paise("2.675"), 268)
        self.assertEqual(s.to_paise("-1.005"), -101)
        self.assertEqual(s.to_paise("1,234.50"), 123450)
        self.assertEqual(s.to_paise(None), 0)
        self.assertEqual(s.to_paise("  "), 0)
        for bad in ("abc", "NaN", "Infinity"):
            with self.assertRaises(ValueError):
                s.to_paise(bad)

    def test_grouped_trial_balance_rows_rupees_totals_paise(self):
        s.add_account(self.con, "Test opening debtor", "Sundry Debtors",
                      "Asset", opening="123.45", opening_side="Dr")
        rows, td, tc = s.trial_balance_grouped(self.con, "2026-27", detailed=True)
        group = next(r for r in rows if r["kind"] == "group" and
                     r["group_key"] == "Sundry Debtors")
        difference = next(r for r in rows if r["name"] == "Difference in opening balances")
        total = rows[-1]
        self.assertEqual(group["dr"], 123.45)
        self.assertEqual(difference["cr"], 123.45)
        self.assertEqual(total["dr"], 123.45)
        self.assertEqual(total["cr"], 123.45)
        self.assertEqual((td, tc), (12345, 12345))

    def test_grouped_trial_balance_pdf_formats_row_totals_as_rupees(self):
        s.add_account(self.con, "PDF opening debtor", "Sundry Debtors",
                      "Asset", opening="123.45", opening_side="Dr")
        rows, td, tc = s.trial_balance_grouped(
            self.con, "2026-27", detailed=True)
        with tempfile.TemporaryDirectory() as directory:
            with patch("utils.pdf_reports._report_dir", return_value=directory):
                path = generate_trial_balance_pdf(
                    "Test Company", "2026-27", rows, td, tc, detailed=True)
            text = "\n".join(page.extract_text() or ""
                            for page in PdfReader(path).pages)
        self.assertIn("123.45", text)
        # A rupee row value must not be passed through paise formatting again.
        self.assertNotIn("12,345.00", text)

    def test_gstr1_and_gstr3b_outward_reconcile_to_invoice_headers(self):
        sale = b.post_sale(
            self.con, self.day, "GST Customer",
            [("Rate 5", "", 3, 33.33, 5),
             ("Rate 18", "", 7, 12.49, 18)], interstate=False)
        original = self.con.execute("SELECT id FROM vouchers WHERE vtype='Sales' AND vno=?", (sale["vno"],)).fetchone()
        # Partial credit note, allocated to the original invoice by billing.
        b.post_sales_return(
            self.con, date(2026, 11, 20), "GST Customer", original["id"],
            [("Rate 5 return", "", 1, 33.33, 5)], interstate=False)

        rep = s.gstr1_report(self.con, "2026-27", 8)  # November 2026
        for component in ("taxable", "cgst", "sgst", "igst", "total"):
            detail_total = round(sum(inv[component] for inv in rep["invoices"]), 2)
            self.assertEqual(round(rep["totals"][component], 2), detail_total,
                             msg=f"GSTR-1 {component} summary must reconcile to invoice headers")

        three_b = s.gstr3b_report(self.con, "2026-27", 8)
        for component in ("cgst", "sgst", "igst"):
            self.assertEqual(round(three_b["outward"][component], 2),
                             round(rep["totals"][component], 2),
                             msg=f"GSTR-3B outward {component} must reconcile to invoice headers")

    def test_open_invoice_payment_and_return_allocations_reduce_balance(self):
        sale = b.post_sale(self.con, self.day, "GST Customer",
                          [("Item", "", 1, 1000, 18)])
        original = self.con.execute("SELECT id FROM vouchers WHERE vtype='Sales' AND vno=?", (sale["vno"],)).fetchone()
        b.record_payment(self.con, "Receipt", "GST Customer",
                         date(2026, 11, 15), 300,
                         allocations=[(original["id"], 300)])
        before_return = b.open_invoices(self.con, "GST Customer", "Sales",
                                       as_of=date(2026, 11, 15))[0]
        self.assertEqual(before_return["balance"], sale["total"] * 100 - 30000)

        b.post_sales_return(self.con, date(2026, 11, 16), "GST Customer",
                            original["id"], [("Return", "", 1, 200, 18)])
        after_return = b.open_invoices(self.con, "GST Customer", "Sales",
                                      as_of=date(2026, 11, 17))[0]
        self.assertEqual(after_return["balance"], before_return["balance"] - 23600)
        # Payment and return allocations are date-scoped for historical balances.
        historical = b.open_invoices(self.con, "GST Customer", "Sales",
                                     as_of=date(2026, 11, 15))[0]
        self.assertEqual(historical["balance"], before_return["balance"])


if __name__ == "__main__":
    unittest.main()
