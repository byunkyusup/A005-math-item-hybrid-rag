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


def render_graph_html(concepts: dict, edges: list, iterations: int = 120) -> str:
    """인터랙티브 3D 그래프 HTML. 3D 좌표를 미리 계산해 심고, 브라우저는
    회전·투영·마우스오버만 처리한다(외부 라이브러리 없음, 912노드도 부드러움)."""
    tags, pos, links = _compute_layout_3d(concepts, edges, iterations)
    nodes = []
    for i, t in enumerate(tags):
        c = concepts[t]
        nodes.append({
            "x": round(pos[i][0], 3), "y": round(pos[i][1], 3), "z": round(pos[i][2], 3),
            "label": c.get("name", t), "grade": c.get("grade", ""),
            "hue": _GRADE_HUE.get(c.get("grade", ""), 0),
            "sem": c.get("semester", ""), "unit": (c.get("chapter") or {}).get("대", ""),
            "band": c.get("band", ""), "cr": c.get("correct_rate"),
            "ic": c.get("item_count", 0),
        })
    link_json = [{"source": a, "target": b} for a, b in links]
    data = json.dumps({"nodes": nodes, "links": link_json},
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


def _compute_layout_3d(concepts: dict, edges: list, iterations: int):
    """3D Fruchterman-Reingold. 피보나치 구면 초기화 → 반발/인력 반복 →
    중심 정렬 + 단위 정규화(반지름 1). 반환: (tags, pos[[x,y,z]], links[(i,j)]).
    난수 없이 결정적. 정규화라 화면 clamp가 필요 없어 가장자리 눌림이 없다."""
    import math

    tags = [t for t in concepts]
    idx = {t: i for i, t in enumerate(tags)}
    links = [(idx[a], idx[b]) for a, b in edges if a in idx and b in idx]
    n = len(tags)
    if n == 0:
        return tags, [], links

    pos = []
    ga = math.pi * (1 + 5 ** 0.5)
    for i in range(n):
        phi = math.acos(1 - 2 * (i + 0.5) / n)
        theta = ga * i
        r = 0.3 + 0.7 * ((i % 7) / 6)  # 반지름 변주로 초기 겹침 완화
        pos.append([r * math.sin(phi) * math.cos(theta),
                    r * math.sin(phi) * math.sin(theta),
                    r * math.cos(phi)])

    k = 2.0 / (n ** (1.0 / 3.0))  # 정규화 공간 이상 거리
    temp = 0.3
    for _ in range(iterations):
        disp = [[0.0, 0.0, 0.0] for _ in range(n)]
        for i in range(n):
            xi, yi, zi = pos[i]
            for j in range(i + 1, n):
                dx, dy, dz = xi - pos[j][0], yi - pos[j][1], zi - pos[j][2]
                d = math.sqrt(dx * dx + dy * dy + dz * dz) or 0.001
                f = k * k / d
                ux, uy, uz = dx / d * f, dy / d * f, dz / d * f
                disp[i][0] += ux; disp[i][1] += uy; disp[i][2] += uz
                disp[j][0] -= ux; disp[j][1] -= uy; disp[j][2] -= uz
        for a, b in links:
            dx, dy, dz = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1], pos[a][2] - pos[b][2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz) or 0.001
            f = d * d / k
            ux, uy, uz = dx / d * f, dy / d * f, dz / d * f
            disp[a][0] -= ux; disp[a][1] -= uy; disp[a][2] -= uz
            disp[b][0] += ux; disp[b][1] += uy; disp[b][2] += uz
        for i in range(n):
            dx, dy, dz = disp[i]
            d = math.sqrt(dx * dx + dy * dy + dz * dz) or 0.001
            step = min(d, temp)
            pos[i][0] += dx / d * step
            pos[i][1] += dy / d * step
            pos[i][2] += dz / d * step
        temp *= 0.98

    cx = sum(p[0] for p in pos) / n
    cy = sum(p[1] for p in pos) / n
    cz = sum(p[2] for p in pos) / n
    maxr = max(math.sqrt((p[0] - cx) ** 2 + (p[1] - cy) ** 2 + (p[2] - cz) ** 2)
               for p in pos) or 1.0
    pos = [[(p[0] - cx) / maxr, (p[1] - cy) / maxr, (p[2] - cz) / maxr] for p in pos]
    return tags, pos, links


