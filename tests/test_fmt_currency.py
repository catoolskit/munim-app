import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.fmt import inr


class INRFormattingTests(unittest.TestCase):
    def test_indian_grouping(self):
        self.assertEqual(inr(1234567.5), "12,34,567.50")

    def test_half_up_paise_rounding(self):
        self.assertEqual(inr(1.005), "1.01")
        self.assertEqual(inr(2.675), "2.68")

    def test_negative_amount_keeps_sign_and_grouping(self):
        self.assertEqual(inr(-12345.675), "-12,345.68")

    def test_integer_and_zero_format(self):
        self.assertEqual(inr(0), "0.00")
        self.assertEqual(inr(125), "125.00")


if __name__ == "__main__":
    unittest.main()
