import unittest

from src import irt


class TestIRT(unittest.TestCase):
    def test_band_boundaries(self):
        self.assertEqual(irt.band(1.0), "상")
        self.assertEqual(irt.band(0.0), "중")
        self.assertEqual(irt.band(-1.0), "하")

    def test_parse_query_difficulty(self):
        self.assertEqual(irt.parse_query_difficulty("어려운 문항"), "상")
        self.assertEqual(irt.parse_query_difficulty("쉬운 문제"), "하")
        self.assertIsNone(irt.parse_query_difficulty("분수 문항"))

    def test_fit_score_band(self):
        self.assertGreater(irt.fit_score(1.0, "상", None), irt.fit_score(-1.0, "상", None))

    def test_fit_score_theta(self):
        self.assertGreater(irt.fit_score(0.1, None, 0.0), irt.fit_score(2.0, None, 0.0))

    def test_fit_score_neutral(self):
        self.assertEqual(irt.fit_score(0.3, None, None), 0.5)


if __name__ == "__main__":
    unittest.main()
