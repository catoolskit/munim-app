import os, sys, tempfile, unittest
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import setup as s, billing as b, reports as r

class BillingTests(unittest.TestCase):
    def setUp(self):
        self.con = s.init_db(os.path.join(tempfile.mkdtemp(), "t.db"))
        s.add_party(self.con, "Ram Traders", "Customer", "03ABCDE1234F1Z5")
        s.add_party(self.con, "Shyam Supplies", "Supplier")
        self.d = date(2026, 11, 14)

    def tb(self):
        rows, dr, cr = s.trial_balance(self.con, "2026-27")
        self.assertEqual(dr, cr)
        return {n: (d, c) for n, d, c in rows}

    def test_intra_state_sale(self):
        res = b.post_sale(self.con, self.d, "Ram Traders", [("Rice", 10, 100, 18)])
        self.assertEqual((res["taxable"], res["cgst"], res["sgst"], res["igst"], res["total"]),
                         (1000, 90, 90, 0, 1180))
        t = self.tb()
        self.assertEqual(t["Ram Traders"], (1180, 0))
        self.assertEqual(t["Sales"], (0, 1000))
        self.assertEqual(t["Output CGST"], (0, 90))

    def test_inter_state_sale_uses_igst(self):
        res = b.post_sale(self.con, self.d, "Ram Traders", [("Rice", 10, 100, 18)], interstate=True)
        self.assertEqual((res["cgst"], res["sgst"], res["igst"], res["total"]), (0, 0, 180, 1180))

    def test_mixed_rates_and_odd_paise_stay_balanced(self):
        res = b.post_sale(self.con, self.d, "Ram Traders",
                          [("A", 3, 33.33, 5), ("B", 7, 12.49, 12), ("C", 1, 99.99, 0)])
        self.assertAlmostEqual(res["total"], res["taxable"] + res["cgst"] + res["sgst"] + res["igst"], places=2)
        self.tb()  # asserts Dr == Cr

    def test_purchase_posts_input_tax(self):
        b.post_purchase(self.con, self.d, "Shyam Supplies", [("Wheat", 100, 50, 5)])
        t = self.tb()
        self.assertEqual(t["Purchase"], (5000, 0))
        self.assertEqual(t["Input CGST"], (125, 0))
        self.assertEqual(t["Shyam Supplies"], (0, 5250))

    def test_sale_flows_into_pl_and_balance_sheet(self):
        b.post_sale(self.con, self.d, "Ram Traders", [("Rice", 10, 100, 18)])
        b.post_purchase(self.con, self.d, "Shyam Supplies", [("Wheat", 4, 100, 18)])
        pl = r.profit_and_loss(self.con, "2026-27")
        self.assertEqual(pl["net_profit"], 600)  # GST is not income or expense
        bs = r.balance_sheet(self.con, "2026-27")
        self.assertEqual(bs["total_assets"], bs["total_liabilities"])

    def test_voucher_numbers_and_validation(self):
        a = b.post_sale(self.con, self.d, "Ram Traders", [("x", 1, 10, 0)])["vno"]
        c = b.post_sale(self.con, self.d, "Ram Traders", [("x", 1, 10, 0)])["vno"]
        self.assertEqual((a, c), (1, 2))
        for bad in ([], [("x", 0, 10, 5)], [("x", 1, -1, 5)], [("x", 1, 10, 50)]):
            with self.assertRaises(ValueError):
                b.post_sale(self.con, self.d, "Ram Traders", bad)
        with self.assertRaises(ValueError):
            b.post_sale(self.con, self.d, "Unknown Party", [("x", 1, 10, 5)])

    def test_is_interstate(self):
        self.assertTrue(b.is_interstate("07ABCDE1234F1Z5", "03ABCDE1234F1Z5"))
        self.assertFalse(b.is_interstate("03ABCDE1234F1Z5", "03ABCDE1234F1Z5"))
        self.assertFalse(b.is_interstate("", "03ABCDE1234F1Z5"))

if __name__ == "__main__":
    unittest.main()
