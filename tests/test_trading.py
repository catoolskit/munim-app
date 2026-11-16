import os, sys, tempfile, unittest
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import setup as s, billing as b, reports as r

D1, D2 = date(2026, 11, 14), date(2027, 5, 1)

class Base(unittest.TestCase):
    def setUp(self):
        self.con = s.init_db(os.path.join(tempfile.mkdtemp(), "t.db"))
        s.add_party(self.con, "Ram Traders", "Customer")
        s.add_party(self.con, "Shyam Supplies", "Supplier")

class LedgerMaster(Base):
    def test_add_validate_and_opening(self):
        s.add_ledger_account(self.con, "Electricity", "Indirect Expenses")
        s.add_ledger_account(self.con, "Freight Inward", "Direct Expenses", 500, "Dr")
        row = [a for a in s.list_accounts(self.con) if a["name"] == "Freight Inward"][0]
        self.assertEqual((row["nature"], row["grp"], row["opening"]), ("Expense", "Direct Expenses", 50000))
        for args in (("", "Fixed Assets"), ("X", "Nonsense"), ("electricity", "Indirect Expenses"),
                     ("Y", "Fixed Assets", "abc"), ("Y", "Fixed Assets", -5), ("Y", "Fixed Assets", 0, "Xx")):
            with self.assertRaises(ValueError, msg=str(args)):
                s.add_ledger_account(self.con, *args)
        s.set_account_opening(self.con, "Electricity", 250, "Dr")
        with self.assertRaises(ValueError):
            s.set_account_opening(self.con, "Nope", 1, "Dr")

    def test_delete_guards(self):
        s.add_ledger_account(self.con, "Telephone", "Indirect Expenses")
        s.add_ledger_account(self.con, "Used", "Indirect Expenses")
        s.post_voucher(self.con, "Payment", D1, "", [("Used", 10, 0), ("Cash", 0, 10)])
        s.delete_ledger_account(self.con, "Telephone")
        for name in ("Used", "Cash", "Ram Traders", "Nope"):
            with self.assertRaises(ValueError, msg=name):
                s.delete_ledger_account(self.con, name)

class PartyChecks(Base):
    def test_bill_must_go_to_a_real_party_or_cash(self):
        item = [("x", 1, 100, 0)]
        for bad in ("Rent", "Capital", "Nobody"):
            with self.assertRaises(ValueError, msg=bad):
                b.post_sale(self.con, D1, bad, item)
        with self.assertRaises(ValueError) as cm:
            b.post_sale(self.con, D1, "Nobody", item)
        self.assertIn("Party Master", str(cm.exception)); self.assertIn("Cash", str(cm.exception))
        with self.assertRaises(ValueError):
            b.post_sale(self.con, D1, "Shyam Supplies", item)          # a supplier is not a customer
        with self.assertRaises(ValueError):
            b.post_purchase(self.con, D1, "Ram Traders", item)
        b.post_sale(self.con, D1, "Cash", item); b.post_sale(self.con, D1, "Bank", item)
        b.post_purchase(self.con, D1, "Cash", item)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM vouchers").fetchone()[0], 3)

class CashBillName(Base):
    def test_name_stored_for_cash_ignored_for_party(self):
        b.post_sale(self.con, D1, "Cash", [("Gold", 1, 1000, 0)], bill_name="  Ramesh Kumar ")
        b.post_sale(self.con, D1, "Ram Traders", [("Gold", 1, 1000, 0)], bill_name="Ignored")
        reg = r.invoice_register(self.con, "2026-27", "Sales")
        self.assertEqual([x["party"] for x in reg], ["Cash (Ramesh Kumar)", "Ram Traders"])
        v = self.con.execute("SELECT id FROM vouchers WHERE vno=1 AND vtype='Sales'").fetchone()["id"]
        self.assertEqual(s.voucher_snapshot(self.con, v)["invoice"]["customer_name"], "Ramesh Kumar")
        b.update_invoice(self.con, v, D1, "Cash", [("Gold", 1, 1000, 0)], bill_name="Suresh")
        self.assertEqual(s.voucher_snapshot(self.con, v)["invoice"]["customer_name"], "Suresh")
        with self.assertRaises(ValueError):
            b.post_sale(self.con, D1, "Cash", [("x", 1, 1, 0)], bill_name="n" * 81)

