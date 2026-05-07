#!/usr/bin/env bash
# bootstrap-server.sh — one-shot server setup, no git required
#
# Run this once on a fresh server to get Archinator running.
# All code stays in ghcr.io — this script only fetches config files.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ErikCrombag/archinator/master/bootstrap-server.sh | bash
#   # or with a PAT for private repo access:
#   GITHUB_PAT=your_pat bash bootstrap-server.sh
set -euo pipefail

REPO="ErikCrombag/archinator"
BRANCH="master"
INSTALL_DIR="${INSTALL_DIR:-$HOME/docker/archinator}"
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH"

AUTH_HEADER=""
if [[ -n "${GITHUB_PAT:-}" ]]; then
  AUTH_HEADER="Authorization: token $GITHUB_PAT"
fi

fetch() {
  local path="$1"
  local dest="$2"
  if [[ -n "$AUTH_HEADER" ]]; then
    curl -fsSL -H "$AUTH_HEADER" "$RAW/$path" -o "$dest"
  else
    curl -fsSL "$RAW/$path" -o "$dest"
  fi
}

echo "[bootstrap] Installing Archinator to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

echo "[bootstrap] Fetching config files from github.com/$REPO..."
fetch "docker-compose.yml"    "$INSTALL_DIR/docker-compose.yml"
fetch "deploy.sh"             "$INSTALL_DIR/deploy.sh"
fetch ".env.example"          "$INSTALL_DIR/.env.example"
chmod +x "$INSTALL_DIR/deploy.sh"

echo "[bootstrap] Files installed:"
ls -1 "$INSTALL_DIR"

echo ""
echo "[bootstrap] Next steps:"
echo "  1. Set your GHCR_OWNER and Ollama settings:"
echo "       cd $INSTALL_DIR"
echo "       cp .env.example .env && nano .env"
echo ""
echo "  2. Log in to ghcr.io (needs a GitHub PAT with read:packages scope):"
echo "       echo YOUR_PAT | docker login ghcr.io -u YOUR_GH_USER --password-stdin"
echo ""
echo "  3. Deploy:"
echo "       ./deploy.sh"
echo ""
echo "  To update later (pull new images + restart):"
echo "       cd $INSTALL_DIR && docker compose pull && docker compose up -d"
