# 수학 문항 추천 Hybrid RAG — 실데이터 완성본 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** AIHub #27752 실데이터(성취수준 + 지식체계)로 개념–문항 지식베이스를 만들어 Hybrid 검색(BM25+bge-m3+RRF) → IRT·θ 재랭킹 → 로컬 LLM 추천 → Obsidian 볼트/graph.html까지 산출하는 완성본으로 A005를 업그레이드한다.

**Architecture:** ETL이 zip을 스트리밍하고 지식체계 JSON과 knowledgeTag로 조인해 경량 카탈로그(concepts/items/edges/learners.json)를 만든다. 검색 인덱스는 **개념 단위**(1,631)로 임베딩하고, 질의→상위 개념→그 개념의 문항을 IRT 난이도·θ로 재랭킹해 최종 문항을 뽑는다. 기존 bm25/dense/fusion/retriever/tokenizer/ollama_client는 재사용한다.

**Tech Stack:** Python 3.10+ 표준 라이브러리만, 로컬 Ollama(bge-m3 임베딩 / qwen2.5:3b 생성), stdlib `unittest`.

## Global Constraints

- 외부 pip 의존성 금지 — 표준 라이브러리 + 로컬 Ollama만.
- 런타임 오프라인. 네트워크는 로컬 Ollama HTTP만.
- 원천 데이터(196만 파일/805MB)와 ETL 산출물은 커밋 금지(`data/` gitignore). README에 다운로드+빌드 절차 명시.
- 파일당 200–400줄, 단일 책임. 불변 패턴(원본 dict 변형 대신 새 dict).
- 무음 실패 금지 — 미매칭/고아 간선/미기동은 카운트·메시지로 표면화.
- 조인 키: `item.knowledgeTag == concept.id`(문자열). 미매칭은 `미분류 개념 {tag}` 폴백.
- 임베딩 캐시 포맷 유지: `{"model","dim","count","vectors":[...]}`, vectors는 doc_id(개념 tag 정렬) 순.
- 원천 경로: `config.RAW_DATA_DIR`(기본 다운로드 절대경로, env `MATH_DATA_DIR` override).

---

## 파일 구조

| 파일 | 상태 | 책임 |
|---|---|---|
| `src/config.py` | 변경 | 실데이터 경로, 카탈로그/볼트 경로, 밴드 임계, θ 가중치 |
| `src/etl.py` | 신규 | zip 스트리밍 + 지식체계 조인 → 카탈로그 4종 |
| `src/irt.py` | 신규 | b→밴드, 질의 난이도 파싱, θ 적합도, 문항 선별 |
| `src/knowledge_graph.py` | 신규 | edges 로드, prereqs/successors/concept 조회 |
| `src/corpus.py` | 변경 | 개념 카드(BM25/임베딩 텍스트), `load_corpus()` |
| `src/recommender.py` | 신규 | 개념 히트→문항 확장→재랭킹→최종 문항 |
| `src/generator.py` | 변경 | 선수개념·선별문항 포함 프롬프트 |
| `src/retriever.py`,`bm25.py`,`dense.py`,`fusion.py`,`tokenizer.py`,`ollama_client.py` | 유지 | 검색 코어 |
| `src/obsidian_export.py` | 신규 | 개념/단원/문항 노트 + graph.html |
| `build_catalog.py` | 신규 | ETL 진입점 |
| `build_index.py` | 변경 | 개념 임베딩 캐시 |
| `query.py` | 변경 | 추천 CLI(플래그 일체) |
| `export_obsidian.py` | 신규 | 볼트 내보내기 CLI |
| `eval.py` | 변경 | 개념 Hit@K sparse/dense/hybrid |
| `gen_data.py` | 삭제 | 합성 생성기 제거 |
| `tests/test_*.py` | 신규 | etl/irt/graph/export/fusion 단위 테스트 |
| `README.md` | 변경 | 실데이터 기준 재작성 |

