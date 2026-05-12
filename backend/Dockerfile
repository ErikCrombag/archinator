FROM python:3.12-slim

WORKDIR /app

# System deps for lxml + sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt-dev build-essential \
    default-jre-headless curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml .
COPY backend/src/ src/
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

# Generate rules_core.md from rules.py at build time so it is always in sync
# with the validator.  Baked into the image layer — docker-compose volume
# mounts only cover chroma/, archinator.db, and semantic_core.md (bootstrap
# output), so rules_core.md is never shadowed at runtime.
ENV DATA_DIR=/app/data
RUN mkdir -p /app/data
COPY scripts/ /app/scripts/
RUN python /app/scripts/render_rules_md.py
# Expected output: /app/data/rules_core.md

# Bake PlantUML JAR — downloaded at build time, never at runtime
ARG PLANTUML_VERSION=1.2026.3
RUN mkdir -p /app/lib && curl -fsSL -o /app/lib/plantuml.jar \
    "https://github.com/plantuml/plantuml/releases/download/v${PLANTUML_VERSION}/plantuml-${PLANTUML_VERSION}.jar" \
    && java -jar /app/lib/plantuml.jar -version

ENV PLANTUML_JAR=/app/lib/plantuml.jar
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "archinator.api"]
