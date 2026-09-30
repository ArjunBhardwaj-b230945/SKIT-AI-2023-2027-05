"""
TaxSathi - Document Parsing Tests
Week: 25-09-2026 to 01-10-2026

Tests cleaning, field detection and structured output.
Run:
    python -m unittest test_document_parsing.py
"""

import unittest

from clean_parsed_text import clean_text
from form16_field_detector import detect_form16_fields
from form26as_field_detector import detect_form26as_fields
from structured_tax_data import build_form16, build_form26as


FORM16_SAMPLE = """
PAN of employee: ABCDE1234F
TAN of employer: DELA12345B
Assessment Year: 2026-27
Salary as per section 17(1): 750000
Perquisites under section 17(2): 20000
Profits in lieu of salary under section 17(3): 0
Travel concession under section 10(5): 15000
House Rent Allowance under section 10(13A): 50000
Standard deduction under section 16(ia): 50000
Tax deducted: 45000
"""

FORM26AS_SAMPLE = """
PAN: ABCDE1234F
Assessment Year: 2026-27
ABCD12345E Employer Pvt Ltd 450000 45000
15/07/2026 123456 20000
"""


class DocumentParsingTests(unittest.TestCase):

    def test_clean_text(self):
        result = clean_text("Salary    17(1):  750000\r\n\r\n\r\nPAN: ABCDE1234F")
        self.assertIn("Salary 17(1): 750000", result)
        self.assertNotIn("\r", result)

    def test_form16_detection(self):
        result = detect_form16_fields(FORM16_SAMPLE)
        self.assertEqual(result["employee_pan"], "ABCDE1234F")
        self.assertEqual(result["employer_tan"], "DELA12345B")
        self.assertEqual(result["assessment_year"], "2026-27")
        self.assertEqual(result["salary_17_1"], 750000.0)

    def test_form16_structuring(self):
        detected = detect_form16_fields(FORM16_SAMPLE)
        structured = build_form16(detected)
        self.assertEqual(structured.employee_pan, "ABCDE1234F")
        self.assertEqual(structured.salary_17_1, 750000.0)

    def test_form26as_detection(self):
        result = detect_form26as_fields(FORM26AS_SAMPLE)
        self.assertEqual(result["pan"], "ABCDE1234F")
        self.assertEqual(result["assessment_year"], "2026-27")
        self.assertGreaterEqual(len(result["tds_rows"]), 1)

    def test_form26as_structuring(self):
        detected = detect_form26as_fields(FORM26AS_SAMPLE)
        structured = build_form26as(detected)
        self.assertEqual(structured.pan, "ABCDE1234F")
        self.assertIsInstance(structured.tds_rows, list)


if __name__ == "__main__":
    unittest.main()
