# 수학 문항 추천 Hybrid RAG — 실데이터 완성본 설계

- 날짜: 2026-07-21
- 대상 저장소: `A005-math-item-hybrid-rag` (기존 합성 데이터 버전을 실데이터 기반으로 업그레이드)
- 데이터: AIHub #27752 「수학분야 학습자 역량 측정」(구축: 아이스크림에듀) — 로컬 다운로드본
- 제약: 외부 pip 의존성 없음(표준 라이브러리) + 로컬 Ollama, 런타임 오프라인

---

## 1. 배경과 문제

기존 A005는 `gen_data.py`로 스키마를 흉내 낸 **합성 데이터**를 문항 텍스트 카드로 만들어 BM25 + bge-m3 + RRF Hybrid RAG를 구현했다. 이번 목표는 **실제 AIHub 데이터로 완성본**을 만드는 것이다.

실데이터를 조사한 결과 두 개의 하위 데이터셋이 확인됐다.

1. **학습자 성취수준 데이터셋** (`[원천]성취수준데이터셋_train.zip`, 805MB, JSON 196만 건)
   - 문항 정오답표: `learnerID, learnerProfile(성별;학교;학년), testID, assessmentItemID, answerCode(정오답 0/1), Timestamp`
   - 문항 IRT(~9,500): `assessmentItemID, difficultyLevel, discriminationLevel, guessLevel, knowledgeTag, testID`
   - 응시자 IRT: `learnerID, testID, theta(능력치), realScore`
   - 학년 1~9
2. **수학 지식체계 데이터셋** (`[라벨]수학 지식체계 데이터 세트_210611.json`)
   - 개념 선후관계 그래프. 각 엔트리 = `fromConcept → toConcept` 간선.
   - 개념 속성: `id, name(개념명), semester(예: 중등-중2-1학기), description(LaTeX 설명), chapter{id, name: "대단원 > 중단원 > 소단원"}, achievement{id, name: 성취기준 문장}`
   - 규모: 고유 개념 **1,631개**, 선후 간선 **3,446개**

**핵심 발견**: 성취수준 데이터의 `knowledgeTag`(예 `7811`)가 지식체계의 개념 `id`와 **94% 매칭**된다(샘플 4,000 문항 기준). 즉 지식체계가 문항에 **실제 텍스트(개념명·설명·단원·성취기준)와 선후관계 그래프**를 부여한다. "문항에 텍스트가 없다"는 문제는 지식체계 조인으로 해소된다.

## 2. 목표와 비목표

**목표**
- 실데이터로 개념–문항 지식베이스를 구축하고, 자연어 질의로 **개념/문항을 Hybrid 검색 → IRT·θ 재랭킹 → 로컬 LLM 추천/근거 생성**한다.
- 결과를 **Obsidian 볼트 + `graph.html`**(개념 선후관계 그래프 시각화)로 내보낸다.
- stdlib-only + 로컬 Ollama 원칙과 재현성(빌드 스크립트로 전 구간 재생성)을 유지한다.

**비목표**
- 원천 데이터(196만 파일, 805MB)를 저장소에 커밋하지 않는다. ETL 산출물(경량 카탈로그)만 재생성 대상으로 둔다.
- 새 KT(knowledge tracing) 모델 학습은 하지 않는다. θ는 데이터에 이미 있는 IRT 값을 사용한다.
- 문항 지문(원문 텍스트)은 데이터에 없으므로 생성/추정하지 않는다. 문항은 소속 개념 텍스트 + IRT + 실측 정답률로 표현한다.

## 3. 확정된 설계 결정 (브레인스토밍 결과)

