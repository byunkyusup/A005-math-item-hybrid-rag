"""개념 검색 품질 비교: sparse(BM25) vs dense(임베딩) vs hybrid(RRF).

질의를 두 종류로 나눠 각 방식의 강·약점을 드러낸다:
  (A) 키워드 질의 — 교육과정 용어를 그대로 사용 → BM25(sparse) 유리
  (B) 의역 질의   — 개념을 풀어 설명, 정확 용어 미포함 → 임베딩(dense) 유리
핵심 메시지: 단일 방식은 한쪽에서 무너지지만 hybrid는 양쪽에서 견고하다.
판정: 상위 K 개념 안에 (학년 + 개념명 부분일치) 조건을 만족하는 개념이 있으면 hit.

사용: python eval.py   (전제: build_catalog.py + build_index.py 완료)
"""

import json
import sys

from src import config
from src.corpus import load_corpus
from src.retriever import HybridRetriever

# (A) 키워드 질의
KEYWORD_QUERIES = [
    {"q": "초3 분수 크기 비교", "grade": "초3", "concept_has": "분수"},
    {"q": "초3 원의 반지름 지름", "grade": "초3", "concept_has": "원"},
    {"q": "초3 나눗셈", "grade": "초3", "concept_has": "나눗셈"},
]

# (B) 의역 질의 (교육과정 용어를 거의 쓰지 않음)
PARAPHRASE_QUERIES = [
    {"q": "피자를 똑같이 나눈 조각 중 몇 조각인지 나타내는 방법", "grade": "초3", "concept_has": "분수"},
    {"q": "한 점에서 같은 거리에 있는 점들이 그리는 동그란 도형", "grade": "초3", "concept_has": "원"},
]

K = 5
MODES = ["sparse", "dense", "hybrid"]


def is_relevant(concept: dict, spec: dict) -> bool:
    return concept["grade"] == spec["grade"] and spec["concept_has"] in concept["name"]


def evaluate(retriever, concepts, queries, mode):
    hits, mrr = 0, 0.0
    for spec in queries:
        results = retriever.retrieve(spec["q"], mode=mode, final_k=K)
        for rank, (doc_id, _) in enumerate(results, 1):
            if is_relevant(concepts[doc_id], spec):
                hits += 1
                mrr += 1.0 / rank
                break
    n = len(queries) or 1
    return hits / n, mrr / n


def print_table(title, retriever, concepts, queries):
    print(f"\n[{title}]  (질의 {len(queries)}건)")
    print(f"{'mode':<8}{'Hit@%d' % K:>10}{'MRR@%d' % K:>10}")
    print("-" * 28)
    for mode in MODES:
        hit, mrr = evaluate(retriever, concepts, queries, mode)
        print(f"{mode:<8}{hit:>10.2f}{mrr:>10.3f}")


def main():
    concept_list, doc_texts, _ = load_corpus()
    with open(config.EMBED_CACHE_PATH, encoding="utf-8") as f:
        embeddings = json.load(f)["vectors"]
    retriever = HybridRetriever(doc_texts, embeddings)

    print_table("A. 키워드 질의 (BM25 유리)", retriever, concept_list, KEYWORD_QUERIES)
    print_table("B. 의역 질의 (임베딩 유리)", retriever, concept_list, PARAPHRASE_QUERIES)
    print_table("A+B 전체 (견고성)", retriever, concept_list,
                KEYWORD_QUERIES + PARAPHRASE_QUERIES)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"[오류] {exc}. 먼저 build_catalog.py / build_index.py 실행 필요.", file=sys.stderr)
        sys.exit(1)
