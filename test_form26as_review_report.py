import unittest
import tempfile, os, csv
from form26as_review_workflow import build_review_queue
from form26as_review_report import create_summary, export_csv

VALID = {
    "tan": "ABCD12345E", "date": "15-10-2026", "section": "194A",
    "candidate_amount": "1250.00", "raw_text": "sample evidence", "source_line": 4
}

class ReviewReportTests(unittest.TestCase):
    def test_summary_counts_candidates(self):
        data = build_review_queue([VALID, dict(VALID, tan="wrong")])
        summary = create_summary(data)
        self.assertEqual(summary["total_candidates"], 2)
        self.assertEqual(summary["status_counts"]["validation_failed"], 1)

    def test_summary_never_claims_tax_verification(self):
        summary = create_summary(build_review_queue([VALID]))
        self.assertFalse(summary["tax_correctness_verified"])

    def test_csv_export_has_header_and_rows(self):
        data = build_review_queue([VALID])
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as f:
            name = f.name
        try:
            export_csv(data, name)
            with open(name, newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["review_id"], "F26AS-0001")
        finally:
            os.unlink(name)

if __name__ == "__main__":
    unittest.main()
