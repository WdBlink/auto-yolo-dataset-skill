#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/c301/.local/node-v22/bin:/home/c301/.local/npm-global/bin:${PATH}"
export ANTHROPIC_AUTH_TOKEN="${ANTHROPIC_AUTH_TOKEN:-ollama}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-ollama}"
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-http://127.0.0.1:11435}"
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-sonnet}"
export LOCAL_CLAUDE_MODEL="${LOCAL_CLAUDE_MODEL:-gemma-4-31B-it}"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="${CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:-1}"

exec /home/c301/.local/npm-global/bin/claude "$@"
