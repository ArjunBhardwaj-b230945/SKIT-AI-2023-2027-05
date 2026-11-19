import unittest
from document_layout_normalizer import normalize_document_text
from form16_extraction import extract_form16
from form26as_extraction import extract_form26as
from document_parsing_pipeline_v2 import parse_document

F16="""Page 1 of 2
Employee PAN: ABCDE1234F
Employer TAN: DELA12345B
Assessment Year: 2026-27
Salary as per section 17(1): ₹ 7,50,000
Standard deduction under section 16(ia): ₹ 50,000
Tax deducted: ₹ 45,000"""
F26="""PAN: ABCDE1234F
Assessment Year: 2026-27
ABCD12345E ABC Company 450000 45000
15/07/2026 123456 20000"""

class TestDocumentParsingV2(unittest.TestCase):
    def test_normalization(self):
        x=normalize_document_text("Page 1 of 2\r\nSalary    value")
        self.assertNotIn("Page 1 of 2",x); self.assertIn("Salary value",x)
    def test_form16(self):
        x=extract_form16(F16); self.assertEqual(x["employee_pan"],"ABCDE1234F"); self.assertEqual(x["salary_17_1"],750000.0)
    def test_form26as(self):
        x=extract_form26as(F26); self.assertEqual(x["pan"],"ABCDE1234F"); self.assertGreaterEqual(len(x["tds_rows"]),1)
    def test_pipeline(self):
        x=parse_document(F16,"form16"); self.assertEqual(x["data"]["assessment_year"],"2026-27")

if __name__=="__main__": unittest.main()
