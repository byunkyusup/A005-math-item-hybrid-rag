"""AIHub #27752 원천 → 경량 카탈로그 ETL.

두 하위 데이터셋을 조인한다.
  - 성취수준(zip): 문항 IRT(난이도/변별도/추측도/knowledgeTag), 정오답표, 응시자 IRT(theta)
  - 지식체계(json): 개념명·설명·단원·성취기준 + 선후관계 간선

산출:
  concepts.json / items.json / edges.json / learners.json
조인 키: item.knowledgeTag == concept.id (문자열). 미매칭은 '미분류 개념' 폴백.
"""

import glob
import json
import os
import sys
import zipfile
from collections import Counter, defaultdict

from src import config, irt


# --------------------------------------------------------------------------- #
# 1) 지식체계 파싱
# --------------------------------------------------------------------------- #
def _split_chapter(name: str) -> dict:
    parts = [p.strip() for p in (name or "").split(">")]
    parts += [""] * (3 - len(parts))
    return {"대": parts[0], "중": parts[1], "소": parts[2]}


def _concept_from_side(side: dict) -> tuple[str, dict]:
    tag = str(side["id"])
    meta = {
        "name": side.get("name", ""),
        # 지식체계 JSON은 설명에 리터럴 '\n'을 담고 있어 개행으로 복원(Obsidian 가독성).
        "description": side.get("description", "").replace("\\n", "\n"),
        "semester": side.get("semester", ""),
        "chapter": _split_chapter((side.get("chapter") or {}).get("name", "")),
        "achievement": (side.get("achievement") or {}).get("name", ""),
    }
    return tag, meta


