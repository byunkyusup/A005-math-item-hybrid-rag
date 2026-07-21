"""AIHub 원천 → 경량 카탈로그(concepts/items/edges/learners.json).

사용:
  python build_catalog.py                 # 전량 (오래 걸림)
  python build_catalog.py --grade 3학년    # 특정 학년만 (반복 지정 가능)
  python build_catalog.py --limit 200000   # 정오답표 집계 상한(개발용)
"""

import argparse
import sys

from src import config, etl


def main():
    p = argparse.ArgumentParser(description="실데이터 → 카탈로그 ETL")
    p.add_argument("--grade", action="append", help="예: 3학년 (반복 가능)")
    p.add_argument("--limit", type=int, default=None, help="정오답표 집계 상한")
    args = p.parse_args()

    grades = set(args.grade) if args.grade else None
    catalog = etl.build_catalog(config.RAW_DATA_DIR, grades=grades, limit=args.limit)
    etl.write_catalog(catalog)
    print(
        f"완료 → {config.DATA_DIR}\n"
        f"  개념 {len(catalog['concepts'])} · 문항 {len(catalog['items'])} · "
        f"간선 {len(catalog['edges'])} · 학습자표본 {len(catalog['learners'])}"
    )


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError, OSError) as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        sys.exit(1)
