"""예시 질의들의 Hybrid RAG 파이프라인을 미리 계산해 정적 데모 페이지를 만든다.

각 질의에 대해 BM25 ∥ dense → RRF → IRT/θ 재랭킹 → LLM 답변을 모두 캡처해
data/demo.json 과 public/index.html(파이프라인 데모)을 생성한다.
전제: build_catalog.py + build_index.py 완료, 로컬 Ollama 실행 중.

사용: python build_demo.py
"""

import json
import os
import sys

from src import config
from src.corpus import load_corpus, load_items_by_tag
from src.fusion import reciprocal_rank_fusion
from src.generator import generate_answer
from src.knowledge_graph import KnowledgeGraph
from src.ollama_client import embed
from src.pipeline_demo import render_demo_html
from src.recommender import recommend
from src.retriever import HybridRetriever
from src.tokenizer import tokenize

# 어휘 질의 / 의역 질의 / 난이도·개인화를 두루 보여주는 예시
QUERIES = [
    {"q": "분수 크기 비교 쉬운 문항", "grade": "초3", "difficulty": "하"},
    {"q": "두 도형이 크기만 다르고 모양이 완전히 같은지 따지는 문제", "grade": None, "difficulty": None},
    {"q": "곱셈 공식을 이용한 두 수의 곱 계산", "grade": None, "difficulty": None},
    {"q": "피자를 똑같이 나눈 조각을 수로 나타내는 방법", "grade": None, "difficulty": None},
    {"q": "삼각형의 넓이 구하기", "grade": None, "difficulty": None},
    {"q": "일차방정식 어려운 문항", "grade": None, "difficulty": "상"},
]

TOPN = 6


def _names(concept_list, hits):
    out = []
    for doc_id, score in hits[:TOPN]:
        c = concept_list[doc_id]
        out.append({"name": c["name"], "grade": c["grade"], "score": round(score, 4)})
    return out


def main():
    concept_list, doc_texts, _ = load_corpus()
    with open(config.EMBED_CACHE_PATH, encoding="utf-8") as f:
        embeddings = json.load(f)["vectors"]
    concepts = {c["tag"]: c for c in concept_list}
    tags = [c["tag"] for c in concept_list]
    items_by_tag = load_items_by_tag()
    with open(config.EDGES_PATH, encoding="utf-8") as f:
        edges = json.load(f)
    graph = KnowledgeGraph(concepts, edges)
    retr = HybridRetriever(doc_texts, embeddings)

    demo = []
    for spec in QUERIES:
        q = spec["q"]
        sp = retr.bm25.search(tokenize(q), TOPN)
        dn = retr.dense.search(embed(q), TOPN)
        fused = reciprocal_rank_fusion([sp, dn], k=config.RRF_K, top_k=TOPN)

        sp_names = {concept_list[d]["name"] for d, _ in sp}
        dn_names = {concept_list[d]["name"] for d, _ in dn}
        fused_out = []
        for doc_id, _ in fused:
            nm = concept_list[doc_id]["name"]
            src = "both" if (nm in sp_names and nm in dn_names) else ("bm25" if nm in sp_names else "dense")
            fused_out.append({"name": nm, "grade": concept_list[doc_id]["grade"], "from": src})

        recs = recommend(q, retr, concepts, items_by_tag, graph, mode="hybrid",
                         grade=spec["grade"], difficulty=spec["difficulty"], theta=None,
                         k=4, concept_tags=tags)
        final = [{"id": r["item"]["assessmentItemID"], "concept": (r["concept"] or {}).get("name", ""),
                  "grade": r["item"].get("grade", ""), "band": r["item"].get("band", ""),
                  "cr": r["item"].get("correct_rate"), "prereqs": r.get("prereqs", [])}
                 for r in recs]
        answer = generate_answer(q, recs)

        demo.append({"q": q, "grade": spec["grade"], "difficulty": spec["difficulty"],
                     "bm25": _names(concept_list, sp), "dense": _names(concept_list, dn),
                     "fused": fused_out, "final": final, "answer": answer})
        print(f"  ✓ {q}", file=sys.stderr)

    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(os.path.join(config.DATA_DIR, "demo.json"), "w", encoding="utf-8") as f:
        json.dump(demo, f, ensure_ascii=False, indent=1)
    public_dir = os.path.join(config.PROJECT_DIR, "public")
    os.makedirs(public_dir, exist_ok=True)
    with open(os.path.join(public_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_demo_html(demo))
    print(f"완료: public/index.html · data/demo.json (예시 {len(demo)}건)")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"[오류] {exc}. 먼저 build_catalog.py / build_index.py 실행 + Ollama 필요.", file=sys.stderr)
        sys.exit(1)