카탈로그 스키마(모두 `data/`):
```
concepts.json: { tag: {name, description, semester, chapter:{대,중,소}, achievement,
                        grade, avg_b, band, correct_rate, item_count, prereq_tags:[], next_tags:[]} }
items.json:    { assessmentItemID: {tag, testID, grade, a, b, c, band, correct_rate, attempts} }
edges.json:    [ [from_tag, to_tag], ... ]
learners.json: { learnerID: {theta, profile, label} }
```

---

### Task 1: config + irt (난이도/θ 순수 로직)

**Files:** Modify `src/config.py`; Create `src/irt.py`, `tests/test_irt.py`

**Interfaces (Produces):**
- `irt.band(b: float) -> str` ("상"|"중"|"하")
- `irt.parse_query_difficulty(text: str) -> str|None`
- `irt.fit_score(item_b: float, target_band: str|None, theta: float|None) -> float` (0..1)
- config: `RAW_DATA_DIR, CONCEPTS_PATH, ITEMS_PATH, EDGES_PATH, LEARNERS_PATH, VAULT_DIR, B_HARD=0.5, B_EASY=-0.5, TOP_CONCEPTS=8, W_SEARCH=0.6, W_FIT=0.4`

- [ ] **Step 1: config에 경로·상수 추가.** `DATA_DIR` 아래 `CONCEPTS_PATH="concepts.json"`, `EDGES_PATH="edges.json"`, `LEARNERS_PATH="learners.json"`, `ITEMS_PATH`는 유지. `RESPONSES_PATH` 제거. 추가:
```python
RAW_DATA_DIR = os.environ.get(
    "MATH_DATA_DIR",
    "/Users/pablo/Downloads/수학분야 학습자 역량 측정 데이터",
)
CONCEPTS_PATH = os.path.join(DATA_DIR, "concepts.json")
EDGES_PATH = os.path.join(DATA_DIR, "edges.json")
LEARNERS_PATH = os.path.join(DATA_DIR, "learners.json")
VAULT_DIR = os.path.join(PROJECT_DIR, "vault")
GRAPH_HTML_PATH = os.path.join(PROJECT_DIR, "graph.html")
B_HARD, B_EASY = 0.5, -0.5          # IRT 난이도 밴드 임계 (b 클수록 어려움)
TOP_CONCEPTS = 8                     # 문항 확장 전 상위 개념 수
W_SEARCH, W_FIT = 0.6, 0.4          # 재랭킹 가중치
REP_ITEMS_PER_CONCEPT = 5           # Obsidian 대표문항 상한
```

- [ ] **Step 2: 실패 테스트** `tests/test_irt.py`:
```python
import unittest
from src import irt

class TestIRT(unittest.TestCase):
    def test_band_boundaries(self):
        self.assertEqual(irt.band(1.0), "상")
        self.assertEqual(irt.band(0.0), "중")
        self.assertEqual(irt.band(-1.0), "하")
    def test_parse_query_difficulty(self):
        self.assertEqual(irt.parse_query_difficulty("어려운 문항"), "상")
        self.assertEqual(irt.parse_query_difficulty("쉬운 문제"), "하")
        self.assertIsNone(irt.parse_query_difficulty("분수 문항"))
    def test_fit_score_band(self):
        self.assertGreater(irt.fit_score(1.0, "상", None), irt.fit_score(-1.0, "상", None))
    def test_fit_score_theta(self):
        # 학습자 능력치에 가까운 난이도가 더 높은 점수
        self.assertGreater(irt.fit_score(0.1, None, 0.0), irt.fit_score(2.0, None, 0.0))
    def test_fit_score_neutral(self):
        self.assertEqual(irt.fit_score(0.3, None, None), 0.5)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run** `python -m unittest tests.test_irt -v` → FAIL(ImportError).

- [ ] **Step 4: 구현** `src/irt.py`:
```python
"""IRT 기반 난이도 밴드·질의 파싱·θ 적합도 (순수 함수, 외부 의존 없음)."""
from src import config

