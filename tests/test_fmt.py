import os, sys, tempfile, unittest
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import fmt, errlog
from db import setup as s

class FmtTests(unittest.TestCase):
    def test_inr(self):
        for v, e in ((999, "999.00"), (1000, "1,000.00"), (100000, "1,00,000.00"),
                     (1234567.5, "12,34,567.50"), (-1234.5, "-1,234.50"), (0, "0.00")):
            self.assertEqual(fmt.inr(v), e)
    def test_amount_and_date(self):
        self.assertEqual(fmt.parse_amount("1,234.50"), 1234.5)
        self.assertEqual(fmt.parse_amount(""), 0.0)
        for bad in ("abc", "-5"):
            with self.assertRaises(ValueError): fmt.parse_amount(bad)
        self.assertEqual(fmt.parse_date("14-11-2026"), date(2026, 11, 14))
        self.assertEqual(fmt.parse_date("14/11/2026"), date(2026, 11, 14))
        with self.assertRaises(ValueError): fmt.parse_date("31-02-2026")
        self.assertEqual(fmt.disp_date("2026-11-14"), "14-11-2026")
    def test_fy_choices(self):
        con = s.init_db(os.path.join(tempfile.mkdtemp(), "t.db"))
        s.post_voucher(con, "Journal", date(2020, 6, 1), "", [("Cash", 1, 0), ("Capital", 0, 1)])
        ch = s.fy_choices(con)
        self.assertIn("2020-21", ch)
        self.assertEqual(ch, sorted(ch, reverse=True))
    def test_errlog(self):
        errlog.log_path = lambda: os.path.join(tempfile.mkdtemp(), "e.log")
        p = errlog.log_path()
        errlog.log_path = lambda: p
        try:
            1 / 0
        except ZeroDivisionError:
            text = errlog.log_exception(*sys.exc_info())
        self.assertIn("ZeroDivisionError", text)
        self.assertIn("ZeroDivisionError", open(p).read())

if __name__ == "__main__":
    unittest.main()
