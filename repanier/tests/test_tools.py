"""Unit tests for the pure helpers used by the business core."""
from decimal import Decimal

from django.test import TestCase

from repanier.tools import cap, round_gov_be, round_tva, sboolean, sint


class SindAndSbooleanTest(TestCase):
    def test_sint(self):
        self.assertEqual(sint("3"), 3)
        self.assertEqual(sint("-5"), -5)
        self.assertEqual(sint("0"), 0)
        self.assertEqual(sint("not a number"), 0)
        self.assertEqual(sint("not a number", default_val=7), 7)
        self.assertEqual(sint(None), 0)

    def test_sboolean(self):
        self.assertIs(sboolean(""), False)
        self.assertIs(sboolean("x"), True)
        self.assertIs(sboolean(None), False)


class CapTest(TestCase):
    def test_short_string_untouched(self):
        self.assertEqual(cap("abcdef", 10), "abcdef")
        self.assertEqual(cap("abcdefghij", 10), "abcdefghij")

    def test_long_string_cut_with_ellipsis(self):
        self.assertEqual(cap("abcdefghijklmnop", 10), "abcdef...")

    def test_non_string_coerced(self):
        self.assertEqual(cap(1234567, 5), "1...")

    def test_none_returns_none(self):
        self.assertIsNone(cap(None, 10))


class RoundGovBeTest(TestCase):
    """round_gov_be implements the Belgian cash rounding regulation.

    Total ends with 1, 2 -> down to 0.00
    Total ends with 3, 4, 6, 7 -> rounded to 0.05
    Total ends with 8, 9 -> rounded up to 0.10
    """

    def test_belgian_cash_rounding_table(self):
        cases = [
            ("10.00", "10.00"),
            ("10.01", "10.00"),
            ("10.02", "10.00"),
            ("10.03", "10.05"),
            ("10.04", "10.05"),
            ("10.05", "10.05"),
            ("10.06", "10.05"),
            ("10.07", "10.05"),
            ("10.08", "10.10"),
            ("10.09", "10.10"),
            ("10.10", "10.10"),
            ("0.03", "0.05"),
            ("0.02", "0.00"),
            ("99.99", "100.00"),
        ]
        for source, expected in cases:
            with self.subTest(amount=source):
                self.assertEqual(
                    round_gov_be(Decimal(source)),
                    Decimal(expected),
                )


class RoundTvaTest(TestCase):
    def test_quantize_three_decimals(self):
        self.assertEqual(round_tva(Decimal("0.1234")), Decimal("0.123"))
        self.assertEqual(round_tva(Decimal("0.1235")), Decimal("0.124"))
        self.assertEqual(round_tva(Decimal("2")), Decimal("2.000"))
