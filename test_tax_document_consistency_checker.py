"""Unit tests for tax_document_consistency_checker.py."""

import unittest

from tax_document_consistency_checker import (
    ConsistencyInputError,
    check_tds_consistency,
)


class TestTaxDocumentConsistencyChecker(unittest.TestCase):
    def test_only_manually_verified_section_192_included_and_matched(self) -> None:
        form16 = {
            "source_file": "form16_sample.pdf",
            "page": 1,
            "salary_tds": 85000.0,
        }
        queue = [
            {
                "candidate_id": "c1",
                "section": "192",
                "review_status": "manually_verified",
                "candidate_amount": 45000.0,
                "source_file": "26as_sample.pdf",
                "page": 1,
                "line": 12,
            },
            {
                "candidate_id": "c2",
                "section": "Section 192",
                "review_status": "verified",
                "candidate_amount": 40000.0,
                "source_file": "26as_sample.pdf",
                "page": 1,
                "line": 13,
            },
            {
                "candidate_id": "c3_unverified",
                "section": "192",
                "review_status": "pending_review",
                "candidate_amount": 15000.0,
            },
            {
                "candidate_id": "c4_other_sec",
                "section": "194A",
                "review_status": "manually_verified",
                "candidate_amount": 5000.0,
            },
        ]

        result = check_tds_consistency(form16, queue)
        self.assertEqual(result["review_status"], "matched")
        self.assertEqual(result["verified_section_192_total"], 85000.0)
        self.assertEqual(result["difference_amount"], 0.0)
        self.assertEqual(result["included_candidate_count"], 2)
        self.assertEqual(result["excluded_candidate_count"], 2)
        self.assertEqual(
            [item["record_id"] for item in result["included_candidates"]],
            ["c1", "c2"],
        )
        self.assertEqual(result["included_candidates"][0]["source_references"]["line"], 12)

    def test_difference_found_when_amounts_differ(self) -> None:
        form16 = {"salary_tds": 92000.0}
        queue = [
            {
                "candidate_id": "c1",
                "section": "192",
                "review_status": "manually_verified",
                "candidate_amount": 80000.0,
            }
        ]

        result = check_tds_consistency(form16, queue)
        self.assertEqual(result["review_status"], "difference_found")
        self.assertEqual(result["verified_section_192_total"], 80000.0)
        self.assertEqual(result["difference_amount"], 12000.0)

    def test_missing_form16_tds_returns_review_required_not_zero(self) -> None:
        form16 = {"salary_tds": None}
        queue = [
            {
                "candidate_id": "c1",
                "section": "192",
                "review_status": "manually_verified",
                "candidate_amount": 50000.0,
            }
        ]

        result = check_tds_consistency(form16, queue)
        self.assertEqual(result["review_status"], "review_required")
        self.assertIsNone(result["form16_salary_tds"])
        self.assertIsNone(result["difference_amount"])
        self.assertEqual(result["verified_section_192_total"], 50000.0)

    def test_unverified_non_192_and_missing_amount_excluded_with_reasons(self) -> None:
        form16 = {"salary_tds": 30000.0}
        queue = [
            {
                "candidate_id": "r1_unverified",
                "section": "192",
                "review_status": "unreviewed",
                "candidate_amount": 30000.0,
            },
            {
                "candidate_id": "r2_sec194j",
                "section": "194J",
                "review_status": "manually_verified",
                "candidate_amount": 10000.0,
            },
            {
                "candidate_id": "r3_no_amount",
                "section": "192",
                "review_status": "manually_verified",
                "candidate_amount": None,
            },
        ]

        result = check_tds_consistency(form16, queue)
        self.assertEqual(result["included_candidate_count"], 0)
        self.assertEqual(result["excluded_candidate_count"], 3)
        self.assertEqual(result["review_status"], "review_required")

        excluded_by_id = {e["record_id"]: e for e in result["excluded_candidates"]}
        self.assertIn("not_manually_verified", excluded_by_id["r1_unverified"]["exclusion_reasons"])
        self.assertTrue(
            any(reason.startswith("not_section_192") for reason in excluded_by_id["r2_sec194j"]["exclusion_reasons"])
        )
        self.assertIn(
            "missing_or_invalid_candidate_amount",
            excluded_by_id["r3_no_amount"]["exclusion_reasons"],
        )

    def test_invalid_inputs_raise_consistency_input_error(self) -> None:
        with self.assertRaises(ConsistencyInputError):
            check_tds_consistency("not_a_dict", [])  # type: ignore[arg-type]

        with self.assertRaises(ConsistencyInputError):
            check_tds_consistency({"salary_tds": 1000.0}, {"unexpected_key": 123})


if __name__ == "__main__":
    unittest.main()
