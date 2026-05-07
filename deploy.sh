#!/usr/bin/env bash
# deploy.sh — first-time and re-deploy script for 10.1.0.2:~/docker/archinator
#
# Images are built by GitHub Actions and pushed to ghcr.io.
# This script pulls pre-built images and starts the stack — no local build needed.
#
# Usage:
#   ./deploy.sh            # pull latest images + (re)start all services
#   ./deploy.sh --pull     # git pull first, then re-deploy
#   ./deploy.sh --build    # force local build instead of pulling (dev/fallback)
#   ./deploy.sh --down     # stop and remove containers (data preserved)
#
# First-time server setup:
#   1. Log in to ghcr.io once:
#        echo YOUR_GITHUB_PAT | docker login ghcr.io -u YOUR_GITHUB_USER --password-stdin
#   2. Copy this repo (or just docker-compose.yml + deploy.sh + .env.example) to the server.
#   3. Run ./deploy.sh
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$DEPLOY_DIR/data"

echo "[deploy] Working in $DEPLOY_DIR"

# ── Parse args ────────────────────────────────────────────────────────────────
PULL=0
DOWN=0
BUILD=0
for arg in "$@"; do
  case "$arg" in
    --pull)  PULL=1 ;;
    --down)  DOWN=1 ;;
    --build) BUILD=1 ;;
  esac
done

# ── Optional git pull ─────────────────────────────────────────────────────────
if [[ $PULL -eq 1 ]]; then
  echo "[deploy] Pulling latest code..."
  git -C "$DEPLOY_DIR" pull --ff-only
fi

# ── Shutdown ──────────────────────────────────────────────────────────────────
if [[ $DOWN -eq 1 ]]; then
  echo "[deploy] Stopping containers..."
  docker compose -f "$DEPLOY_DIR/docker-compose.yml" down
  echo "[deploy] Done. Data preserved in $DATA_DIR"
  exit 0
fi

# ── Initialise data directory ─────────────────────────────────────────────────
# Docker bind-mounts create a *directory* if the path doesn't exist.
# Pre-create files so the mounts work correctly.
echo "[deploy] Initialising data directory..."
mkdir -p "$DATA_DIR/chroma"

# archinator.db — SQLite file, pre-create as empty file
if [[ ! -f "$DATA_DIR/archinator.db" ]]; then
  touch "$DATA_DIR/archinator.db"
  echo "[deploy]   created data/archinator.db"
fi

# semantic_core.md — optional bootstrap output, pre-create as empty file
if [[ ! -f "$DATA_DIR/semantic_core.md" ]]; then
  touch "$DATA_DIR/semantic_core.md"
  echo "[deploy]   created data/semantic_core.md (empty — run bootstrap to populate)"
fi

# ── .env ─────────────────────────────────────────────────────────────────────
if [[ ! -f "$DEPLOY_DIR/.env" ]]; then
  echo "[deploy] No .env found — copying from .env.example"
  cp "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/.env"
  echo "[deploy] ⚠  Review $DEPLOY_DIR/.env before continuing."
  echo "[deploy]    Key settings: OLLAMA_BASE_URL, VITE_API_URL"
  read -r -p "[deploy] Press Enter to continue with defaults, or Ctrl-C to edit first..."
fi

# ── Pull images + start ───────────────────────────────────────────────────────
if [[ $BUILD -eq 1 ]]; then
  echo "[deploy] Building images locally (--build flag set)..."
  docker compose -f "$DEPLOY_DIR/docker-compose.yml" up --build -d
else
  echo "[deploy] Pulling pre-built images from ghcr.io..."
  docker compose -f "$DEPLOY_DIR/docker-compose.yml" pull
  echo "[deploy] Starting containers..."
  docker compose -f "$DEPLOY_DIR/docker-compose.yml" up -d
fi

echo ""
echo "[deploy] Done."
echo "  Backend:  http://10.1.0.2:8000/health"
echo "  Frontend: http://10.1.0.2:3000"
echo ""
echo "  First-time? Create an API key:"
echo "    docker compose -f $DEPLOY_DIR/docker-compose.yml exec backend \\"
echo "      python -c \""
echo "        import asyncio"
echo "        from archinator.auth.api_keys import init_db, create_key"
echo "        async def run():"
echo "          await init_db()"
echo "          raw, rec = await create_key('admin')"
echo "          print('API key:', raw)"
echo "        asyncio.run(run())"
echo "      \""
