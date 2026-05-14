# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Local dev environment

- **Ollama**: running locally at `http://localhost:11434` — no AI server needed for local runs
- **Training data**: `training/training_data/` — PDFs in `training/training_data/books/` (ArchiMate-Cookbook.pdf, Mastering ArchiMate.pdf)
- **Path remapping**: sources.txt uses `/app/data` (Docker paths) → bootstrap remaps to `training/training_data/` automatically for local runs
- **Always use** `--skip-vision` locally (no vision model available); `--ollama-url http://localhost:11434`

```bash
# Local bootstrap example (index only, no vision, local Ollama)
python training/bootstrap.py --index-only --skip-vision --ollama-url http://localhost:11434

# Chunk-size sweep (run each, then eval per collection)
python training/bootstrap.py --index-only --skip-vision --ollama-url http://localhost:11434 --chunk-words 150 --overlap-words 25  --collection-name archimate_spec_c150
python training/bootstrap.py --index-only --skip-vision --ollama-url http://localhost:11434 --chunk-words 300 --overlap-words 50  --collection-name archimate_spec_c300
python training/bootstrap.py --index-only --skip-vision --ollama-url http://localhost:11434 --chunk-words 800 --overlap-words 130 --collection-name archimate_spec_c800

python training/eval_embeddings.py --models bge-m3 --ollama-url http://localhost:11434 --source-collection archimate_spec_c150
python training/eval_embeddings.py --models bge-m3 --ollama-url http://localhost:11434 --source-collection archimate_spec_c300
python training/eval_embeddings.py --models bge-m3 --ollama-url http://localhost:11434  # default c500
python training/eval_embeddings.py --models bge-m3 --ollama-url http://localhost:11434 --source-collection archimate_spec_c800
```

## Commands

```bash
# Tests (run from repo root — requires lxml + pytest on host)
python -m pytest tests/ -v
python -m pytest tests/test_validation.py::test_access_behavior_to_passive_passes  # single test

# Render rules_core.md from rules.py (also runs at Docker build time)
python training/render_rules_md.py

# Bootstrap (one-time setup — PDFs auto-discovered from sources.txt)
# Builds ChromaDB RAG index (examples, patterns, guidance) + semantic_core.md
python training/bootstrap.py --ollama-url http://localhost:11434 --skip-vision
python training/bootstrap.py --index-only --skip-vision             # RAG index only, skip guidance extraction
python training/bootstrap.py --guidance-only                        # guidance only, skip RAG rebuild
python training/bootstrap.py --skip-review                          # non-interactive

# Embedding model evaluation (standalone, no backend package needed)
pip install -r training/requirements.txt
python training/eval_embeddings.py --ollama-url http://localhost:11434                        # default models, k=[5,10,20,50,100,200]
python training/eval_embeddings.py --models bge-m3 --ollama-url http://localhost:11434        # bge-m3 only
python training/eval_embeddings.py --models all-ollama --ollama-url http://localhost:11434    # all Ollama models
python training/eval_embeddings.py --rebuild                                                  # force re-embed

# Run backend locally (install deps first)
cd backend && pip install -e .
cp .env.example .env  # then set OLLAMA_BASE_URL
python -m archinator.api          # FastAPI HTTP server on :8000
python -m archinator.server       # MCP stdio server
# or use installed entry points: archinator-api / archinator-server

# Docker
docker compose up --build
docker compose up backend         # backend only
```

## Architecture

### Training pipeline vs production pipeline

Two separate applications. Only handover: `data/chroma/` (ChromaDB index) and `data/*.md` (markdown knowledge files).

```
training/                              Production:
  bootstrap.py  ──→ data/chroma/  ──→  backend/src/archinator/knowledge/rag.py
  eval_embeddings.py               ──→ backend/src/archinator/knowledge/core.py
  render_rules_md.py → data/rules_core.md
  inspect_chroma.py  (debug)
  training_data/
    sources.txt     ← source config (/app/data → training/training_data/ locally)
    books/          ← PDFs (gitignored — copy books here)
    eval/
      queries.jsonl ← golden query set (committed)
      results/      ← eval output JSON (gitignored)
```

**Training deps**: `pip install -r training/requirements.txt` (chromadb, httpx, pymupdf, rich, click).  
**HF models**: additionally `pip install sentence-transformers`.  
Training scripts never import from `archinator` package.

### Two server entry points, one codebase

`server.py` — MCP stdio server (for Claude Desktop / MCP clients). Exposes 4 tools: `generate_diagram`, `validate_diagram`, `query_spec`, `list_formats`.

`api.py` — FastAPI HTTP wrapper around the same pipeline. Used by the React frontend and direct API consumers. Requires `X-API-Key` header on all endpoints except `/health`.

Both call into the same `generation/pipeline.py` → `validation/validator.py` → `formatting/` chain.

### Generation pipeline (`generation/pipeline.py`)

```
query
  → RAG retrieval (knowledge/rag.py — ChromaDB)
  → system prompt = semantic_core.md + element/rel lists (generation/prompts.py)
  → Ollama /api/chat with format=json
  → _parse_model_json → ArchiMateModel
  → validator.validate()  ← if violations: retry up to 3x with violation feedback
  → compact_model() if compaction != full
  → re-validate compact model
  → formatters (formatting/)
```

