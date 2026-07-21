import unittest

from src import obsidian_export as ox


class FakeGraph:
    concepts = {"1": {"name": "A"}}

    def prereqs(self, tag):
        return ["1"]

    def successors(self, tag):
        return []

    def concept(self, tag):
        return self.concepts.get(tag)


class TestExport(unittest.TestCase):
    def test_filename_safe(self):
        fn = ox.concept_filename("100", "분수 / 나눗셈")
        self.assertTrue(fn.startswith("100 "))
        self.assertNotIn("/", fn)

    def test_note_has_frontmatter_and_links(self):
        c = {"tag": "2", "name": "B", "description": "설명", "semester": "중1", "grade": "중1",
             "chapter": {"대": "수", "중": "정수", "소": "덧셈"}, "achievement": "성취",
             "avg_b": 0.1, "band": "중", "correct_rate": 55.0, "item_count": 3,
             "prereq_tags": ["1"], "next_tags": []}
        note = ox.concept_note(c, FakeGraph(),
                               {"2": [{"assessmentItemID": "i1", "band": "중", "correct_rate": 55.0}]})
        self.assertIn("band: 중", note)
        self.assertIn("[[1 A]]", note)
        self.assertIn("[[i1]]", note)

    def test_graph_html_counts(self):
        html = ox.render_graph_html(
            {"1": {"name": "A", "grade": "초3"}, "2": {"name": "B", "grade": "초3"}},
            [["1", "2"]],
        )
        self.assertIn("<html", html.lower())
        self.assertIn('"source"', html)


if __name__ == "__main__":
    unittest.main()