| 결정 | 선택 | 비고 |
|---|---|---|
| 방향 | **개념–문항 지식베이스 Hybrid RAG** | 개인화 추천(θ)은 재랭킹 단계로 흡수 |
| 개념명 매핑 | **공식 지식체계 데이터셋 조인** | knowledgeTag→개념 id, 94% 매칭, 미매칭은 폴백 라벨 |
| 프로젝트 위치 | **A005 갈아엎기** | 기존 저장소 in-place 업그레이드 |
| 문항 노트 범위 | **개념 전량 + 개념당 대표문항 소수** | 그래프 밀도·성능 균형 |
| θ 개인화 | **포함** | 응시자 IRT theta로 난이도 적합도 재랭킹 |

## 4. 아키텍처

```
[ETL] 성취수준 zip(스트리밍) + 지식체계 JSON
   → concepts.json / items.json / edges.json / learners.json   (경량 카탈로그)
        │
[Index] 개념 카드(이름+설명+단원+성취기준+집계) 1,631건
   → BM25(어휘) + bge-m3 임베딩(의미, Ollama)                  (개념 단위로 인덱싱)
        │
[Query] "중2 일차방정식 어려운 문항"  (+ --grade/--difficulty/--theta/--learner)
   → 개념 Hybrid 검색(RRF) → 상위 개념 확장(그 개념의 문항)
   → IRT 난이도밴드·θ 적합도로 문항 재랭킹 → 최종 문항 N건
        │
[Generate] 로컬 LLM: 추천 + 근거(학년·단원·난이도·정답률) + 선수개념 안내
        │
[Obsidian] 개념/단원(MOC)/대표문항 노트(frontmatter + [[선후개념]]) + graph.html
```

**검색 단위를 '개념'으로 두는 이유**: 문항 ~9,500개는 다수가 동일 개념 텍스트를 공유한다. 문항 단위 임베딩은 중복·낭비이며 의미 검색이 개념 클러스터를 통째로 반환한다. 개념(1,631) 단위로 임베딩한 뒤 상위 개념을 문항으로 확장·재랭킹하면 (a) 임베딩 비용 최소화, (b) 의미적으로 또렷한 검색, (c) "개념→대표문항" 산출이 자연스럽다.

## 5. 데이터 흐름 상세

### 5.1 조인 키
- 문항 → 개념: `item.knowledgeTag == concept.id` (문자열 비교). 미매칭(~6%)은 `미분류 개념 {tag}` 폴백 개념으로 흡수하고 로그로 카운트 표기(무음 실패 금지).
- 학년: 원천 zip의 최상위 폴더(`1학년`…`9학년`) 또는 `learnerProfile`에서 파생.
- 선후관계: 지식체계 간선을 `from_tag → to_tag`로 정규화하고, **양쪽 개념이 카탈로그에 존재하는 간선만** 유지(고아 간선 제거).

### 5.2 집계
- 개념/문항별 **실측 정답률** = `sum(answerCode) / count` (196만 정오답표 1-pass 스트리밍 집계).
- 개념 평균 난이도 = 소속 문항 `difficultyLevel(b)` 평균 → 밴드(상/중/하) 매핑.
- θ(개인화): 응시자 IRT에서 `(learnerID → 평균 theta)` 집계. 데모용 대표 학습자 소수(저/중/고 성취 각 1명)를 `learners.json`에 표본으로 저장.

### 5.3 원천 데이터 위치와 산출물
- 입력 경로: `config.RAW_DATA_DIR`(기본값 = 다운로드 폴더 절대경로, 환경변수 `MATH_DATA_DIR`로 override).
- 산출물(모두 `data/`, `.gitignore` 유지 → 사용자가 빌드로 재생성):
  - `concepts.json` `{tag: {name, description, semester, chapter{대,중,소}, achievement, grade, avg_b, band, correct_rate, item_count, prereq_tags, next_tags}}`
  - `items.json` `{assessmentItemID: {tag, testID, grade, a, b, c, band, correct_rate, attempts}}`
  - `edges.json` `[[from_tag, to_tag], ...]`
  - `learners.json` `{learnerID: {theta, profile, label}}` (표본)
  - `embeddings.json` `{tag: [1024 floats]}` (개념 임베딩 캐시)
