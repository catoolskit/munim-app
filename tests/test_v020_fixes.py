import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

from db import setup as db, billing
from utils.company_backup import export_company_backup, restore_company_backup


class V020FixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.con = db.init_db(os.path.join(self.tmp, "company.db"))
        db.add_party(self.con, "Walk-in Customer", "Customer")

    def tearDown(self):
        self.con.close()

    def test_unregistered_sales_post_no_gst_in_voucher_or_invoice(self):
        with patch("utils.settings.load_settings", return_value={"gst_registered": False}):
            result = billing.post_sale(
                self.con, date(2026, 11, 26), "Cash",
                [("Gold", "7109", 3, 180000, 18, None)])
        self.assertEqual(result["taxable"], 540000)
        self.assertEqual(result["cgst"], 0)
        self.assertEqual(result["sgst"], 0)
        self.assertEqual(result["igst"], 0)
        self.assertEqual(result["total"], 540000)
        invoice = self.con.execute("SELECT * FROM invoices WHERE kind='Sales'").fetchone()
        self.assertEqual((invoice["taxable"], invoice["cgst"], invoice["sgst"], invoice["igst"], invoice["total"]),
                         (54000000, 0, 0, 0, 54000000))
        item = self.con.execute("SELECT gst FROM invoice_items WHERE invoice_id=?", (invoice["id"],)).fetchone()
        self.assertEqual(float(item["gst"]), 0.0)
        output_tax = self.con.execute("SELECT COALESCE(SUM(cr),0) FROM entries e JOIN accounts a ON a.id=e.account_id WHERE a.name LIKE 'Output %'").fetchone()[0]
        self.assertEqual(output_tax, 0)

    def test_company_backup_roundtrip(self):
        db.post_voucher(self.con, "Journal", date(2026, 11, 26), "Opening",
                        [("Cash", 1000, 0), ("Capital", 0, 1000)])
        backup = os.path.join(self.tmp, "company.json")
        export_company_backup(self.con, "Test Company", backup,
                              settings_override={"company_name": "Test Company", "gst_registered": False})
        restored = db.init_db(os.path.join(self.tmp, "restored.db"))
        with patch("utils.settings.save_settings"):
            result = restore_company_backup(restored, backup, "Test Company")
        self.assertGreater(result["records_restored"], 0)
        self.assertEqual(restored.execute("SELECT COUNT(*) FROM vouchers").fetchone()[0], 1)
        self.assertEqual(restored.execute("SELECT COUNT(*) FROM entries").fetchone()[0], 2)
        restored.close()

    def test_mobile_import_respects_unregistered_company(self):
        from utils.mobile_export import import_mobile_invoices
        payload = {"invoices": [{
            "mobile_id": "mobile-001", "inv_no": "M-1", "date": "2026-11-26",
            "party": "Cash", "items": [{"name": "Gold", "hsn": "7109", "qty": 3,
                                             "rate": 180000, "gst_rate": 18}]
        }]}
        source = os.path.join(self.tmp, "mobile.json")
        with open(source, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        with patch("utils.settings.load_settings", return_value={"gst_registered": False}):
            result = import_mobile_invoices(self.con, source)
        self.assertEqual(len(result["imported"]), 1)
        inv = self.con.execute("SELECT total,cgst,sgst,igst FROM invoices WHERE kind='Sales'").fetchone()
        self.assertEqual(tuple(inv), (54000000, 0, 0, 0))
        out_tax = self.con.execute("SELECT COALESCE(SUM(cr),0) FROM entries e JOIN accounts a ON a.id=e.account_id WHERE a.name LIKE 'Output %'").fetchone()[0]
        self.assertEqual(out_tax, 0)

    def test_repair_existing_sales_gst_updates_reports_and_ledgers(self):
        original = billing.post_sale(
            self.con, date(2026, 11, 26), "Cash",
            [("Gold", "7109", 3, 180000, 18, None)])
        self.assertEqual(original["total"], 637200)
        with patch("utils.settings.load_settings", return_value={"gst_registered": False}):
            result = billing.repair_unregistered_sales_gst(self.con, "admin")
        self.assertEqual(result["corrected"], 1)
        invoice = self.con.execute("SELECT total,cgst,sgst,igst FROM invoices WHERE kind='Sales'").fetchone()
        self.assertEqual(tuple(invoice), (54000000, 0, 0, 0))
        snapshot = db.voucher_snapshot(self.con, self.con.execute("SELECT voucher_id FROM invoices").fetchone()[0])
        self.assertEqual(sum(line["dr"] for line in snapshot["lines"]), 54000000)
        self.assertEqual(sum(line["cr"] for line in snapshot["lines"]), 54000000)

    def test_company_deletion_creates_json_recovery_backup(self):
        company_root = os.path.join(self.tmp, "data")
        os.makedirs(company_root, exist_ok=True)
        with patch("db.setup.data_dir", return_value=company_root):
            db.create_company("Delete Test Co")
            db.delete_company("Delete Test Co")
        deleted = os.path.join(company_root, "Deleted companies")
        backups = [n for n in os.listdir(deleted) if n.endswith("_MUNIM_Backup.json")]
        self.assertEqual(len(backups), 1)
        with open(os.path.join(deleted, backups[0]), encoding="utf-8") as f:
            payload = json.load(f)
        self.assertEqual(payload["company_name"], "Delete Test Co")
        self.assertNotIn("licence_key", payload.get("company_settings", {}))


if __name__ == "__main__":
    unittest.main()
