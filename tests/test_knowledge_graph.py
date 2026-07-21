import unittest

from src.knowledge_graph import KnowledgeGraph


class TestGraph(unittest.TestCase):
    def setUp(self):
        self.g = KnowledgeGraph({"1": {"name": "A"}, "2": {"name": "B"}}, [["1", "2"]])

    def test_prereqs(self):
        self.assertEqual(self.g.prereqs("2"), ["1"])

    def test_successors(self):
        self.assertEqual(self.g.successors("1"), ["2"])

    def test_concept_lookup(self):
        self.assertEqual(self.g.concept("1")["name"], "A")

    def test_self_edge_ignored(self):
        g = KnowledgeGraph({"1": {}}, [["1", "1"]])
        self.assertEqual(g.successors("1"), [])


if __name__ == "__main__":
    unittest.main()