- **성능 가드**: ETL은 zip을 추출하지 않고 스트리밍하며, `--grade N`·`--limit K` 옵션으로 부분 빌드 지원(개발 반복 속도). 전량 1-pass 목표.

## 6. 컴포넌트 (파일 단위)

기존 모듈 재사용을 최대화한다. (신규) = 새 파일, (변경) = 기존 수정, (유지) = 그대로, (삭제) = 제거.

| 파일 | 상태 | 책임 |
|---|---|---|
| `src/config.py` | 변경 | 실데이터 경로, 카탈로그/임베딩 경로, 난이도 밴드 임계, θ 재랭크 가중치 |
| `src/etl.py` | 신규 | zip 스트리밍 + 지식체계 조인 → concepts/items/edges/learners.json |
| `src/knowledge_graph.py` | 신규 | edges 로드, `prereqs(tag)`/`successors(tag)`/`concept(tag)` 조회 |
| `src/irt.py` | 신규 | b→밴드(상/중/하), 질의 난이도 파싱, θ 적합도 점수, 개념→문항 선별 |
| `src/corpus.py` | 변경 | **개념** 카드 텍스트 생성(이름+설명+단원+성취기준+학년+난이도+정답률) |
| `src/retriever.py` | 유지(경미) | 문서집합=개념 카드. BM25+dense+RRF 그대로 |
| `src/bm25.py` `src/dense.py` `src/fusion.py` `src/tokenizer.py` | 유지 | 검색 코어 |
| `src/recommender.py` | 신규 | 개념 히트→문항 확장→IRT·θ 재랭킹→최종 문항 |
| `src/generator.py` | 변경 | 프롬프트에 선수개념·선별 문항 포함 |
| `src/ollama_client.py` | 유지 | embed/generate |
| `src/obsidian_export.py` | 신규 | 개념/단원/문항 노트 + `graph.html` 생성 |
| `build_catalog.py` | 신규 | ETL 실행 진입점 (`gen_data.py` 역할 대체) |
| `build_index.py` | 변경 | 개념 임베딩 캐시 생성 |
| `query.py` | 변경 | 개념 검색→문항 추천→생성. `--grade/--difficulty/--theta/--learner/--mode/--no-gen` |
| `export_obsidian.py` | 신규 | 볼트 + graph.html 내보내기 CLI |
| `eval.py` | 변경 | 개념 검색 Hit@K (sparse/dense/hybrid 비교) |
| `gen_data.py` | 삭제 | 합성 데이터 생성기 제거 |
| `tests/` | 신규 | etl 조인·irt·graph·export·fusion 단위 테스트 |
| `README.md` | 변경 | 실데이터 기준 재작성 |

파일은 200–400줄 이내, 단일 책임 유지(공용 코딩 규칙).

## 7. Obsidian 출력 명세

- `vault/concepts/{tag} {개념명}.md` — 파일명에 tag를 포함해 동명 개념(예 "거듭제곱"이 학기별 중복) 충돌 방지.
  - frontmatter: `tag, grade, semester, 대단원, 중단원, 소단원, achievement, avg_b, band, correct_rate, item_count`
  - 본문: 개념 설명 → `## 선수개념` `[[...]]` → `## 후속개념` `[[...]]` → `## 대표문항` `[[...]]` → `단원 MOC` `[[...]]`
- `vault/units/{대단원}.md` — 대단원 MOC. 소속 개념 링크 목록.
- `vault/items/{assessmentItemID}.md` — frontmatter(IRT a/b/c, band, correct_rate, attempts, grade) + 본문 `[[개념]]` 백링크. **개념당 대표문항 소수**(난이도 상/중/하 커버, 최대 5개)만 생성.
- `vault/queries/{slug}.md` — (선택) 질의 실행 결과 노트: 추천 문항 `[[링크]]` + LLM 근거.
- `graph.html` — 단독 실행 force-directed 시각화(A006 방식 재사용). 노드=개념(학년별 색), 간선=선후관계. 문항은 그래프에서 제외해 가독성 확보(토글 옵션 여지).
- 위키링크는 노트 제목 기준. 링크 문자열은 파일명(`{tag} {개념명}`)과 일치시켜 깨진 링크 방지.

