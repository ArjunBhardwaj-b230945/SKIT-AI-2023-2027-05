import unittest
from form26as_transaction_extractor import extract_transactions


class Form26ASTransactionExtractorTests(unittest.TestCase):
    def test_extracts_row_with_date_tan_section_and_amounts(self):
        text = "15/06/2025 ABCD12345E 194A Interest paid 10,000.00 1,000.00"
        rows = extract_transactions(text, "sample.txt")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].date, "15/06/2025")
        self.assertEqual(rows[0].tan, "ABCD12345E")
        self.assertEqual(rows[0].section, "194A")
        self.assertEqual(rows[0].candidate_amount, "1000.00")
        self.assertEqual(rows[0].status, "review_required")

    def test_ignores_unrelated_line_without_transaction_clues(self):
        self.assertEqual(extract_transactions("The report was generated successfully."), [])

    def test_keeps_evidence_and_warnings(self):
        rows = extract_transactions("TDS credit 450.00")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].source_line, 1)
        self.assertTrue(rows[0].warnings)


if __name__ == "__main__":
    unittest.main()
