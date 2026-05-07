from __future__ import annotations
import hashlib
from pathlib import Path
from functools import lru_cache

_DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / "data"
_CHROMA_DIR = _DATA_DIR / "chroma"


@lru_cache(maxsize=1)
def _get_collection():  # type: ignore
    import chromadb  # type: ignore
    from sentence_transformers import SentenceTransformer  # type: ignore

    client = chromadb.PersistentClient(path=str(_CHROMA_DIR))
    collection = client.get_or_create_collection(
        name="archimate_spec",
        metadata={"hnsw:space": "cosine"},
    )
    return collection, SentenceTransformer("all-MiniLM-L6-v2")


def query(question: str, n_results: int = 5) -> list[str]:
    """Return top-n relevant spec chunks for the given question."""
    if not _CHROMA_DIR.exists():
        return []
    try:
        collection, model = _get_collection()
        if collection.count() == 0:
            return []
        embedding = model.encode([question]).tolist()
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
