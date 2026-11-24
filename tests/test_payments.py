import os, sys, tempfile, unittest
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import setup as s, billing as b, reports as r

D = date(2026, 11, 14)

class Base(unittest.TestCase):
    def setUp(self):
        self.con = s.init_db(os.path.join(tempfile.mkdtemp(), "t.db"))
        s.add_party(self.con, "Ram Traders", "Customer", "03ABCDE1234F1Z5")
        s.add_party(self.con, "Shyam Supplies", "Supplier")
    def vid(self, vtype, vno):
        return self.con.execute("SELECT id FROM vouchers WHERE vtype=? AND vno=?", (vtype, vno)).fetchone()["id"]
    def tb(self):
        rows, dr, cr = s.trial_balance(self.con, "2026-27")
        self.assertEqual(dr, cr)
        return {n: (d, c) for n, d, c in rows}
    def sale(self, amount, d=D, **kw):
        return b.post_sale(self.con, d, "Ram Traders", [("Goods", 1, amount, 0)], **kw)

class UserScenario(Base):
    def test_90000_sale_with_10000_cash_received(self):
        res = self.sale(90000, received=10000, mode="Cash")
        self.assertEqual((res["total"], res["received"], res["balance"]), (90000, 10000, 80000))
        t = self.tb()
        self.assertEqual(t["Ram Traders"], (80000, 0))         # customer owes the rest
        self.assertEqual(t["Cash"], (10000, 0))
        self.assertEqual(t["Sales"], (0, 90000))               # sale is still the full 90,000
        reg = r.invoice_register(self.con, "2026-27", "Sales")[0]
        self.assertEqual((reg["total"], reg["balance"], reg["status"]), (90000, 80000, "Partly paid"))
        # customer pays the balance later by bank
        pay = b.record_payment(self.con, "Receipt", "Ram Traders", D + timedelta(days=20), 80000, "Bank")
        self.assertEqual((pay["allocated"], pay["on_account"], pay["settled_bills"]), (80000, 0, [(1, 80000)]))
        reg = r.invoice_register(self.con, "2026-27", "Sales")[0]
        self.assertEqual((reg["balance"], reg["status"]), (0, "Paid"))
        self.assertNotIn("Ram Traders", self.tb())             # fully squared up in the ledger too

    def test_unpaid_and_fully_paid_now(self):
        self.sale(1000)
        self.sale(500, received=500, mode="Bank")
        st = [x["status"] for x in r.invoice_register(self.con, "2026-27", "Sales")]
        self.assertEqual(st, ["Unpaid", "Paid"])

class Payments(Base):
    def test_fifo_across_bills_with_partial_last(self):
        self.sale(1000, D - timedelta(days=40)); self.sale(2000, D - timedelta(days=10)); self.sale(3000, D)
        res = b.record_payment(self.con, "Receipt", "Ram Traders", D, 2500, "Cash")
        self.assertEqual(res["settled_bills"], [(1, 1000), (2, 1500)])
        ob = b.open_invoices(self.con, "Ram Traders", "Sales")
        self.assertEqual([(o["vno"], o["balance"]) for o in ob], [(2, 50000), (3, 300000)])
        self.tb()

    def test_overpayment_goes_on_account(self):
        self.sale(1000)
        res = b.record_payment(self.con, "Receipt", "Ram Traders", D, 1500, "Cash")
        self.assertEqual((res["allocated"], res["on_account"]), (1000, 500))
        rep = r.outstanding_report(self.con, "Sales", D)
        p = rep["parties"][0]
        self.assertEqual((p["balance"], p["on_account"], p["bills"]), (-500, -500, []))

    def test_manual_allocation_and_validation(self):
        self.sale(1000); self.sale(2000)
        v2 = self.vid("Sales", 2)
        res = b.record_payment(self.con, "Receipt", "Ram Traders", D, 700, "Cash", allocations=[(v2, 700)])
        self.assertEqual(res["settled_bills"], [(2, 700)])
        for bad in ([(v2, 5000)], [(9999, 10)], [(v2, 0)]):
            with self.assertRaises(ValueError):
                b.record_payment(self.con, "Receipt", "Ram Traders", D, 100, "Cash", allocations=bad)
        with self.assertRaises(ValueError):
            b.record_payment(self.con, "Receipt", "Ram Traders", D, 100, "Cash", allocations=[(self.vid("Sales", 1), 80), (v2, 80)])

    def test_input_validation(self):
        self.sale(1000)
        for args in ((0, "Cash"), (-5, "Cash"), (10, "Cheque")):
            with self.assertRaises(ValueError):
                b.record_payment(self.con, "Receipt", "Ram Traders", D, *args)
        with self.assertRaises(ValueError):
            b.record_payment(self.con, "Receipt", "Shyam Supplies", D, 10, "Cash")   # supplier, wrong kind
        with self.assertRaises(ValueError):
            b.record_payment(self.con, "Payment", "Ram Traders", D, 10, "Cash")
        with self.assertRaises(ValueError):
            self.sale(1000, received=1500)                                           # more than the bill
        with self.assertRaises(ValueError):
            b.post_sale(self.con, D, "Cash", [("x", 1, 100, 0)], received=50)         # cash bill
        self.assertEqual(len(r.invoice_register(self.con, "2026-27", "Sales")), 1)  # failed ones left nothing

    def test_purchase_paid_now_and_payment(self):
        res = b.post_purchase(self.con, D, "Shyam Supplies", [("Wheat", 100, 50, 0)], received=2000, mode="Bank")
        self.assertEqual((res["total"], res["received"], res["balance"]), (5000, 2000, 3000))
        t = self.tb()
        self.assertEqual(t["Shyam Supplies"], (0, 3000))
        self.assertEqual(t["Bank"], (0, 2000))
        pay = b.record_payment(self.con, "Payment", "Shyam Supplies", D, 3000, "Cash")
        self.assertEqual(pay["settled_bills"], [(1, 3000)])
        self.assertEqual(r.invoice_register(self.con, "2026-27", "Purchase")[0]["status"], "Paid")

