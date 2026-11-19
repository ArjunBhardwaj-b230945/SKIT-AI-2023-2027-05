import unittest
from form26as_duplicate_checker import find_duplicates

class DuplicateTests(unittest.TestCase):
    def test_exact_duplicates_flagged(self):
        row={"tan":"ABCD12345E","date":"01/06/2025","section":"192",
             "candidate_amount":"1000","raw_text":"TDS 1000"}
        r=find_duplicates({"transactions":[row, dict(row)]})
        self.assertEqual(r["possible_duplicate_group_count"], 1)
        self.assertEqual(r["possible_duplicate_row_count"], 2)
    def test_different_rows_not_flagged(self):
        r=find_duplicates({"transactions":[{"raw_text":"row one"},{"raw_text":"row two"}]})
        self.assertEqual(r["possible_duplicate_group_count"], 0)
    def test_source_rows_retained(self):
        r=find_duplicates({"transactions":[{"raw_text":"same"},{"raw_text":"same"}]})
        self.assertEqual(r["input_row_count"], 2)
if __name__ == "__main__": unittest.main()
