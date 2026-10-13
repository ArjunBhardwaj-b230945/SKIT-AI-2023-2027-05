import unittest
from tax_data_extractor import extract_tax_data
class TaxDataExtractorTests(unittest.TestCase):
    def test_candidate_fields(self):
        f16="PAN of the Employee: ABCDE1234F\nAssessment Year: 2026-27\nGross Salary: 850000\nIncome chargeable under the head Salaries: 800000\nTax Deducted at Source: 25000"
        f26="PAN of the Taxpayer: ABCDE1234F\nAssessment Year: 2026-27\nFinancial Year: 2025-26"
        r=extract_tax_data(f16,f26)
        self.assertEqual(r.taxpayer.pan.value,"ABCDE1234F")
        self.assertEqual(r.salary.gross_salary.value,"850000")
        self.assertEqual(r.salary.taxable_salary.value,"800000")
    def test_pan_mismatch(self):
        r=extract_tax_data("PAN: ABCDE1234F\nAssessment Year: 2026-27","PAN: PQRSX6789L\nAssessment Year: 2026-27")
        self.assertTrue(any("PAN mismatch" in x for x in r.warnings))
    def test_missing_is_not_zero(self):
        r=extract_tax_data("PAN: ABCDE1234F","PAN: ABCDE1234F")
        self.assertIsNone(r.salary.gross_salary.value)
        self.assertEqual(r.salary.gross_salary.status,"missing")
if __name__=="__main__": unittest.main()
