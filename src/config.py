"""중앙 설정값. Ollama 엔드포인트·모델명, 검색 파라미터, 데이터 경로."""

import os

# --- Ollama ---
OLLAMA_HOST = "http://localhost:11434"
# 임베딩 모델: bge-m3는 다국어(한국어 포함) 지원으로 의역 질의에 강하다.
# nomic-embed-text(768d)는 영어 위주라 한국어 의미 검색이 약하다 — README 비교 참고.
EMBED_MODEL = "bge-m3"             # 1024차원, 다국어 임베딩
GEN_MODEL = "qwen2.5:3b"           # 답변 생성 (다국어, 한국어 양호)
EMBED_DIM = 1024

# --- 검색 파라미터 ---
TOP_K_SPARSE = 30   # BM25 1차 후보 수
TOP_K_DENSE = 30    # 임베딩 1차 후보 수
RRF_K = 60          # RRF 상수 (관례적으로 60)
FINAL_K = 5         # 최종적으로 LLM에 넘길 문항 수
TOP_CONCEPTS = 8    # 문항 확장 전 상위 개념 수

# --- BM25 하이퍼파라미터 ---
BM25_K1 = 1.5
BM25_B = 0.75

# --- IRT 난이도 밴드 / θ 재랭킹 ---
B_HARD = 0.5        # IRT 난이도 b 임계 (b 클수록 어려움)
B_EASY = -0.5
W_SEARCH = 0.6      # 재랭킹: 검색 순위 가중치
W_FIT = 0.4         # 재랭킹: 난이도·θ 적합도 가중치
REP_ITEMS_PER_CONCEPT = 5   # Obsidian 개념당 대표문항 상한

# --- 경로 ---
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(_SRC_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
# 원천(AIHub 다운로드본) 경로 — 환경변수로 override 가능.
RAW_DATA_DIR = os.environ.get(
    "MATH_DATA_DIR",
    "/Users/pablo/Downloads/수학분야 학습자 역량 측정 데이터",
)
# ETL 산출 카탈로그
CONCEPTS_PATH = os.path.join(DATA_DIR, "concepts.json")
ITEMS_PATH = os.path.join(DATA_DIR, "items.json")
EDGES_PATH = os.path.join(DATA_DIR, "edges.json")
LEARNERS_PATH = os.path.join(DATA_DIR, "learners.json")
EMBED_CACHE_PATH = os.path.join(DATA_DIR, "embeddings.json")
# Obsidian 출력
VAULT_DIR = os.path.join(PROJECT_DIR, "vault")
GRAPH_HTML_PATH = os.path.join(PROJECT_DIR, "graph.html")

# 난이도 밴드 임계 — build_catalog.py가 실제 b 분포 분위수(33/66%)로 산출해 저장.
# 파일이 있으면 그 값으로 B_HARD/B_EASY를 덮어써 상/중/하 분류를 데이터에 맞춘다.
THRESHOLDS_PATH = os.path.join(DATA_DIR, "thresholds.json")


def _load_thresholds():
    import json
    try:
        with open(THRESHOLDS_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return float(d["b_hard"]), float(d["b_easy"])
    except (OSError, KeyError, ValueError, TypeError):
        return B_HARD, B_EASY


B_HARD, B_EASY = _load_thresholds()