_HARD_KW = ("어려운", "고난도", "난도 상", "상난이도", "심화", "어렵")
_EASY_KW = ("쉬운", "기초", "쉽", "저난도", "하난이도")
_MID_KW = ("보통", "중난도", "중간")

def band(b):
    if b >= config.B_HARD: return "상"
    if b <= config.B_EASY: return "하"
    return "중"

def parse_query_difficulty(text):
    t = text.lower()
    if any(k in t for k in _HARD_KW): return "상"
    if any(k in t for k in _EASY_KW): return "하"
    if any(k in t for k in _MID_KW): return "중"
    return None

def fit_score(item_b, target_band=None, theta=None):
    """0..1. theta 우선, 없으면 target_band, 둘 다 없으면 중립 0.5."""
    if theta is not None:
        return 1.0 / (1.0 + abs(item_b - theta))
    if target_band is not None:
        return 1.0 if band(item_b) == target_band else 0.3
    return 0.5
```

- [ ] **Step 5: Run** `python -m unittest tests.test_irt -v` → PASS. **Commit** `feat: config 실데이터 경로 + IRT 난이도/θ 로직`.

---

### Task 2: ETL (지식체계 파싱 + zip 조인 → 카탈로그)

**Files:** Create `src/etl.py`, `build_catalog.py`, `tests/test_etl.py`

**Interfaces (Produces):**
- `etl.parse_knowledge_system(path) -> (concepts_meta: dict[str,dict], edges: list[tuple[str,str]])`
- `etl.build_catalog(raw_dir, grades=None, limit=None) -> dict` (concepts/items/edges/learners)
- `etl.write_catalog(catalog)` — 4개 파일 기록

**Interfaces (Consumes):** `irt.band` (Task 1)

- [ ] **Step 1: 실패 테스트** `tests/test_etl.py` — 소형 픽스처로 순수 조인 검증:
```python
import unittest
from src import etl

class TestJoin(unittest.TestCase):
    def test_join_and_fallback(self):
        concepts_meta = {"100": {"name": "분수", "description": "d", "semester": "초3",
                                 "chapter": {"대":"수와연산","중":"분수","소":"진분수"}, "achievement":"a"}}
        edges = [("100", "200")]  # 200은 메타에 없음 → 고아
        item_irt = {"IT1": {"tag":"100","testID":"T1","a":1.0,"b":0.8,"c":0.2,"grade":"초3"},
                    "IT2": {"tag":"999","testID":"T1","a":1.0,"b":-0.9,"c":0.2,"grade":"초3"}}
        resp = {"IT1": (7, 10), "IT2": (2, 4)}
        cat = etl.assemble(concepts_meta, edges, item_irt, resp, learners={})
        self.assertIn("100", cat["concepts"])
        self.assertEqual(cat["concepts"]["100"]["band"], "상")          # b=0.8
        self.assertEqual(cat["concepts"]["100"]["correct_rate"], 70.0)
        self.assertTrue(cat["concepts"]["999"]["name"].startswith("미분류"))  # 폴백
        self.assertEqual(cat["edges"], [])                              # 고아 간선 제거
        self.assertEqual(cat["items"]["IT1"]["band"], "상")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run** → FAIL. 

