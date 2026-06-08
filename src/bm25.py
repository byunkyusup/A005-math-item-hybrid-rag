"""순수 파이썬 BM25 (Okapi) 구현 + 역색인(postings)으로 검색 가속.

희소(sparse) 어휘 검색을 담당한다. 정확한 키워드(학년/단원/개념)에 강하다.
"""

import math
from collections import Counter, defaultdict

from src import config


class BM25:
    def __init__(self, tokenized_docs, k1=config.BM25_K1, b=config.BM25_B):
        self.k1 = k1
        self.b = b
        self.n_docs = len(tokenized_docs)
        self.doc_len = [len(doc) for doc in tokenized_docs]
        self.avgdl = (sum(self.doc_len) / self.n_docs) if self.n_docs else 0.0

        # 문서별 단어 빈도 + 역색인(term -> [(doc_id, tf), ...])
        self.postings = defaultdict(list)
        df = Counter()
        for doc_id, doc in enumerate(tokenized_docs):
            tf = Counter(doc)
            for term, freq in tf.items():
                self.postings[term].append((doc_id, freq))
                df[term] += 1

        # IDF (BM25 변형: 음수 방지를 위해 1+ 형태 사용)
        self.idf = {
            term: math.log(1 + (self.n_docs - n + 0.5) / (n + 0.5))
            for term, n in df.items()
        }

    def search(self, query_tokens, top_k):
        """질의 토큰으로 BM25 점수 상위 top_k를 [(doc_id, score)]로 반환."""
        scores = defaultdict(float)
        for term in query_tokens:
            idf = self.idf.get(term)
            if idf is None:
                continue
            for doc_id, freq in self.postings[term]:
                denom = freq + self.k1 * (
                    1 - self.b + self.b * self.doc_len[doc_id] / self.avgdl
                )
                scores[doc_id] += idf * (freq * (self.k1 + 1)) / denom

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:top_k]
