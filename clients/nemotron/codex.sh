#!/usr/bin/env bash
set -euo pipefail
exec codex --model 'nemotron' \
  -c 'model_provider="recipes_local"' \
  -c 'model_context_window=65536' \
  -c 'model_auto_compact_token_limit=55296' \
  -c 'model_supports_reasoning_summaries=false' \
  -c 'model_providers.recipes_local.name="recipes / llama.cpp local"' \
  -c 'model_providers.recipes_local.base_url="http://127.0.0.1:1919/v1"' \
  -c 'model_providers.recipes_local.wire_api="responses"' \
  -c 'model_providers.recipes_local.requires_openai_auth=false' \
  -c 'model_providers.recipes_local.supports_websockets=false' "$@"
