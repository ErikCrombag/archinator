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
        --ollama-url http://ollama:11434 --ollama-model llama4:16x17b
    python scripts/bootstrap.py --pdf data/archimate_book.pdf \\
        --sources data/sources.txt   # default, explicit override possible
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
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

DEFAULT_SOURCES_FILE = Path(__file__).parent.parent / "data" / "sources.txt"


def parse_sources(sources_file: Path) -> tuple[list[Path], list[str]]:
    """Parse sources.txt → (pdf_paths, urls).

    Handles:
      - Local *.pdf files
      - Local directories (globs all *.pdf inside)
      - https:// URLs ending in .pdf  → remote PDF
      - https:// URLs (other)         → web page
    """
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
            p = Path(line)
            if p.is_dir():
                pdf_paths.extend(sorted(p.glob("*.pdf")))
            elif p.suffix.lower() == ".pdf":
                pdf_paths.append(p)
            else:
                console.print(f"[yellow]  sources.txt: skipping unknown entry: {line}[/yellow]")

    return pdf_paths, urls


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


def _describe_diagram(img_b64: str, page_num: int, view_ref: str | None,
                      model: str, ollama_url: str) -> str | None:
    """Send a page image to Ollama vision model and return diagram description."""
    label = view_ref or f"page {page_num}"
    prompt = (
        f"This is page {page_num} of an ArchiMate 3.2 modeling book ({label}).\n"
        "Describe the diagram(s) on this page in detail:\n"
        "1. What type of ArchiMate viewpoint or diagram is shown?\n"
        "2. List all visible elements with their exact ArchiMate type names.\n"
        "3. List all visible relationships with their types and direction.\n"
        "4. What does this diagram illustrate or demonstrate?\n"
        "5. Note any labels, annotations, or callouts visible.\n"
        "Be precise with ArchiMate terminology. If no diagram is present, say 'No diagram'."
    )
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "images": [img_b64],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1024},
        }
        with httpx.Client(timeout=120) as client:
            r = client.post(f"{ollama_url}/api/generate", json=payload)
            r.raise_for_status()
            text = r.json().get("response", "").strip()
        if text.lower().startswith("no diagram"):
            return None
        return text
    except Exception as exc:
        console.print(f"[yellow]  vision warning page {page_num}: {exc}[/yellow]")
        return None


