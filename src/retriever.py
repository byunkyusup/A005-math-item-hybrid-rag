"""Hybrid 검색기 — BM25(sparse) + 임베딩(dense) + RRF 병합 오케스트레이션.

mode:
  - "sparse" : BM25 단독
  - "dense"  : 임베딩 단독
  - "hybrid" : 둘을 RRF로 병합 (기본)
"""

from src import config
from src.bm25 import BM25
from src.dense import DenseIndex
from src.fusion import reciprocal_rank_fusion
from src.ollama_client import embed
from src.tokenizer import tokenize


class HybridRetriever:
    def __init__(self, doc_texts, embeddings):
        self.doc_texts = doc_texts
        self.bm25 = BM25([tokenize(t) for t in doc_texts])
        self.dense = DenseIndex(embeddings)

    def retrieve(self, query, mode="hybrid", final_k=config.FINAL_K):
        """반환: [(doc_id, score), ...] (최대 final_k건)."""
        if mode == "sparse":
            return self.bm25.search(tokenize(query), config.TOP_K_SPARSE)[:final_k]

        if mode == "dense":
            qvec = embed(query)
            return self.dense.search(qvec, config.TOP_K_DENSE)[:final_k]

        # hybrid: 두 검색을 각각 돌린 뒤 RRF로 병합
        sparse_hits = self.bm25.search(tokenize(query), config.TOP_K_SPARSE)
        dense_hits = self.dense.search(embed(query), config.TOP_K_DENSE)
        return reciprocal_rank_fusion(
            [sparse_hits, dense_hits], k=config.RRF_K, top_k=final_k
        )