## 8. 검색·재랭킹 로직

1. 질의 → (선택)`--grade` 프리필터, `--difficulty 상|중|하` 또는 `--theta`/`--learner` 파싱.
2. 개념 Hybrid 검색: BM25(TOP_K_SPARSE) + dense(TOP_K_DENSE) → RRF(k=60) → 상위 개념.
3. 개념 확장: 각 개념의 문항 로드(학년 필터 적용).
4. 문항 재랭킹 점수 = `w1·검색순위점수 + w2·난이도적합도`.
   - 난이도적합도: `--difficulty` 지정 시 밴드 일치도, θ 지정 시 `1 - |b - theta|` 정규화.
5. 최종 문항 `FINAL_K`건 + 근거 개념/선수개념을 생성기에 전달.

## 9. 에러 처리·검증 (경계)

- 원천 경로 부재/zip 손상 → 명확한 메시지로 조기 실패(startup 검증).
- knowledgeTag 미매칭·고아 간선 → 폴백 처리 + 카운트 로그(무음 실패 금지).
- Ollama 미기동 → embed/generate 호출 지점에서 사용자 친화 메시지.
- 카탈로그/임베딩 미생성 상태로 query 실행 → "먼저 build_catalog.py / build_index.py 실행" 안내.
- 외부 입력(질의, CLI 인자) 파싱은 화이트리스트/기본값으로 방어.

## 10. 테스트 (stdlib unittest)

- `etl`: knowledgeTag→개념 조인, 미매칭 폴백, 정답률 집계, 고아 간선 제거.
- `irt`: b→밴드 매핑 경계값, θ 적합도 점수 단조성, 질의 난이도 파싱.
- `knowledge_graph`: prereqs/successors 정확성, 순환/자기간선 방어.
- `obsidian_export`: frontmatter/링크 문자열 생성, 파일명 충돌 회피, graph.html 노드/간선 수.
- `fusion`: 기존 RRF 동작(회귀).
- Ollama 의존 경로(embed/generate, 실검색)는 소형 스모크 테스트로 한정.
- 소형 픽스처(개념 3~4개, 문항 6개, 응답 로그 소량)로 실행. 순수 함수 중심 커버리지 확보.

## 11. 구축 순서 (구현 계획의 뼈대)

1. `config` + `etl` + `build_catalog.py` — 실데이터 → 경량 카탈로그(concepts/items/edges/learners).
2. `knowledge_graph` + `irt` 모듈 + 단위 테스트.
3. `corpus`(개념 카드) + `retriever` 연결 + `build_index.py`(개념 임베딩).
4. `recommender`(문항 확장·재랭킹) + `generator` 프롬프트 갱신.
5. `query.py` CLI(플래그 일체) 통합.
6. `obsidian_export` + `graph.html` + `export_obsidian.py`.
7. `eval.py`(Hit@K sparse/dense/hybrid) + 나머지 테스트.
8. `gen_data.py` 제거, `README.md` 실데이터 기준 재작성.

## 12. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 196만 파일 스트리밍이 느림 | zip 추출 없이 1-pass, `--grade/--limit` 부분 빌드, 정답률만 집계 |
| 원천 데이터 재배포 불가/대용량 | 저장소엔 카탈로그 산출물만(그마저 gitignore), README에 AIHub 다운로드+빌드 절차 명시 |
| 개념명 중복으로 위키링크 충돌 | 파일명·링크에 tag 접두 |
| knowledgeTag 6% 미매칭 | 폴백 개념 + 카운트 로그, README에 매칭률 명기 |
| Obsidian 그래프 과밀 | 그래프는 개념+선후관계만, 문항 노트는 대표문항으로 제한 |
```