def _index_pdf_images(
    pdf_file: Path,
    label: str,
    key_prefix: str,
    ollama_url: str,
    vision_model: str,
    add_chunk_fn,
    min_image_pixels: int = 50_000,
) -> int:
    """Render pages with significant images and add vision descriptions as chunks.

    Returns number of diagram chunks added.
    """
    import base64
    import fitz  # type: ignore

    doc = fitz.open(str(pdf_file))
    pages_with_images = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        images = page.get_images(full=True)
        # Filter: only pages where at least one image is large enough
        for img in images:
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.width * pix.height >= min_image_pixels:
                    pages_with_images.append(page_num)
                    break
            except Exception:
                continue

    if not pages_with_images:
        doc.close()
        return 0

    console.print(f"[cyan]Vision pass:[/cyan] {label} — {len(pages_with_images)} pages with diagrams")
    added = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as prog:
        task = prog.add_task(
            f"Describing diagrams in {label}...", total=len(pages_with_images)
        )
        for page_num in pages_with_images:
            page = doc[page_num]
            text = page.get_text().strip()
            view_ref = _detect_view_ref(text)

            # Render page at 150 DPI (balance quality vs token cost)
            mat = fitz.Matrix(150 / 72, 150 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_b64 = base64.b64encode(pix.tobytes("png")).decode()

            description = _describe_diagram(img_b64, page_num + 1, view_ref,
                                            vision_model, ollama_url)
            if description:
                chunk_text = (
                    f"[Diagram — {label} page {page_num + 1}"
                    + (f" — {view_ref}" if view_ref else "")
                    + f"]\n\n{description}"
                )
                meta: dict = {
                    "source": label,
                    "page": page_num + 1,
                    "kind": "diagram",
                }
                if view_ref:
                    meta["view_ref"] = view_ref
                add_chunk_fn(chunk_text, meta, f"{key_prefix}:img:p{page_num}")
                added += 1

            prog.advance(task)

    doc.close()
    console.print(f"[green]  {added} diagram descriptions indexed from {label}[/green]")
    return added


def build_rag_index(
    ollama_url: str,
    sources_file: Path | None = None,
    vision_model: str | None = None,
) -> None:
    """
    Chunk and embed all sources from sources_file (PDFs, dirs, URLs).
    Metadata stored per chunk: source, page (PDF) or url (web), kind, view_ref.
    """
    import fitz  # type: ignore
    import chromadb  # type: ignore

    console.print(Panel("[bold]Phase 1: Building RAG index[/bold]", style="cyan"))
    phase1_start = time.time()

    if CHROMA_DIR.exists():
        console.print(f"[yellow]Removing existing ChromaDB at {CHROMA_DIR}[/yellow]")
        shutil.rmtree(CHROMA_DIR)

    embed_base_url = ollama_url
    embed_model_name = os.environ.get("EMBED_MODEL", "nomic-embed-text")

    def _embed(texts: list[str]) -> list[list[float]]:
        resp = httpx.post(
            f"{embed_base_url}/api/embed",
            json={"model": embed_model_name, "input": texts},
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name="archimate_spec",
        metadata={"hnsw:space": "cosine"},
    )

    pending_chunks: list[str] = []
    pending_ids: list[str] = []
    pending_meta: list[dict] = []
    _batch_num = 0
    _total_embedded = 0

    def flush() -> None:
        nonlocal _batch_num, _total_embedded
        if not pending_chunks:
            return
        _batch_num += 1
        n = len(pending_chunks)
        t0 = time.time()
        console.print(f"  [dim]embed batch {_batch_num} ({n} chunks)...[/dim]", end="")
        embeddings = _embed(pending_chunks)
        elapsed = time.time() - t0
        _total_embedded += n
        console.print(f" [green]{elapsed:.1f}s[/green]  total: {_total_embedded}")
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

    CHUNK_WORDS = 500
    OVERLAP_WORDS = 80

    # ── Additional sources from sources.txt ───────────────────────────────────
    import tempfile
    sf = sources_file or DEFAULT_SOURCES_FILE
    extra_pdf_paths, urls = parse_sources(sf)
    console.print(f"[cyan]Sources file:[/cyan] {sf} — {len(extra_pdf_paths)} PDFs, {len(urls)} URLs")

    def _index_pdf_file(pdf_file: Path, label: str, key_prefix: str) -> None:
        d = fitz.open(str(pdf_file))
        total = len(d)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as prog:
            task = prog.add_task(f"Indexing {label} ({total} pages)...", total=total)
            for page_num in range(total):
                text = d[page_num].get_text().strip()
                if not text:
                    prog.advance(task)
                    continue
                view_ref = _detect_view_ref(text)
                words = text.split()
                for i in range(0, max(1, len(words) - OVERLAP_WORDS), CHUNK_WORDS - OVERLAP_WORDS):
                    chunk = " ".join(words[i : i + CHUNK_WORDS])
                    meta: dict = {"source": label, "page": page_num + 1, "kind": "book"}
                    if view_ref:
                        meta["view_ref"] = view_ref
                    add_chunk(chunk, meta, f"{key_prefix}:p{page_num}:w{i}")
                prog.advance(task)
        d.close()

    for extra_pdf in extra_pdf_paths:
        _index_pdf_file(extra_pdf, extra_pdf.name, f"pdf:{extra_pdf.name}")
        if vision_model:
            _index_pdf_images(extra_pdf, extra_pdf.name, f"pdf:{extra_pdf.name}",
                              ollama_url, vision_model, add_chunk)

    # Remote PDF URLs (ends with .pdf) — download then index
    web_urls: list[str] = []
    _downloaded_pdfs: list[tuple[Path, str]] = []  # (tmp_path, label)
    with httpx.Client(timeout=120, follow_redirects=True) as dl_client:
        for url in urls:
            if url.lower().split("?")[0].endswith(".pdf"):
                console.print(f"[cyan]Downloading remote PDF:[/cyan] {url}")
                try:
                    r = dl_client.get(url)
                    r.raise_for_status()
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        tmp.write(r.content)
                        tmp_path = Path(tmp.name)
                    label = url.split("/")[-1].split("?")[0]
                    _index_pdf_file(tmp_path, label, f"pdf:{label}")
                    _downloaded_pdfs.append((tmp_path, label))
                except Exception as exc:
                    console.print(f"[yellow]  warning: could not download {url}: {exc}[/yellow]")
            else:
                web_urls.append(url)

    # Vision pass for downloaded remote PDFs
    if vision_model:
        for tmp_path, label in _downloaded_pdfs:
            _index_pdf_images(tmp_path, label, f"pdf:{label}",
                              ollama_url, vision_model, add_chunk)

    flush()

    # ── Web pages ─────────────────────────────────────────────────────────────
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for url in web_urls:
            try:
                r = client.get(url)
                r.raise_for_status()
                text = _strip_html(r.text)
                words = text.split()
                for i in range(0, max(1, len(words) - OVERLAP_WORDS), CHUNK_WORDS - OVERLAP_WORDS):
                    chunk = " ".join(words[i : i + CHUNK_WORDS])
                    meta = {"source": url, "kind": "web"}
                    add_chunk(chunk, meta, f"web:{url}:w{i}")
                console.print(f"[green]  indexed {url} ({len(words):,} words)[/green]")
            except Exception as exc:
                console.print(f"[yellow]  warning: could not fetch {url}: {exc}[/yellow]")

    flush()
    elapsed = time.time() - phase1_start
    console.print(f"[bold green]RAG index ready: {collection.count()} chunks in {elapsed:.0f}s[/bold green]")


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


def _fetch_web_for_guidance(sources_file: Path | None = None) -> str:
    """Fetch non-PDF URLs from sources.txt for use in guidance extraction."""
    _, urls = parse_sources(sources_file or DEFAULT_SOURCES_FILE)
    web_urls = [u for u in urls if not u.lower().split("?")[0].endswith(".pdf")]
    parts: list[str] = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for url in web_urls:
            try:
                r = client.get(url)
                r.raise_for_status()
                text = _strip_html(r.text)
                parts.append(f"## {url}\n\n{text[:6000]}")
            except Exception as exc:
                console.print(f"[yellow]  warning: {url}: {exc}[/yellow]")
    return "\n\n---\n\n".join(parts)


def call_ollama(prompt: str, model: str, base_url: str) -> str:
    """Call Ollama with streaming — prints tokens live so long runs stay visible."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": 0.1, "num_predict": 6000},
    }
    console.print(f"\n[dim]{'─' * 60}[/dim]")
    console.print(f"[cyan]Ollama ({model}) generating — streaming output:[/cyan]\n")
    t0 = time.time()
    tokens: list[str] = []
    with httpx.Client(timeout=600) as client:
        with client.stream("POST", f"{base_url}/api/generate", json=payload) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = data.get("response", "")
                if token:
                    print(token, end="", flush=True)
                    tokens.append(token)
                if data.get("done"):
                    break
    elapsed = time.time() - t0
    console.print(f"\n\n[dim]{'─' * 60}[/dim]")
    console.print(f"[green]Done: {len(tokens)} tokens in {elapsed:.1f}s ({len(tokens)/elapsed:.0f} tok/s)[/green]\n")
    return "".join(tokens)


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
@click.option("--pdf", "pdf_path", type=click.Path(exists=True), default=None,
              help="Primary PDF for guidance extraction. If omitted, uses first PDF from sources.txt.")
@click.option("--sources", "sources_path",
              type=click.Path(), default=None,
              help=f"Sources manifest file (default: data/sources.txt)")
@click.option("--ollama-url", default="http://localhost:11434", show_default=True)
@click.option("--ollama-model", default="llama3.3", show_default=True)
@click.option("--vision-model", default=None,
              help="Ollama model for diagram vision pass (default: same as --ollama-model). "
                   "Use --skip-vision to disable.")
@click.option("--skip-vision", is_flag=True, default=False,
              help="Skip vision pass — do not describe diagrams")
@click.option("--index-only", is_flag=True, default=False,
              help="Only build RAG index; skip guidance extraction")
@click.option("--guidance-only", is_flag=True, default=False,
              help="Only extract guidance; skip RAG index rebuild")
@click.option("--skip-review", is_flag=True, default=False,
              help="Auto-accept guidance draft without interactive review")
def main(
    pdf_path: str | None,
    sources_path: str | None,
    ollama_url: str,
    ollama_model: str,
    vision_model: str | None,
    skip_vision: bool,
    index_only: bool,
    guidance_only: bool,
    skip_review: bool,
) -> None:
    DATA_DIR.mkdir(exist_ok=True)

    if index_only and guidance_only:
        console.print("[red]--index-only and --guidance-only are mutually exclusive.[/red]")
        sys.exit(1)

    sources = Path(sources_path) if sources_path else DEFAULT_SOURCES_FILE

    # Derive guidance PDF: explicit --pdf, else first PDF from sources.txt
    guidance_pdf: Path | None = Path(pdf_path) if pdf_path else None
    if guidance_pdf is None and not index_only:
        extra_pdfs, _ = parse_sources(sources)
        if extra_pdfs:
            guidance_pdf = extra_pdfs[0]
            console.print(f"[cyan]Guidance PDF:[/cyan] {guidance_pdf} (first PDF from sources.txt)")
        else:
            console.print("[yellow]No PDF found — guidance extraction will be skipped.[/yellow]")

    # ── Phase 1: RAG index ────────────────────────────────────────────────────
    if not guidance_only:
        effective_vision = None if skip_vision else (vision_model or ollama_model)
        if effective_vision:
            console.print(f"[cyan]Vision model:[/cyan] {effective_vision}")
        else:
            console.print("[yellow]Vision pass disabled (--skip-vision)[/yellow]")
        build_rag_index(ollama_url, sources, effective_vision)

    # ── Phase 2: Guidance extraction ──────────────────────────────────────────
    if not index_only and guidance_pdf:
        console.print(Panel("[bold]Phase 2: Extracting modeling guidance[/bold]", style="cyan"))

        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
            t = p.add_task("Scanning PDF for guidance content...", total=None)
            pdf_text = _extract_pdf_for_guidance(guidance_pdf)
            p.update(t, description="Fetching web sources...")
            web_text = _fetch_web_for_guidance(sources)

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
                + pdf_text[:15000]
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
