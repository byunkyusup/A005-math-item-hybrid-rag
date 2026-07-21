import unittest

from src import etl


class TestJoin(unittest.TestCase):
    def test_join_and_fallback(self):
        concepts_meta = {
            "100": {
                "name": "분수", "description": "d", "semester": "초3",
                "chapter": {"대": "수와연산", "중": "분수", "소": "진분수"},
                "achievement": "a",
            }
        }
        edges = [("100", "200")]  # 200은 메타·문항에 없음 → 고아
        item_irt = {
            "IT1": {"tag": "100", "testID": "T1", "a": 1.0, "b": 0.8, "c": 0.2, "grade": "초3"},
            "IT2": {"tag": "999", "testID": "T1", "a": 1.0, "b": -0.9, "c": 0.2, "grade": "초3"},
        }
        resp = {"IT1": (7, 10), "IT2": (2, 4)}
        cat = etl.assemble(concepts_meta, edges, item_irt, resp, learners={})

        self.assertIn("100", cat["concepts"])
        self.assertEqual(cat["concepts"]["100"]["band"], "상")           # b=0.8
        self.assertEqual(cat["concepts"]["100"]["correct_rate"], 70.0)
        self.assertTrue(cat["concepts"]["999"]["name"].startswith("미분류"))
        self.assertEqual(cat["edges"], [])                               # 고아 간선 제거
        self.assertEqual(cat["items"]["IT1"]["band"], "상")

    def test_split_chapter(self):
        ch = etl._split_chapter("식의 계산 > 단항식의 계산 > 지수법칙")
        self.assertEqual(ch, {"대": "식의 계산", "중": "단항식의 계산", "소": "지수법칙"})

    def test_grade_label(self):
        self.assertEqual(etl._grade_label("3학년"), "초3")
        self.assertEqual(etl._grade_label("7학년"), "중1")


if __name__ == "__main__":
    unittest.main()
