"""Hybrid RAG 질의 CLI.

사용 예:
  python query.py "초등 3학년 분수 어려운 문항 추천해줘"
  python query.py --mode sparse "일차방정식 단답형 문항"
  python query.py --no-gen "피타고라스 정리 정답률 낮은 문항"

옵션:
  --mode {hybrid,sparse,dense}  검색 방식 (기본 hybrid)
  --k N                          최종 문항 수 (기본 config.FINAL_K)
  --no-gen                       LLM 생성 생략(검색 결과만 출력)
"""

import argparse
import json
import sys

from src import config
from src.corpus import load_corpus
from src.generator import generate_answer
from src.retriever import HybridRetriever


def load_embeddings():
    try:
        with open(config.EMBED_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)["vectors"]
    except FileNotFoundError:
        print("[오류] 임베딩 캐시가 없습니다. 먼저 `python build_index.py`를 실행하세요.",
              file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="수학 문항 추천 Hybrid RAG")
    parser.add_argument("query", help="자연어 질의")
    parser.add_argument("--mode", choices=["hybrid", "sparse", "dense"], default="hybrid")
    parser.add_argument("--k", type=int, default=config.FINAL_K)
    parser.add_argument("--no-gen", action="store_true", help="LLM 생성 생략")
    args = parser.parse_args()

    items, doc_texts, _embed_texts = load_corpus()
    embeddings = load_embeddings()
    retriever = HybridRetriever(doc_texts, embeddings)

    hits = retriever.retrieve(args.query, mode=args.mode, final_k=args.k)
    retrieved = [items[doc_id] for doc_id, _ in hits]

    print(f"\n=== 검색 결과 (mode={args.mode}, {len(retrieved)}건) ===")
    for rank, ((doc_id, score), item) in enumerate(zip(hits, retrieved), 1):
        rate = item.get("observedCorrectRate")
        rate_str = f"{rate:.1f}%" if rate is not None else "-"
        print(f"{rank}. [{item['assessmentItemID']}] {item['grade']} "
              f"{item['area']} > {item['concept']} | {item['itemType']} | "
              f"난이도 {item['difficultyGrade']}(b={item['difficulty']['b']}) | "
              f"정답률 {rate_str} | score={score:.4f}")

    if args.no_gen:
        return

    print("\n=== LLM 추천 (Ollama) ===")
    print(generate_answer(args.query, retrieved))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        sys.exit(1)
