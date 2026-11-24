import os, sys, tempfile, unittest
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import setup as s, reports as r

class Base(unittest.TestCase):
    def setUp(self):
        self.con = s.init_db(os.path.join(tempfile.mkdtemp(), "t.db"))
    def post(self, vtype, d, lines):
        return s.post_voucher(self.con, vtype, d, "", lines)

class ReportTests(Base):
    def books(self):
        d = date(2026, 11, 14)
        self.post("Journal", d, [("Cash", 50000, 0), ("Capital", 0, 50000)])
        self.post("Sales", d, [("Cash", 10000, 0), ("Sales", 0, 10000)])
        self.post("Purchase", d, [("Purchase", 6000, 0), ("Cash", 0, 6000)])
        self.post("Payment", d, [("Rent", 1000, 0), ("Cash", 0, 1000)])

    def test_pl_and_balance_sheet_balance(self):
        self.books()
        pl = r.profit_and_loss(self.con, "2026-27")
        self.assertEqual(pl["net_profit"], 3000)
        bs = r.balance_sheet(self.con, "2026-27")
        self.assertEqual(bs["total_assets"], bs["total_liabilities"])
        self.assertEqual(dict(bs["assets"])["Cash"], 53000)
        self.assertEqual(dict(bs["liabilities"])["Profit & Loss A/c"], 3000)

    def test_closing_stock_raises_profit_and_assets(self):
        self.books()
        pl = r.profit_and_loss(self.con, "2026-27", closing_stock=2000)
        self.assertEqual(pl["net_profit"], 5000)
        bs = r.balance_sheet(self.con, "2026-27", closing_stock=2000)
        self.assertEqual(bs["total_assets"], bs["total_liabilities"])
        self.assertEqual(bs["total_assets"], 55000)

    def test_loss_shows_on_asset_side(self):
        self.post("Journal", date(2026, 11, 14), [("Cash", 1000, 0), ("Capital", 0, 1000)])
        self.post("Payment", date(2026, 11, 14), [("Rent", 300, 0), ("Cash", 0, 300)])
        bs = r.balance_sheet(self.con, "2026-27")
        self.assertEqual(dict(bs["assets"])["Profit & Loss A/c (loss)"], 300)
        self.assertEqual(bs["total_assets"], bs["total_liabilities"])

    def test_year_rollover_carries_forward(self):
        self.books()
        self.post("Sales", date(2027, 5, 1), [("Cash", 500, 0), ("Sales", 0, 500)])
        rows, dr, cr = s.trial_balance(self.con, "2027-28")
        self.assertEqual(dr, cr)
        names = {n: (d, c) for n, d, c in rows}
        self.assertEqual(names["Cash"], (53500, 0))            # 53,000 carried + 500
        self.assertEqual(names["Profit & Loss A/c (b/f)"], (0, 3000))
        self.assertEqual(names["Sales"], (0, 500))             # P&L accounts restart at zero
        self.assertNotIn("Rent", names)
        bs = r.balance_sheet(self.con, "2027-28")
        self.assertEqual(bs["total_assets"], bs["total_liabilities"])
        self.assertEqual(dict(bs["liabilities"])["Profit & Loss A/c"], 3500)

    def test_ledger_running_balance_and_carry(self):
        self.books()
        self.post("Sales", date(2027, 5, 1), [("Cash", 500, 0), ("Sales", 0, 500)])
        led = r.ledger_view(self.con, "Cash", "2026-27")
        self.assertEqual((led["opening"], led["closing"], led["closing_side"]), (0, 53000, "Dr"))
        self.assertEqual([x["balance"] for x in led["rows"]], [50000, 60000, 54000, 53000])
        nxt = r.ledger_view(self.con, "Cash", "2027-28")
        self.assertEqual((nxt["opening"], nxt["opening_side"], nxt["closing"]), (53000, "Dr", 53500))
        with self.assertRaises(ValueError):
            r.ledger_view(self.con, "Nope", "2026-27")

    def test_day_book_range(self):
        self.books()
        self.post("Sales", date(2027, 5, 1), [("Cash", 1, 0), ("Sales", 0, 1)])
        db = r.day_book(self.con, date(2026, 11, 1), date(2026, 11, 30))
        self.assertEqual(len(db), 4)
        self.assertEqual(db[0]["vtype"], "Journal")
        self.assertEqual(len(r.day_book(self.con, date(2027, 5, 1), date(2027, 5, 1))), 1)

    def test_opening_difference_still_balances(self):
        s.add_party(self.con, "Ram", "Customer", opening=5000)
        bs = r.balance_sheet(self.con, "2026-27")
        self.assertEqual(bs["total_assets"], bs["total_liabilities"])

if __name__ == "__main__":
    unittest.main()
