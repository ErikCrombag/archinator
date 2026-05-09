"""Quick ChromaDB inspector — run from repo root."""
import os
import sys
import httpx
import chromadb

CHROMA_DIR = "data/chroma"
COLLECTION = "archimate_spec"
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")


def embed(text: str) -> list[float]:
    resp = httpx.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": [text]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"][0]


client = chromadb.PersistentClient(path=CHROMA_DIR)
col = client.get_collection(COLLECTION)

print(f"Collection: {COLLECTION}")
print(f"Chunks:     {col.count()}\n")

if len(sys.argv) > 1:
    query = " ".join(sys.argv[1:])
    print(f"Query: {query!r}  (embedding via {EMBED_MODEL})\n")
    vec = embed(query)
    results = col.query(query_embeddings=[vec], n_results=5)
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        print(meta)
        print(doc[:300])
        print("---")
else:
    print("Peek (first 5):")
    peek = col.peek(5)
    for doc, meta in zip(peek["documents"], peek["metadatas"]):
        print(meta)
        print(doc[:300])
        print("---")
    print('\nUsage: python scripts/inspect_chroma.py "query terms"')