class Integrity(Base):
    def test_delete_receipt_reopens_bill(self):
        self.sale(1000, received=400)
        rid = self.vid("Receipt", 1)
        s.delete_voucher(self.con, rid, "sumit")
        self.assertEqual(r.invoice_register(self.con, "2026-27", "Sales")[0]["status"], "Unpaid")
        self.assertEqual(self.tb()["Ram Traders"], (1000, 0))

    def test_delete_invoice_leaves_receipt_on_account(self):
        self.sale(1000, received=400)
        s.delete_voucher(self.con, self.vid("Sales", 1))
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM allocations").fetchone()[0], 0)
        self.assertEqual(self.tb()["Ram Traders"], (0, 400))     # 400 received, no bill: advance

    def test_edit_guards(self):
        self.sale(1000, received=400)
        with self.assertRaises(ValueError):
            s.update_voucher(self.con, self.vid("Receipt", 1), "Receipt", D, "",
                             [("Cash", 1, 0), ("Ram Traders", 0, 1)])
        sv = self.vid("Sales", 1)
        with self.assertRaises(ValueError):       # total below what is already settled
            b.update_invoice(self.con, sv, D, "Ram Traders", [("Goods", 1, 300, 0)])
        with self.assertRaises(ValueError):       # party change
            s.add_party(self.con, "Other", "Customer")
            b.update_invoice(self.con, sv, D, "Other", [("Goods", 1, 1000, 0)])
        b.update_invoice(self.con, sv, D, "Ram Traders", [("Goods", 1, 2000, 0)])   # raising it is fine
        self.assertEqual(r.invoice_register(self.con, "2026-27", "Sales")[0]["balance"], 1600)
        snap = s.voucher_snapshot(self.con, sv)
        self.assertEqual([p["amount"] for p in snap["payments_in"]], [40000])

class OutstandingReport(Base):
    def test_ageing_buckets_and_totals(self):
        self.sale(1000, D - timedelta(days=5)); self.sale(2000, D - timedelta(days=45))
        self.sale(3000, D - timedelta(days=75)); self.sale(4000, D - timedelta(days=200))
        rep = r.outstanding_report(self.con, "Sales", D)
        self.assertEqual(rep["buckets"], {"0-30": 1000, "31-60": 2000, "61-90": 3000, "90+": 4000})
        self.assertEqual(rep["total"], 10000)
        p = rep["parties"][0]
        self.assertEqual([x["days"] for x in p["bills"]], [200, 75, 45, 5])
        self.assertEqual(p["on_account"], 0)

    def test_opening_balance_shows_on_account_and_payables(self):
        s.add_party(self.con, "Old Customer", "Customer", opening=7000)
        b.post_purchase(self.con, D, "Shyam Supplies", [("W", 10, 100, 0)])
        rep = r.outstanding_report(self.con, "Sales", D)
        old = [p for p in rep["parties"] if p["party"] == "Old Customer"][0]
        self.assertEqual((old["balance"], old["on_account"], old["bills"]), (7000, 7000, []))
        pay = r.outstanding_report(self.con, "Purchase", D)
        self.assertEqual((pay["total"], pay["parties"][0]["bills"][0]["balance"]), (1000, 1000))
        self.assertEqual(r.receivable_payable(self.con, D), (7000, 1000))

class DailySummary(Base):
    def test_exclusive_and_inclusive_summary(self):
        items = b.summary_items([("18", 1000), ("5", 2000), ("0", 0)], inclusive=False)
        self.assertEqual([(i[0], float(i[2])) for i in items], [("Sales summary @18%", 1000.0), ("Sales summary @5%", 2000.0)])
        res = b.post_sale(self.con, D, "Cash", items, False, "Daily sales summary")
        self.assertEqual((res["taxable"], res["cgst"], res["sgst"], res["total"]), (3000, 140, 140, 3280))
        t = self.tb()
        self.assertEqual(t["Cash"], (3280, 0))
        self.assertEqual(t["Sales"], (0, 3000))
        reg = r.invoice_register(self.con, "2026-27", "Sales")[0]
        self.assertEqual((reg["party"], reg["status"], reg["balance"]), ("Cash", "Paid", 0))

    def test_inclusive_backs_out_gst(self):
        items = b.summary_items([("18", 1180), ("5", 1050)], inclusive=True)
        self.assertEqual([float(i[2]) for i in items], [1000.0, 1000.0])
        res = b.post_sale(self.con, D, "Bank", items, False, "")
        self.assertEqual(res["total"], 2230)           # 1180 + 1050, exactly as typed
        self.tb()

    def test_summary_validation(self):
        for bad in ([], [("18", 0)], [("18", -5)]):
            with self.assertRaises(ValueError):
                b.summary_items(bad)

    def test_summary_is_editable_like_an_invoice(self):
        b.post_sale(self.con, D, "Cash", b.summary_items([("18", 1000)]), False, "")
        vid = self.vid("Sales", 1)
        b.update_invoice(self.con, vid, D, "Cash", b.summary_items([("18", 2000)]), False, "edited")
        self.assertEqual(r.invoice_register(self.con, "2026-27", "Sales")[0]["total"], 2360)
        self.tb()

if __name__ == "__main__":
    unittest.main()
