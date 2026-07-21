"""개념 선후관계 그래프 조회 (fromConcept=선수 → toConcept=후속)."""

from collections import defaultdict


class KnowledgeGraph:
    def __init__(self, concepts: dict, edges: list):
        self.concepts = concepts
        self._pre: dict = defaultdict(list)
        self._suc: dict = defaultdict(list)
        for a, b in edges:
            if a == b:
                continue
            self._suc[a].append(b)
            self._pre[b].append(a)

    def prereqs(self, tag: str) -> list:
        return self._pre.get(tag, [])

    def successors(self, tag: str) -> list:
        return self._suc.get(tag, [])

    def concept(self, tag: str) -> dict | None:
        return self.concepts.get(tag)
