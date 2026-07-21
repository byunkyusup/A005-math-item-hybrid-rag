"""개념·단원·문항을 Obsidian 볼트(markdown) + graph.html로 내보낸다.

- 개념 노트: frontmatter(학년·단원·IRT·정답률) + 설명 + [[선수개념]]/[[후속개념]]/[[대표문항]]
- 단원 MOC: 대단원별 개념 링크 모음
- 문항 노트: 개념당 대표문항(난이도 상/중/하 커버, 상한 REP_ITEMS_PER_CONCEPT)
- graph.html: 라이브러리 없는 단독 force-directed 뷰(개념=노드, 선후관계=간선)
파일명·위키링크에 tag 접두를 붙여 동명 개념 충돌을 방지한다.
"""

import json
import os

from src import config

_BAD = '/\\:*?"<>|[]#^'


def _safe(name: str) -> str:
    for ch in _BAD:
        name = name.replace(ch, " ")
    return " ".join(name.split()).strip()


def concept_filename(tag: str, name: str) -> str:
    return f"{tag} {_safe(name)}.md"


def concept_link(tag: str, name: str) -> str:
    return f"[[{tag} {_safe(name)}]]"


def _rep_items(items: list) -> list:
    """난이도 밴드(상/중/하)를 고루 커버하는 대표문항 선별."""
    groups: dict = {"상": [], "중": [], "하": []}
    for it in items:
        groups.get(it.get("band", "중"), groups["중"]).append(it)
    out: list = []
    order = ["하", "중", "상"]
    idx = 0
    while len(out) < config.REP_ITEMS_PER_CONCEPT:
        band = order[idx % 3]
        if groups[band]:
            out.append(groups[band].pop(0))
        elif all(not groups[b] for b in order):
            break
        idx += 1
    return out


def concept_note(concept: dict, graph, items_by_tag: dict) -> str:
    c = concept
    ch = c.get("chapter", {})
    rate = c.get("correct_rate")
    fm = [
        "---",
        f"tag: {c['tag']}",
        f"grade: {c.get('grade', '')}",
        f"semester: {c.get('semester', '')}",
        f"대단원: {ch.get('대', '')}",
        f"중단원: {ch.get('중', '')}",
        f"소단원: {ch.get('소', '')}",
        f"성취기준: {c.get('achievement', '')}",
        f"avg_b: {c.get('avg_b', '')}",
        f"band: {c.get('band', '')}",
        f"correct_rate: {rate if rate is not None else ''}",
        f"item_count: {c.get('item_count', 0)}",
        "---",
    ]
    lines = ["\n".join(fm), "", f"# {c.get('name', '')}", "", c.get("description", "")]

    def _links(tags):
        out = []
        for t in tags:
            oc = graph.concept(t)
            if oc:
                out.append(f"- {concept_link(t, oc.get('name', ''))}")
        return out or ["- (없음)"]

    lines += ["", "## 선수개념", *_links(graph.prereqs(c["tag"]))]
    lines += ["", "## 후속개념", *_links(graph.successors(c["tag"]))]

    lines += ["", "## 대표문항"]
    reps = _rep_items(list(items_by_tag.get(c["tag"], [])))
    if reps:
        for it in reps:
            r = it.get("correct_rate")
            r_str = f"{r:.1f}%" if r is not None else "-"
            lines.append(f"- [[{it['assessmentItemID']}]] (난이도 {it.get('band', '')}, 정답률 {r_str})")
    else:
        lines.append("- (없음)")

    lines += ["", "## 단원", f"[[대단원 {_safe(ch.get('대', ''))}]]", ""]
    return "\n".join(lines)


