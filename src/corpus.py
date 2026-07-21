"""개념(concept)을 검색용 '문서 텍스트'로 변환.

검색 단위는 개념이다. 문항 ~9,500개는 다수가 동일 개념 텍스트를 공유하므로,
개념(1,631) 단위로 임베딩한 뒤 상위 개념을 문항으로 확장·재랭킹한다.

  - doc_texts   : BM25(어휘)용 카드. 학년/단원/성취기준/난이도밴드/정답률 키워드 포함.
  - embed_texts : 임베딩(의미)용 텍스트. 숫자 노이즈 제외, 자연어 중심.
개념·문항의 실측 정답률·IRT는 ETL 카탈로그(concepts/items.json)에 이미 집계돼 있다.
"""

import json
from collections import defaultdict

from src import config


def _load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_document_text(c: dict) -> str:
    """BM25용 전체 카드 (키워드 풍부)."""
    ch = c["chapter"]
    rate = c.get("correct_rate")
    rate_str = f"{rate:.1f}%" if rate is not None else "정보 없음"
    return (
        f"[{c['grade']} {c.get('semester', '')} 수학] "
        f"{ch['대']} > {ch['중']} > {ch['소']}\n"
        f"개념: {c['name']}\n"
        f"성취기준: {c.get('achievement', '')}\n"
        f"난이도: {c['band']} (평균 b={c['avg_b']}) | 실측 정답률: {rate_str} "
        f"| 문항 {c['item_count']}개\n"
        f"설명: {c.get('description', '')}"
    )


def build_embedding_text(c: dict) -> str:
    """임베딩용 의미 텍스트 (숫자 노이즈 제거)."""
    ch = c["chapter"]
    return (
        f"{c['grade']} 수학 개념. "
        f"단원: {ch['대']} {ch['중']} {ch['소']}. "
        f"개념: {c['name']}. "
        f"성취기준: {c.get('achievement', '')}. "
        f"{c.get('description', '')}"
    )


def load_corpus() -> tuple[list, list, list]:
    """반환: (concept_list, doc_texts, embed_texts) — 모두 tag 정렬 동일 순서.

    concept_list[i]['tag'] 로 문항 확장·그래프 조회와 연결된다.
    """
    concepts = _load_json(config.CONCEPTS_PATH)
    concept_list = [concepts[tag] for tag in sorted(concepts)]
    doc_texts = [build_document_text(c) for c in concept_list]
    embed_texts = [build_embedding_text(c) for c in concept_list]
    return concept_list, doc_texts, embed_texts


def load_items_by_tag() -> dict:
    """items.json을 개념 tag별 문항 리스트로 그룹화."""
    items = _load_json(config.ITEMS_PATH)
    by_tag: dict = defaultdict(list)
    for aid, it in items.items():
        row = dict(it)
        row["assessmentItemID"] = aid
        by_tag[it["tag"]].append(row)
    return by_tag
