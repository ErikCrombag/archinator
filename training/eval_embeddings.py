#!/usr/bin/env python3
"""
Embedding model evaluation for ArchiMate RAG retrieval.

Standalone script — no imports from the archinator backend package.
Handover from training to production is via data/chroma/ and markdown files only.

USAGE
-----
  python training/eval_embeddings.py
  python training/eval_embeddings.py --models nomic-embed-text hf:BAAI/bge-large-en-v1.5
  python training/eval_embeddings.py --models all-ollama --k 5 10
  python training/eval_embeddings.py --rebuild  # force re-embed even if collections exist

BACKENDS
--------
  Ollama models : specify by name, e.g. nomic-embed-text
  HF models     : prefix with hf:, e.g. hf:BAAI/bge-large-en-v1.5
                  Requires: pip install sentence-transformers

SCORING
-------
  recall@k : fraction of queries where >=1 relevant_term appears in top-k chunks
  MRR@k    : mean reciprocal rank of first hit (0 if no hit in top-k)
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import httpx
from rich.console import Console
from rich.table import Table

console = Console()

# ── Paths ─────────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).parent.parent
_TRAINING_DIR = Path(__file__).parent
_TRAINING_DATA_DIR = _TRAINING_DIR / "training_data"
_CHROMA_DIR = _ROOT / "data" / "chroma"       # handover artifact — read by production
_SOURCES_FILE = _TRAINING_DATA_DIR / "sources.txt"
_QUERIES_FILE = _TRAINING_DATA_DIR / "eval" / "queries.jsonl"
_RESULTS_DIR = _TRAINING_DATA_DIR / "eval" / "results"

# ── Model context limits (chars) ──────────────────────────────────────────────
# Conservative: ~3.5 chars/token. Truncate before sending to avoid 400s.
MODEL_MAX_CHARS: dict[str, int] = {
    "mxbai-embed-large": 400,       # 512 token limit; conservative for dense content
    "snowflake-arctic-embed": 400,  # 512 token limit
    "all-minilm": 400,              # 512 token limit
    "granite-embedding": 400,       # 512 token limit
    # nomic-embed-text, bge-m3, jina: 8192 tokens — no truncation needed
}
_DEFAULT_MAX_CHARS = 7000  # safe for 8192-token models

# ── Default candidate models ───────────────────────────────────────────────────

DEFAULT_MODELS = [
    "nomic-embed-text",
    "mxbai-embed-large",
    "hf:BAAI/bge-large-en-v1.5",
]

ALL_OLLAMA_CANDIDATES = [
    "nomic-embed-text",
    "mxbai-embed-large",
    "snowflake-arctic-embed",
    "bge-m3",
    "all-minilm",
    "granite-embedding",
]

ALL_HF_CANDIDATES = [
    "hf:BAAI/bge-large-en-v1.5",
    "hf:intfloat/e5-large-v2",
    "hf:Alibaba-NLP/gte-large-en-v1.5",
    "hf:dunzhang/stella_en_400M_v5",
    "hf:mixedbread-ai/mxbai-embed-large-v1",
    "hf:sentence-transformers/all-mpnet-base-v2",
]

# ── Ollama helpers ─────────────────────────────────────────────────────────────


def _ollama_embed(texts: list[str], model: str, ollama_url: str) -> list[list[float]]:
    resp = httpx.post(
        f"{ollama_url}/api/embed",
        json={"model": model, "input": texts, "truncate": True},
        timeout=120.0,
    )
    if not resp.is_success:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()["embeddings"]


def _ollama_available_models(ollama_url: str) -> list[str]:
    try:
        resp = httpx.get(f"{ollama_url}/api/tags", timeout=10.0)
        resp.raise_for_status()
        return [m["name"].split(":")[0] for m in resp.json().get("models", [])]
    except Exception:
        return []


def _ollama_pull(model: str, container: str) -> bool:
    """Pull model into Ollama via docker exec. Returns True on success."""
    try:
        result = subprocess.run(
            ["docker", "exec", container, "ollama", "pull", model],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# ── HuggingFace helpers ────────────────────────────────────────────────────────


def _hf_embed(texts: list[str], model_name: str) -> list[list[float]]:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError:
        console.print("[red]sentence-transformers not installed. Run: pip install sentence-transformers[/red]")
        sys.exit(1)

    model = SentenceTransformer(model_name, device="cpu")
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


# ── Unified embed dispatcher ───────────────────────────────────────────────────


def _truncate(texts: list[str], model_spec: str) -> list[str]:
    base = model_spec.split(":")[0].removeprefix("hf:")
    limit = MODEL_MAX_CHARS.get(base, _DEFAULT_MAX_CHARS)
    return [t[:limit] for t in texts]


def embed(texts: list[str], model_spec: str, ollama_url: str) -> list[list[float]]:
    texts = _truncate(texts, model_spec)
    if model_spec.startswith("hf:"):
        return _hf_embed(texts, model_spec[3:])
    return _ollama_embed(texts, model_spec, ollama_url)


def model_slug(model_spec: str) -> str:
    """Safe collection-name slug from model spec."""
    return re.sub(r"[^a-zA-Z0-9]", "_", model_spec)


# ── ChromaDB helpers ───────────────────────────────────────────────────────────


def _get_chroma_client(chroma_dir: Path):
    import chromadb  # type: ignore

    return chromadb.PersistentClient(path=str(chroma_dir))


def load_source_chunks(
    chroma_dir: Path, collection_name: str = "archimate_spec"
) -> tuple[list[str], list[str], list[dict], dict]:
    """Load texts, ids, metadatas, and collection metadata from a named collection."""
    client = _get_chroma_client(chroma_dir)
    try:
        col = client.get_collection(collection_name)
    except Exception:
        return [], [], [], {}

    count = col.count()
    if count == 0:
        return [], [], [], {}

    result = col.get(include=["documents", "metadatas"])
    return result["documents"], result["ids"], result["metadatas"], col.metadata or {}


def get_or_build_eval_collection(
    chroma_dir: Path,
    model_spec: str,
    texts: list[str],
    ids: list[str],
    metadatas: list[dict],
    ollama_url: str,
    rebuild: bool,
    source_collection: str = "archimate_spec",
):
    """Return eval collection for model_spec, building it if needed."""
    import chromadb  # type: ignore

    client = _get_chroma_client(chroma_dir)
    src_slug = model_slug(source_collection)[:20]
    name = f"eval_{src_slug}_{model_slug(model_spec)}"[:63]

    if rebuild:
        try:
            client.delete_collection(name)
        except Exception:
            pass

    col = client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )

    if col.count() == len(texts):
        console.print(f"  [dim]collection {name!r} exists ({col.count()} chunks), skipping build[/dim]")
        return col

    console.print(f"  embedding {len(texts)} chunks with [cyan]{model_spec}[/cyan] ...")
    batch_size = 64
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        all_embeddings.extend(embed(batch, model_spec, ollama_url))

    col.upsert(
        ids=ids,
        documents=texts,
        embeddings=all_embeddings,
        metadatas=metadatas,
    )
    console.print(f"  [green]built {name!r}[/green] ({len(texts)} chunks)")
    return col


# ── Sources fallback ───────────────────────────────────────────────────────────


def _parse_sources(sources_file: Path, data_root: Path) -> tuple[list[Path], list[str]]:
    """Parse sources.txt, remapping /app/data → data_root."""
    pdf_paths: list[Path] = []
    urls: list[str] = []

    if not sources_file.exists():
        return pdf_paths, urls

    for raw_line in sources_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("http://") or line.startswith("https://"):
            urls.append(line)
        else:
            # Remap Docker /app/data paths to local data_root
            remapped = line.replace("/app/data", str(data_root), 1) if line.startswith("/app/data") else line
            p = Path(remapped)
            if p.is_dir():
                pdf_paths.extend(sorted(p.glob("*.pdf")))
            elif p.suffix.lower() == ".pdf" and p.exists():
                pdf_paths.append(p)

    return pdf_paths, urls


def _chunk_text(text: str, chunk_words: int = 500, overlap_words: int = 80) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_words])
        chunks.append(chunk[:2000])
        i += chunk_words - overlap_words
    return chunks


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_chunks_from_sources(sources_file: Path, data_root: Path) -> tuple[list[str], list[str], list[dict]]:
    """Fallback: build text chunks from sources.txt PDFs and web URLs (no vision pass)."""
    import fitz  # type: ignore  # pymupdf

    pdf_paths, urls = _parse_sources(sources_file, data_root)
    if not pdf_paths and not urls:
        return [], [], []

    texts, ids, metadatas = [], [], []

    for pdf_path in pdf_paths:
        console.print(f"  parsing [cyan]{pdf_path.name}[/cyan] ...")
        doc = fitz.open(str(pdf_path))
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text()
            if not page_text.strip():
                continue
            for chunk_i, chunk in enumerate(_chunk_text(page_text)):
                chunk_id = f"src:{pdf_path.name}:p{page_num}:c{chunk_i}"
                texts.append(chunk)
                ids.append(chunk_id)
                metadatas.append({"source": pdf_path.name, "page": page_num, "kind": "book"})
        doc.close()

    for url in urls:
        console.print(f"  fetching [cyan]{url}[/cyan] ...")
        try:
            resp = httpx.get(url, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            page_text = _strip_html(resp.text)
            if not page_text.strip():
                continue
            for chunk_i, chunk in enumerate(_chunk_text(page_text)):
                chunk_id = f"web:{hashlib.md5(f'{url}:{chunk_i}'.encode()).hexdigest()[:8]}"
                texts.append(chunk)
                ids.append(chunk_id)
                metadatas.append({"source": url, "kind": "web"})
        except Exception as exc:
            console.print(f"  [yellow]failed to fetch {url}: {exc}[/yellow]")

    return texts, ids, metadatas


# ── Scoring ────────────────────────────────────────────────────────────────────


def score_query(retrieved: list[str], relevant_terms: list[str], min_matches: int = 1) -> int | None:
    """Return 1-based rank of first chunk where >= min_matches relevant_terms appear, or None."""
    for rank, chunk in enumerate(retrieved, start=1):
        chunk_lower = chunk.lower()
        matches = sum(1 for t in relevant_terms if t.lower() in chunk_lower)
        if matches >= min_matches:
            return rank
    return None


def compute_metrics(ranks: list[int | None], k: int) -> tuple[float, float]:
    """Return (recall@k, MRR@k)."""
    hits = [r for r in ranks if r is not None and r <= k]
    recall = len(hits) / len(ranks) if ranks else 0.0
    mrr = sum(1.0 / r for r in hits) / len(ranks) if ranks else 0.0
    return recall, mrr


# ── Main ───────────────────────────────────────────────────────────────────────


@click.command()
@click.option("--models", multiple=True, default=DEFAULT_MODELS, show_default=True,
              help="Models to evaluate. Use 'all-ollama', 'all-hf', or 'all' as shortcuts.")
@click.option("--k", "k_values", multiple=True, type=int, default=[5, 10, 20, 50, 100, 200], show_default=True,
              help="k values for recall@k and MRR@k.")
@click.option("--ollama-url", default="http://localhost:11434", show_default=True)
@click.option("--ollama-container", default="ollama", show_default=True,
              help="Docker container name for auto-pulling Ollama models.")
@click.option("--chroma-dir", type=click.Path(path_type=Path), default=_CHROMA_DIR, show_default=True)
@click.option("--sources", "sources_file", type=click.Path(path_type=Path), default=_SOURCES_FILE, show_default=True)
@click.option("--data-root", type=click.Path(path_type=Path), default=_TRAINING_DATA_DIR, show_default=True,
              help="Remaps /app/data paths in sources.txt to this directory.")
@click.option("--queries", "queries_file", type=click.Path(path_type=Path), default=_QUERIES_FILE, show_default=True)
@click.option("--rebuild", is_flag=True, default=False, help="Force rebuild of eval collections.")
@click.option("--no-autopull", is_flag=True, default=False, help="Skip auto-pulling Ollama models.")
@click.option("--source-collection", default="archimate_spec", show_default=True,
              help="ChromaDB collection to load source chunks from (matches --collection-name in bootstrap).")
def main(
    models: tuple[str, ...],
    k_values: tuple[int, ...],
    ollama_url: str,
    ollama_container: str,
    chroma_dir: Path,
    sources_file: Path,
    data_root: Path,
    queries_file: Path,
    rebuild: bool,
    no_autopull: bool,
    source_collection: str,
) -> None:
    k_values = sorted(set(k_values))

    # Resolve all paths to absolute and print for transparency
    chroma_dir = chroma_dir.resolve()
    sources_file = sources_file.resolve()
    data_root = data_root.resolve()
    queries_file = queries_file.resolve()
    results_dir = (_RESULTS_DIR).resolve()
    console.print(f"[dim]chroma_dir  : {chroma_dir}[/dim]")
    console.print(f"[dim]sources     : {sources_file}[/dim]")
    console.print(f"[dim]data_root   : {data_root}[/dim]")
    console.print(f"[dim]queries     : {queries_file}[/dim]")
    console.print(f"[dim]results_dir : {results_dir}[/dim]")

    # Expand model shortcuts
    model_list: list[str] = []
    for m in models:
        if m == "all-ollama":
            model_list.extend(ALL_OLLAMA_CANDIDATES)
        elif m == "all-hf":
            model_list.extend(ALL_HF_CANDIDATES)
        elif m == "all":
            model_list.extend(ALL_OLLAMA_CANDIDATES)
            model_list.extend(ALL_HF_CANDIDATES)
        else:
            model_list.append(m)
    model_list = list(dict.fromkeys(model_list))  # deduplicate, preserve order

    # ── Load queries ──────────────────────────────────────────────────────────
    if not queries_file.exists():
        console.print(f"[red]Queries file not found: {queries_file}[/red]")
        sys.exit(1)

    queries: list[dict[str, Any]] = []
    for line in queries_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            queries.append(json.loads(line))
    console.print(f"Loaded [bold]{len(queries)}[/bold] queries from {queries_file}")

    # ── Load or build source chunks ───────────────────────────────────────────
    console.print(f"\nLoading chunks from [cyan]{chroma_dir}[/cyan] collection [cyan]{source_collection!r}[/cyan] ...")
    texts, ids, metadatas, col_meta = load_source_chunks(chroma_dir, source_collection)
    chunk_words: int = col_meta.get("chunk_words", 0)
    overlap_words: int = col_meta.get("overlap_words", 0)
    if chunk_words:
        console.print(f"  [dim]chunk_words={chunk_words}, overlap_words={overlap_words}[/dim]")

    if not texts:
        console.print("[yellow]Collection empty or missing. Falling back to sources.[/yellow]")
        texts, ids, metadatas = build_chunks_from_sources(sources_file, data_root)
        col_meta = {}

    if not texts:
        console.print("[red]No chunks available. Run bootstrap first, or check sources.txt.[/red]")
        sys.exit(1)

    console.print(f"  {len(texts)} chunks ready for re-embedding.\n")

    # ── Auto-pull Ollama models ───────────────────────────────────────────────
    ollama_models_needed = [m for m in model_list if not m.startswith("hf:")]
    if ollama_models_needed and not no_autopull:
        available = set(_ollama_available_models(ollama_url))
        for m in ollama_models_needed:
            base = m.split(":")[0]
            if base not in available:
                console.print(f"  pulling [cyan]{m}[/cyan] via docker exec {ollama_container} ...")
                ok = _ollama_pull(m, ollama_container)
                if not ok:
                    console.print(f"  [yellow]auto-pull failed for {m}. Run manually: docker exec {ollama_container} ollama pull {m}[/yellow]")

    # ── Build eval collections + run queries ──────────────────────────────────
    results: dict[str, dict[str, Any]] = {}

    for model_spec in model_list:
        console.print(f"\n[bold]Model:[/bold] {model_spec}")
        try:
            col = get_or_build_eval_collection(
                chroma_dir, model_spec, texts, ids, metadatas, ollama_url, rebuild, source_collection
            )
        except Exception as exc:
            console.print(f"  [red]failed to build collection: {exc}[/red]")
            continue

        ranks: list[int | None] = []
        for q in queries:
            try:
                q_emb = embed([q["query"]], model_spec, ollama_url)
                n = min(max(k_values), col.count())
                res = col.query(query_embeddings=q_emb, n_results=n, include=["documents"])
                retrieved: list[str] = res.get("documents", [[]])[0]
                ranks.append(score_query(retrieved, q["relevant_terms"], q.get("min_matches", 1)))
            except Exception as exc:
                console.print(f"  [yellow]query {q['id']} failed: {exc}[/yellow]")
                ranks.append(None)

        results[model_spec] = {"ranks": ranks}

    # ── Print results table ───────────────────────────────────────────────────
    console.print()
    table = Table(title="Embedding Model Evaluation", show_header=True, header_style="bold")
    table.add_column("Model", style="cyan", no_wrap=True)
    for k in k_values:
        table.add_column(f"recall@{k}", justify="right")
        table.add_column(f"MRR@{k}", justify="right")

    for model_spec, data in results.items():
        label = model_spec + (" [baseline]" if model_spec == "nomic-embed-text" else "")
        row = [label]
        for k in k_values:
            recall, mrr = compute_metrics(data["ranks"], k)
            row += [f"{recall:.3f}", f"{mrr:.3f}"]
        table.add_row(*row)

    console.print(table)

    # ── Save JSON results ─────────────────────────────────────────────────────
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = results_dir / f"results_{ts}.json"

    output = {
        "timestamp": ts,
        "source_collection": source_collection,
        "chunk_words": chunk_words or None,
        "overlap_words": overlap_words or None,
        "queries": len(queries),
        "chunks": len(texts),
        "k_values": list(k_values),
        "models": {
            model_spec: {
                f"recall@{k}": compute_metrics(data["ranks"], k)[0]
                for k in k_values
            } | {
                f"MRR@{k}": compute_metrics(data["ranks"], k)[1]
                for k in k_values
            }
            for model_spec, data in results.items()
        },
    }
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    console.print(f"\nResults saved to [cyan]{out_path}[/cyan]")


if __name__ == "__main__":
    main()