### Three-tier knowledge system

1. **Semantic core** (`data/semantic_core.md`) — always injected into system prompt. Generated by `scripts/bootstrap.py` from the spec PDF + opengroup.org. Committed to repo after human review. Falls back to built-in element list if file is placeholder.
2. **RAG** (`data/chroma/`) — ChromaDB index of the 260-page PDF, queried per request. Built by bootstrap. Gitignored.
3. **Programmatic rules** (`validation/rules.py`) — hardcoded ArchiMate 3.2 element catalogue (63 types), relationship aspect rules, 19 viewpoint definitions, layer order. The authoritative source for validation — not overridden by the LLM.

### RAG & Knowledge Strategy

#### Current architecture

| Mechanism | Scope | Loaded | Source |
|---|---|---|---|
| `rules_core.md` | All element/rel/viewpoint facts | Once (lru_cache) | Generated from `rules.py` |
| `semantic_core.md` | Qualitative patterns, examples, anti-patterns | Once (lru_cache) | Bootstrap LLM extraction from spec PDF |
| ChromaDB RAG | Per-request top-k spec excerpts | Per query | Bootstrap: PDF text chunks + vision descriptions |

Both `rules_core.md` and `semantic_core.md` inject into the **system prompt** (static).  
RAG chunks inject into the **generation prompt** (dynamic, cosine similarity, k=5, `nomic-embed-text` embeddings via Ollama).

#### Open issues & improvement paths

**1. Retrieval coverage — k and chunk sizing**  
Current default: k=5 chunks, chunk size set at bootstrap time (unknown at runtime).  
Risk: k too low → missed coverage; k too high → noise dilutes signal.  
Open: benchmark optimal k per query type; measure chunk overlap impact on recall.

**2. Vision-derived chunk quality**  
Bootstrap sends PDF page images to Ollama vision model → text descriptions → RAG chunks.  
Risk: vision model hallucinates element names and relationship directions → pollutes index with false "spec truth".  
Mitigation options: human review pass on vision chunks before indexing; separate vision collection with lower retrieval weight; confidence score filtering.

**3. Hybrid retrieval (dense + BM25)**  
Current: pure cosine similarity (dense only). Misses exact ArchiMate term matches when query phrasing differs.  
Example: "what connects application and technology layer" may miss chunks about "Serving relationship".  
ChromaDB does not support BM25 natively. Hybrid would require `rank_bm25` alongside, or switch to Qdrant/Weaviate.  
Open: evaluate whether exact-term miss rate justifies the migration cost.

**4. Semantic core selectivity**  
Full `semantic_core.md` injected every request regardless of query scope — Technology-layer query receives all Motivation layer guidance.  
Option: detect query intent (layer keywords) → inject only relevant sections by slicing on section headers.  
Open: measure token savings vs. implementation complexity before committing.

**5. Feedback loop / curated diagram store**  
No signal from production. Validated diagrams are discarded; no learning over time.  
Option A: auto-ingest validated outputs back into ChromaDB (risk: hallucinated diagrams pollute index).  
Option B: human-curated example store — separate collection, higher retrieval weight (preferred — no hallucination risk).  
Option C: track user edits/corrections as a quality signal.  
Preferred path: Option B, implemented as a separate `archimate_examples` ChromaDB collection.

**6. Embedding model quality**  
`nomic-embed-text` is general-purpose. ArchiMate vocabulary ("Serving", "Realization", "Plateau") may drift in embedding space.  
Option A: fine-tune on ArchiMate corpus.  
Option B: evaluate `mxbai-embed-large` or `snowflake-arctic-embed` — better domain term handling out of box.  
Option C: compensate with larger k and post-retrieval filtering.  
Open: run retrieval quality eval before investing in fine-tuning.

#### Decisions made

**Embedding model → `bge-m3`** (2026-05-14)  
Evaluated 6 models on 25 ArchiMate-specific queries (min 2 compound term matches required). Results:

| Model | recall@5 | MRR@5 | recall@10 |
|---|---|---|---|
| bge-m3 ✓ | **0.880** | **0.740** | **0.920** |
| mxbai-embed-large | 0.840 | 0.703 | 0.880 |
| hf:BAAI/bge-large-en-v1.5 | 0.840 | 0.693 | 0.920 |
| hf:intfloat/e5-large-v2 | 0.840 | 0.585 | 0.880 |
| snowflake-arctic-embed | 0.480 | 0.396 | 0.560 |
| nomic-embed-text (old) | 0.240 | 0.181 | 0.560 |

`bge-m3` wins all metrics. Already available via Ollama — no extra infra. Default updated in `rag.py`, `.env.example`, `docker-compose.yml`, `bootstrap.py`. Re-run bootstrap after deploy to rebuild `data/chroma/` with bge-m3 embeddings.

**k=10, chunk_words=500** (2026-05-15)  
2D sweep across chunk sizes [150, 300, 500, 800] × k [5, 10, 20, 50, 100, 200] using bge-m3 on 25 eval queries:

