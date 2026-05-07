#!/usr/bin/env bash
# bootstrap-server.sh — one-shot server setup, no git required
#
# Run this once on a fresh server to get Archinator running.
# All code stays in ghcr.io — this script only fetches config files.
# Repo and packages are public; no authentication needed.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ErikCrombag/archinator/master/bootstrap-server.sh | bash
set -euo pipefail

REPO="ErikCrombag/archinator"
BRANCH="master"
INSTALL_DIR="${INSTALL_DIR:-$HOME/docker/archinator}"
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH"

echo "[bootstrap] Installing Archinator to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

echo "[bootstrap] Fetching config files from github.com/$REPO..."
curl -fsSL "$RAW/docker-compose.yml"     -o "$INSTALL_DIR/docker-compose.yml"
curl -fsSL "$RAW/deploy.sh"              -o "$INSTALL_DIR/deploy.sh"
curl -fsSL "$RAW/.env.example"           -o "$INSTALL_DIR/.env.example"
mkdir -p "$INSTALL_DIR/data"
curl -fsSL "$RAW/data/sources.txt"       -o "$INSTALL_DIR/data/sources.txt"
mkdir -p "$INSTALL_DIR/data/books"
chmod +x "$INSTALL_DIR/deploy.sh"

echo "[bootstrap] Files installed:"
ls -1 "$INSTALL_DIR"

echo ""
echo "[bootstrap] Next steps:"
echo "  1. Configure:"
echo "       cd $INSTALL_DIR"
echo "       cp .env.example .env && nano .env"
echo "       # Key settings: GHCR_OWNER, OLLAMA_BASE_URL, VITE_API_URL"
echo ""
echo "  2. Deploy:"
echo "       ./deploy.sh"
echo ""
echo "  To update later (pull new images + restart):"
echo "       cd $INSTALL_DIR && docker compose pull && docker compose up -d"
