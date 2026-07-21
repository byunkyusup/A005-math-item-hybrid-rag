import unittest

from src import recommender


class FakeRetr:
    def retrieve(self, q, mode="hybrid", final_k=8):
        return [("tagA", 1.0), ("tagB", 0.5)]


class FakeGraph:
    def prereqs(self, tag):
        return []


class TestRecommend(unittest.TestCase):
    def test_grade_filter_and_rerank(self):
        concepts = {
            "tagA": {"tag": "tagA", "name": "A", "grade": "초3"},
            "tagB": {"tag": "tagB", "name": "B", "grade": "중1"},
        }
        items = {
            "tagA": [{"assessmentItemID": "i1", "tag": "tagA", "grade": "초3",
                      "b": 1.0, "band": "상", "correct_rate": 40.0}],
            "tagB": [{"assessmentItemID": "i2", "tag": "tagB", "grade": "중1",
                      "b": -1.0, "band": "하", "correct_rate": 90.0}],
        }
        recs = recommender.recommend(
            "어려운 초등 문항", FakeRetr(), concepts, items, FakeGraph(),
            mode="hybrid", grade="초3", difficulty=None, theta=None, k=5,
        )
        self.assertEqual([r["item"]["assessmentItemID"] for r in recs], ["i1"])

    def test_difficulty_prefers_matching_band(self):
        concepts = {"t": {"tag": "t", "name": "C", "grade": "초3"}}
        items = {"t": [
            {"assessmentItemID": "easy", "tag": "t", "grade": "초3", "b": -1.0, "band": "하"},
            {"assessmentItemID": "hard", "tag": "t", "grade": "초3", "b": 1.0, "band": "상"},
        ]}

        class R:
            def retrieve(self, q, mode="hybrid", final_k=8):
                return [("t", 1.0)]

        recs = recommender.recommend(
            "문항", R(), concepts, items, FakeGraph(),
            mode="hybrid", grade=None, difficulty="상", theta=None, k=2,
        )
        self.assertEqual(recs[0]["item"]["assessmentItemID"], "hard")


if __name__ == "__main__":
    unittest.main()
