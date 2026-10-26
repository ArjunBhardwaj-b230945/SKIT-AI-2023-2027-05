import unittest
from tax_data_quality_report import build_quality_report

class Tests(unittest.TestCase):
    def test_coverage_and_warnings(self):
        data={"transactions":[{"tan":"ABCD12345E","date":"01/06/2025","section":"192","candidate_amount":"100","warnings":[]},
                              {"tan":None,"date":None,"section":None,"candidate_amount":None,"warnings":["check"]}]}
        r=build_quality_report(data)
        self.assertEqual(r["candidate_count"], 2)
        self.assertEqual(r["checks"][0]["coverage_percent"], 50.0)
        self.assertEqual(r["rows_with_extraction_warnings"], 1)
    def test_empty_input(self):
        r=build_quality_report({"transactions":[]})
        self.assertTrue(r["warnings"])
if __name__ == "__main__": unittest.main()
