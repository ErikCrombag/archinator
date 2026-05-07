FROM python:3.12-slim

WORKDIR /app

# System deps for lxml + sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

COPY src/ src/

# Pre-download embedding model so container starts fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "archinator.api"]
