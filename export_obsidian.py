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

    html_doc = render_graph_html(concepts, edges)   # 인터랙티브(확대·이동·마우스오버)
    svg_doc = render_graph_svg(concepts, edges)      # README 첨부용 정적 이미지

    # 웹 랜딩(public/index.html) = 인터랙티브 그래프. 저장소 루트에도 graph.html로 둔다.
    for path in (config.GRAPH_HTML_PATH,
                 os.path.join(config.PROJECT_DIR, "public", "index.html")):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_doc)
    # README 첨부용 정적 SVG
    assets_dir = os.path.join(config.PROJECT_DIR, "docs", "assets")
    os.makedirs(assets_dir, exist_ok=True)
    with open(os.path.join(assets_dir, "concept-graph.svg"), "w", encoding="utf-8") as f:
        f.write(svg_doc)

    print(f"볼트 → {config.VAULT_DIR}")
    print(f"  개념 {stats['concepts']} · 단원 {stats['units']} · 대표문항 {stats['items']}")
    print(f"그래프 → graph.html · public/index.html(인터랙티브) · docs/assets/concept-graph.svg "
          f"(개념 {len(concepts)} · 간선 {len(edges)})")


if __name__ == "__main__":
    main()
