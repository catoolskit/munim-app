import os, sys, unittest
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.licence import generate_key, validate_key, days_remaining, licence_status

class LicenceTests(unittest.TestCase):
    def test_roundtrip(self):
        expiry = date.today() + timedelta(days=365)
        key = generate_key("ramtraders", expiry)
        self.assertTrue(key.startswith("MNM-"))
        user, exp = validate_key(key)
        self.assertEqual(user, "ramtraders")
        self.assertEqual(exp, expiry)

    def test_case_insensitive(self):
        expiry = date.today() + timedelta(days=30)
        key = generate_key("TestUser", expiry)
        user, _ = validate_key(key.lower())
        self.assertEqual(user, "TestUser")

    def test_expired_raises(self):
        key = generate_key("x", date.today() - timedelta(days=1))
        with self.assertRaises(ValueError, msg="expired"):
            validate_key(key)

    def test_tampered_raises(self):
        key = generate_key("sumit", date.today() + timedelta(days=100))
        bad = key[:-1] + ("X" if key[-1] != "X" else "Y")
        with self.assertRaises(ValueError):
            validate_key(bad)

    def test_garbage_raises(self):
        for bad in ("", "MNM-", "NOTAKEY", "MNM-ABC-XYZ-123"):
            with self.assertRaises(ValueError, msg=bad):
                validate_key(bad)

    def test_days_remaining(self):
        key = generate_key("x", date.today() + timedelta(days=10))
        self.assertEqual(days_remaining(key), 10)
        expired = generate_key("x", date.today() - timedelta(days=5))
        self.assertEqual(days_remaining(expired), 0)

    def test_status_messages(self):
        valid = generate_key("x", date.today() + timedelta(days=100))
        self.assertIn("Valid until", licence_status(valid))
        expiring = generate_key("x", date.today() + timedelta(days=3))
        self.assertIn("Expiring", licence_status(expiring))
        self.assertIn("Not activated", licence_status(""))

class ResetDataTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from db.setup import init_db, add_party
        from db import billing as b
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")
        self.con = init_db(self.path)
        add_party(self.con, "Ram", "Customer")
        b.post_sale(self.con, date(2026, 11, 14), "Ram", [("Goods", 1, 1000, 18)])

    def test_reset_wipes_data_keeps_users(self):
        from db.setup import reset_all_data, list_users, change_password
        change_password(self.con, "admin", "NewPass#1")
        reset_all_data(self.con, "NewPass#1")
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM vouchers").fetchone()[0], 0)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM parties").fetchone()[0], 0)
        self.assertEqual(len(list_users(self.con)), 1)  # admin still there

    def test_reset_wrong_password_rejected(self):
        from db.setup import reset_all_data
        with self.assertRaises(ValueError):
            reset_all_data(self.con, "wrongpassword")
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM vouchers").fetchone()[0], 1)

class UserMgmtTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from db.setup import init_db
        self.con = init_db(os.path.join(tempfile.mkdtemp(), "t.db"))

    def test_add_list_delete(self):
        from db.setup import add_user, list_users, delete_user, login
        add_user(self.con, "staff1", "StaffPass1", "staff", must_change=1)
        users = [u["username"] for u in list_users(self.con)]
        self.assertIn("staff1", users)
        self.assertIn("admin", users)
        delete_user(self.con, "staff1")
        self.assertNotIn("staff1", [u["username"] for u in list_users(self.con)])

    def test_delete_nonexistent_raises(self):
        from db.setup import delete_user
        with self.assertRaises(ValueError):
            delete_user(self.con, "ghost")

    def test_duplicate_username_raises(self):
        from db.setup import add_user
        add_user(self.con, "staff1", "StaffPass1")
        with self.assertRaises(Exception):
            add_user(self.con, "staff1", "AnotherPass1")

if __name__ == "__main__":
    unittest.main()