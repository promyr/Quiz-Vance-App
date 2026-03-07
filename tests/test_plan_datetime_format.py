# -*- coding: utf-8 -*-
"""Testes de formatacao de validade para planos."""

import unittest

from main_v2 import _format_datetime_label


class PlanDateTimeFormatTest(unittest.TestCase):
    def test_iso_datetime_with_microseconds(self):
        formatted = _format_datetime_label("2026-02-24T00:11:05.764386")
        self.assertEqual(formatted, "24/02/2026 00:11")

    def test_iso_datetime_zulu(self):
        formatted = _format_datetime_label("2026-02-24T03:15:59Z")
        self.assertEqual(formatted, "24/02/2026 03:15")

    def test_sql_datetime(self):
        formatted = _format_datetime_label("2026-02-24 18:35:10")
        self.assertEqual(formatted, "24/02/2026 18:35")

    def test_empty_value(self):
        self.assertEqual(_format_datetime_label(""), "")
        self.assertEqual(_format_datetime_label(None), "")


if __name__ == "__main__":
    unittest.main()
