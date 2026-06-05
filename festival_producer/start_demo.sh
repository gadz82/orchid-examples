#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     Festival Producer — Orchid Demo         ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

if ! command -v docker &>/dev/null; then
  echo -e "${YELLOW}WARNING: Docker not found. Only CLI/API modes available.${NC}"
fi

if [ ! -f .env ]; then
  echo -e "${YELLOW}No .env found — copying from .env.example${NC}"
  cp .env.example .env
  echo -e "${YELLOW}Edit .env to set your API keys, then re-run this script.${NC}"
  echo ""
fi

echo -e "${GREEN}Choose start mode:${NC}"
echo "  1) Docker compose (full stack: API + Qdrant + Frontend + MCP)"
echo "  2) Standalone API (requires Python deps installed)"
echo "  3) CLI interactive chat (lightest — no API needed)"
echo "  q) Quit"
echo ""
read -rp "Select [1/2/3/q]: " mode

case "$mode" in
  1)
    echo ""
    echo -e "${GREEN}Starting full stack with Docker...${NC}"
    echo -e "  API:  ${CYAN}http://localhost:8080${NC}"
    echo -e "  UI:   ${CYAN}http://localhost:3000${NC}"
    echo -e "  MCP:  ${CYAN}http://localhost:9000/mcp${NC}"
    echo ""
    docker compose up --build
    ;;
  2)
    echo ""
    echo -e "${GREEN}Starting standalone API...${NC}"
    echo -e "  ${CYAN}http://localhost:8000${NC}"
    echo ""
    echo -e "${YELLOW}Make sure Qdrant is running if using RAG.${NC}"
    echo ""
    ORCHID_CONFIG=examples/festival_producer/orchid.yml uvicorn orchid_api.main:app --host 0.0.0.0 --port 8000
    ;;
  3)
    echo ""
    echo -e "${GREEN}Starting CLI interactive chat...${NC}"
    echo ""
    orchid chat interactive --config examples/festival_producer/orchid.yml
    ;;
  q)
    echo "Exiting."
    exit 0
    ;;
  *)
    echo -e "${YELLOW}Invalid option. Exiting.${NC}"
    exit 1
    ;;
esac