- [ ] **Step 3: 구현** `src/etl.py`. 핵심 함수:
  - `parse_knowledge_system(path)`: JSON 로드 후 각 엔트리의 `fromConcept`/`toConcept`를 순회. `str(c["id"])` 키로 `{name, description, semester, chapter{대,중,소 = chapter.name.split(" > ")}, achievement=achievement.name}` 수집, `edges.append((str(from.id), str(to.id)))`.
  - `stream_zip(raw_dir, grades, limit)`: `zipfile`로 `[원천]성취수준데이터셋_train.zip` 열어 namelist 순회. `2_문항IRT`→`item_irt[aid]`, `1_문항정오답표`→`resp[aid]=(correct,total)`(answerCode int 합), `3_응시자IRT`→`theta[lid].append(theta)`. `grades`(예 {"3학년"}) / `limit`로 필터. 폴더 첫 토큰으로 grade("초3"/"중1") 매핑.
  - `assemble(concepts_meta, edges, item_irt, resp, learners)`: 
    - items: aid별 band=irt.band(b), correct_rate=corr/total*100.
    - concepts: item_irt에 등장한 tag 집합 기준. 메타 없으면 폴백 `{"name": f"미분류 개념 {tag}", ...}`. avg_b=평균, band, correct_rate=태그 응답 집계, item_count, grade=최빈 학년, prereq_tags/next_tags = edges에서 양쪽 present인 것만.
    - edges: 양쪽 tag가 concepts에 있는 것만 유지.
    - learners: 저/중/고 theta 대표 표본.
  - `write_catalog(catalog)`: 4개 JSON 기록(ensure_ascii=False).
  - `build_catalog(raw_dir, grades, limit)`: parse_knowledge_system + stream_zip + assemble.
  - 미매칭/고아 카운트를 stderr로 로그.

- [ ] **Step 4: Run** `python -m unittest tests.test_etl -v` → PASS.

- [ ] **Step 5: build_catalog.py** 작성(진입점):
```python
"""AIHub 원천 → 경량 카탈로그. 사용: python build_catalog.py [--grade 3학년] [--limit N]"""
import argparse, sys
from src import config, etl

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--grade", action="append", help="예: 3학년 (반복 가능)")
    p.add_argument("--limit", type=int, default=None)
    a = p.parse_args()
    cat = etl.build_catalog(config.RAW_DATA_DIR, grades=set(a.grade) if a.grade else None, limit=a.limit)
    etl.write_catalog(cat)
    print(f"완료: 개념 {len(cat['concepts'])} · 문항 {len(cat['items'])} · 간선 {len(cat['edges'])}")

if __name__ == "__main__":
    try: main()
    except (RuntimeError, FileNotFoundError, OSError) as e:
        print(f"[오류] {e}", file=sys.stderr); sys.exit(1)
```

- [ ] **Step 6:** 실데이터 스모크(부분): `python build_catalog.py --grade 3학년`. 개념/문항 수 출력 확인. **Commit** `feat: 실데이터 ETL + build_catalog`.

---

### Task 3: knowledge_graph + corpus(개념 카드) + build_index

**Files:** Create `src/knowledge_graph.py`, `tests/test_knowledge_graph.py`; Modify `src/corpus.py`, `build_index.py`

**Interfaces (Produces):**
- `KnowledgeGraph(concepts: dict, edges: list).prereqs(tag)->list[str]`, `.successors(tag)->list[str]`, `.concept(tag)->dict`
- `corpus.load_corpus() -> (concept_list, doc_texts, embed_texts)` — tag 정렬 순서. `concept_list[i]["tag"]` 포함.
- `corpus.load_items_by_tag() -> dict[str, list[item]]`

