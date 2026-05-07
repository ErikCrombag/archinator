FROM python:3.12-slim

WORKDIR /app

# System deps for lxml + sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

COPY backend/src/ src/

# Pre-download embedding model so container starts fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Generate rules_core.md from rules.py at build time so it is always in sync
# with the validator.  Baked into the image layer — docker-compose volume
# mounts only cover chroma/, archinator.db, and semantic_core.md (bootstrap
# output), so rules_core.md is never shadowed at runtime.
ENV DATA_DIR=/app/data
RUN mkdir -p /app/data
COPY scripts/render_rules_md.py /app/scripts/render_rules_md.py
RUN python /app/scripts/render_rules_md.py
# Expected output: /app/data/rules_core.md

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "archinator.api"]
