import os, sys, tempfile, unittest
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import setup as s

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")
        self.con = s.init_db(self.path)

    def test_fy(self):
        self.assertEqual(s.fy_of(date(2027, 3, 31)), "2026-27")
        self.assertEqual(s.fy_of(date(2027, 4, 1)), "2027-28")

    def test_unbalanced_rejected(self):
        with self.assertRaises(ValueError):
            s.post_voucher(self.con, "Journal", date(2026, 11, 14), "x",
                           [("Cash", 100, 0), ("Sales", 0, 99.99)])

    def test_tb_balances(self):
        d = date(2026, 11, 14)
        s.post_voucher(self.con, "Journal", d, "capital", [("Cash", 50000, 0), ("Capital", 0, 50000)])
        s.post_voucher(self.con, "Sales", d, "cash sale", [("Cash", 11800.50, 0), ("Sales", 0, 11800.50)])
        s.post_voucher(self.con, "Purchase", d, "buy", [("Purchase", 7000.10, 0), ("Cash", 0, 7000.10)])
        rows, dr, cr = s.trial_balance(self.con, "2026-27")
        self.assertEqual(dr, cr)
        self.assertEqual(dr, 61800.50)

    def test_voucher_numbering(self):
        d = date(2026, 11, 14)
        a = s.post_voucher(self.con, "Sales", d, "", [("Cash", 1, 0), ("Sales", 0, 1)])
        b = s.post_voucher(self.con, "Sales", d, "", [("Cash", 1, 0), ("Sales", 0, 1)])
        self.assertEqual((a, b), (1, 2))

    def test_login(self):
        self.assertEqual(s.check_login(self.con, "admin", "admin123"), "admin")
        self.assertIsNone(s.check_login(self.con, "admin", "bad"))

class Step2aTests(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")
        self.con = s.init_db(self.path)

    def test_default_admin_must_change(self):
        self.assertEqual(s.login(self.con, "admin", "admin123")["must_change"], 1)

    def test_change_password(self):
        with self.assertRaises(ValueError):
            s.change_password(self.con, "admin", "short")
        with self.assertRaises(ValueError):
            s.change_password(self.con, "admin", "admin123")
        s.change_password(self.con, "admin", "Strong#Pass1")
        self.assertIsNone(s.login(self.con, "admin", "admin123"))
        self.assertEqual(s.login(self.con, "admin", "Strong#Pass1")["must_change"], 0)
        s.init_db(self.path)  # reopening must not force a change again
        self.assertEqual(s.login(self.con, "admin", "Strong#Pass1")["must_change"], 0)

    def test_migration_from_step1_db(self):
        import sqlite3
        path = os.path.join(tempfile.mkdtemp(), "old.db")
        c = sqlite3.connect(path)
        c.executescript("""CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            salt TEXT NOT NULL, pw_hash TEXT NOT NULL, role TEXT NOT NULL);""")
        c.commit(); c.close()
        con = s.init_db(path)
        self.assertEqual(s.login(con, "admin", "admin123")["must_change"], 1)

    def test_party_creates_ledger_account(self):
        s.add_party(self.con, "Ram Traders", "Customer", "03ABCDE1234F1Z5", opening=5000)
        s.add_party(self.con, "Shyam Supplies", "Supplier", opening=2500)
        rows, dr, cr = s.trial_balance(self.con, "2026-27")
        self.assertEqual(dr, cr)  # one-sided openings are balanced by a difference row
        self.assertIn("Difference in opening balances", [r[0] for r in rows])
        names = {r[0]: (r[1], r[2]) for r in rows}
        self.assertEqual(names["Ram Traders"], (5000, 0))
        self.assertEqual(names["Shyam Supplies"], (0, 2500))
        self.assertEqual(len(s.list_parties(self.con, "Customer")), 1)

    def test_party_validation(self):
        with self.assertRaises(ValueError):
            s.add_party(self.con, "", "Customer")
        with self.assertRaises(ValueError):
            s.add_party(self.con, "X", "Customer", gstin="BADGSTIN")
        with self.assertRaises(ValueError):
            s.add_party(self.con, "Cash", "Customer")  # clashes with ledger account
        with self.assertRaises(ValueError):
            s.add_party(self.con, "Y", "Customer", opening="abc")
        s.add_party(self.con, "Z", "Customer")
        with self.assertRaises(ValueError):
            s.add_party(self.con, "Z", "Supplier")

class BackupTests(unittest.TestCase):
    def test_backup_copies_data(self):
        import sqlite3
        con = s.init_db(os.path.join(tempfile.mkdtemp(), "t.db"))
        s.add_party(con, "Ram Traders", "Customer", opening=100)
        out = s.backup_db(con, tempfile.mkdtemp())
        copy = sqlite3.connect(out)
        self.assertEqual(copy.execute("SELECT COUNT(*) FROM parties").fetchone()[0], 1)
        copy.close()

if __name__ == "__main__":
    unittest.main()
