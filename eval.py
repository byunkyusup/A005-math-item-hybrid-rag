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

# (A) 키워드 질의: 교육과정 용어를 그대로 포함 → 어휘 매칭(BM25) 우세 예상
KEYWORD_QUERIES = [
    {"q": "분수 크기 비교", "concept_has": "분수"},
    {"q": "삼각형의 넓이 구하기", "concept_has": "삼각형"},
    {"q": "원의 반지름과 지름", "concept_has": "원"},
    {"q": "곱셈 공식", "concept_has": "곱셈"},
    {"q": "닮음의 성질", "concept_has": "닮음"},
    {"q": "일차방정식의 풀이", "concept_has": "방정식"},
    {"q": "정수와 유리수의 덧셈", "concept_has": "덧셈"},
    {"q": "각의 크기와 종류", "concept_has": "각"},
]

# (B) 의역 질의: 교육과정 용어를 거의 쓰지 않고 상황으로 묻는다 → 의미 검색(dense) 우세 예상
PARAPHRASE_QUERIES = [
    {"q": "두 도형이 크기만 다르고 모양이 완전히 같은지 따지는 문제", "concept_has": "닮음"},
    {"q": "피자를 똑같이 여러 조각으로 나눴을 때 한 조각을 수로 나타내기", "concept_has": "분수"},
    {"q": "세 변의 길이로 삼각형의 넓이를 구하는 문제", "concept_has": "삼각형"},
    {"q": "막대 모양으로 자료의 많고 적음을 한눈에 보여주는 그림", "concept_has": "그래프"},
    {"q": "물건을 여러 사람에게 똑같이 나누어 주는 계산", "concept_has": "나눗셈"},
    {"q": "모르는 수를 기호로 두고 식을 세워 그 값을 찾는 문제", "concept_has": "방정식"},
    {"q": "여러 값을 모두 더한 뒤 개수로 나눠 대표값을 구하기", "concept_has": "평균"},
    {"q": "동전을 던졌을 때 앞면이 나올 가능성을 수로 표현", "concept_has": "확률"},
]

K = 5
MODES = ["sparse", "dense", "hybrid"]


def is_relevant(concept: dict, spec: dict) -> bool:
    return spec["concept_has"] in concept["name"]


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