- [ ] **Step 1: 실패 테스트** `tests/test_knowledge_graph.py`:
```python
import unittest
from src.knowledge_graph import KnowledgeGraph
class T(unittest.TestCase):
    def setUp(self):
        self.g = KnowledgeGraph({"1":{"name":"A"},"2":{"name":"B"}}, [["1","2"]])
    def test_prereqs(self): self.assertEqual(self.g.prereqs("2"), ["1"])
    def test_successors(self): self.assertEqual(self.g.successors("1"), ["2"])
    def test_self_edge_ignored(self):
        g = KnowledgeGraph({"1":{}}, [["1","1"]]); self.assertEqual(g.successors("1"), [])
if __name__ == "__main__": unittest.main()
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: 구현** `src/knowledge_graph.py`:
```python
"""개념 선후관계 그래프 조회 (fromConcept=선수 → toConcept=후속)."""
from collections import defaultdict
class KnowledgeGraph:
    def __init__(self, concepts, edges):
        self.concepts = concepts
        self._pre = defaultdict(list); self._suc = defaultdict(list)
        for a, b in edges:
            if a == b: continue
            self._suc[a].append(b); self._pre[b].append(a)
    def prereqs(self, tag): return self._pre.get(tag, [])
    def successors(self, tag): return self._suc.get(tag, [])
    def concept(self, tag): return self.concepts.get(tag)
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: corpus.py 재작성.** `load_corpus()`가 `concepts.json`을 읽어 tag 정렬 리스트로 반환. `build_document_text(concept)`=BM25 카드(학년·단원 대/중/소·개념명·성취기준·난이도밴드·정답률·설명), `build_embedding_text(concept)`=의미 텍스트(개념명·단원·설명·성취기준, 숫자 제외). `load_items_by_tag()`는 `items.json`을 tag별 그룹화. (기존 응답 집계 코드 제거 — 정답률은 카탈로그에 이미 있음.)

- [ ] **Step 6: build_index.py 수정.** `load_corpus()`의 `embed_texts`(개념)로 임베딩. 출력 포맷 유지. 진행 로그 개념 수 기준.

- [ ] **Step 7: Run** `python -m unittest tests.test_knowledge_graph -v` → PASS. **Commit** `feat: 지식그래프 + 개념 코퍼스 + 개념 임베딩 인덱스`.

---

### Task 4: recommender + generator + query CLI

**Files:** Create `src/recommender.py`; Modify `src/generator.py`, `query.py`

**Interfaces (Produces):**
- `recommender.recommend(query, retriever, concepts, items_by_tag, graph, *, mode, grade, difficulty, theta, k) -> list[dict]` — 각 dict: `{item, concept, prereqs}`
- `generator.generate_answer(query, recommendations) -> str`

**Consumes:** `HybridRetriever.retrieve` (기존), `irt.fit_score/parse_query_difficulty` (Task1), `KnowledgeGraph` (Task3), `config.TOP_CONCEPTS/W_SEARCH/W_FIT`.

