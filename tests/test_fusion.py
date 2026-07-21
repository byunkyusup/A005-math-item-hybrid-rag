import unittest

from src.fusion import reciprocal_rank_fusion


class TestFusion(unittest.TestCase):
    def test_rrf_merges_both_lists(self):
        a = [("x", 9), ("y", 8)]
        b = [("y", 7), ("z", 6)]
        out = dict(reciprocal_rank_fusion([a, b], k=60))
        # y는 양쪽 리스트 상위에 등장 → 최상위여야 한다.
        self.assertGreater(out["y"], out["x"])
        self.assertGreater(out["y"], out["z"])

    def test_top_k_limit(self):
        a = [("x", 1), ("y", 1), ("z", 1)]
        self.assertEqual(len(reciprocal_rank_fusion([a], top_k=2)), 2)


if __name__ == "__main__":
    unittest.main()
