"""문서 텍스트를 Ollama 임베딩으로 변환해 data/embeddings.json 에 캐시.

질의 때마다 문서를 재임베딩하지 않도록 1회 계산해 저장한다.
사용: python build_index.py
"""

import json
import sys
import time

from src import config
from src.corpus import load_corpus
from src.ollama_client import embed


def main():
    concepts, doc_texts, embed_texts = load_corpus()
    print(f"개념 {len(embed_texts)}건 임베딩 시작 (모델: {config.EMBED_MODEL})")

    vectors = []
    t0 = time.time()
    for i, text in enumerate(embed_texts, 1):
        vectors.append(embed(text))
        if i % 25 == 0 or i == len(doc_texts):
            print(f"  {i}/{len(doc_texts)} ... ({time.time() - t0:.1f}s)")

    payload = {
        "model": config.EMBED_MODEL,
        "dim": len(vectors[0]) if vectors else 0,
        "count": len(vectors),
        "vectors": vectors,  # doc_id 순서와 정렬
    }
    with open(config.EMBED_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    print(f"완료: {config.EMBED_CACHE_PATH} (dim={payload['dim']}, {time.time() - t0:.1f}s)")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        sys.exit(1)
