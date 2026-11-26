"""Unit tests for tax_data_review_bundle.py."""

import unittest

from tax_data_review_bundle import ReviewBundleInputError, build_review_bundle


class TestTaxDataReviewBundle(unittest.TestCase):
    def test_bundle_contains_form16_statuses_and_26as_counts(self) -> None:
        form16 = {
            "source_file": "form16.json",
            "page": 1,
            "fields": {
                "pan": "ABCDE1234F",
                "assessment_year": "2026-27",
                "salary_tds": 75000.0,
                "taxable_salary": None,
            },
        }
        queue = [
            {
                "candidate_id": "q1",
                "section": "192",
                "review_status": "manually_verified",
                "candidate_amount": 75000.0,
                "source_file": "26as.json",
                "page": 2,
                "line": 7,
            },
            {
                "candidate_id": "q2",
                "section": "192",
                "review_status": "pending_review",
                "candidate_amount": 5000.0,
                "source_file": "26as.json",
                "page": 2,
                "line": 8,
            },
        ]

        bundle = build_review_bundle(form16, queue)
        self.assertEqual(bundle["form16"]["field_review_statuses"]["pan"], "present_pending_review")
        self.assertEqual(bundle["form16"]["field_review_statuses"]["taxable_salary"], "missing")
        self.assertEqual(bundle["form26as"]["candidate_counts_by_review_status"]["manually_verified"], 1)
        self.assertEqual(bundle["form26as"]["candidate_counts_by_review_status"]["pending_review"], 1)
        self.assertEqual(bundle["form26as"]["eligible_verified_section_192_count"], 1)
        self.assertEqual(bundle["form26as"]["excluded_candidate_count"], 1)
        self.assertEqual(bundle["cross_document_tds_comparison"]["status"], "matched")

    def test_completeness_warnings_included_when_report_supplied(self) -> None:
        form16 = {"salary_tds": 50000.0}
        queue = [
            {
                "candidate_id": "q1",
                "section": "192",
                "review_status": "manually_verified",
                "candidate_amount": 50000.0,
            }
        ]
        completeness_report = {
            "is_complete": False,
            "warnings": [
                {"code": "MISSING_OPTIONAL_FIELD", "field": "standard_deduction", "message": "Standard deduction not found."}
            ],
        }

        bundle = build_review_bundle(form16, queue, completeness_report=completeness_report)
        self.assertIsNotNone(bundle["form16"]["completeness"])
        warning_codes = [w.get("code") for w in bundle["warnings"]]
        self.assertIn("MISSING_OPTIONAL_FIELD", warning_codes)

    def test_preserves_source_references_and_avoids_tax_correctness_claims(self) -> None:
        form16 = {
            "source_file": "form16_doc.pdf",
            "page": 1,
            "line": 4,
            "salary_tds": 60000.0,
        }
        queue = [
            {
                "candidate_id": "q1",
                "section": "192",
                "review_status": "manually_verified",
                "candidate_amount": 60000.0,
                "source_file": "form26as_doc.pdf",
                "page": 3,
                "line": 19,
            }
        ]

        bundle = build_review_bundle(form16, queue)
        self.assertGreaterEqual(len(bundle["source_references"]), 2)
        disclaimer_lower = bundle["disclaimer"].lower()
        self.assertIn("review", disclaimer_lower)
        self.assertIn("does not", disclaimer_lower)

    def test_invalid_completeness_report_type_raises_error(self) -> None:
        with self.assertRaises(ReviewBundleInputError):
            build_review_bundle({"salary_tds": 1000.0}, [], completeness_report="invalid")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