class TradingAccount(Base):
    def books(self):
        s.set_account_opening(self.con, "Cash", 100000, "Dr")
        s.set_account_opening(self.con, "Capital", 110000, "Cr")      # includes 10,000 opening stock
        s.add_ledger_account(self.con, "Freight Inward", "Direct Expenses")
        s.add_ledger_account(self.con, "Interest Received", "Indirect Income")
        s.post_voucher(self.con, "Journal", D1, "", [("Cash", 100000, 0), ("Sales", 0, 100000)])
        s.post_voucher(self.con, "Journal", D1, "", [("Purchase", 60000, 0), ("Cash", 0, 60000)])
        s.post_voucher(self.con, "Payment", D1, "", [("Freight Inward", 5000, 0), ("Cash", 0, 5000)])
        s.post_voucher(self.con, "Payment", D1, "", [("Rent", 8000, 0), ("Cash", 0, 8000)])
        s.post_voucher(self.con, "Receipt", D1, "", [("Cash", 1000, 0), ("Interest Received", 0, 1000)])
        s.set_stock(self.con, "2026-27", opening=10000, closing=20000)

    def test_gross_and_net_profit_worked_by_hand(self):
        self.books()
        ta = r.trading_and_pl(self.con, "2026-27")
        t, p = ta["trading"], ta["pl"]
        self.assertEqual(dict(t["left"]), {"Opening Stock": 10000, "Purchase": 60000, "Freight Inward": 5000, "Gross Profit c/d": 45000})
        self.assertEqual(dict(t["right"]), {"Sales": 100000, "Closing Stock": 20000})
        self.assertEqual((t["left_total"], t["right_total"], t["gross_profit"]), (120000, 120000, 45000))
        self.assertEqual(dict(p["left"]), {"Rent": 8000, "Net Profit": 38000})
        self.assertEqual(dict(p["right"]), {"Gross Profit b/d": 45000, "Interest Received": 1000})
        self.assertEqual((p["left_total"], p["right_total"], p["net_profit"]), (46000, 46000, 38000))
        self.assertEqual(r.profit_and_loss(self.con, "2026-27")["net_profit"], 38000)   # same answer both ways

    def test_balance_sheet_balances_with_stock(self):
        self.books()
        bs = r.balance_sheet(self.con, "2026-27")
        self.assertEqual(bs["total_assets"], bs["total_liabilities"])
        self.assertEqual(dict(bs["assets"])["Closing Stock"], 20000)
        self.assertEqual(dict(bs["assets"])["Cash"], 128000)
        self.assertEqual(dict(bs["liabilities"])["Profit & Loss A/c"], 38000)
        self.assertEqual(bs["total_assets"], 148000)

    def test_gross_loss_and_net_loss(self):
        s.post_voucher(self.con, "Journal", D1, "", [("Cash", 1000, 0), ("Sales", 0, 1000)])
        s.post_voucher(self.con, "Journal", D1, "", [("Purchase", 3000, 0), ("Cash", 0, 3000)])
        s.post_voucher(self.con, "Payment", D1, "", [("Rent", 500, 0), ("Cash", 0, 500)])
        ta = r.trading_and_pl(self.con, "2026-27")
        self.assertEqual(ta["trading"]["gross_profit"], -2000)
        self.assertIn(("Gross Loss c/d", 2000), ta["trading"]["right"])
        self.assertIn(("Gross Loss b/d", 2000), ta["pl"]["left"])
        self.assertIn(("Net Loss", 2500), ta["pl"]["right"])
        for side in ("trading", "pl"):
            self.assertEqual(ta[side]["left_total"], ta[side]["right_total"])

    def test_next_year_opening_follows_last_closing_and_everything_balances(self):
        self.books()
        s.post_voucher(self.con, "Journal", D2, "", [("Cash", 50000, 0), ("Sales", 0, 50000)])
        s.post_voucher(self.con, "Journal", D2, "", [("Purchase", 30000, 0), ("Cash", 0, 30000)])
        s.set_stock(self.con, "2027-28", closing=25000)                   # opening left blank = auto
        self.assertEqual(s.get_stock(self.con, "2027-28"), (2000000, 2500000))
        ta = r.trading_and_pl(self.con, "2027-28")
        self.assertEqual(ta["opening_stock"], 20000)
        self.assertEqual(ta["trading"]["gross_profit"], 25000)           # 50,000 + 25,000 - 20,000 - 30,000
        bs = r.balance_sheet(self.con, "2027-28")
        self.assertEqual(bs["total_assets"], bs["total_liabilities"])
        self.assertEqual(bs["total_assets"], 173000)
        self.assertEqual(dict(bs["liabilities"])["Profit & Loss A/c"], 63000)   # 28,000 ledger + 10,000 stock + 25,000
        rows, dr, cr = s.trial_balance(self.con, "2027-28")
        self.assertEqual(dr, cr)

    def test_stock_value_rules(self):
        s.set_stock(self.con, "2026-27", closing=500)
        self.assertEqual(s.get_stock(self.con, "2026-27"), (0, 50000))
        s.set_stock(self.con, "2027-28", opening=1)                         # explicit opening wins
        self.assertEqual(s.get_stock(self.con, "2027-28")[0], 100)
        s.set_stock(self.con, "2027-28", opening="")                        # blank = follow last closing again
        self.assertEqual(s.get_stock(self.con, "2027-28")[0], 50000)
        for bad in ("abc", -5):
            with self.assertRaises(ValueError):
                s.set_stock(self.con, "2026-27", closing=bad)
        self.assertEqual(r.profit_and_loss(self.con, "2026-27", closing_stock=900)["closing_stock"], 900)

if __name__ == "__main__":
    unittest.main()
