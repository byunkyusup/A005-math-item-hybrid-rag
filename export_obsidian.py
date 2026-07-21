"""카탈로그 → Obsidian 볼트(vault/) + graph.html 내보내기.

사용: python export_obsidian.py
전제: build_catalog.py 로 concepts/items/edges.json 생성 완료.
"""

import json
import os
import sys

from src import config
from src.corpus import load_items_by_tag
from src.knowledge_graph import KnowledgeGraph
from src.obsidian_export import render_graph_html, render_graph_svg, write_vault


def _load(path, err):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[오류] {err}", file=sys.stderr)
        sys.exit(1)


def main():
    concepts = _load(config.CONCEPTS_PATH, "카탈로그가 없습니다. 먼저 `python build_catalog.py`.")
    edges = _load(config.EDGES_PATH, "카탈로그가 없습니다. 먼저 `python build_catalog.py`.")
    items_by_tag = load_items_by_tag()
    graph = KnowledgeGraph(concepts, edges)

    stats = write_vault(concepts, items_by_tag, graph, config.VAULT_DIR)

    html_doc = render_graph_html(concepts, edges)
    svg_doc = render_graph_svg(concepts, edges)

    # 웹 랜딩(public/index.html): 미리 계산된 정적 SVG를 인라인 → JS/연산 없이 즉시 렌더.
    index_doc = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>수학 개념 선후관계 그래프</title>"
        "<style>html,body{margin:0;background:#0f1116;color:#e6e6e6;"
        "font-family:system-ui,sans-serif}header{padding:14px 18px}"
        "h1{font-size:18px;margin:0}p{margin:6px 0 0;opacity:.85;font-size:13px}"
        "a{color:#8ab4ff}svg{display:block;width:100%;height:auto}</style></head>"
        "<body><header><h1>수학 개념 선후관계 그래프</h1>"
        "<p>912개념 · 1,633 선후간선 · 학년별 색 · AIHub #27752 실데이터 · "
        '<a href="./graph.html">인터랙티브(드래그) 버전 →</a></p></header>'
        + svg_doc + "</body></html>"
    )

    # 인터랙티브 graph.html (저장소 루트) + 웹 배포용 public/{index.html, graph.html}
    with open(config.GRAPH_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_doc)
    public_dir = os.path.join(config.PROJECT_DIR, "public")
    os.makedirs(public_dir, exist_ok=True)
    with open(os.path.join(public_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_doc)
    with open(os.path.join(public_dir, "graph.html"), "w", encoding="utf-8") as f:
        f.write(html_doc)
    # README 첨부용 정적 SVG
    assets_dir = os.path.join(config.PROJECT_DIR, "docs", "assets")
    os.makedirs(assets_dir, exist_ok=True)
    with open(os.path.join(assets_dir, "concept-graph.svg"), "w", encoding="utf-8") as f:
        f.write(svg_doc)

    print(f"볼트 → {config.VAULT_DIR}")
    print(f"  개념 {stats['concepts']} · 단원 {stats['units']} · 대표문항 {stats['items']}")
    print(f"그래프 → graph.html · public/index.html · docs/assets/concept-graph.svg "
          f"(개념 {len(concepts)} · 간선 {len(edges)})")


if __name__ == "__main__":
    main()
