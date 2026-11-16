import os, sys, tempfile, unittest, csv
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import setup as s, billing as b, reports as r
from utils import export

D = date(2026, 11, 14)

class Base(unittest.TestCase):
    def setUp(self):
        self.con = s.init_db(os.path.join(tempfile.mkdtemp(), "t.db"))
        s.add_party(self.con, "Ram Traders", "Customer", credit_days=30)
        s.add_party(self.con, "Quick Pay", "Customer")
        s.add_party(self.con, "Shyam Supplies", "Supplier", credit_days=45)
    def sale(self, amount, ago, party="Ram Traders"):
        return b.post_sale(self.con, D - timedelta(days=ago), party, [("Goods", 1, amount, 0)])

class Ranges(Base):
    def test_parse_and_labels(self):
        self.assertEqual(r.parse_edges("90,120,180"), [90, 120, 180])
        self.assertEqual(r.parse_edges("30 60;90"), [30, 60, 90])
        for bad in ("", "abc", "60,30", "30,30", "0,30", "1,2,3,4,5,6,7", "-5"):
            with self.assertRaises(ValueError, msg=bad):
                r.parse_edges(bad)
        self.assertEqual(r.ageing_labels([90, 120, 180]), ["0-90", "91-120", "121-180", "180+"])
        self.assertEqual(r.ageing_labels([30], due=True), ["Not due", "0-30", "30+"])

    def test_user_ranges_0_90_91_120_121_180_180plus(self):
        for amt, ago in ((1000, 10), (2000, 90), (3000, 91), (4000, 120), (5000, 121), (6000, 180), (7000, 181)):
            self.sale(amt, ago)
        rep = r.outstanding_report(self.con, "Sales", D, edges=[90, 120, 180])
        self.assertEqual(rep["labels"], ["0-90", "91-120", "121-180", "180+"])
        self.assertEqual(rep["buckets"], {"0-90": 3000, "91-120": 7000, "121-180": 11000, "180+": 7000})
        self.assertEqual(rep["total"], 28000)
        p = rep["parties"][0]
        self.assertEqual(p["bucket_amounts"], rep["buckets"])
        self.assertEqual(sum(p["bucket_amounts"].values()), p["balance"])

    def test_default_ranges_unchanged(self):
        self.sale(1000, 5); self.sale(2000, 45)
        rep = r.outstanding_report(self.con, "Sales", D)
        self.assertEqual(rep["buckets"], {"0-30": 1000, "31-60": 2000, "61-90": 0, "90+": 0})

class DueDateBasis(Base):
    def test_credit_days_move_bills_to_not_due(self):
        self.sale(1000, 10)          # due in 20 days  -> not due
        self.sale(2000, 50)          # due 20 days ago -> 0-30 overdue
        self.sale(3000, 100)         # 70 days overdue -> 61-90
        rep = r.outstanding_report(self.con, "Sales", D, basis="due")
        self.assertEqual(rep["labels"], ["Not due", "0-30", "31-60", "61-90", "90+"])
        self.assertEqual(rep["buckets"], {"Not due": 1000, "0-30": 2000, "31-60": 0, "61-90": 3000, "90+": 0})
        bills = rep["parties"][0]["bills"]
        self.assertEqual([x["days"] for x in bills], [70, 20, -20])
        # same bills aged from bill date
        bill_basis = r.outstanding_report(self.con, "Sales", D, basis="bill")
        self.assertEqual(bill_basis["buckets"], {"0-30": 1000, "31-60": 2000, "61-90": 0, "90+": 3000})

    def test_party_without_credit_days_is_due_immediately(self):
        self.sale(500, 0, "Quick Pay")
        rep = r.outstanding_report(self.con, "Sales", D, basis="due")
        self.assertEqual(rep["buckets"]["Not due"], 500)       # due today, 0 days overdue

    def test_payables_use_supplier_credit_days(self):
        b.post_purchase(self.con, D - timedelta(days=60), "Shyam Supplies", [("W", 1, 1000, 0)])
        rep = r.outstanding_report(self.con, "Purchase", D, basis="due", edges=[30, 60])
        self.assertEqual(rep["buckets"]["0-30"], 1000)          # 60 days old, 45 credit -> 15 overdue

    def test_credit_days_validation_and_change(self):
        for bad in ("abc", -1, 400, "1.5"):
            with self.assertRaises(ValueError, msg=str(bad)):
                s.add_party(self.con, "X" + str(bad), "Customer", credit_days=bad)
        s.set_credit_days(self.con, "Quick Pay", 15)
        self.assertEqual([p["credit_days"] for p in s.list_parties(self.con, "Customer") if p["name"] == "Quick Pay"], [15])

class AsOnDate(Base):
    def test_past_as_on_ignores_later_bills_and_payments(self):
        self.sale(1000, 60)                                              # 15-09
        b.record_payment(self.con, "Receipt", "Ram Traders", D - timedelta(days=20), 600, "Cash")   # 25-10
        self.sale(500, 5)                                                # 09-11
        now = r.outstanding_report(self.con, "Sales", D)
        self.assertEqual(now["total"], 900)
        month_end = r.outstanding_report(self.con, "Sales", date(2026, 10, 31))
        self.assertEqual(month_end["total"], 400)                        # 1000 bill - 600 received, no 09-11 bill
        before_pay = r.outstanding_report(self.con, "Sales", date(2026, 10, 1))
        self.assertEqual((before_pay["total"], before_pay["parties"][0]["bills"][0]["settled"]), (1000, 0))

class Export(unittest.TestCase):
    def test_xlsx_roundtrip(self):
        import openpyxl
        path = os.path.join(tempfile.mkdtemp(), "r.xlsx")
        out = export.write_table(path, "Ageing", ["Party", "0-30", "Total"], [["Ram", 1000.0, 1000.0], ["Total", 1000.0, 1000.0]])
        self.assertEqual(out, path)
        ws = openpyxl.load_workbook(path).active
        self.assertEqual([c.value for c in ws[3]], ["Party", "0-30", "Total"])
        self.assertEqual(ws["B4"].value, 1000.0)

    def test_csv_fallback(self):
        import builtins
        real = builtins.__import__
        builtins.__import__ = lambda n, *a, **k: (_ for _ in ()).throw(ImportError()) if n.startswith("openpyxl") else real(n, *a, **k)
        try:
            path = os.path.join(tempfile.mkdtemp(), "r.xlsx")
            out = export.write_table(path, "T", ["A", "B"], [[1, 2]])
        finally:
            builtins.__import__ = real
        self.assertTrue(out.endswith(".csv"))
        self.assertEqual(list(csv.reader(open(out, encoding="utf-8-sig")))[2:], [["A", "B"], ["1", "2"]])

if __name__ == "__main__":
    unittest.main()
