from __future__ import annotations
import os
from pathlib import Path
from functools import lru_cache

import httpx

_DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / "data"
_CHROMA_DIR = _DATA_DIR / "chroma"
_OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
_EMBED_MODEL = os.environ.get("EMBED_MODEL", "bge-m3")


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed texts via Ollama /api/embed (batch)."""
    resp = httpx.post(
        f"{_OLLAMA_URL}/api/embed",
        json={"model": _EMBED_MODEL, "input": texts},
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


@lru_cache(maxsize=1)
def _get_collection():  # type: ignore
    import chromadb  # type: ignore

    client = chromadb.PersistentClient(path=str(_CHROMA_DIR))
    return client.get_or_create_collection(
        name="archimate_spec",
        metadata={"hnsw:space": "cosine"},
    )


def query(question: str, n_results: int = 5) -> list[str]:
    """Return top-n relevant spec chunks for the given question."""
    if not _CHROMA_DIR.exists():
        return []
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return []
        embedding = _embed([question])
        results = collection.query(
            query_embeddings=embedding,
            n_results=min(n_results, collection.count()),
            include=["documents"],
        )
        docs: list[str] = results.get("documents", [[]])[0]
        return docs
    except Exception:
        return []


def index_available() -> bool:
    return _CHROMA_DIR.exists() and any(_CHROMA_DIR.iterdir()) if _CHROMA_DIR.exists() else False
