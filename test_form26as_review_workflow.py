import unittest
from form26as_review_workflow import build_review_queue, apply_manual_decisions, load_records
import tempfile, json, os

VALID = {
    "tan": "ABCD12345E",
    "date": "15-10-2026",
    "section": "194A",
    "candidate_amount": "1,250.00",
    "raw_text": "ABCD12345E 15-10-2026 194A 1250.00",
    "source_file": "sample.txt",
    "source_line": 12,
}

class ReviewWorkflowTests(unittest.TestCase):
    def test_valid_row_pending_manual_review(self):
        result = build_review_queue([VALID])
        self.assertEqual(result["candidates"][0]["review_status"], "pending_manual_review")

    def test_invalid_tan_fails_validation(self):
        row = dict(VALID, tan="BAD")
        result = build_review_queue([row])
        self.assertEqual(result["candidates"][0]["review_status"], "validation_failed")
        self.assertIn("tan_format_valid", result["candidates"][0]["validation_errors"])

    def test_duplicate_is_flagged(self):
        result = build_review_queue([VALID, VALID])
        self.assertFalse(result["candidates"][0]["duplicate_candidate"])
        self.assertTrue(result["candidates"][1]["duplicate_candidate"])

    def test_manual_decision_is_recorded(self):
        queue = build_review_queue([VALID])
        updated = apply_manual_decisions(queue, {"F26AS-0001": "needs_clarification"})
        self.assertEqual(updated["candidates"][0]["review_status"], "reviewer_needs_clarification")

    def test_invalid_decision_rejected(self):
        queue = build_review_queue([VALID])
        with self.assertRaises(ValueError):
            apply_manual_decisions(queue, {"F26AS-0001": "auto_approve"})

    def test_unknown_review_id_rejected(self):
        queue = build_review_queue([VALID])
        with self.assertRaises(ValueError):
            apply_manual_decisions(queue, {"F26AS-9999": "verified"})

    def test_load_records_from_object(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"candidates": [VALID]}, f)
            name = f.name
        try:
            self.assertEqual(len(load_records(name)), 1)
        finally:
            os.unlink(name)

if __name__ == "__main__":
    unittest.main()
