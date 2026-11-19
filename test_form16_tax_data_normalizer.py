import unittest
from form16_tax_data_normalizer import normalize_form16

class Form16NormalizerTests(unittest.TestCase):
    def test_numeric_amount_is_normalized(self):
        result = normalize_form16({"gross_salary": "8,50,000.00"})
        self.assertEqual(result["fields"]["gross_salary"]["value"], 850000.0)

    def test_missing_value_remains_null(self):
        result = normalize_form16({})
        self.assertIsNone(result["fields"]["gross_salary"]["value"])
        self.assertTrue(any("left as null" in w for w in result["warnings"]))

    def test_invalid_pan_needs_review(self):
        result = normalize_form16({"pan": "INVALID"})
        self.assertEqual(result["fields"]["pan"]["status"], "review_required")

    def test_source_evidence_is_preserved(self):
        result = normalize_form16({
            "gross_salary": "500000",
            "source_file": "form16.txt",
            "source_page": 2,
            "source_evidence": {"gross_salary": "Gross Salary: 500000"}
        })
        field = result["fields"]["gross_salary"]
        self.assertEqual(field["source_file"], "form16.txt")
        self.assertEqual(field["source_page"], 2)
        self.assertEqual(field["evidence"], "Gross Salary: 500000")

    def test_section10_exemptions_preserved(self):
        value = {"travel_concession_10_5": "12000"}
        result = normalize_form16({"section_10_exemptions": value})
        self.assertEqual(result["fields"]["section_10_exemptions"]["value"], value)

if __name__ == "__main__":
    unittest.main()
