"""로컬 Ollama HTTP API 클라이언트 (stdlib urllib 사용, 외부 의존성 없음)."""

import json
import urllib.request
import urllib.error

from src import config


def _post(path, payload, timeout=120):
    """Ollama 엔드포인트에 JSON POST 후 응답을 dict로 반환."""
    url = config.OLLAMA_HOST + path
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Ollama 호출 실패 ({url}). Ollama가 실행 중인지 확인하세요: `ollama serve`. 원인: {exc}"
        ) from exc


def embed(text):
    """단일 텍스트를 임베딩 벡터(list[float])로 변환."""
    result = _post("/api/embeddings", {"model": config.EMBED_MODEL, "prompt": text})
    vec = result.get("embedding")
    if not vec:
        raise RuntimeError(f"임베딩 응답이 비어 있습니다: {result}")
    return vec


def generate(prompt, temperature=0.3):
    """프롬프트로 텍스트 생성 (스트리밍 비활성, 완성된 문자열 반환)."""
    result = _post(
        "/api/generate",
        {
            "model": config.GEN_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout=300,
    )
    return result.get("response", "").strip()
