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

# --- BM25 하이퍼파라미터 ---
BM25_K1 = 1.5
BM25_B = 0.75

# --- 경로 ---
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(_SRC_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
ITEMS_PATH = os.path.join(DATA_DIR, "items.json")
RESPONSES_PATH = os.path.join(DATA_DIR, "responses.json")
EMBED_CACHE_PATH = os.path.join(DATA_DIR, "embeddings.json")
