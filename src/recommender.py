"""개념 Hybrid 검색 결과를 문항으로 확장하고 IRT 난이도·θ로 재랭킹.

흐름: 질의 → 상위 개념(TOP_CONCEPTS) → 그 개념의 문항 수집(학년 필터)
     → 점수 = W_SEARCH·검색순위 + W_FIT·난이도적합도 → 상위 k 문항.
각 추천에 소속 개념과 선수개념(이름)을 부착해 생성 단계에 넘긴다.
"""

from src import config, irt


def _resolve_tag(doc_id, concepts: dict, concept_tags):
    """retriever가 돌려준 doc_id를 개념 tag로 해석.

    - doc_id가 이미 tag면 그대로(테스트/직접 tag 반환용).
    - 정수 인덱스면 concept_tags[doc_id]로 매핑(실사용).
    """
    if doc_id in concepts:
        return doc_id
    if concept_tags is not None and isinstance(doc_id, int) and 0 <= doc_id < len(concept_tags):
        return concept_tags[doc_id]
    return None


def recommend(query, retriever, concepts: dict, items_by_tag: dict, graph, *,
              mode="hybrid", grade=None, difficulty=None, theta=None,
              k=config.FINAL_K, concept_tags=None) -> list:
    """반환: [{item, concept, prereqs:[name,...]}, ...] (최대 k건)."""
    target_band = difficulty or irt.parse_query_difficulty(query)
    hits = retriever.retrieve(query, mode=mode, final_k=config.TOP_CONCEPTS)
    max_score = max((s for _, s in hits), default=0.0) or 1.0

    candidates = []
    for doc_id, score in hits:
        tag = _resolve_tag(doc_id, concepts, concept_tags)
        if tag is None:
            continue
        norm = score / max_score
        for it in items_by_tag.get(tag, []):
            if grade and it["grade"] != grade:
                continue
            fit = irt.fit_score(it["b"], target_band, theta)
            rank = config.W_SEARCH * norm + config.W_FIT * fit
            candidates.append((rank, tag, it))

    candidates.sort(key=lambda x: x[0], reverse=True)

    out = []
    for _rank, tag, it in candidates[:k]:
        prereqs = [
            concepts[p]["name"] for p in graph.prereqs(tag) if p in concepts
        ]
        out.append({"item": it, "concept": concepts.get(tag), "prereqs": prereqs})
    return out
