import unittest
from form26as_candidate_aggregator import aggregate_candidates

class Tests(unittest.TestCase):
    def test_group_subtotals(self):
        data={"transactions":[{"section":"192","tan":"ABCD12345E","candidate_amount":"100"},
                              {"section":"192","tan":"ABCD12345E","candidate_amount":"25"}]}
        r=aggregate_candidates(data)
        self.assertEqual(r["candidate_subtotal"], "125.00")
        self.assertEqual(r["by_section"]["192"]["row_count"], 2)
        self.assertEqual(r["status"], "review_required")
    def test_invalid_amount_warned(self):
        r=aggregate_candidates({"transactions":[{"candidate_amount":"bad"}]})
        self.assertEqual(r["candidate_subtotal"], "0.00")
        self.assertEqual(len(r["warnings"]), 1)
if __name__ == "__main__": unittest.main()