- [ ] **Step 1: 실패 테스트** `tests/test_recommender.py` — 가짜 retriever로 순위 로직 검증:
```python
import unittest
from src import recommender
class FakeRetr:
    def retrieve(self, q, mode="hybrid", final_k=8): return [("tagA", 1.0), ("tagB", 0.5)]
class T(unittest.TestCase):
    def test_grade_filter_and_rerank(self):
        concepts = {"tagA":{"tag":"tagA","name":"A","grade":"초3"}, "tagB":{"tag":"tagB","name":"B","grade":"중1"}}
        items = {"tagA":[{"assessmentItemID":"i1","tag":"tagA","grade":"초3","b":1.0,"band":"상","correct_rate":40.0}],
                 "tagB":[{"assessmentItemID":"i2","tag":"tagB","grade":"중1","b":-1.0,"band":"하","correct_rate":90.0}]}
        class G: 
            def prereqs(self,t): return []
        recs = recommender.recommend("어려운 초등 문항", FakeRetr(), concepts, items, G(),
                                     mode="hybrid", grade="초3", difficulty=None, theta=None, k=5)
        self.assertEqual([r["item"]["assessmentItemID"] for r in recs], ["i1"])  # 초3만
if __name__ == "__main__": unittest.main()
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: 구현** `src/recommender.py`:
  - `retriever.retrieve` 결과는 doc_id(=개념 인덱스). 여기서는 concept_list 순서와 tag 매핑 필요 → recommend는 `concepts`(tag→dict)와 `concept_tags`(doc_id→tag) 둘 다 받도록 조정. (query.py가 load_corpus 순서로 tag 리스트 전달.)
  - 상위 개념 확장 → 문항 수집(grade 필터) → 점수 `W_SEARCH*정규화검색점수 + W_FIT*irt.fit_score(b, target, theta)` → 상위 k → 각 문항의 concept·prereqs 부착.
  - (테스트의 FakeRetr는 tag를 직접 반환하므로, recommend는 doc_id가 concepts에 있으면 tag로 간주하는 방어 분기 포함.)

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: generator.py 수정.** `build_prompt(query, recommendations)`가 각 추천의 개념·선수개념·IRT·정답률을 카드로 넣고 "선수개념을 함께 안내" 지침 추가. `generate_answer` 시그니처 변경.

- [ ] **Step 6: query.py 수정.** 플래그 `--grade --difficulty {상,중,하} --theta(float) --learner(id) --mode --k --no-gen`. `load_corpus`로 concept_list/doc_texts, 임베딩 로드, `HybridRetriever`, `recommend(...)`, 결과 표 출력 + (옵션) 생성. `--learner`는 `learners.json`에서 theta 조회.

- [ ] **Step 7: Run** `python -m unittest tests.test_recommender -v` → PASS. **Commit** `feat: 추천 재랭킹 + 생성 프롬프트 + query CLI`.

---

### Task 5: Obsidian export + graph.html

**Files:** Create `src/obsidian_export.py`, `export_obsidian.py`, `tests/test_obsidian_export.py`

**Interfaces (Produces):**
- `obsidian_export.concept_filename(tag, name) -> str` (`f"{tag} {safe(name)}.md"`)
- `obsidian_export.concept_note(concept, graph, items_by_tag) -> str`
- `obsidian_export.write_vault(concepts, items_by_tag, graph, vault_dir)`
- `obsidian_export.render_graph_html(concepts, edges) -> str`

- [ ] **Step 1: 실패 테스트** `tests/test_obsidian_export.py`:
```python
import unittest
from src import obsidian_export as ox
class T(unittest.TestCase):
    def test_filename_safe(self):
        fn = ox.concept_filename("100", "분수 / 나눗셈")
        self.assertTrue(fn.startswith("100 ")); self.assertNotIn("/", fn)
    def test_note_has_frontmatter_and_links(self):
        c = {"tag":"2","name":"B","description":"설명","semester":"중1","grade":"중1",
             "chapter":{"대":"수","중":"정수","소":"덧셈"},"achievement":"성취","avg_b":0.1,
             "band":"중","correct_rate":55.0,"item_count":3,"prereq_tags":["1"],"next_tags":[]}
        class G:
            concepts={"1":{"name":"A"}}
            def prereqs(self,t): return ["1"]
            def successors(self,t): return []
            def concept(self,t): return self.concepts.get(t)
        note = ox.concept_note(c, G(), {"2":[{"assessmentItemID":"i1","band":"중","correct_rate":55.0}]})
        self.assertIn("band: 중", note); self.assertIn("[[1 A]]", note)
    def test_graph_html_counts(self):
        html = ox.render_graph_html({"1":{"name":"A","grade":"초3"},"2":{"name":"B","grade":"초3"}}, [["1","2"]])
        self.assertIn("<html", html.lower()); self.assertIn('"source"', html)
if __name__ == "__main__": unittest.main()
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: 구현** `src/obsidian_export.py`:
  - `concept_filename`: 이름의 `/ \ : * ? " < > | [ ]` → 공백/제거.
  - `concept_note`: YAML frontmatter(tag,grade,semester,대/중/소단원,achievement,avg_b,band,correct_rate,item_count) + 본문(설명 → `## 선수개념` prereqs `[[fn]]` → `## 후속개념` → `## 대표문항`(band 상/중/하 커버, 최대 `REP_ITEMS_PER_CONCEPT`) `[[item]]` → 단원 MOC 링크).
  - `write_vault`: `vault/concepts/`, `vault/units/`(대단원 MOC), `vault/items/`(대표문항만) 생성.
  - `render_graph_html`: 단독 HTML + 내장 JS(라이브러리 없이 canvas force-directed 또는 간단 SVG). 노드=개념(grade별 색), 링크={source,target}. A006 방식 참고하되 자체 포함.

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: export_obsidian.py** CLI: `load_corpus`+`items_by_tag`+`edges`→`KnowledgeGraph`→`write_vault`+`render_graph_html`→`graph.html`. 출력 노트 수 표기.

