#!/usr/bin/env python3
"""
Archinator bootstrap script.

PURPOSE
-------
Build the qualitative knowledge base that the LLM draws on at generation time.
Formal rules (element types, relationship constraints, viewpoints) are owned by
validation/rules.py and rendered into data/rules_core.md at Docker build time.
This script handles everything rules.py cannot capture:

  • Examples and diagram patterns from the book / spec
  • Modeling best practices and dos & don'ts
  • Layer-specific guidance (when to use X vs Y)
  • Relationship selection heuristics
  • Common modelling anti-patterns

OUTPUTS
-------
  data/chroma/         — ChromaDB RAG index (primary output)
  data/semantic_core.md — Qualitative guidance for the LLM system prompt (optional)

PHASES
------
  1. Build RAG index from PDF + web sources  (always runs unless --guidance-only)
  2. Extract qualitative guidance → semantic_core.md  (skipped with --index-only)
  3. Interactive review of semantic_core.md  (skipped with --skip-review)

Usage:
    python scripts/bootstrap.py --pdf data/archimate_book.pdf
    python scripts/bootstrap.py --pdf data/archimate_book.pdf --index-only
    python scripts/bootstrap.py --pdf data/archimate_book.pdf --guidance-only
    python scripts/bootstrap.py --pdf data/archimate_book.pdf --skip-review
    python scripts/bootstrap.py --pdf data/archimate_book.pdf \\
        --ollama-url http://ai-server:11434 --ollama-model llama3.3
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

console = Console()
DATA_DIR = Path(__file__).parent.parent / "data"
DRAFT_PATH = DATA_DIR / "semantic_core_draft.md"
FINAL_PATH = DATA_DIR / "semantic_core.md"
CHROMA_DIR = DATA_DIR / "chroma"

# Web sources for supplementary content.
# Focus on usage examples, patterns, and community guidance — not the normative spec
# (the spec's formal rules are already in rules_core.md via rules.py).
WEB_SOURCES: list[dict] = [
    {
        "url": "https://pubs.opengroup.org/architecture/archimate32-doc/chap08.html",
        "label": "ArchiMate 3.2 Business Layer",
        "kind": "spec",
    },
    {
        "url": "https://pubs.opengroup.org/architecture/archimate32-doc/chap09.html",
        "label": "ArchiMate 3.2 Application Layer",
        "kind": "spec",
    },
    {
        "url": "https://pubs.opengroup.org/architecture/archimate32-doc/chap10.html",
        "label": "ArchiMate 3.2 Technology Layer",
        "kind": "spec",
    },
    {
        "url": "https://pubs.opengroup.org/architecture/archimate32-doc/chap11.html",
        "label": "ArchiMate 3.2 Physical Layer",
        "kind": "spec",
    },
    {
        "url": "https://pubs.opengroup.org/architecture/archimate32-doc/chap06.html",
        "label": "ArchiMate 3.2 Motivation",
        "kind": "spec",
    },
    {
        "url": "https://pubs.opengroup.org/architecture/archimate32-doc/chap07.html",
        "label": "ArchiMate 3.2 Strategy",
        "kind": "spec",
    },
    {
        "url": "https://pubs.opengroup.org/architecture/archimate32-doc/apdxc.html",
        "label": "ArchiMate 3.2 Example Viewpoints",
        "kind": "examples",
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ── Phase 1: RAG index ────────────────────────────────────────────────────────

def _detect_view_ref(text: str) -> str | None:
    """Return 'View N' label if page text references a numbered view/figure."""
    m = re.search(r"\b(?:View|Figure)\s+(\d+)", text)
    return f"View {m.group(1)}" if m else None


def build_rag_index(pdf_path: Path, extra_urls: list[str] | None = None) -> None:
    """
    Chunk and embed:
      - All pages of the PDF (not keyword-filtered — LLM query handles relevance)
      - Web sources from WEB_SOURCES + any extra_urls passed in

    Metadata stored per chunk: source, page (PDF) or url (web), kind, view_ref.
    """
    import fitz  # type: ignore
    import chromadb  # type: ignore
    from sentence_transformers import SentenceTransformer  # type: ignore

    console.print(Panel("[bold]Phase 1: Building RAG index[/bold]", style="cyan"))

    if CHROMA_DIR.exists():
        console.print(f"[yellow]Removing existing ChromaDB at {CHROMA_DIR}[/yellow]")
        shutil.rmtree(CHROMA_DIR)

    embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name="archimate_spec",
        metadata={"hnsw:space": "cosine"},
    )

    pending_chunks: list[str] = []
    pending_ids: list[str] = []
    pending_meta: list[dict] = []

    def flush() -> None:
        if not pending_chunks:
            return
        embeddings = embed_model.encode(pending_chunks, show_progress_bar=False).tolist()
        collection.upsert(
            ids=pending_ids,
            documents=pending_chunks,
            embeddings=embeddings,
            metadatas=pending_meta,
        )
        pending_chunks.clear()
        pending_ids.clear()
        pending_meta.clear()

    def add_chunk(text: str, meta: dict, key: str) -> None:
        chunk_id = hashlib.md5(key.encode()).hexdigest()
        pending_chunks.append(text)
        pending_ids.append(chunk_id)
        pending_meta.append(meta)
        if len(pending_chunks) >= 64:
            flush()

    # ── PDF ──────────────────────────────────────────────────────────────────
    CHUNK_WORDS = 500
    OVERLAP_WORDS = 80

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Indexing PDF pages...", total=total_pages)

        for page_num in range(total_pages):
            text = doc[page_num].get_text().strip()
            if not text:
                progress.advance(task)
                continue

            view_ref = _detect_view_ref(text)
            words = text.split()

            for i in range(0, max(1, len(words) - OVERLAP_WORDS), CHUNK_WORDS - OVERLAP_WORDS):
                chunk = " ".join(words[i : i + CHUNK_WORDS])
                meta: dict = {
                    "source": pdf_path.name,
                    "page": page_num + 1,
                    "kind": "book",
                }
                if view_ref:
                    meta["view_ref"] = view_ref
                add_chunk(chunk, meta, f"pdf:p{page_num}:w{i}")

            progress.advance(task)

    doc.close()

    # ── Web sources ───────────────────────────────────────────────────────────
    all_web = list(WEB_SOURCES)
    for url in (extra_urls or []):
        all_web.append({"url": url, "label": url, "kind": "web"})

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for src in all_web:
            url = src["url"]
            try:
                r = client.get(url)
                r.raise_for_status()
                text = _strip_html(r.text)
                words = text.split()
                for i in range(0, max(1, len(words) - OVERLAP_WORDS), CHUNK_WORDS - OVERLAP_WORDS):
                    chunk = " ".join(words[i : i + CHUNK_WORDS])
                    meta = {"source": url, "label": src.get("label", url), "kind": src.get("kind", "web")}
                    add_chunk(chunk, meta, f"web:{url}:w{i}")
                console.print(f"[green]  indexed {url} ({len(words):,} words)[/green]")
            except Exception as exc:
                console.print(f"[yellow]  warning: could not fetch {url}: {exc}[/yellow]")

    flush()
    console.print(f"[green]RAG index ready: {collection.count()} chunks.[/green]")


# ── Phase 2: Guidance extraction ──────────────────────────────────────────────

def _guidance_prompt(pdf_text: str, web_text: str) -> str:
    return textwrap.dedent(f"""
        You are an ArchiMate 3.2 modeling expert. Using the source material below,
        produce a concise reference titled "ArchiMate 3.2 Modeling Guidance".

        IMPORTANT: Do NOT reproduce formal rules (element types, relationship aspect pairs,
        viewpoint element lists). Those are defined elsewhere. Focus exclusively on:

        1. **Layer-by-layer modeling guidance**
           For each layer (Strategy, Business, Application, Technology, Physical,
           Motivation, Implementation): when and how to use it, typical patterns,
           common mistakes.

        2. **Relationship selection heuristics**
           When to prefer Serving vs Association, Realization vs Assignment,
           Access vs Flow, Influence vs Realization, etc.
           Concrete examples: "Use Serving when X; use Association when Y."

        3. **Dos and Don'ts** (20–30 bullet points)
           Practical rules that prevent common modelling errors.
           Examples:
           - Do: assign a BusinessRole to a BusinessActor via Assignment
           - Don't: use Triggering between structure elements
           - Do: keep Motivation elements in the Motivation layer

        4. **Common anti-patterns** (10–15 items)
           Patterns that look plausible but violate ArchiMate semantics.
           Explain why each is wrong and what to use instead.

        5. **Viewpoint selection guidance**
           How to choose the right viewpoint for a given audience/concern.
           Brief description of when each standard viewpoint is appropriate.

        6. **Cross-layer modeling tips**
           How to correctly model the interfaces between layers (realization chains,
           serving relationships, cross-layer access).

        Be specific and practical. Use exact ArchiMate element and relationship type names.
        Output ONLY the Markdown document, no preamble or closing remarks.

        --- PDF SOURCE ---
        {pdf_text[:25000]}

        --- WEB SOURCE ---
        {web_text[:8000]}
    """).strip()


def _extract_pdf_for_guidance(pdf_path: Path) -> str:
    """Extract pages most likely to contain modeling guidance and examples."""
    import fitz  # type: ignore

    doc = fitz.open(str(pdf_path))
    guidance_keywords = [
        "best practice", "guideline", "example", "illustrat", "recommend",
        "avoid", "do not", "should", "typical", "common", "pattern",
        "when to use", "instead of", "rather than", "note:", "tip:",
    ]
    parts: list[str] = []
    for page_num in range(len(doc)):
        text = doc[page_num].get_text().strip()
        lower = text.lower()
        if any(kw in lower for kw in guidance_keywords):
            parts.append(f"[Page {page_num + 1}]\n{text}")
    doc.close()
    return "\n\n---\n\n".join(parts)


def _fetch_web_for_guidance() -> str:
    parts: list[str] = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for src in WEB_SOURCES:
            if src.get("kind") not in ("examples", "spec"):
                continue
            try:
                r = client.get(src["url"])
                r.raise_for_status()
                text = _strip_html(r.text)
                parts.append(f"## {src['label']}\n\n{text[:6000]}")
            except Exception as exc:
                console.print(f"[yellow]  warning: {src['url']}: {exc}[/yellow]")
    return "\n\n---\n\n".join(parts)


def call_ollama(prompt: str, model: str, base_url: str) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 6000},
    }
    with httpx.Client(timeout=300) as client:
        r = client.post(f"{base_url}/api/generate", json=payload)
        r.raise_for_status()
        return r.json()["response"]


# ── Phase 3: Interactive review ───────────────────────────────────────────────

def review_draft() -> bool:
    console.print(Panel("[bold]Phase 3: Review guidance draft[/bold]", style="cyan"))
    console.print(Markdown(DRAFT_PATH.read_text(encoding="utf-8")))
    console.print()

    while True:
        choice = console.input(
            "[cyan]Accept? [A]ccept / [E]dit in editor / [R]eject: [/cyan]"
        ).strip().upper()

        if choice == "A":
            return True
        if choice == "E":
            editor = os.environ.get("EDITOR", "notepad" if sys.platform == "win32" else "nano")
            subprocess.run([editor, str(DRAFT_PATH)], check=False)
            console.print(Markdown(DRAFT_PATH.read_text(encoding="utf-8")))
        elif choice == "R":
            console.print("[red]Rejected. Re-run bootstrap to re-extract.[/red]")
            return False
        else:
            console.print("[yellow]Enter A, E, or R.[/yellow]")


# ── CLI ───────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--pdf", "pdf_path", type=click.Path(exists=True), required=True,
              help="Path to ArchiMate book / spec PDF")
@click.option("--ollama-url", default="http://localhost:11434", show_default=True)
@click.option("--ollama-model", default="llama3.3", show_default=True)
@click.option("--extra-url", "extra_urls", multiple=True,
              help="Additional URLs to crawl and index (repeatable)")
@click.option("--index-only", is_flag=True, default=False,
              help="Only build RAG index; skip guidance extraction")
@click.option("--guidance-only", is_flag=True, default=False,
              help="Only extract guidance; skip RAG index rebuild")
@click.option("--skip-review", is_flag=True, default=False,
              help="Auto-accept guidance draft without interactive review")
def main(
    pdf_path: str,
    ollama_url: str,
    ollama_model: str,
    extra_urls: tuple[str, ...],
    index_only: bool,
    guidance_only: bool,
    skip_review: bool,
) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    pdf = Path(pdf_path)

    if index_only and guidance_only:
        console.print("[red]--index-only and --guidance-only are mutually exclusive.[/red]")
        sys.exit(1)

    # ── Phase 1: RAG index ────────────────────────────────────────────────────
    if not guidance_only:
        build_rag_index(pdf, list(extra_urls))

    # ── Phase 2: Guidance extraction ──────────────────────────────────────────
    if not index_only:
        console.print(Panel("[bold]Phase 2: Extracting modeling guidance[/bold]", style="cyan"))

        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
            t = p.add_task("Scanning PDF for guidance content...", total=None)
            pdf_text = _extract_pdf_for_guidance(pdf)
            p.update(t, description="Fetching web sources...")
            web_text = _fetch_web_for_guidance()

        console.print(
            f"[green]PDF guidance excerpts: {len(pdf_text):,} chars | "
            f"Web: {len(web_text):,} chars[/green]"
        )

        prompt = _guidance_prompt(pdf_text, web_text)

        console.print(f"[cyan]Calling Ollama ({ollama_model}) for guidance extraction...[/cyan]")
        try:
            draft = call_ollama(prompt, ollama_model, ollama_url)
        except Exception as exc:
            console.print(f"[red]Ollama call failed: {exc}[/red]")
            console.print("[yellow]Writing raw excerpts as draft for manual editing.[/yellow]")
            draft = (
                "# ArchiMate 3.2 Modeling Guidance\n\n"
                "> AUTO-EXTRACTION FAILED — edit manually.\n\n"
                f"{pdf_text[:15000]}"
            )

        DRAFT_PATH.write_text(draft, encoding="utf-8")
        console.print(f"[green]Draft written to {DRAFT_PATH}[/green]")

        # ── Phase 3: Review ───────────────────────────────────────────────────
        if skip_review:
            accepted = True
            console.print("[yellow]--skip-review: auto-accepting.[/yellow]")
        else:
            accepted = review_draft()

        if not accepted:
            sys.exit(1)

        import shutil as _shutil
        _shutil.copy(DRAFT_PATH, FINAL_PATH)
        console.print(f"[green]Guidance written to {FINAL_PATH}[/green]")

    console.print("[bold green]Bootstrap complete.[/bold green]")


if __name__ == "__main__":
    main()
