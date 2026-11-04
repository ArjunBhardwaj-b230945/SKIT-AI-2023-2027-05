import unittest
from form26as_candidate_validator import validate_candidate, validate_payload

class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.row={"source_file":"sample.txt","source_line":3,"raw_text":"TDS row",
                  "tan":"ABCD12345E","date":"01/06/2025","section":"192","candidate_amount":"1000"}
    def test_valid_formats(self):
        r=validate_candidate(self.row)
        self.assertEqual(r["failed_checks"], [])
        self.assertEqual(r["status"], "format_checks_passed_review_required")
    def test_invalid_formats(self):
        r=validate_candidate(dict(self.row, tan="bad", date="2025/99/99", section="XYZ", candidate_amount="-4"))
        self.assertIn("tan_format_valid", r["failed_checks"])
        self.assertIn("candidate_amount_valid", r["failed_checks"])
    def test_payload_counts(self):
        r=validate_payload({"transactions":[self.row, {"tan":"bad"}]})
        self.assertEqual(r["candidate_count"], 2)
        self.assertEqual(r["candidates_with_format_issues"], 1)
if __name__ == "__main__": unittest.main()
