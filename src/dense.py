"""밀집(dense) 임베딩 검색 — 코사인 유사도 기반.

의미·문맥 유사도에 강하다 (동의어, 의역 질의). 벡터는 미리 계산해 캐시한다.
"""

import math


class DenseIndex:
    def __init__(self, embeddings):
        """embeddings: 문서 id 순서와 정렬된 list[list[float]]."""
        self.emb = embeddings
        self.norms = [self._norm(v) for v in embeddings]

    @staticmethod
    def _norm(vec):
        return math.sqrt(sum(x * x for x in vec)) or 1e-9

    def search(self, query_vec, top_k):
        """질의 벡터로 코사인 유사도 상위 top_k를 [(doc_id, score)]로 반환."""
        qn = self._norm(query_vec)
        scores = []
        for doc_id, vec in enumerate(self.emb):
            dot = sum(a * b for a, b in zip(vec, query_vec))
            scores.append((doc_id, dot / (self.norms[doc_id] * qn)))
        scores.sort(key=lambda kv: kv[1], reverse=True)
        return scores[:top_k]