| chunk_words | chunks | k=5 recall | k=10 recall | k=10 MRR | tokens@k=10 |
|---|---|---|---|---|---|
| 150 | 1744 | 0.840 | 0.920 | 0.669 | ~1500 |
| 300 | 924 | 0.840 | 0.920 | 0.732 | ~3000 |
| 500 ✓ | 614 | 0.880 | **0.920** | 0.735 | ~5000 |
| 800 | 453 | 0.880 | **0.920** | **0.760** | ~8000 |

Findings:
- **Elbow at k=10 for all chunk sizes** — recall@10 = recall@200, no gain beyond k=10. Bumped default from 5→10 in `rag.py`.
- **Ceiling 0.920** — 8% of queries have no match at any k; content gap in indexed sources, not a retrieval problem.
- **MRR rises with chunk size** — larger chunks keep concepts together → better embedding specificity → relevant chunks rank higher.
- **c500 vs c800**: both hit recall 0.920 at k=10. c800 has better MRR (0.760 vs 0.735) but injects ~8000 tokens vs ~5000 per generation. Staying on c500 (current index).

**Upgrade path to c800**: re-run bootstrap with `--chunk-words 800 --overlap-words 130` (no `--collection-name` needed, overwrites default `archimate_spec`). No code changes required — worth testing if generation quality feels shallow on context.

---

### Validation rules data (`validation/rules.py`)

This is the single source of truth for what is valid ArchiMate 3.2. Key structures:
- `ELEMENT_TYPES` — 63 types mapping to `{layer, aspect}`
- `RELATIONSHIP_RULES` — per relationship type: `allowed_pairs` of `(source_aspect, target_aspect)`, `cross_layer` flag
- `VIEWPOINTS` — 19 standard viewpoints with `element_types` and `relationship_types` allow-lists (empty = all allowed)
- `ABSTRACTION_PRIORITY` — integer priority per element type used by abstraction compaction

When the spec requires a rules update, edit `rules.py` — validator.py reads from it dynamically.

### Compaction (`compaction/compact.py`)

Two modes beyond `full`:
- **viewpoint** — filters elements/relationships to the viewpoint's allow-lists; dangling relationships dropped
- **abstraction** — removes low-priority elements (threshold < 4 in `ABSTRACTION_PRIORITY`), redirects their relationships to nearest surviving neighbor, deduplicates

Both modes re-validate the compacted model. The compact validation result is returned alongside the full model validation in the API response.

### Auth (`auth/`)

API keys stored in SQLite (`data/archinator.db`). Keys are SHA-256 hashed; only the prefix is stored for display. `create_key()` returns the raw key once — never retrievable after. Admin endpoints (`/admin/keys`) are gated by the same `require_api_key` dependency; Caddy + Authentik SSO is the external layer that restricts admin role access to those routes.

### Internal model representation

`models.py` defines `ArchiMateModel` / `Element` / `Relationship` / `View` dataclasses. All pipeline logic operates on these. Formatters transform them to output strings. The `__init__.py` package root contains `_parse_diagram_input()` which reverses the transform (JSON and Exchange XML parseable; Mermaid/PlantUML are output-only for now).

## Key constraints

- `load_semantic_core()` in `knowledge/core.py` uses `lru_cache` — `semantic_core.md` is read once per process. After running bootstrap, restart the server for the new core to take effect.
- `validation/rules.py` must stay consistent with `validation/validator.py` — the validator reads `RELATIONSHIP_RULES[rel.type]["allowed_pairs"]` expecting `(source_aspect, target_aspect)` tuples. `ANY = "__ANY__"` is the wildcard.
- Tests live in `tests/` at repo root and add `backend/src` to `sys.path` directly — no install required to run them.
- `data/semantic_core.md` is committed (human-reviewed); `data/chroma/` and `data/archinator.db` are gitignored.
- Ollama is called via `/api/chat` with `format: "json"` — requires a model that respects JSON mode. `llama3.3` is the tested default.

## SSH

SSH settings and commands can be found in `.claude/ssh.md`

## Test Prompts

ArchiMate prompts that exercise different layers/viewpoints:

### Motivation layer

Map the strategic drivers and goals for a retail bank launching a mobile payment product. Include stakeholders, business drivers, goals, and requirements.

### Application layer

Design the application architecture for an e-commerce order management system. Show the application components, services, and data objects involved in order processing.

### Cross-layer (Business + Application + Technology)

Model a CI/CD pipeline for a software delivery organization. Show the business process, supporting application toolchain, and underlying infrastructure.

### Technology layer

Design the infrastructure architecture for a Kubernetes-hosted microservices platform. Include nodes, devices, system software, and network components.

### Motivation + Business

Model the capability map for a logistics company expanding into same-day delivery. Show capabilities, value streams, business processes, and key roles.

### Implementation & Migration

Create a migration roadmap for moving a monolithic ERP system to a cloud-native architecture. Show work packages, plateaus, and gaps.

## Open / next session

- Test MCP server behaviour
