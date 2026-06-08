"""한국어 친화 토크나이저 (형태소 분석기 의존성 없이 BM25용 토큰 생성).

한국어는 어간/조사가 붙어 있어 공백 분리만으로는 recall이 떨어진다.
어절 토큰에 더해 한글 문자 bigram을 추가로 생성해 부분 일치를 보강한다.
예) "분수의" -> ["분수의", "분수", "수의"]  →  질의 "분수"가 매칭됨.
"""

import re

# 숫자 / 영문 / 한글 덩어리를 각각 분리
_TOKEN_RE = re.compile(r"[0-9]+|[a-zA-Z]+|[가-힣]+")


def _char_bigrams(word):
    return [word[i : i + 2] for i in range(len(word) - 1)]


def tokenize(text):
    """텍스트를 BM25용 토큰 리스트로 변환."""
    tokens = []
    for chunk in _TOKEN_RE.findall(text.lower()):
        is_hangul = "가" <= chunk[0] <= "힣"
        if is_hangul and len(chunk) > 2:
            tokens.append(chunk)                 # 어절 원형
            tokens.extend(_char_bigrams(chunk))  # 문자 bigram 보강
        else:
            tokens.append(chunk)
    return tokens
