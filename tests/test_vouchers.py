import os, sys, tempfile, unittest
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import setup as s, billing as b, reports as r

D = date(2026, 11, 14)

class Base(unittest.TestCase):
    def setUp(self):
        self.con = s.init_db(os.path.join(tempfile.mkdtemp(), "t.db"))
        s.add_party(self.con, "Ram Traders", "Customer", "03ABCDE1234F1Z5")
    def vid(self, vtype, vno):
        return self.con.execute("SELECT id FROM vouchers WHERE vtype=? AND vno=?", (vtype, vno)).fetchone()["id"]
    def tb_balanced(self):
        rows, dr, cr = s.trial_balance(self.con, "2026-27")
        self.assertEqual(dr, cr)
        return {n: (d, c) for n, d, c in rows}

class InvoiceStorage(Base):
    def test_sale_stores_items_and_party(self):
        b.post_sale(self.con, D, "Ram Traders", [("Gold", 10, 100, 18), ("Silver", 2, 50.5, 5)], username="sumit")
        snap = s.voucher_snapshot(self.con, self.vid("Sales", 1))
        inv = snap["invoice"]
        self.assertEqual(inv["party"], "Ram Traders")
        self.assertEqual([i["description"] for i in inv["items"]], ["Gold", "Silver"])
        self.assertEqual(inv["items"][0]["amount"], 100000)
        self.assertEqual(inv["total"], sum(l["dr"] for l in snap["lines"]))

    def test_register_and_legacy_voucher(self):
        b.post_sale(self.con, D, "Ram Traders", [("Gold", 10, 100, 18)])
        s.post_voucher(self.con, "Sales", D, "old style", [("Cash", 500, 0), ("Sales", 0, 500)])
        reg = r.invoice_register(self.con, "2026-27", "Sales")
        self.assertEqual(len(reg), 2)
        self.assertEqual((reg[0]["party"], reg[0]["taxable"], reg[0]["cgst"], reg[0]["total"]),
                         ("Ram Traders", 1000, 90, 1180))
        self.assertEqual((reg[1]["party"], reg[1]["total"]), ("(details not stored)", 500))
        self.assertEqual(r.invoice_register(self.con, "2025-26", "Sales"), [])
        self.assertEqual(r.invoice_register(self.con, "2026-27", "Purchase"), [])

class EditDelete(Base):
    def test_update_invoice_recomputes_and_keeps_number(self):
        b.post_sale(self.con, D, "Ram Traders", [("Gold", 10, 100, 18)])
        b.post_sale(self.con, D, "Ram Traders", [("Gold", 1, 100, 18)])
        vid = self.vid("Sales", 1)
        res = b.update_invoice(self.con, vid, D, "Ram Traders", [("Gold", 20, 100, 18)], True, "fixed", "sumit")
        self.assertEqual((res["vno"], res["igst"], res["cgst"], res["total"]), (1, 360, 0, 2360))
        t = self.tb_balanced()
        self.assertEqual(t["Output IGST"], (0, 360))
        self.assertEqual(t["Output CGST"], (0, 9))      # only invoice no. 2 remains: 18 tax = 9 CGST + 9 SGST
        self.assertEqual(s.voucher_snapshot(self.con, vid)["invoice"]["interstate"], 1)
        self.assertEqual(len(s.voucher_snapshot(self.con, vid)["invoice"]["items"]), 1)

    def test_delete_removes_everything_and_logs(self):
        b.post_sale(self.con, D, "Ram Traders", [("Gold", 10, 100, 18)])
        vid = self.vid("Sales", 1)
        s.delete_voucher(self.con, vid, "sumit")
        for tbl in ("vouchers", "entries", "invoices", "invoice_items"):
            self.assertEqual(self.con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0], 0, tbl)
        self.assertEqual(r.invoice_register(self.con, "2026-27", "Sales"), [])
        log = s.audit_entries(self.con)
        self.assertEqual([(x["action"], x["vtype"], x["vno"], x["user"], x["amount"]) for x in log],
                         [("delete", "Sales", 1, "sumit", 1180), ("create", "Sales", 1, "", 1180)])
        self.tb_balanced()

    def test_edit_journal_changes_type_and_year(self):
        s.post_voucher(self.con, "Journal", D, "", [("Cash", 1000, 0), ("Capital", 0, 1000)])
        vid = self.vid("Journal", 1)
        s.update_voucher(self.con, vid, "Receipt", date(2027, 5, 1), "moved",
                         [("Cash", 700, 0), ("Capital", 0, 700)], "sumit")
        v = s.voucher_snapshot(self.con, vid)
        self.assertEqual((v["vtype"], v["vno"], v["fy"], v["vdate"]), ("Receipt", 1, "2027-28", "2027-05-01"))
        self.assertEqual(v["lines"][0]["dr"], 70000)
        self.assertEqual(s.audit_entries(self.con)[0]["action"], "edit")

    def test_failed_edit_leaves_original_untouched(self):
        s.post_voucher(self.con, "Journal", D, "orig", [("Cash", 1000, 0), ("Capital", 0, 1000)])
        vid = self.vid("Journal", 1)
        for bad in ([("Cash", 100, 0), ("Capital", 0, 90)], [("Cash", 100, 0), ("Nope", 0, 100)]):
            with self.assertRaises(ValueError):
                s.update_voucher(self.con, vid, "Journal", D, "x", bad)
        v = s.voucher_snapshot(self.con, vid)
        self.assertEqual((v["narration"], v["lines"][0]["dr"]), ("orig", 100000))
        with self.assertRaises(ValueError):
            b.update_invoice(self.con, vid, D, "Ram Traders", [("x", 1, 1, 0)])  # not an invoice

    def test_edit_guards(self):
        b.post_sale(self.con, D, "Ram Traders", [("Gold", 1, 100, 18)])
        vid = self.vid("Sales", 1)
        with self.assertRaises(ValueError):
            s.update_voucher(self.con, vid, "Journal", D, "", [("Cash", 1, 0), ("Capital", 0, 1)])
        with self.assertRaises(ValueError):
            b.update_invoice(self.con, vid, D, "Ghost Party", [("x", 1, 1, 0)])
        self.assertEqual(s.voucher_snapshot(self.con, vid)["invoice"]["party"], "Ram Traders")
        s.post_voucher(self.con, "Sales", D, "legacy", [("Cash", 5, 0), ("Sales", 0, 5)])
        with self.assertRaises(ValueError):
            b.update_invoice(self.con, self.vid("Sales", 2), D, "Cash", [("x", 1, 1, 0)])
        with self.assertRaises(ValueError):
            s.delete_voucher(self.con, 9999)

if __name__ == "__main__":
    unittest.main()
