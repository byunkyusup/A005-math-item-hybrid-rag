"""RRF (Reciprocal Rank Fusion) — 서로 다른 검색 결과를 순위 기반으로 병합.

점수 스케일이 다른 BM25와 코사인 유사도를 정규화 없이 합칠 수 있어 실무에서 선호된다.
score(d) = sum_over_lists( 1 / (k + rank(d)) )
"""

from src import config


def reciprocal_rank_fusion(result_lists, k=config.RRF_K, top_k=None):
    """result_lists: 각 [(doc_id, score), ...] 형태의 검색 결과 묶음.

    반환: 병합 점수 내림차순 [(doc_id, rrf_score), ...].
    """
    fused = {}
    for results in result_lists:
        for rank, (doc_id, _score) in enumerate(results):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

    ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
    return ranked[:top_k] if top_k else ranked
