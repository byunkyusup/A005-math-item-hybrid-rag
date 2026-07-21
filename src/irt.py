"""IRT 기반 난이도 밴드·질의 난이도 파싱·θ 적합도 (순수 함수, 외부 의존 없음).

- band(b): IRT 난이도 모수 b를 상/중/하로 이산화. b가 클수록 어렵다.
- parse_query_difficulty(text): 질의에서 원하는 난이도 의도를 추출.
- fit_score(b, band, theta): 재랭킹용 적합도. theta(학습자 능력치)가 있으면
  능력치에 가까운 난이도를, 없으면 요청 밴드 일치를 선호한다.
"""

from src import config

_HARD_KW = ("어려운", "고난도", "난도 상", "상난이도", "심화", "어렵", "고난이도")
_EASY_KW = ("쉬운", "기초", "쉽", "저난도", "하난이도")
_MID_KW = ("보통", "중난도", "중간")


def band(b: float, hard: float | None = None, easy: float | None = None) -> str:
    if hard is None:
        hard = config.B_HARD
    if easy is None:
        easy = config.B_EASY
    if b >= hard:
        return "상"
    if b <= easy:
        return "하"
    return "중"


def parse_query_difficulty(text: str) -> str | None:
    t = text.lower()
    if any(k in t for k in _HARD_KW):
        return "상"
    if any(k in t for k in _EASY_KW):
        return "하"
    if any(k in t for k in _MID_KW):
        return "중"
    return None


def fit_score(item_b: float, target_band: str | None = None,
              theta: float | None = None) -> float:
    """0..1 적합도. theta 우선, 없으면 target_band, 둘 다 없으면 중립 0.5."""
    if theta is not None:
        return 1.0 / (1.0 + abs(item_b - theta))
    if target_band is not None:
        return 1.0 if band(item_b) == target_band else 0.3
    return 0.5
