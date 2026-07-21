"""Hybrid RAG 파이프라인 데모 페이지 렌더러.

미리 계산된 예시 질의들의 전체 파이프라인(BM25 ∥ dense → RRF → IRT/θ 재랭킹 → LLM)을
정적 HTML로 시각화한다. 런타임에 Ollama가 필요 없어 Vercel 정적 배포에 그대로 올린다.
"""

import json


def render_demo_html(demo: list) -> str:
    data = json.dumps(demo, ensure_ascii=False).replace("<", "\\u003c")
    return _TEMPLATE.replace("__DATA__", data)


_TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hybrid RAG 파이프라인 데모 · 수학 문항 추천</title>
<style>
 :root{--card:rgba(20,24,33,.7);--line:rgba(255,255,255,.1);--accent:#8ab4ff;
   --bm25:#5ec8a8;--dense:#c08bff;--both:#ffd54a}
 *{box-sizing:border-box}
 html,body{margin:0;color:#e6e6e6;font-family:'Pretendard',system-ui,-apple-system,sans-serif;
   background:radial-gradient(1200px 900px at 75% -10%,#161d2b 0%,#0b0d12 55%,#07080c 100%);min-height:100%}
 a{color:var(--accent)}
 .wrap{max-width:1180px;margin:0 auto;padding:26px 20px 60px}
 header h1{margin:0;font-size:22px;letter-spacing:-.02em}
 header p{margin:6px 0 0;opacity:.72;font-size:13px;line-height:1.6}
 .nav{margin-top:10px;font-size:13px}
 .chips{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0 8px}
 .chip{cursor:pointer;border:1px solid var(--line);background:#ffffff0d;color:#e6e6e6;
   padding:8px 13px;border-radius:999px;font-size:13px;transition:.15s}
 .chip:hover{background:#ffffff1a}
 .chip.on{background:var(--accent);color:#08101f;border-color:transparent;font-weight:600}
 .card{background:var(--card);border:1px solid var(--line);border-radius:14px;
   backdrop-filter:blur(8px);box-shadow:0 8px 30px rgba(0,0,0,.3)}
 .stage{padding:16px 18px;margin-top:16px}
 .stage h2{margin:0 0 3px;font-size:13px;letter-spacing:.02em;text-transform:uppercase;opacity:.65}
 .stage .sub{font-size:12px;opacity:.55;margin-bottom:12px}
 .qbox{font-size:17px;font-weight:600;letter-spacing:-.01em}
 .qmeta{margin-top:8px;font-size:12px;opacity:.7}
 .qmeta span{background:#ffffff14;border:1px solid var(--line);border-radius:6px;padding:2px 8px;margin-right:6px}
 .two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
 @media(max-width:680px){.two{grid-template-columns:1fr}}
 .col h3{margin:0 0 8px;font-size:13px;display:flex;align-items:center;gap:7px}
 .dot{width:9px;height:9px;border-radius:50%;display:inline-block}
 ol{margin:0;padding:0;list-style:none;counter-reset:r}
 li{counter-increment:r;display:flex;gap:9px;align-items:baseline;padding:5px 0;border-bottom:1px solid #ffffff08;font-size:13px}
 li::before{content:counter(r);opacity:.4;font-size:11px;min-width:14px}
 li .nm{flex:1}
 li .gr{opacity:.5;font-size:11px}
 li .sc{opacity:.45;font-size:11px;font-variant-numeric:tabular-nums}
 .badge{font-size:10px;padding:1px 6px;border-radius:5px;font-weight:600}
 .b-both{background:var(--both);color:#3a2c00}
 .b-bm25{background:var(--bm25);color:#04231a}
 .b-dense{background:var(--dense);color:#1e0a3a}
 .arrow{text-align:center;opacity:.4;font-size:20px;margin:4px 0}
 .items{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
 .item{border:1px solid var(--line);border-radius:11px;padding:12px 13px;background:#ffffff08}
 .item .cn{font-weight:600;font-size:14px;letter-spacing:-.01em}
 .item .mt{margin-top:7px;font-size:12px;opacity:.75;line-height:1.6}
 .item .pill{display:inline-block;font-size:11px;background:#ffffff14;border-radius:5px;padding:1px 7px;margin:2px 4px 0 0}
 .ans{white-space:pre-wrap;line-height:1.7;font-size:14px}
 .legend2{font-size:12px;opacity:.7;margin-top:6px}
 .legend2 b{font-weight:600}
</style></head><body><div class="wrap">
<header>
 <h1>Hybrid RAG 파이프라인 · 수학 문항 추천</h1>
 <p>자연어 질의가 <b>어휘 검색(BM25)</b>과 <b>의미 검색(bge-m3)</b>을 거쳐 <b>RRF로 병합</b>되고,
 <b>IRT 난이도·θ로 재랭킹</b>된 뒤 <b>로컬 LLM</b>이 근거와 함께 추천하는 과정을 보여줍니다.
 AIHub #27752 실데이터 · 미리 계산된 예시(정적).</p>
 <div class="nav"><a href="./graph.html">🕸 개념 선후관계 3D 지식그래프(검색 대상 코퍼스) 보기 →</a></div>
</header>
<div class="chips" id="chips"></div>
<div id="view"></div>
</div>
<script id="demo-data" type="application/json">__DATA__</script>
<script>
const DEMO=JSON.parse(document.getElementById('demo-data').textContent);
const chips=document.getElementById('chips'),view=document.getElementById('view');
DEMO.forEach((d,i)=>{const b=document.createElement('button');b.className='chip'+(i===0?' on':'');
 b.textContent=d.q.length>34?d.q.slice(0,33)+'…':d.q;b.onclick=()=>{sel(i);};chips.appendChild(b);});
function esc(s){return (s==null?'':(''+s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function list(arr){return '<ol>'+arr.map(x=>'<li><span class="nm">'+esc(x.name)+'</span>'
 +'<span class="gr">'+esc(x.grade)+'</span><span class="sc">'+(x.score!=null?x.score:'')+'</span></li>').join('')+'</ol>';}
function fusedList(arr){return '<ol>'+arr.map(x=>{const b=x.from==='both'?'b-both':(x.from==='bm25'?'b-bm25':'b-dense');
 const lab=x.from==='both'?'둘 다':(x.from==='bm25'?'BM25':'의미');
 return '<li><span class="nm">'+esc(x.name)+'</span><span class="gr">'+esc(x.grade)+'</span>'
 +'<span class="badge '+b+'">'+lab+'</span></li>';}).join('')+'</ol>';}
function items(arr){return '<div class="items">'+arr.map(it=>'<div class="item">'
 +'<div class="cn">'+esc(it.concept)+'</div>'
 +'<div class="mt">문항 '+esc(it.id)+' · '+esc(it.grade)+' · 난이도 '+esc(it.band)
 +' · 정답률 '+(it.cr==null?'-':it.cr+'%')+'</div>'
 +(it.prereqs&&it.prereqs.length?'<div class="mt">선수개념: '+it.prereqs.map(p=>'<span class="pill">'+esc(p)+'</span>').join('')+'</div>':'')
 +'</div>').join('')+'</div>';}
function sel(i){[...chips.children].forEach((c,j)=>c.classList.toggle('on',j===i));
 const d=DEMO[i];
 const meta=[d.grade?('학년 '+d.grade):null,d.difficulty?('난이도 '+d.difficulty):null,'모드 hybrid']
   .filter(Boolean).map(x=>'<span>'+x+'</span>').join('');
 view.innerHTML=
 '<div class="stage card"><h2>① 질의</h2><div class="qbox">"'+esc(d.q)+'"</div><div class="qmeta">'+meta+'</div></div>'
 +'<div class="arrow">▾ 두 갈래 병렬 검색</div>'
 +'<div class="two">'
   +'<div class="stage card col"><h3><span class="dot" style="background:var(--bm25)"></span>② BM25 · 어휘 검색</h3>'
     +'<div class="sub">정확한 교육과정 용어에 강함</div>'+list(d.bm25)+'</div>'
   +'<div class="stage card col"><h3><span class="dot" style="background:var(--dense)"></span>② bge-m3 · 의미 검색</h3>'
     +'<div class="sub">의역·실생활 맥락 질의에 강함</div>'+list(d.dense)+'</div>'
 +'</div>'
 +'<div class="arrow">▾ RRF(Reciprocal Rank Fusion)</div>'
 +'<div class="stage card"><h2>③ RRF 병합</h2><div class="sub">두 순위를 합산 — '
   +'<span class="badge b-both">둘 다</span> 나온 개념이 상위로 올라간다</div>'+fusedList(d.fused)+'</div>'
 +'<div class="arrow">▾ IRT 난이도 · θ 적합도</div>'
 +'<div class="stage card"><h2>④ 재랭킹 → 추천 문항</h2>'
   +'<div class="sub">개념을 문항으로 확장하고 난이도로 재정렬</div>'+items(d.final)+'</div>'
 +'<div class="arrow">▾ 로컬 LLM (qwen2.5:3b)</div>'
 +'<div class="stage card"><h2>⑤ LLM 추천 근거</h2><div class="ans">'+esc(d.answer)+'</div></div>';
 window.scrollTo({top:0,behavior:'smooth'});
}
sel(0);
</script></body></html>"""