- [ ] **Step 6: Run** `python -m unittest tests.test_obsidian_export -v` → PASS. **Commit** `feat: Obsidian 볼트 + graph.html 익스포트`.

---

### Task 6: eval + gen_data 제거 + README + 회귀 테스트

**Files:** Modify `eval.py`, `README.md`; Delete `gen_data.py`; Create `tests/test_fusion.py`

**Interfaces (Consumes):** 기존 fusion/retriever, 개념 코퍼스.

- [ ] **Step 1: 회귀 테스트** `tests/test_fusion.py` — RRF 병합이 두 리스트 상위를 끌어올리는지:
```python
import unittest
from src.fusion import reciprocal_rank_fusion
class T(unittest.TestCase):
    def test_rrf_merges(self):
        a=[("x",9),("y",8)]; b=[("y",7),("z",6)]
        out=dict(reciprocal_rank_fusion([a,b], k=60))
        self.assertGreater(out["y"], out["x"])  # 양쪽 등장 y가 최상위
if __name__ == "__main__": unittest.main()
```

- [ ] **Step 2: Run** `python -m unittest tests.test_fusion -v` → PASS(기존 로직).

- [ ] **Step 3: eval.py 수정.** 개념 검색 기준 Hit@K/MRR. `is_relevant(concept, spec)`=학년 일치 & `spec["concept_has"] in concept["name"]`. 질의셋(키워드/의역)은 실데이터 개념명에 맞게 조정. sparse/dense/hybrid 비교표 유지. FileNotFound 안내를 `build_catalog.py`/`build_index.py`로 갱신.

- [ ] **Step 4: gen_data.py 삭제**, `.gitignore`에서 `data/responses.json` → `data/concepts.json data/edges.json data/learners.json`로 갱신(items/embeddings 유지). `vault/`, `graph.html`도 gitignore 추가.

- [ ] **Step 5: README.md 재작성.** 실데이터 파이프라인(다운로드→build_catalog→build_index→query→export_obsidian), 조인 94% 매칭 명기, 개념 단위 인덱싱 설명, Obsidian/graph.html 스크린샷 자리, 아키텍처 mermaid, eval 표.

- [ ] **Step 6: 전체 테스트** `python -m unittest discover -s tests -v` → 전부 PASS. **Commit** `feat: 개념 eval + gen_data 제거 + README 실데이터 재작성`.

---

## Self-Review

- **Spec coverage:** ETL/조인/폴백(T2) · 개념 인덱싱(T3) · IRT/θ 재랭킹(T1,T4) · 생성(T4) · Obsidian+graph.html(T5) · eval/테스트/README(T6) · 원천 미커밋(T6 gitignore) — 스펙 §4–12 전부 매핑됨.
- **Placeholder scan:** 각 신규 모듈의 핵심 코드/시그니처 명시. "적절히 처리" 류 없음.
- **Type consistency:** `load_corpus()`는 전 태스크에서 3-튜플(concept_list, doc_texts, embed_texts). `recommend(...)`는 doc_id↔tag 매핑을 query.py가 주입. `concept_filename(tag,name)` 링크 문자열 `[[{tag} {name}]]`로 노트 전반 일치.

## 실행/검증 유의
- 실데이터 전량 ETL·임베딩은 시간이 큼 → 개발/검증은 `--grade 3학년` 등 부분셋으로. Ollama 미기동 시 임베딩/생성 스텝은 스킵하고 순수 로직 테스트로 검증.
- 최종 완료 후 `feat/realdata-hybrid-rag` 브랜치로 push.
