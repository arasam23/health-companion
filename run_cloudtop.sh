#!/usr/bin/env bash
# Launches Health Companion on this Cloudtop.
# The Gemini API key is loaded at runtime from ~/.config/health-companion/env
# (chmod 600, outside the repo) — never commit it.
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE="${HEALTH_ENV_FILE:-$HOME/.config/health-companion/env}"
if [[ ! -r "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE (expected a line: GEMINI_API_KEY=...)" >&2
  exit 1
fi
set -a; . "$ENV_FILE"; set +a

. .venv/bin/activate
PORT="${PORT:-8501}"

python db.py
# Build the RAG vector store once from knowledge_base/.
[[ -d chroma_db ]] || python strategist.py

exec streamlit run frontend.py \
  --server.port="$PORT" \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --server.enableCORS=false \
  --server.enableXsrfProtection=false \
  --browser.gatherUsageStats=false
