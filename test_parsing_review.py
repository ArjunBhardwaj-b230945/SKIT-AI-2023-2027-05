import unittest
from parsing_field_rules import normalize_text
from document_parsing_review import review_document
class ParsingReviewTests(unittest.TestCase):
    def test_wrapped_word(self):
        self.assertEqual(normalize_text("gross sala-\nry   amount"), "gross salary amount")
    def test_form16_label(self):
        r=review_document("Form 16\nGross Salary 850000\nAssessment Year 2026-27","form16")
        self.assertTrue(r["fields"]["gross_salary"]["found"])
    def test_form26as_label(self):
        r=review_document("Form 26AS\nTax Deducted 12000","form26as")
        self.assertTrue(r["fields"]["tax_deducted"]["found"])
    def test_invalid_type(self):
        with self.assertRaises(ValueError): review_document("x","form27")
if __name__=="__main__": unittest.main()
