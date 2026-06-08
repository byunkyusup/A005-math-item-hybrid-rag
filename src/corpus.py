"""문항(item) + 응답로그(response)를 읽어 검색용 '문서 텍스트'로 변환.

AIHub #27752 스키마:
  - 문항 메타: assessmentItemID, testID, grade, semester, area, concept,
               itemType, difficulty(a,b,c=변별도/난이도/추측도), difficultyGrade, keywords
  - 응답로그: learnerID, learnerProfile, testID, assessmentItemID, answerCode(정오답), timeStamp

응답로그에서 문항별 실측 정답률을 집계해 문서 카드에 포함한다.
문항 1건 = 검색 단위 문서 1건.
"""

import json

from src import config


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _aggregate_correct_rate(responses):
    """assessmentItemID -> (정답수, 응답수)."""
    agg = {}
    for r in responses:
        aid = r["assessmentItemID"]
        correct, total = agg.get(aid, (0, 0))
        agg[aid] = (correct + r["answerCode"], total + 1)
    return agg


def build_document_text(item):
    """BM25(어휘 검색)용 전체 카드. 학년/단원/IRT/정답률 등 키워드를 모두 포함."""
    d = item["difficulty"]
    rate = item.get("observedCorrectRate")
    rate_str = f"{rate:.1f}%" if rate is not None else "정보 없음"
    keywords = " ".join(item.get("keywords", []))
    return (
        f"[{item['grade']} {item['semester']}학기 수학] "
        f"{item['area']} > {item['concept']}\n"
        f"문항유형: {item['itemType']} | 난이도등급: {item['difficultyGrade']}\n"
        f"IRT 모수: 난이도 b={d['b']}, 변별도 a={d['a']}, 추측도 c={d['c']}\n"
        f"실측 정답률: {rate_str} (응답 {item.get('observedCount', 0)}건)\n"
        f"핵심개념: {keywords}\n"
        f"설명: {item['description']}"
    )


def build_embedding_text(item):
    """임베딩(의미 검색)용 텍스트. 숫자 노이즈(IRT/정답률)를 제외하고 의미만 남긴다.

    의역 질의("직각삼각형 세 변의 관계")가 문항 설명과 잘 매칭되도록 자연어 중심으로 구성.
    """
    keywords = ", ".join(item.get("keywords", []))
    return (
        f"{item['grade']} {item['semester']}학기 수학 문항. "
        f"영역: {item['area']}. 단원: {item['concept']}. "
        f"{item['description']} 핵심개념: {keywords}."
    )


def load_corpus():
    """반환: (enriched_items, doc_texts, embed_texts) — 모두 동일한 doc_id 순서로 정렬.

    - doc_texts:   BM25용 전체 카드 (키워드 풍부)
    - embed_texts: 임베딩용 의미 텍스트 (숫자 노이즈 제거)
    - enriched_items[i] 에는 실측 정답률(observedCorrectRate/observedCount)이 추가된다.
    """
    items = _load_json(config.ITEMS_PATH)
    responses = _load_json(config.RESPONSES_PATH)
    agg = _aggregate_correct_rate(responses)

    enriched, doc_texts, embed_texts = [], [], []
    for item in items:
        correct, total = agg.get(item["assessmentItemID"], (0, 0))
        item = dict(item)
        item["observedCount"] = total
        item["observedCorrectRate"] = (correct / total * 100) if total else None
        enriched.append(item)
        doc_texts.append(build_document_text(item))
        embed_texts.append(build_embedding_text(item))

    return enriched, doc_texts, embed_texts
