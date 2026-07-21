"""수학 문항 추천 Hybrid RAG 질의 CLI.

사용 예:
  python query.py "초등 3학년 분수 어려운 문항 추천해줘"
  python query.py --grade 초3 --difficulty 하 "분수 크기 비교"
  python query.py --learner 저성취 "곱셈 문항"
  python query.py --mode sparse --no-gen "원의 반지름"

옵션:
  --mode {hybrid,sparse,dense}  검색 방식 (기본 hybrid)
  --grade GRADE                 학년 필터 (예: 초3, 중1)
  --difficulty {상,중,하}        원하는 난이도 (미지정 시 질의에서 추론)
  --theta FLOAT                  학습자 능력치 직접 지정 (난이도 적합도 재랭킹)
  --learner LABEL_OR_ID          learners.json의 대표 학습자 theta 사용
  --k N                          최종 문항 수 (기본 config.FINAL_K)
  --no-gen                       LLM 생성 생략(검색 결과만)
"""

import argparse
import json
import sys

from src import config
from src.corpus import load_corpus, load_items_by_tag
from src.generator import generate_answer
from src.knowledge_graph import KnowledgeGraph
from src.recommender import recommend
from src.retriever import HybridRetriever


def _load_json(path, err):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[오류] {err}", file=sys.stderr)
        sys.exit(1)


def _resolve_theta(args, learners):
    if args.theta is not None:
        return args.theta
    if args.learner:
        for lid, info in learners.items():
            if args.learner in (lid, info.get("label")):
                return info["theta"]
        print(f"[경고] 학습자 '{args.learner}'를 찾지 못해 θ 없이 진행합니다.", file=sys.stderr)
    return None


def main():
    p = argparse.ArgumentParser(description="수학 문항 추천 Hybrid RAG")
    p.add_argument("query", help="자연어 질의")
    p.add_argument("--mode", choices=["hybrid", "sparse", "dense"], default="hybrid")
    p.add_argument("--grade", default=None)
    p.add_argument("--difficulty", choices=["상", "중", "하"], default=None)
    p.add_argument("--theta", type=float, default=None)
    p.add_argument("--learner", default=None)
    p.add_argument("--k", type=int, default=config.FINAL_K)
    p.add_argument("--no-gen", action="store_true")
    args = p.parse_args()

    concept_list, doc_texts, _ = load_corpus()
    embeddings = _load_json(config.EMBED_CACHE_PATH,
                            "임베딩 캐시가 없습니다. 먼저 `python build_index.py`.")["vectors"]
    items_by_tag = load_items_by_tag()
    edges = _load_json(config.EDGES_PATH, "카탈로그가 없습니다. 먼저 `python build_catalog.py`.")
    learners = _load_json(config.LEARNERS_PATH, "카탈로그가 없습니다. 먼저 `python build_catalog.py`.")

    concepts = {c["tag"]: c for c in concept_list}
    concept_tags = [c["tag"] for c in concept_list]
    graph = KnowledgeGraph(concepts, edges)
    retriever = HybridRetriever(doc_texts, embeddings)
    theta = _resolve_theta(args, learners)

    recs = recommend(
        args.query, retriever, concepts, items_by_tag, graph,
        mode=args.mode, grade=args.grade, difficulty=args.difficulty,
        theta=theta, k=args.k, concept_tags=concept_tags,
    )

    print(f"\n=== 추천 문항 (mode={args.mode}, {len(recs)}건) ===")
    for rank, r in enumerate(recs, 1):
        it, c = r["item"], r["concept"] or {}
        rate = it.get("correct_rate")
        rate_str = f"{rate:.1f}%" if rate is not None else "-"
        pre = ", ".join(r["prereqs"]) or "없음"
        print(f"{rank}. [{it['assessmentItemID']}] {it.get('grade','')} · {c.get('name','')} "
              f"| 난이도 {it.get('band','')}(b={it.get('b')}) | 정답률 {rate_str}")
        print(f"    선수개념: {pre}")

    if args.no_gen:
        return
    print("\n=== LLM 추천 (Ollama) ===")
    print(generate_answer(args.query, recs))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        sys.exit(1)