def render_graph_svg(concepts: dict, edges: list, width: int = 1200, height: int = 800,
                     iterations: int = 200) -> str:
    """정적 SVG 그래프(브라우저 불필요, README 첨부용). 2D 레이아웃."""
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
<title>수학 개념 선후관계 3D 지식그래프</title>
<style>
 :root{--card:rgba(20,24,33,.74);--line:rgba(255,255,255,.10)}
 html,body{margin:0;height:100%;overflow:hidden;color:#e6e6e6;
   font-family:'Pretendard',system-ui,-apple-system,sans-serif;
   background:radial-gradient(1200px 800px at 70% 20%,#161d2b 0%,#0b0d12 60%,#07080c 100%)}
 .card{position:fixed;z-index:2;background:var(--card);border:1px solid var(--line);
   border-radius:12px;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
   box-shadow:0 8px 30px rgba(0,0,0,.35)}
 #hud{top:14px;left:14px;padding:12px 14px;max-width:min(72vw,560px);pointer-events:none}
 #hud h1{margin:0;font-size:15px;font-weight:700;letter-spacing:-.01em}
 #hud p{margin:5px 0 0;font-size:12px;line-height:1.6;opacity:.72}
 #hud kbd{font:inherit;background:#ffffff14;border:1px solid var(--line);border-radius:4px;padding:0 5px}
 #legend{top:14px;right:14px;padding:10px 12px;font-size:12px;user-select:none}
 #legend b{display:block;margin:0 0 6px;font-size:11px;opacity:.6;font-weight:600;letter-spacing:.03em}
 #legend .row{display:flex;align-items:center;gap:7px;margin:2px 0;cursor:pointer;border-radius:6px;padding:1px 4px}
 #legend .row:hover{background:#ffffff12}
 #legend .row.off{opacity:.3}
 #legend i{width:10px;height:10px;border-radius:50%;display:inline-block;box-shadow:0 0 6px currentColor}
 #legend .hint{margin-top:6px;font-size:10px;opacity:.5}
 #tip{position:fixed;padding:8px 11px;background:var(--card);border:1px solid var(--line);
   border-radius:8px;font-size:12px;line-height:1.5;pointer-events:none;display:none;z-index:4;
   max-width:280px;backdrop-filter:blur(8px);box-shadow:0 8px 24px rgba(0,0,0,.4)}
 #tip b{font-size:13px}
 #panel{left:14px;bottom:14px;padding:14px 16px 16px;max-width:min(84vw,340px);display:none;z-index:3}
 #panel h2{margin:0 8px 10px 0;font-size:15px;letter-spacing:-.01em}
 #panel .grid{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;font-size:12px;line-height:1.6}
 #panel .k{opacity:.55}
 #panel .close{position:absolute;top:9px;right:11px;cursor:pointer;opacity:.6;font-size:15px;border:0;background:none;color:#fff}
 canvas{display:block;cursor:grab;touch-action:none;outline:none}
</style></head><body>
<div id="hud" class="card">
 <h1>수학 개념 선후관계 3D 지식그래프</h1>
 <p>912개념 · 1,633 선후간선 · 학년별 색 · AIHub #27752 실데이터<br>
 <kbd>드래그</kbd> 회전 · <kbd>휠</kbd> 확대 · <kbd>클릭</kbd> 상세 · <kbd>더블클릭</kbd> 초기화 · <kbd>방향키</kbd> 회전</p>
</div>
<div id="legend" class="card"></div>
<div id="panel" class="card"></div>
<div id="tip"></div>
<canvas id="c" tabindex="0" role="img" aria-label="수학 개념 912개의 학년별 선후관계 3D 지식그래프. 드래그로 회전, 방향키로 회전, 클릭으로 개념 상세."></canvas>
<script id="graph-data" type="application/json">__DATA__</script>
<script>
const G=JSON.parse(document.getElementById('graph-data').textContent);
const N=G.nodes,L=G.links;
const cv=document.getElementById('c'),ctx=cv.getContext('2d');
const tip=document.getElementById('tip'),panel=document.getElementById('panel');
const adj=N.map(()=>new Set());
for(const l of L){adj[l.source].add(l.target);adj[l.target].add(l.source);}
const deg=N.map((_,i)=>adj[i].size);
const hubs=new Set(N.map((_,i)=>i).sort((a,b)=>deg[b]-deg[a]).slice(0,14));   // 핵심 허브 라벨
const reduce=matchMedia('(prefers-reduced-motion:reduce)').matches;           // 접근성: 모션 최소화 존중
let W,H,cx,cy,R;
function fit(){W=cv.width=innerWidth;H=cv.height=innerHeight;cx=W/2;cy=H/2;R=Math.min(W,H)*0.42;}
fit();addEventListener('resize',fit);
let yaw=0.6,pitch=-0.35,dist=3.0,auto=!reduce,hover=-1,selected=-1;
const P=N.map(()=>({X:0,Y:0,Z:0}));
const active=new Set(N.map(n=>n.grade));   // 표시 중 학년(범례 필터)
const vis=i=>active.has(N[i].grade);
function project(){
 const cY=Math.cos(yaw),sY=Math.sin(yaw),cX=Math.cos(pitch),sX=Math.sin(pitch);
 for(let i=0;i<N.length;i++){const n=N[i];
   const x1=n.x*cY+n.z*sY, z1=-n.x*sY+n.z*cY, y1=n.y;
   const y2=y1*cX-z1*sX, z2=y1*sX+z1*cX;
   let depth=dist-z2; if(depth<0.1)depth=0.1;
   const s=R/depth; const p=P[i]; p.X=cx+x1*s; p.Y=cy+y2*s; p.Z=z2;}
}
const order=N.map((_,i)=>i);
function draw(){
 project();
 order.sort((a,b)=>P[a].Z-P[b].Z);
 ctx.clearRect(0,0,W,H);
 ctx.lineWidth=1;
 const fnode=hover>=0?hover:selected;
 for(const l of L){if(!vis(l.source)||!vis(l.target))continue;
   const hot=fnode>=0&&(l.source===fnode||l.target===fnode);
   ctx.strokeStyle=hot?'#ffd54abb':'#ffffff10';ctx.beginPath();
   ctx.moveTo(P[l.source].X,P[l.source].Y);ctx.lineTo(P[l.target].X,P[l.target].Y);ctx.stroke();}
 for(const i of order){if(!vis(i))continue;const n=N[i],p=P[i];
   const foc=fnode>=0?(i===fnode||adj[fnode].has(i)):true;
   const depth=dist-p.Z; let r=(i===fnode?5.5:(foc?3.2:2.6))*(2.4/depth); if(r<1.4)r=1.4;
   const dk=Math.max(0,Math.min(1,(p.Z+1)/2));
   ctx.globalAlpha=foc?(0.45+0.55*dk):0.12;
   ctx.beginPath();ctx.arc(p.X,p.Y,r,0,7);
   ctx.fillStyle='hsl('+n.hue+','+(55+20*dk)+'%,'+(45+18*dk)+'%)';ctx.fill();
   if(i===fnode){ctx.lineWidth=2;ctx.strokeStyle='#fff';ctx.stroke();ctx.lineWidth=1;}
   ctx.globalAlpha=1;}
 ctx.textAlign='center';ctx.font='11px system-ui,sans-serif';
 for(const i of order){if(!vis(i))continue;
   const show=(hubs.has(i)&&fnode<0)||i===fnode;
   if(!show)continue;const p=P[i],w=ctx.measureText(N[i].label).width;
   ctx.fillStyle='#000a';ctx.fillRect(p.X-w/2-4,p.Y-23,w+8,15);
   ctx.fillStyle='#fff';ctx.fillText(N[i].label,p.X,p.Y-12);}
}
function pick(mx,my){let best=-1,bd=11;
 for(let i=0;i<N.length;i++){if(!vis(i))continue;const d=Math.hypot(P[i].X-mx,P[i].Y-my);if(d<bd){bd=d;best=i;}}return best;}
function showPanel(i){selected=i;const n=N[i];const cr=(n.cr==null?'-':n.cr+'%');
 panel.style.display='block';
 panel.innerHTML='<button class="close" aria-label="닫기">×</button><h2>'+n.label+'</h2><div class="grid">'
  +'<span class="k">학년</span><span>'+n.grade+'</span>'
  +'<span class="k">학기</span><span>'+(n.sem||'-')+'</span>'
  +'<span class="k">대단원</span><span>'+(n.unit||'-')+'</span>'
  +'<span class="k">난이도</span><span>'+n.band+'</span>'
  +'<span class="k">평균 정답률</span><span>'+cr+'</span>'
  +'<span class="k">문항 수</span><span>'+n.ic+'개</span>'
  +'<span class="k">선후 연결</span><span>'+deg[i]+'개</span></div>';
 panel.querySelector('.close').onclick=()=>{panel.style.display='none';selected=-1;};
}
let drag=null,moved=false;
cv.addEventListener('mousedown',e=>{drag={x:e.clientX,y:e.clientY};moved=false;auto=false;cv.style.cursor='grabbing';});
addEventListener('mouseup',()=>{drag=null;cv.style.cursor='grab';});
cv.addEventListener('click',e=>{if(moved)return;const h=pick(e.clientX,e.clientY);
 if(h>=0)showPanel(h);else{selected=-1;panel.style.display='none';}});
cv.addEventListener('mousemove',e=>{const mx=e.clientX,my=e.clientY;
 if(drag){moved=true;yaw+=(mx-drag.x)*0.01;pitch+=(my-drag.y)*0.01;pitch=Math.max(-1.4,Math.min(1.4,pitch));drag={x:mx,y:my};return;}
 const h=pick(mx,my);hover=h;
 if(h>=0){const n=N[h];tip.style.display='block';tip.style.left=(mx+14)+'px';tip.style.top=(my+14)+'px';
   tip.innerHTML='<b>'+n.label+'</b><br>'+n.grade+' · 선후연결 '+deg[h]+'개 · 클릭=상세';}
 else tip.style.display='none';});
cv.addEventListener('wheel',e=>{e.preventDefault();dist*=e.deltaY<0?0.92:1.08;dist=Math.max(1.6,Math.min(7,dist));},{passive:false});
cv.addEventListener('dblclick',()=>{yaw=0.6;pitch=-0.35;dist=3.0;auto=!reduce;});
cv.addEventListener('keydown',e=>{const k=e.key;
 if(k==='ArrowLeft')yaw-=0.08;else if(k==='ArrowRight')yaw+=0.08;
 else if(k==='ArrowUp')pitch=Math.max(-1.4,pitch-0.08);else if(k==='ArrowDown')pitch=Math.min(1.4,pitch+0.08);
 else return;auto=false;e.preventDefault();});
cv.addEventListener('touchstart',e=>{if(e.touches[0]){drag={x:e.touches[0].clientX,y:e.touches[0].clientY};moved=false;auto=false;}},{passive:true});
cv.addEventListener('touchmove',e=>{if(drag&&e.touches[0]){e.preventDefault();const t=e.touches[0];moved=true;
 yaw+=(t.clientX-drag.x)*0.01;pitch+=(t.clientY-drag.y)*0.01;pitch=Math.max(-1.4,Math.min(1.4,pitch));
 drag={x:t.clientX,y:t.clientY};}},{passive:false});
cv.addEventListener('touchend',()=>{drag=null;});
// 범례 = 학년 표시/숨김 필터
const seen={};for(const n of N)seen[n.grade]=n.hue;
const lg=document.getElementById('legend');
lg.innerHTML='<b>학년 · 클릭=표시/숨김</b>'+Object.keys(seen).sort().map(g=>
 '<div class="row" data-g="'+g+'"><i style="background:hsl('+seen[g]+',70%,60%);color:hsl('+seen[g]+',70%,60%)"></i>'+g+'</div>').join('')
 +'<div class="hint">더블클릭 = 전체 다시 표시</div>';
lg.querySelectorAll('.row').forEach(el=>{
 el.onclick=()=>{const g=el.dataset.g;active.has(g)?active.delete(g):active.add(g);el.classList.toggle('off',!active.has(g));};
 el.ondblclick=()=>{Object.keys(seen).forEach(x=>active.add(x));lg.querySelectorAll('.row').forEach(r=>r.classList.remove('off'));};});
function loop(){if(auto&&!drag)yaw+=0.0025;draw();requestAnimationFrame(loop);}loop();
</script></body></html>"""
