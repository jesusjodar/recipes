#!/usr/bin/env bash
set -euo pipefail
# FreeToken exposes the Anthropic Messages adapter at the root URL.
export ANTHROPIC_BASE_URL="http://127.0.0.1:1919"
export ANTHROPIC_AUTH_TOKEN="local-no-key"
unset ANTHROPIC_API_KEY CLAUDE_CODE_OAUTH_TOKEN
export ANTHROPIC_DEFAULT_OPUS_MODEL="gpt-oss"
export ANTHROPIC_DEFAULT_SONNET_MODEL="gpt-oss"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="gpt-oss"
export CLAUDE_CODE_SUBAGENT_MODEL="gpt-oss"
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=8192
exec claude --model "gpt-oss" "$@"
