#!/usr/bin/env python3
"""
Archinator bootstrap script.

Phases:
  1. Extract semantic core from PDF + OpenGroup website
  2. Interactive review — accept / edit / re-extract
  3. Build ChromaDB RAG index from PDF

Usage:
    python scripts/bootstrap.py --pdf data/archimate_spec.pdf [--skip-review] [--index-only]
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
DATA_DIR = Path(__file__).parent.parent / "data"
DRAFT_PATH = DATA_DIR / "semantic_core_draft.md"
FINAL_PATH = DATA_DIR / "semantic_core.md"
CHROMA_DIR = DATA_DIR / "chroma"

OPENGROUP_URLS = [
    "https://pubs.opengroup.org/architecture/archimate32-doc/",
    "https://pubs.opengroup.org/architecture/archimate32-doc/chap03.html",
    "https://pubs.opengroup.org/architecture/archimate32-doc/chap04.html",
    "https://pubs.opengroup.org/architecture/archimate32-doc/chap05.html",
    "https://pubs.opengroup.org/architecture/archimate32-doc/chap06.html",
    "https://pubs.opengroup.org/architecture/archimate32-doc/chap07.html",
    "https://pubs.opengroup.org/architecture/archimate32-doc/chap08.html",
    "https://pubs.opengroup.org/architecture/archimate32-doc/chap09.html",
]


# ── Phase 1: Extraction ──────────────────────────────────────────────────────

def extract_pdf_sections(pdf_path: Path) -> str:
    import fitz  # type: ignore

    doc = fitz.open(str(pdf_path))
    sections: list[str] = []

    keywords = [
        "element", "relationship", "viewpoint", "layer", "aspect",
        "composition", "aggregation", "assignment", "realization",
        "serving", "access", "influence", "association", "triggering",
        "flow", "specialization", "abstraction", "notation",
    ]

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        lower = text.lower()
        if any(kw in lower for kw in keywords):
            sections.append(f"### Page {page_num + 1}\n\n{text.strip()}")

    doc.close()
    return "\n\n---\n\n".join(sections)


def fetch_opengroup_content() -> str:
    parts: list[str] = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for url in OPENGROUP_URLS:
            try:
                r = client.get(url)
                r.raise_for_status()
                # Strip HTML tags naively; lxml would be more reliable
                text = re.sub(r"<[^>]+>", " ", r.text)
                text = re.sub(r"\s+", " ", text).strip()
                parts.append(f"## Source: {url}\n\n{text[:8000]}")
            except Exception as exc:
                console.print(f"[yellow]Warning: could not fetch {url}: {exc}[/yellow]")
    return "\n\n---\n\n".join(parts)


def build_semantic_core_prompt(pdf_text: str, web_text: str) -> str:
    return textwrap.dedent(f"""
        You are an ArchiMate 3.2 expert. Using the source material below, produce a concise,
        structured reference document titled "ArchiMate 3.2 Semantic Core Reference".

        The document MUST include the following sections, in order:

        1. **Element Catalogue** — All element types grouped by layer and aspect.
           For each: type name, layer, aspect, brief description (1 sentence).

        2. **Relationship Types** — All relationship types.
           For each: name, direction (directed/undirected), short description, and the
           allowed (source aspect, target aspect) pairs from the generic metamodel.

        3. **Layer Definitions** — Brief description of each layer
           (Strategy, Business, Application, Technology, Physical, Motivation,
           Implementation & Migration).

        4. **Viewpoint Catalogue** — All standard viewpoints.
           For each: name, permitted element types, permitted relationships, purpose.

        5. **Abstraction Rules** — Rules for abstracting/compacting diagrams
           (grouping, aggregation, specialization collapsing, cross-layer hiding).

        6. **Key Validity Rules** — The most important rules that make a diagram
           valid or invalid (max 20 bullet points, precise language).

        Be precise. Use the exact ArchiMate type names. Do not invent types.
        Output ONLY the Markdown document, no preamble.

        --- PDF SOURCE (relevant sections) ---
        {pdf_text[:20000]}

        --- OPENGROUP WEBSITE SOURCE ---
        {web_text[:10000]}
    """).strip()


def call_ollama_for_extraction(prompt: str, model: str, base_url: str) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 4096},
    }
    with httpx.Client(timeout=300) as client:
        r = client.post(f"{base_url}/api/generate", json=payload)
        r.raise_for_status()
        return r.json()["response"]


# ── Phase 2: Interactive review ───────────────────────────────────────────────

def review_draft(draft_path: Path) -> bool:
    """Returns True if user accepted the draft."""
    console.print(Panel("[bold]Phase 2: Semantic Core Review[/bold]", style="cyan"))
    console.print(Markdown(draft_path.read_text(encoding="utf-8")))
    console.print()

    while True:
        choice = console.input(
            "[cyan]Accept this draft? [A]ccept / [E]dit in editor / [R]eject: [/cyan]"
        ).strip().upper()

        if choice == "A":
            return True

        if choice == "E":
            editor = os.environ.get("EDITOR", "notepad" if sys.platform == "win32" else "nano")
            subprocess.run([editor, str(draft_path)], check=False)
            console.print("[green]Re-displaying edited draft...[/green]")
            console.print(Markdown(draft_path.read_text(encoding="utf-8")))

        elif choice == "R":
            console.print("[red]Draft rejected. Re-run bootstrap to re-extract.[/red]")
            return False

        else:
            console.print("[yellow]Please enter A, E, or R.[/yellow]")


# ── Phase 3: RAG index ────────────────────────────────────────────────────────

def build_rag_index(pdf_path: Path, chroma_dir: Path) -> None:
    import fitz  # type: ignore
    import chromadb  # type: ignore
    from sentence_transformers import SentenceTransformer  # type: ignore

    console.print(Panel("[bold]Phase 3: Building RAG index[/bold]", style="cyan"))

    if chroma_dir.exists():
        console.print(f"[yellow]Removing existing ChromaDB at {chroma_dir}[/yellow]")
        shutil.rmtree(chroma_dir)

    model = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_or_create_collection(
        name="archimate_spec",
        metadata={"hnsw:space": "cosine"},
    )

    doc = fitz.open(str(pdf_path))
    chunk_size = 600  # tokens-ish (words)
    chunks: list[str] = []
    ids: list[str] = []
    metadatas: list[dict] = []

    for page_num in range(len(doc)):
        text = doc[page_num].get_text().strip()
        if not text:
            continue
        words = text.split()
        # Sliding window with 100-word overlap
        for i in range(0, len(words), chunk_size - 100):
            chunk = " ".join(words[i : i + chunk_size])
            chunk_id = hashlib.md5(f"p{page_num}_{i}".encode()).hexdigest()
            chunks.append(chunk)
            ids.append(chunk_id)
            metadatas.append({"page": page_num + 1, "offset": i})
            if len(chunks) >= 100:
                _upsert_batch(collection, model, chunks, ids, metadatas)
                chunks, ids, metadatas = [], [], []

    if chunks:
        _upsert_batch(collection, model, chunks, ids, metadatas)

    doc.close()
    console.print(f"[green]RAG index built: {collection.count()} chunks indexed.[/green]")


def _upsert_batch(collection, model, chunks, ids, metadatas) -> None:  # type: ignore
    embeddings = model.encode(chunks, show_progress_bar=False).tolist()
    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )


# ── CLI entry point ───────────────────────────────────────────────────────────

@click.command()
@click.option("--pdf", "pdf_path", type=click.Path(exists=True), required=True,
              help="Path to ArchiMate 3.2 spec PDF")
@click.option("--ollama-url", default="http://localhost:11434", show_default=True)
@click.option("--ollama-model", default="llama3.3", show_default=True)
@click.option("--skip-review", is_flag=True, default=False,
              help="Skip interactive review; auto-accept draft")
@click.option("--index-only", is_flag=True, default=False,
              help="Skip extraction; only (re)build the RAG index")
def main(
    pdf_path: str,
    ollama_url: str,
    ollama_model: str,
    skip_review: bool,
    index_only: bool,
) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    pdf = Path(pdf_path)

    if not index_only:
        # ── Phase 1 ──────────────────────────────────────────────────────────
        console.print(Panel("[bold]Phase 1: Extracting semantic core[/bold]", style="cyan"))

        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
            t = p.add_task("Parsing PDF...", total=None)
            pdf_text = extract_pdf_sections(pdf)
            p.update(t, description="Fetching OpenGroup website...")
            web_text = fetch_opengroup_content()

        console.print(f"[green]PDF: {len(pdf_text):,} chars extracted from relevant sections.[/green]")
        console.print(f"[green]Web: {len(web_text):,} chars fetched from OpenGroup.[/green]")

        prompt = build_semantic_core_prompt(pdf_text, web_text)

        console.print(f"[cyan]Calling Ollama ({ollama_model}) for extraction...[/cyan]")
        try:
            draft_content = call_ollama_for_extraction(prompt, ollama_model, ollama_url)
        except Exception as exc:
            console.print(f"[red]Ollama call failed: {exc}[/red]")
            console.print("[yellow]Writing raw extracted text as draft for manual editing.[/yellow]")
            draft_content = f"# ArchiMate 3.2 Semantic Core Reference\n\n## RAW EXTRACT (NEEDS MANUAL EDITING)\n\n{pdf_text[:15000]}"

        DRAFT_PATH.write_text(draft_content, encoding="utf-8")
        console.print(f"[green]Draft written to {DRAFT_PATH}[/green]")

        # ── Phase 2 ──────────────────────────────────────────────────────────
        if skip_review:
            accepted = True
            console.print("[yellow]--skip-review set: auto-accepting draft.[/yellow]")
        else:
            accepted = review_draft(DRAFT_PATH)

        if not accepted:
            sys.exit(1)

        shutil.copy(DRAFT_PATH, FINAL_PATH)
        console.print(f"[green]Semantic core written to {FINAL_PATH}[/green]")

    # ── Phase 3 ──────────────────────────────────────────────────────────────
    build_rag_index(pdf, CHROMA_DIR)
    console.print("[bold green]Bootstrap complete.[/bold green]")


if __name__ == "__main__":
    main()
