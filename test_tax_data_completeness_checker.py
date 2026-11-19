import unittest
from form16_tax_data_normalizer import normalize_form16
from tax_data_completeness_checker import check_completeness

class CompletenessCheckerTests(unittest.TestCase):
    def test_missing_required_fields_are_reported(self):
        report = check_completeness(normalize_form16({}))
        self.assertIn("pan", report["required_fields_missing"])
        self.assertIn("gross_salary", report["required_fields_missing"])

    def test_optional_missing_fields_do_not_become_zero(self):
        normalized = normalize_form16({
            "pan": "ABCDE1234F",
            "assessment_year": "AY 2026-27",
            "gross_salary": "500000"
        })
        report = check_completeness(normalized)
        self.assertIn("salary_tds", report["optional_fields_missing"])
        self.assertIsNone(normalized["fields"]["salary_tds"]["value"])

    def test_salary_component_mismatch_warning(self):
        normalized = normalize_form16({
            "pan": "ABCDE1234F", "assessment_year": "AY 2026-27",
            "gross_salary": "100000",
            "salary_17_1": "70000", "perquisites_17_2": "10000",
            "profit_in_lieu_17_3": "5000"
        })
        report = check_completeness(normalized)
        self.assertIsNotNone(report["salary_component_consistency_warning"])

    def test_matching_salary_components_no_component_warning(self):
        normalized = normalize_form16({
            "pan": "ABCDE1234F", "assessment_year": "AY 2026-27",
            "gross_salary": "100000",
            "salary_17_1": "85000", "perquisites_17_2": "10000",
            "profit_in_lieu_17_3": "5000"
        })
        report = check_completeness(normalized)
        self.assertIsNone(report["salary_component_consistency_warning"])

    def test_report_does_not_claim_tax_verification(self):
        report = check_completeness(normalize_form16({}))
        self.assertFalse(report["tax_correctness_verified"])

if __name__ == "__main__":
    unittest.main()
