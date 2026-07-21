"""검색·재랭킹된 문항을 컨텍스트로 Ollama LLM이 추천/설명을 생성 (RAG의 G 단계)."""

from src.ollama_client import generate


def format_card(rank: int, rec: dict) -> str:
    """LLM 컨텍스트용 추천 카드 (개념·IRT·정답률·선수개념)."""
    it = rec["item"]
    c = rec["concept"] or {}
    rate = it.get("correct_rate")
    rate_str = f"{rate:.1f}%" if rate is not None else "정보 없음"
    prereq = ", ".join(rec.get("prereqs") or []) or "없음"
    ch = c.get("chapter", {})
    unit = " > ".join(x for x in (ch.get("대"), ch.get("중"), ch.get("소")) if x)
    return (
        f"{rank}. [{it['assessmentItemID']}] "
        f"{it.get('grade', '')} · {unit}\n"
        f"   개념: {c.get('name', '')} | 난이도: {it.get('band', '')}"
        f"(b={it.get('b')}) | 실측 정답률: {rate_str}\n"
        f"   선수개념: {prereq}"
    )


def build_prompt(query: str, recommendations: list) -> str:
    cards = "\n".join(format_card(i + 1, r) for i, r in enumerate(recommendations))
    return (
        "당신은 초·중등 수학 문항 추천 도우미입니다. "
        "아래 '후보 문항'은 검색 시스템이 사용자 요청에 맞춰 실제 데이터에서 찾아온 문항들입니다.\n\n"
        f"[사용자 요청]\n{query}\n\n"
        f"[후보 문항]\n{cards}\n\n"
        "[지침]\n"
        "- 후보 중에서 요청에 가장 적합한 문항을 추천하고, 학년·단원·난이도·정답률 근거로 이유를 설명하세요.\n"
        "- 각 추천에 대해 먼저 익혀야 할 선수개념을 함께 안내하세요.\n"
        "- 후보에 없는 문항을 지어내지 마세요. 반드시 위 목록 안에서만 고르세요.\n"
        "- 한국어로, 교사가 바로 활용할 수 있도록 간결하게 답하세요.\n"
    )


def generate_answer(query: str, recommendations: list) -> str:
    if not recommendations:
        return "조건에 맞는 문항을 찾지 못했습니다."
    return generate(build_prompt(query, recommendations))
