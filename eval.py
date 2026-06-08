"""sparse(BM25) vs dense(임베딩) vs hybrid(RRF) 검색 품질 비교.

질의를 두 종류로 나눠 각 방식의 강·약점을 정직하게 드러낸다:
  (A) 키워드 질의  — 교육과정 용어를 그대로 사용 → BM25(sparse)에 유리
  (B) 의역 질의    — 개념을 풀어 설명, 정확 용어 미포함 → 임베딩(dense)에 유리

핵심 메시지: 단일 방식은 한쪽 세트에서 무너지지만, hybrid는 양쪽에서 견고하다.
판정: 상위 K개 안에 정답 조건(학년+개념)을 만족하는 문항이 있으면 hit.

사용: python eval.py
"""

import json
import sys

from src import config
from src.corpus import load_corpus
from src.retriever import HybridRetriever

# (A) 키워드 질의: 교육과정 용어를 그대로 포함 → 어휘 매칭(BM25) 우세 예상
KEYWORD_QUERIES = [
    {"q": "초등 3학년 분수 문항", "grade": "초3", "concept_has": "분수"},
    {"q": "약분과 통분 관련 문제", "grade": "초5", "concept_has": "약분"},
    {"q": "중학교 일차방정식 문항 찾아줘", "grade": "중1", "concept_has": "일차방정식"},
    {"q": "피타고라스 정리 문제", "grade": "중2", "concept_has": "피타고라스"},
    {"q": "곱셈구구 연습 문항", "grade": "초2", "concept_has": "곱셈구구"},
]

# (B) 실생활 맥락 질의: 교육과정 용어를 거의 쓰지 않고 상황으로 묻는다.
#     문항 텍스트와 어휘 겹침이 적어 BM25는 약하고, 의미 검색(dense)이 우세할 것으로 기대.
PARAPHRASE_QUERIES = [
    {"q": "사다리를 벽에 비스듬히 세웠을 때 꼭대기 높이를 계산하는 활용 문제", "grade": "중2", "concept_has": "피타고라스"},
    {"q": "지도를 실제보다 줄여 그릴 때 길이가 어떻게 변하는지 다루는 문제", "grade": "중2", "concept_has": "닮음"},
    {"q": "내일 비가 올 가망이 얼마나 되는지 숫자로 표현하는 문제", "grade": "중2", "concept_has": "확률"},
    {"q": "물건값을 나눠 낼 때 사람 수에 맞춰 공평하게 분배하는 문제", "grade": "초6", "concept_has": "비례배분"},
    {"q": "키가 매달 얼마나 자랐는지 시간 흐름에 따른 변화를 보여 주는 문제", "grade": "초4", "concept_has": "꺾은선"},
]

K = 5
MODES = ["sparse", "dense", "hybrid"]


def is_relevant(item, spec):
    return item["grade"] == spec["grade"] and spec["concept_has"] in item["concept"]


def evaluate(retriever, items, queries, mode):
    hits, mrr = 0, 0.0
    for spec in queries:
        results = retriever.retrieve(spec["q"], mode=mode, final_k=K)
        for rank, (doc_id, _) in enumerate(results, 1):
            if is_relevant(items[doc_id], spec):
                hits += 1
                mrr += 1.0 / rank
                break
    n = len(queries)
    return hits / n, mrr / n


def print_table(title, retriever, items, queries):
    print(f"\n[{title}]  (질의 {len(queries)}건)")
    print(f"{'mode':<8}{'Hit@%d' % K:>10}{'MRR@%d' % K:>10}")
    print("-" * 28)
    for mode in MODES:
        hit, mrr = evaluate(retriever, items, queries, mode)
        print(f"{mode:<8}{hit:>10.2f}{mrr:>10.3f}")


def main():
    items, doc_texts, _embed_texts = load_corpus()
    with open(config.EMBED_CACHE_PATH, encoding="utf-8") as f:
        embeddings = json.load(f)["vectors"]
    retriever = HybridRetriever(doc_texts, embeddings)

    print_table("A. 키워드 질의 (BM25 유리)", retriever, items, KEYWORD_QUERIES)
    print_table("B. 의역 질의 (임베딩 유리)", retriever, items, PARAPHRASE_QUERIES)
    print_table("A+B 전체 (견고성)", retriever, items,
                KEYWORD_QUERIES + PARAPHRASE_QUERIES)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"[오류] {exc}. 먼저 gen_data.py / build_index.py 실행 필요.", file=sys.stderr)
        sys.exit(1)