def parse_knowledge_system(path: str) -> tuple[dict, list]:
    """반환: (concepts_meta: {tag: meta}, edges: [(from_tag, to_tag), ...])."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    concepts_meta: dict = {}
    edges: list = []
    for entry in data.values():
        src = entry.get("fromConcept") or {}
        dst = entry.get("toConcept") or {}
        if "id" not in src or "id" not in dst:
            continue
        for side in (src, dst):
            tag, meta = _concept_from_side(side)
            concepts_meta.setdefault(tag, meta)
        edges.append((str(src["id"]), str(dst["id"])))
    return concepts_meta, edges


# --------------------------------------------------------------------------- #
# 2) 성취수준 zip 스트리밍
# --------------------------------------------------------------------------- #
def _grade_label(folder: str) -> str:
    """'3학년' -> '초3', '7학년' -> '중1'."""
    try:
        n = int(folder.replace("학년", "").strip())
    except ValueError:
        return folder
    return f"초{n}" if n <= 6 else f"중{n - 6}"


def stream_zip(zip_path: str, grades=None, limit=None):
    """반환: (item_irt, resp, theta_map, profiles).

    item_irt[aid] = {tag, testID, a, b, c, grade}
    resp[aid]     = (정답수, 응답수)
    theta_map[lid]= [theta, ...]   profiles[lid] = learnerProfile
    """
    item_irt: dict = {}
    resp: dict = defaultdict(lambda: [0, 0])
    theta_map: dict = defaultdict(list)
    profiles: dict = {}
    seen_resp = 0

    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if not name.endswith(".json"):
                continue
            folder = name.split("/")[0]
            if grades and folder not in grades:
                continue
            grade = _grade_label(folder)

            if "/2_문항IRT/" in name:
                d = json.loads(z.read(name))
                item_irt[d["assessmentItemID"]] = {
                    "tag": str(d["knowledgeTag"]),
                    "testID": d["testID"],
                    "a": d["discriminationLevel"],
                    "b": d["difficultyLevel"],
                    "c": d["guessLevel"],
                    "grade": grade,
                }
            elif "/1_문항정오답표/" in name:
                if limit and seen_resp >= limit:
                    continue
                d = json.loads(z.read(name))
                aid = d["assessmentItemID"]
                cell = resp[aid]
                cell[0] += int(d["answerCode"])
                cell[1] += 1
                seen_resp += 1
            elif "/3_응시자IRT/" in name:
                d = json.loads(z.read(name))
                lid = d["learnerID"]
                theta_map[lid].append(d["theta"])
                profiles.setdefault(lid, d.get("learnerProfile", ""))

    return item_irt, {k: tuple(v) for k, v in resp.items()}, theta_map, profiles


def sample_learners(theta_map: dict, profiles: dict) -> dict:
    """저/중/고 성취 대표 학습자 3명 표본 (theta 평균 기준)."""
    if not theta_map:
        return {}
    means = sorted(
        ((lid, sum(v) / len(v)) for lid, v in theta_map.items()),
        key=lambda kv: kv[1],
    )
    picks = {
        "저성취": means[0],
        "중간": means[len(means) // 2],
        "고성취": means[-1],
    }
    out = {}
    for label, (lid, theta) in picks.items():
        out[lid] = {"theta": round(theta, 4), "profile": profiles.get(lid, ""), "label": label}
    return out


# --------------------------------------------------------------------------- #
# 3) 조립
# --------------------------------------------------------------------------- #
def _fallback_meta(tag: str) -> dict:
    return {
        "name": f"미분류 개념 {tag}",
        "description": "",
        "semester": "",
        "chapter": {"대": "미분류", "중": "", "소": ""},
        "achievement": "",
    }


def assemble(concepts_meta: dict, edges: list, item_irt: dict, resp: dict,
             learners: dict) -> dict:
    """조인 결과를 카탈로그 dict로 조립."""
    import statistics

    # 난이도 밴드 임계를 실제 b 분포 분위수(33/66%)로 산출 — 상/중/하를 데이터에 맞춤.
    all_b = [row["b"] for row in item_irt.values()]
    if len(all_b) >= 2:
        qs = statistics.quantiles(all_b, n=3)
        b_easy, b_hard = round(qs[0], 4), round(qs[1], 4)
    else:
        b_easy, b_hard = config.B_EASY, config.B_HARD

    # --- items ---
    items: dict = {}
    for aid, irt_row in item_irt.items():
        correct, total = resp.get(aid, (0, 0))
        rate = round(correct / total * 100, 1) if total else None
        items[aid] = {
            "tag": irt_row["tag"],
            "testID": irt_row["testID"],
            "grade": irt_row["grade"],
            "a": irt_row["a"],
            "b": irt_row["b"],
            "c": irt_row["c"],
            "band": irt.band(irt_row["b"], b_hard, b_easy),
            "correct_rate": rate,
            "attempts": total,
        }

    # --- 태그별 집계 ---
    concept_tags = {row["tag"] for row in item_irt.values()}
    by_tag_b: dict = defaultdict(list)
    by_tag_grade: dict = defaultdict(Counter)
    by_tag_resp: dict = defaultdict(lambda: [0, 0])
    for aid, it in items.items():
        tag = it["tag"]
        by_tag_b[tag].append(it["b"])
        by_tag_grade[tag][it["grade"]] += 1
        c, t = resp.get(aid, (0, 0))
        by_tag_resp[tag][0] += c
        by_tag_resp[tag][1] += t

    # --- edges: 양쪽 존재하는 간선만 (고아 제거) ---
    kept_edges = [[a, b] for a, b in edges if a in concept_tags and b in concept_tags]
    pre_map: dict = defaultdict(list)
    nxt_map: dict = defaultdict(list)
    for a, b in kept_edges:
        if a == b:
            continue
        nxt_map[a].append(b)
        pre_map[b].append(a)

    unmatched = 0
    concepts: dict = {}
    for tag in concept_tags:
        meta = concepts_meta.get(tag)
        if meta is None:
            meta = _fallback_meta(tag)
            unmatched += 1
        avg_b = sum(by_tag_b[tag]) / len(by_tag_b[tag])
        c, t = by_tag_resp[tag]
        concepts[tag] = {
            "tag": tag,
            "name": meta["name"],
            "description": meta["description"],
            "semester": meta["semester"],
            "chapter": meta["chapter"],
            "achievement": meta["achievement"],
            "grade": by_tag_grade[tag].most_common(1)[0][0],
            "avg_b": round(avg_b, 4),
            "band": irt.band(avg_b, b_hard, b_easy),
            "correct_rate": round(c / t * 100, 1) if t else None,
            "item_count": len(by_tag_b[tag]),
            "prereq_tags": pre_map.get(tag, []),
            "next_tags": nxt_map.get(tag, []),
        }

    print(
        f"[etl] 개념 {len(concepts)} (미매칭 폴백 {unmatched}) · "
        f"문항 {len(items)} · 간선 {len(kept_edges)}/{len(edges)} 유지",
        file=sys.stderr,
    )
    return {"concepts": concepts, "items": items, "edges": kept_edges,
            "learners": learners, "thresholds": {"b_hard": b_hard, "b_easy": b_easy}}


# --------------------------------------------------------------------------- #
# 4) 진입점
# --------------------------------------------------------------------------- #
def _find(root: str, pattern: str) -> str:
    hits = glob.glob(os.path.join(root, "**", pattern), recursive=True)
    if not hits:
        raise FileNotFoundError(f"원천 파일을 찾을 수 없습니다: {pattern} (root={root})")
    return hits[0]


def build_catalog(raw_dir: str, grades=None, limit=None) -> dict:
    ks_path = _find(raw_dir, "[[]라벨[]]수학 지식체계 데이터 세트*.json")
    zip_path = _find(raw_dir, "[[]원천[]]성취수준데이터셋_train.zip")
    concepts_meta, edges = parse_knowledge_system(ks_path)
    item_irt, resp, theta_map, profiles = stream_zip(zip_path, grades, limit)
    learners = sample_learners(theta_map, profiles)
    return assemble(concepts_meta, edges, item_irt, resp, learners)


def write_catalog(catalog: dict) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    for key, path in (
        ("concepts", config.CONCEPTS_PATH),
        ("items", config.ITEMS_PATH),
        ("edges", config.EDGES_PATH),
        ("learners", config.LEARNERS_PATH),
        ("thresholds", config.THRESHOLDS_PATH),
    ):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(catalog[key], f, ensure_ascii=False)
