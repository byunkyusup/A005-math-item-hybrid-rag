"""검색된 문항을 컨텍스트로 Ollama LLM이 추천/설명을 생성 (RAG의 G 단계)."""

from src.ollama_client import generate


def format_card(rank, item):
    """LLM 컨텍스트에 넣을 문항 카드 (간결 버전)."""
    rate = item.get("observedCorrectRate")
    rate_str = f"{rate:.1f}%" if rate is not None else "정보 없음"
    d = item["difficulty"]
    return (
        f"{rank}. [{item['assessmentItemID']}] "
        f"{item['grade']} {item['semester']}학기 · {item['area']} > {item['concept']}\n"
        f"   유형: {item['itemType']} | 난이도: {item['difficultyGrade']} "
        f"(b={d['b']}) | 실측 정답률: {rate_str}\n"
        f"   {item['description']}"
    )


def build_prompt(query, items):
    cards = "\n".join(format_card(i + 1, it) for i, it in enumerate(items))
    return (
        "당신은 초·중등 수학 문항 추천 도우미입니다. "
        "아래 '후보 문항'은 검색 시스템이 사용자 요청에 맞춰 찾아온 실제 문항들입니다.\n\n"
        f"[사용자 요청]\n{query}\n\n"
        f"[후보 문항]\n{cards}\n\n"
        "[지침]\n"
        "- 후보 문항 중에서 요청에 가장 적합한 문항을 추천하고, 그 이유를 학년·단원·난이도·정답률 근거로 설명하세요.\n"
        "- 후보에 없는 문항을 지어내지 마세요. 반드시 위 목록 안에서만 고르세요.\n"
        "- 한국어로, 교사가 바로 활용할 수 있도록 간결하게 답하세요.\n"
    )


def generate_answer(query, items):
    """질의 + 검색된 문항 리스트로 추천 답변 생성."""
    if not items:
        return "조건에 맞는 문항을 찾지 못했습니다."
    return generate(build_prompt(query, items))