def item_note(item: dict, concept: dict) -> str:
    rate = item.get("correct_rate")
    fm = [
        "---",
        f"assessmentItemID: {item['assessmentItemID']}",
        f"grade: {item.get('grade', '')}",
        f"band: {item.get('band', '')}",
        f"b: {item.get('b', '')}",
        f"a: {item.get('a', '')}",
        f"c: {item.get('c', '')}",
        f"correct_rate: {rate if rate is not None else ''}",
        f"attempts: {item.get('attempts', 0)}",
        "---",
    ]
    name = (concept or {}).get("name", "")
    tag = (concept or {}).get("tag", "")
    body = [
        "\n".join(fm), "",
        f"# 문항 {item['assessmentItemID']}", "",
        f"개념: {concept_link(tag, name)}" if tag else "개념: (미상)",
        f"난이도 밴드: {item.get('band', '')} (b={item.get('b')})",
        f"실측 정답률: {rate if rate is not None else '-'}", "",
    ]
    return "\n".join(body)


def write_vault(concepts: dict, items_by_tag: dict, graph, vault_dir: str) -> dict:
    c_dir = os.path.join(vault_dir, "concepts")
    u_dir = os.path.join(vault_dir, "units")
    i_dir = os.path.join(vault_dir, "items")
    for d in (c_dir, u_dir, i_dir):
        os.makedirs(d, exist_ok=True)

    units: dict = {}
    n_items = 0
    for tag, c in concepts.items():
        with open(os.path.join(c_dir, concept_filename(tag, c.get("name", ""))),
                  "w", encoding="utf-8") as f:
            f.write(concept_note(c, graph, items_by_tag))
        units.setdefault(c.get("chapter", {}).get("대", "미분류"), []).append(c)
        for it in _rep_items(list(items_by_tag.get(tag, []))):
            with open(os.path.join(i_dir, f"{it['assessmentItemID']}.md"),
                      "w", encoding="utf-8") as f:
                f.write(item_note(it, c))
            n_items += 1

    for unit, clist in units.items():
        lines = [f"# 대단원 {unit}", ""]
        for c in sorted(clist, key=lambda x: x.get("grade", "")):
            lines.append(f"- {concept_link(c['tag'], c.get('name', ''))} "
                         f"({c.get('grade', '')}, 난이도 {c.get('band', '')})")
        with open(os.path.join(u_dir, f"대단원 {_safe(unit)}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    return {"concepts": len(concepts), "units": len(units), "items": n_items}


# --------------------------------------------------------------------------- #
# graph.html — 단독 force-directed 뷰 (외부 라이브러리 없음)
# --------------------------------------------------------------------------- #
_GRADE_HUE = {"초1": 10, "초2": 40, "초3": 70, "초4": 110, "초5": 150,
              "초6": 190, "중1": 230, "중2": 270, "중3": 310}


def render_graph_html(concepts: dict, edges: list, width: int = 1200, height: int = 800,
                      iterations: int = 200) -> str:
    """인터랙티브 그래프 HTML. 레이아웃 좌표를 미리 계산해 심어, 브라우저는
    물리연산 없이 그리기 + 확대/이동/마우스오버만 처리한다(912노드도 즉시 렌더)."""
    tags, pos, links = _compute_layout(concepts, edges, width, height, iterations)
    nodes = [
        {"x": round(pos[i][0], 1), "y": round(pos[i][1], 1),
         "label": concepts[t].get("name", t), "grade": concepts[t].get("grade", ""),
         "hue": _GRADE_HUE.get(concepts[t].get("grade", ""), 0)}
        for i, t in enumerate(tags)
    ]
    link_json = [{"source": a, "target": b} for a, b in links]
    data = json.dumps({"nodes": nodes, "links": link_json, "w": width, "h": height},
                      ensure_ascii=False).replace("<", "\\u003c")
    return _GRAPH_TEMPLATE.replace("__DATA__", data)


def _compute_layout(concepts: dict, edges: list, width: int, height: int, iterations: int):
    """Fruchterman-Reingold 레이아웃. 난수 없이 인덱스 기반 초기 배치(재현 가능).

    반환: (tags, pos, links) — pos[i]=[x,y], links=[(i,j), ...].
    SVG(정적)와 HTML(인터랙티브)이 동일 좌표를 공유한다.
    """
    import math

    tags = [t for t in concepts]
    idx = {t: i for i, t in enumerate(tags)}
    links = [(idx[a], idx[b]) for a, b in edges if a in idx and b in idx]
    n = len(tags)
    if n == 0:
        return tags, [], links

    # 결정적 초기 배치(원형 나선)
    pos = []
    for i in range(n):
        ang = i * 2.399963  # 황금각
        r = (i / n) ** 0.5 * min(width, height) * 0.45
        pos.append([width / 2 + r * math.cos(ang), height / 2 + r * math.sin(ang)])

    k = math.sqrt(width * height / n)  # 이상 거리
    temp = width / 10.0
    for _ in range(iterations):
        disp = [[0.0, 0.0] for _ in range(n)]
        for i in range(n):
            xi, yi = pos[i]
            for j in range(i + 1, n):
                dx, dy = xi - pos[j][0], yi - pos[j][1]
                d = math.hypot(dx, dy) or 0.01
                f = k * k / d
                ux, uy = dx / d * f, dy / d * f
                disp[i][0] += ux; disp[i][1] += uy
                disp[j][0] -= ux; disp[j][1] -= uy
        for a, b in links:
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            d = math.hypot(dx, dy) or 0.01
            f = d * d / k
            ux, uy = dx / d * f, dy / d * f
            disp[a][0] -= ux; disp[a][1] -= uy
            disp[b][0] += ux; disp[b][1] += uy
        for i in range(n):
            dx, dy = disp[i]
            d = math.hypot(dx, dy) or 0.01
            pos[i][0] += dx / d * min(d, temp)
            pos[i][1] += dy / d * min(d, temp)
            pos[i][0] = min(width - 12, max(12, pos[i][0]))
            pos[i][1] = min(height - 12, max(12, pos[i][1]))
        temp *= 0.97
    return tags, pos, links


def render_graph_svg(concepts: dict, edges: list, width: int = 1200, height: int = 800,
                     iterations: int = 200) -> str:
    """정적 SVG 그래프(브라우저 불필요, README 첨부용)."""
    tags, pos, links = _compute_layout(concepts, edges, width, height, iterations)
    n = len(tags)
    if n == 0:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"></svg>'

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#0f1116"/>',
        '<g stroke="#ffffff22" stroke-width="1">',
    ]
    for a, b in links:
        parts.append(f'<line x1="{pos[a][0]:.1f}" y1="{pos[a][1]:.1f}" '
                     f'x2="{pos[b][0]:.1f}" y2="{pos[b][1]:.1f}"/>')
    parts.append("</g><g>")
    for i, t in enumerate(tags):
        hue = _GRADE_HUE.get(concepts[t].get("grade", ""), 0)
        parts.append(f'<circle cx="{pos[i][0]:.1f}" cy="{pos[i][1]:.1f}" r="4" '
                     f'fill="hsl({hue},70%,60%)"/>')
    parts.append("</g>")
    # 학년 색 범례
    lx, ly = 16, 24
    for g, hue in _GRADE_HUE.items():
        parts.append(f'<circle cx="{lx}" cy="{ly}" r="5" fill="hsl({hue},70%,60%)"/>'
                     f'<text x="{lx + 10}" y="{ly + 4}" fill="#ccc" font-size="12">{g}</text>')
        ly += 20
    parts.append("</svg>")
    return "\n".join(parts)


_GRAPH_TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>수학 개념 선후관계 그래프</title>
<style>
 html,body{margin:0;height:100%;overflow:hidden;background:#0f1116;color:#e6e6e6;font-family:system-ui,sans-serif}
 #hud{position:fixed;top:10px;left:12px;font-size:13px;opacity:.85;z-index:2;pointer-events:none}
 #legend{position:fixed;top:10px;right:12px;font-size:12px;z-index:2;background:#0009;padding:8px 10px;border-radius:8px}
 #legend div{display:flex;align-items:center;gap:6px;margin:2px 0}
 #legend i{width:10px;height:10px;border-radius:50%;display:inline-block}
 #tip{position:fixed;padding:5px 9px;background:#000d;border:1px solid #ffffff33;border-radius:6px;font-size:12px;pointer-events:none;display:none;z-index:3;max-width:280px}
 canvas{display:block;cursor:grab}
</style></head><body>
<div id="hud">수학 개념 선후관계 그래프 · 노드=개념(학년별 색), 간선=선수→후속 · 휠=확대 · 드래그=이동 · 마우스오버=상세</div>
<div id="legend"></div>
<div id="tip"></div>
<canvas id="c"></canvas>
<script id="graph-data" type="application/json">__DATA__</script>
<script>
const G=JSON.parse(document.getElementById('graph-data').textContent);
const N=G.nodes,L=G.links;
const cv=document.getElementById('c'),ctx=cv.getContext('2d'),tip=document.getElementById('tip');
let W,H,scale=1,ox=0,oy=0;
const adj=N.map(()=>new Set());
for(const l of L){adj[l.source].add(l.target);adj[l.target].add(l.source);}
function fit(){W=cv.width=innerWidth;H=cv.height=innerHeight;
 const s=Math.min(W/G.w,H/G.h)*0.92;scale=s;ox=(W-G.w*s)/2;oy=(H-G.h*s)/2;}
fit();addEventListener('resize',()=>{fit();draw();});
const sx=p=>p.x*scale+ox, sy=p=>p.y*scale+oy;
let hover=-1,dragNode=-1,pan=null;
function draw(){
 ctx.clearRect(0,0,W,H);
 ctx.lineWidth=1;
 for(const l of L){const hot=hover>=0&&(l.source===hover||l.target===hover);
   ctx.strokeStyle=hot?'#ffd54aaa':'#ffffff18';ctx.beginPath();
   ctx.moveTo(sx(N[l.source]),sy(N[l.source]));ctx.lineTo(sx(N[l.target]),sy(N[l.target]));ctx.stroke();}
 for(let i=0;i<N.length;i++){const n=N[i];
   const near=hover>=0&&(i===hover||adj[hover].has(i));
   const r=i===hover?8:(near?6:4);
   ctx.globalAlpha=(hover<0||near)?1:0.3;
   ctx.beginPath();ctx.arc(sx(n),sy(n),r,0,7);ctx.fillStyle='hsl('+n.hue+',70%,60%)';ctx.fill();
   if(i===hover){ctx.lineWidth=2;ctx.strokeStyle='#fff';ctx.stroke();ctx.lineWidth=1;}
   ctx.globalAlpha=1;}
}
function pick(mx,my){let best=-1,bd=11;
 for(let i=0;i<N.length;i++){const d=Math.hypot(sx(N[i])-mx,sy(N[i])-my);if(d<bd){bd=d;best=i;}}return best;}
cv.addEventListener('mousemove',e=>{const mx=e.clientX,my=e.clientY;
 if(dragNode>=0){N[dragNode].x=(mx-ox)/scale;N[dragNode].y=(my-oy)/scale;draw();return;}
 if(pan){ox=pan.ox+(mx-pan.x);oy=pan.oy+(my-pan.y);draw();return;}
 const h=pick(mx,my);if(h!==hover){hover=h;draw();}
 if(h>=0){const n=N[h];tip.style.display='block';tip.style.left=(mx+12)+'px';tip.style.top=(my+12)+'px';
   tip.innerHTML='<b>'+n.label+'</b><br>학년: '+n.grade+' · 선후연결 '+adj[h].size+'개';}
 else tip.style.display='none';});
cv.addEventListener('mousedown',e=>{const h=pick(e.clientX,e.clientY);
 if(h>=0)dragNode=h;else{pan={x:e.clientX,y:e.clientY,ox,oy};cv.style.cursor='grabbing';}});
addEventListener('mouseup',()=>{dragNode=-1;pan=null;cv.style.cursor='grab';});
cv.addEventListener('wheel',e=>{e.preventDefault();const f=e.deltaY<0?1.1:0.9,mx=e.clientX,my=e.clientY;
 ox=mx-(mx-ox)*f;oy=my-(my-oy)*f;scale*=f;draw();},{passive:false});
const seen={};for(const n of N)seen[n.grade]=n.hue;
document.getElementById('legend').innerHTML=Object.keys(seen).sort().map(g=>
 '<div><i style="background:hsl('+seen[g]+',70%,60%)"></i>'+g+'</div>').join('');
draw();
</script></body></html>"""
