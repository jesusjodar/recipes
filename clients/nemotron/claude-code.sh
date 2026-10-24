#!/usr/bin/env bash
set -euo pipefail
# llama.cpp b11828 exposes /v1/messages; the client adds /v1/messages to this root.
export ANTHROPIC_BASE_URL="http://127.0.0.1:1919"
export ANTHROPIC_AUTH_TOKEN="local-no-key"
unset ANTHROPIC_API_KEY CLAUDE_CODE_OAUTH_TOKEN
export ANTHROPIC_DEFAULT_OPUS_MODEL="nemotron"
export ANTHROPIC_DEFAULT_SONNET_MODEL="nemotron"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="nemotron"
export CLAUDE_CODE_SUBAGENT_MODEL="nemotron"
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=8192
exec claude --model "nemotron" "$@"
