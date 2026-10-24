![recipes — measured local AI configurations](assets/recipes-blueprint.png)

# recipes

[English](README.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md)

My local inference recipes for **AMD Ryzen 5 5600X · RTX 3060 12 GiB · 32 GiB RAM**: model files, engine pins, automatic launchers, agent clients and measured performance. **Text only, one generation at a time.** This repository remains private while being prepared.

Inventory and log recovery: **2026-10-24**. Flint measurements: October 22; Nemotron: October 23; new Qwen/Gemma/GPT measurements: October 24. These are the selected profiles among the settings tried on this machine, not proof of a global optimum.

## Contents

- [Models and performance](#models)
- [Hardware and scope](#hardware)
- [Quick start](#quick-start)
- [Model recipes](#recipes)
  - [Qwen 3.6](#qwen)
  - [Gemma 4](#gemma)
  - [GPT-OSS](#gpt-oss)
  - [Flint](#flint)
  - [Nemotron + DFlash](#nemotron)
- [OpenAI compatible API](#api)
- [OpenCode, Hermes, Codex and Claude Code](#clients)
- [FreeToken Desktop](#desktop)
- [Logs and reproduction](#evidence)
- [Repository layout and licenses](#layout)

<a id="models"></a>
## Models and performance

**Context includes input, history, templates, reasoning and output.** Speeds are tokens/s; capacities are tokens. Output is a default budget, not a claim that every model has been measured generating that many tokens.

| Model | Engine | Total context | Input budget¹ | Output¹ | Drafter | Prefill | Decode | Measured workload | Quantization | Sources / config |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen 3.6 35B A3B | FreeToken | 66560 | 58368 | 8192 | No | 2841.17² | 70.51² | 4106 + 200 × 3 | NVFP4 ModelOpt (mixed) | [Original](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) · [Weights](https://huggingface.co/nvidia/Qwen3.6-35B-A3B-NVFP4) · [Config](profiles/qwen3.6.json) |
| Gemma 4 26B A4B | FreeToken | 66560 | 58368 | 8192 | No | 1442.59² | 32.11² | 4109 + 200 × 3 | NVFP4 ModelOpt (mixed) | [Original](https://huggingface.co/google/gemma-4-26B-A4B-it) · [Weights](https://huggingface.co/nvidia/Gemma-4-26B-A4B-NVFP4) · [Config](profiles/gemma4.json) |
| GPT-OSS 20B | FreeToken | 66560 | 58368 | 8192 | No | 2272.64² | 42.31² | 4163 + 200 × 3 | MXFP4 | [Original](https://huggingface.co/openai/gpt-oss-20b) · [Weights](https://huggingface.co/openai/gpt-oss-20b) · [Config](profiles/gpt-oss.json) |
| Flint 39.8B A2.5B | FreeToken | 73728 | 65536 | 8192 | No | 1543.59³ | 49.97³ | 65536 + 8192 | NVFP4 GGUF official | [Original](https://huggingface.co/RecursiveSI/flint) · [Weights](https://huggingface.co/RecursiveSI/flint-nvfp4-gguf) · [Config](profiles/flint.json) |
| NVIDIA Nemotron 3.5 Bolt E4B | llama.cpp | 65536 | 57344 | 8192 | BF16 DFlash | 1964.10³ | 108.04³ | 277–411 + 1242–1762 | Unsloth UD-Q8_K_XL GGUF (mixed) | [Original](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-BF16) · [Weights](https://huggingface.co/unsloth/NVIDIA-Nemotron-3.5-Bolt-E4B-GGUF) · [Config](profiles/nemotron.json) |

1. The catalog reserves **8192 output tokens** for agent use; reasoning consumes that budget too. Input budgets include system instructions, tool schemas and the chat template. Only Flint has a preserved 65536-input + 8192-output run. A 65536-total context, such as Nemotron's, leaves 57344 for input with this output reservation.
2. Qwen/Gemma/GPT: **new HTTP stream measurements**, mean of three requests after a warmup. Prefill = prompt tokens / time to first nonempty content **or reasoning** event. Decode = (completion tokens − 1) / time between first and last such events. Includes local serving overhead and assumes token accounting matches streamed chunks. All three use distinct synthetic prefixes; see the raw logs for cache counts. These replace the incomplete historical logs in the main table.
3. Flint uses the historical HTTP protocol timed to the first **text** event. Nemotron uses llama.cpp's per-request timings; its prefill counts only uncached tokens (38 cached per request). **Different workloads and metrics are not a controlled engine comparison.** Short prompts on a 64K-capacity server do not measure performance with 64K of active history.

Historical Gemma/GPT engine-log figures remain in [their evidence](evidence): 328.21 / 41.24 and 307.26 / 65.15 respectively. They use periodic engine accounting and must not be mixed with the new HTTP rates.

<a id="hardware"></a>
## Hardware and scope

Ryzen 5 5600X, 6 cores / 12 threads, 32 GiB nominal RAM, RTX 3060 12 GiB (SM86), NVIDIA driver 615.78.08. FreeToken uses CPU/GPU hybrid expert offload; Nemotron fits target and drafter entirely on the 3060. [Hardware](evidence/hardware.json) · [Bandwidth microbenchmarks](evidence/bandwidth.json).

An RTX 2070 8 GiB is also installed. Earlier mixed GPU experiments were affected by thermal throttling (88°C / 300 MHz), so their results are not presented as an optimized recipe. The launchers select the 3060 by UUID and expose it as device 0. NVFP4 storage on Ampere does not imply Blackwell native FP4 instructions.

<a id="quick-start"></a>
## Quick start

![From weights to workflow](assets/workflow-blueprint.png)

Requirements: Linux x86_64, Python 3.12+, Git, an NVIDIA driver compatible with the selected CUDA runtime, enough disk/RAM, and [`uv`](https://docs.astral.sh/uv/getting-started/installation/) for FreeToken. FreeToken uses pinned CPython 3.12 wheels and may need a CUDA 13 toolkit for uncached kernels. Nemotron uses the official llama.cpp b11828 CUDA 13.4 binary/runtime archives, with verified SHA-256 hashes.

```bash
gh repo clone jesusjodar/recipes
cd recipes
./recipes list

./recipes install
./recipes download gemma4
./recipes serve gemma4

# Independent engine for Nemotron; no FreeToken installation required.
./recipes install --llama-cpp
./recipes download nemotron
./recipes serve nemotron
```

Run **one server at a time**, wait for `LISTO`, then connect a client. Stop other model servers to free VRAM. Ctrl+C cleans up the processes started by the launcher. FreeToken needs both the API port and port + 1; llama.cpp needs the API port.

```bash
./recipes serve gemma4 --port 22420
./recipes serve gemma4 --gpu GPU-YOUR-CARD-UUID
./recipes show gemma4
./recipes serve nemotron --print-command
```

Downloads default to `~/.freetoken/models`; set `RECIPES_MODEL_DIR` for another library. Nemotron also reuses the existing `~/Desktop/AI/models` files when present and hash verified. Its engine archives can be reused from `~/Desktop/AI/bin`. Qwen/Gemma/GPT reuse complete local shards, whose historical weight revisions are unknown; the published pins are for **new downloads**. Nemotron's target and drafters have full SHA-256 verification against Hub blobs. [Inventory](evidence/inventory.json) · [Runtime pins](runtime.json).

<a id="recipes"></a>
## Model recipes

<a id="qwen"></a>
### Qwen 3.6 35B A3B

66560 total context, 3328 expert slots, four GDN/Mamba state slots, hybrid fetch 1. Start with 1024 experts, then rebuild. The Desktop `swaTokens=2048` field is unused for this recurrent model; **the CLI rebuild omits `num_swa_pages`**, which the engine rejects. Sampling: temperature 1, top-p 0.95, top-k 20.

```bash
./recipes install
./recipes download qwen3.6
./recipes serve qwen3.6
```

New evidence contains three 4106-input + 200-output requests, complete startup/rebuild logs and SSE events. Full active context and the 8192 output default are not validated by these requests. [Profile](profiles/qwen3.6.json) · [Measurements](evidence/qwen3.6.json) · [Clients](clients/qwen3.6).

<a id="gemma"></a>
### Gemma 4 26B A4B

**Vision and audio disabled.** 66560 total context, 448 experts, hybrid fetch 1. The CLI retains its initial SWA pool of 13312 tokens; Desktop stores 1024. These are different geometries. The new run exposed a CUDA OOM with an 8192 prefill ceiling; the recipe now chunks prefill at **1024**, preserving the failed log and the successful replacement measurements. Sampling for normal use: temperature 1, top-p 0.95, top-k 64.

```bash
./recipes install
./recipes download gemma4
./recipes serve gemma4
```

The old 1425-expert configuration did not fit the larger context. New short-request logs supersede the old excerpt for this CLI recipe; they do not establish generation at the full 66560-token capacity. [Profile](profiles/gemma4.json) · [Measurements and historical excerpt](evidence/gemma4.json) · [Clients](clients/gemma4).

<a id="gpt-oss"></a>
### GPT-OSS 20B

MXFP4 weights, 66560 total context, 256 experts, hybrid fetch 1. The previous 535-expert configuration at 16K left insufficient room for the larger context. CLI SWA pool: 13312; Desktop: 512. The engine uses Harmony and checkpoint sampling defaults. Measurements request temperature 0.

```bash
./recipes install
./recipes download gpt-oss
./recipes serve gpt-oss
```

[Profile](profiles/gpt-oss.json) · [Measurements and historical excerpt](evidence/gpt-oss.json) · [Clients](clients/gpt-oss). Context reservation is distinct from the short input actually benchmarked.

<a id="flint"></a>
### Flint 39.8B A2.5B

Official NVFP4 GGUF, pinned revision `6ec43e19…`. **65536 input + 8192 output**. Final expert cache 3456, SWA 5120, prefill chunks 4096, memory ratio 0.90, CUDA normalization and prefill D2D hits. Start with 1024 experts and rebuild after loading.

```bash
./recipes install --flint
./recipes download flint
./recipes serve flint
```

Support is proposed in [FreeToken #797](https://github.com/FlashML-org/FreeToken/pull/797). The installer pins reviewed Python commit `6ee048e…`, reusing wheel native extensions; **performance was measured on the earlier tree `edfba5e…` and has not been rerun on the installed commit**. This is not a clean CUDA source build.

| Historical workload | Effective prefill | Decode | TTFT |
|---|---:|---:|---:|
| 8192 + 256, cold, mean of 3 | 2783.31 | 66.53 | ≈2.94 s |
| 65536 + 8192, cold, one run | 1543.59 | 49.97 | 42.46 s |
| 65536 + 256, reused prefix | 65535 tokens reused | 50.38 | 0.88 s |

Only the throughput benchmark forces `ignore_eos`; normal serving respects EOS. A separate >64K tool cycle completed, which does not establish general coding quality. Peak observed VRAM: 10.61 GiB including desktop; host experts: about 19.8 GiB. Sampling: temperature 1, top-p 0.95, top-k 20. [Profile](profiles/flint.json) · [Results](evidence/flint.json) · [Sweep and validation logs](evidence/logs/flint) · [Clients](clients/flint).

A separate [FutureMLS-Lab Flint ModelOpt export](https://huggingface.co/FutureMLS-Lab/flint-nvfp4-coldgptq), revision `56f37fcf…`, is also present in the research library, locally reshaped into per-layer safetensors. It was used for parity, AIME and cache validation at 8192 serving capacity, with no optimized long-context throughput or output target. It is inventoried, not advertised as another optimized recipe. [Validation logs](evidence/logs/flint-validation).

<a id="nemotron"></a>
### NVIDIA Nemotron 3.5 Bolt E4B + DFlash

**llama.cpp b11828 CUDA 13.4**, Unsloth **UD-Q8_K_XL** target, official NVIDIA **BF16 GGUF DFlash** drafter, draft max 7 (block size 8), full GPU offload for both, Flash Attention, Jinja, one slot, fitting disabled, **65536 total context**. No vision projector. Temperature 1, top-p 0.95. The catalog adds an 8192 output default; historical requests set their own limits.

```bash
./recipes install --llama-cpp
./recipes download nemotron
./recipes serve nemotron
```

At 64K capacity, three synthetic coding tasks used 277–411 prompt tokens and generated **1242 / 1721 / 1762** tokens, all ending normally. Mean engine prefill **1964.10**, engine decode **108.04**, API end-to-end output rate **106.86**; draft acceptance **32.4%**. Each request reused 38 prompt tokens. VRAM was about 8.6 GiB. **Near-full 64K active history has not been benchmarked.** Generated patches are timing samples, not validated correct solutions.

Earlier four-task 8K tests (256 output tokens each) gave **117.63 API / 121.63 engine decode** with the official BF16 drafter, versus **85.34 / 87.52** with the downloaded Unsloth Q8_0 drafter. The BF16 drafter is selected. These are not native NVFP4 drafter results; that experiment is not a measured recipe. The new default endpoint is port **1919**, matching the client files; the existing Desktop/AI service uses **8000** and is not modified by these commands.

[Profile](profiles/nemotron.json) · [Evidence](evidence/nemotron.json) · [Original benchmark JSON/scripts](evidence/logs/nemotron) · [Clients](clients/nemotron) · [Target weights](https://huggingface.co/unsloth/NVIDIA-Nemotron-3.5-Bolt-E4B-GGUF) · [Official drafter](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB-DFlash).

<a id="api"></a>
## OpenAI compatible API

Every launcher binds to `127.0.0.1`, without a required API key or public exposure. Model IDs: `qwen3.6`, `gemma4`, `gpt-oss`, `flint`, `nemotron`.

```bash
curl --fail-with-body http://127.0.0.1:1919/v1/models
curl --fail-with-body http://127.0.0.1:1919/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"nemotron","messages":[{"role":"user","content":"Summarize this project."}],"max_tokens":8192,"stream":true}'
```

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:1919/v1", api_key="local-no-key")
r = client.chat.completions.create(
    model="nemotron", max_tokens=8192,
    messages=[{"role": "user", "content": "Summarize the diff."}],
)
print(r.choices[0].message.content)
```

`local-no-key` is a public SDK placeholder. The OpenAI SDK is included in the FreeToken environment; for a llama.cpp-only installation, install it separately (`uv run --with openai your_script.py`). Both engines expose `/v1/responses` and `/v1/messages`; the pinned llama.cpp routes are documented [here](https://github.com/ggml-org/llama.cpp/blob/b11828/tools/server/README.md). These local adapters do not imply full OpenAI/Anthropic feature parity. FreeToken Responses is stateless: resend history and tools, without relying on stored responses, `previous_response_id` or background tasks. Preserve reasoning fields where required.

<a id="clients"></a>
## Agent clients

Start a recipe first. Examples below use **Nemotron**; replace the ID, client folder and context when switching models. Every model has its own files in `clients/`. These are configuration examples and endpoint checks, **not validated full coding sessions with every client**.

| Client | Protocol | Files |
|---|---|---|
| OpenCode v2.1.4 | Chat Completions | [v2 JSON](clients/nemotron/opencode-v2.json) |
| OpenCode v1 | Chat Completions, different schema | [v1 JSON](clients/nemotron/opencode-v1.json) |
| Hermes Agent | Custom provider, Chat Completions | [YAML](clients/nemotron/hermes.yaml) |
| Codex CLI 0.164.0 | Responses | [Wrapper](clients/nemotron/codex.sh) · [TOML](clients/nemotron/codex.toml) |
| Claude Code 2.1.310 | Anthropic Messages adapter | [Wrapper](clients/nemotron/claude-code.sh) |

### OpenCode

Merge the matching JSON into the working project's `opencode.json`, keeping existing settings. v2 uses `providers/package/settings`; v1 uses `provider/npm/options`. Choose `recipes/nemotron` in `/models`, or:

```bash
opencode run --model recipes/nemotron "Summarize the project structure"
```

The files declare text, tools, reasoning field, context/input/output budgets and `max_tokens=8192`.

### Hermes

Install through the [official guide](https://hermes-agent.nousresearch.com/docs/getting-started/installation), then choose Custom endpoint with `hermes model`, or:

```bash
hermes config set model.provider custom
hermes config set model.default nemotron
hermes config set model.base_url http://127.0.0.1:1919/v1
hermes config set model.api_mode chat_completions
hermes config set model.context_length 65536
hermes chat
```

Do not add obsolete `model.max_tokens`. The server default is 8192. Contexts: Nemotron 65536; Qwen/Gemma/GPT 66560; Flint 73728.

### Codex

```bash
bash clients/nemotron/codex.sh
```

The wrapper overrides the provider for that process, retaining global login/configuration. It uses Responses, no OpenAI authentication or WebSockets, and compacts before exhausting the input budget. The TOML shows the same options for manual integration.

### Claude Code

```bash
bash clients/nemotron/claude-code.sh
```

Use the root URL **without `/v1`**; the client appends `/v1/messages`. All model aliases point to the same local model. Non-Claude models are **not officially supported by Anthropic**; behavior depends on adapter/model compatibility. No extra Chat Completions→Messages proxy is required for these two pinned engines. Approval controls remain enabled. [Detailed client notes and official sources, in Spanish](docs/clients.md).

<a id="desktop"></a>
## FreeToken Desktop

```bash
./recipes desktop gemma4
# Close Desktop before applying.
./recipes desktop gemma4 --apply
```

Preview first; `--apply` backs up the file and merges only that model's cache profile and text-only flag. It does not install Flint support or change global settings, engine or Downloads cards. **Nemotron's measured recipe uses llama.cpp and has no FreeToken Desktop profile.** [Captured globals and CLI/Desktop differences](docs/desktop.md).

<a id="evidence"></a>
## Logs and reproduction

- [Log manifest](evidence/logs/manifest.json): recovered sources, SHA-256 hashes and sanitization. Home paths, workspace paths, GPU UUIDs and terminal colors are removed; personal conversations, credentials, voice artifacts and network details are excluded.
- [Qwen](evidence/logs/qwen3.6), [Gemma](evidence/logs/gemma4), [GPT-OSS](evidence/logs/gpt-oss): new full server logs and per-request SSE captures, plus recovered historical output where available. Gemma's failed 8192-prefill attempt is retained.
- [Nemotron](evidence/logs/nemotron): original JSON measurements, benchmark scripts and reports. Historical complete server stdout was not retained; it cannot be reconstructed faithfully from summaries.
- [Flint](evidence/logs/flint): original sweep logs, JSON and GPU samples; [separate validation](evidence/logs/flint-validation).
- [Method and caveats](docs/measurements.md) · [Recovery audit](docs/log-recovery.md) · [Runtime pins](runtime.json) · [Key dependency constraints](constraints.txt).

The original temporary Gemma/GPT log files were lost. Terminal captures are explicitly labeled as recovered and can retain original truncation; fresh measurements are separate evidence, not replacements masquerading as historical originals. `null` means unknown. Model weights are never committed.

To reproduce, run one model with the recorded geometry and log its stdout/stderr, then use the synthetic benchmark (FreeToken environment required):

```bash
./recipes serve gemma4 > /tmp/gemma4-server.log 2>&1
# In another terminal, after LISTO:
.venv/bin/python scripts/benchmark-freetoken.py gemma4 \
  --output /tmp/gemma4-new-measurement.json
```

Record engine revision, hardware, checkpoint hashes, actual token usage, cache state, EOS policy, warmups and all samples. New measurements use `ignore_eos` only for fixed-length benchmarking. Verify actual near-limit input/output before claiming full context performance. The installer saves a local `uv pip freeze`, not a full transitive dependency lock; a clean FreeToken bootstrap has not been validated.

<a id="layout"></a>
## Repository layout and licenses

```text
profiles/        model, engine, launch arguments, context and output policy
clients/         per-model OpenCode, Hermes, Codex and Claude examples
evidence/        measurements, inventory and sanitized logs
scripts/         install, download, serve, Desktop merge and benchmarks
assets/          two original blueprint banners generated with ImageGen
docs/            methodology, recovery, Desktop, clients and artwork provenance
runtime.json     engine pins, archive/wheel hashes and Flint commit
```

Add a profile, pinned source, real benchmark workload/logs, client examples and a table row for each new recipe. Keep reserved capacity, tested workload and intended output separate. Supporting documents are mainly in Spanish; all three READMEs contain the complete usage overview.

[MIT](LICENSE) covers original recipes/scripts; engines and models retain their own licenses. Nemotron is under **OpenMDW-1.1**; consult each upstream model card. [Banner prompts and provenance](docs/artwork.md): original ImageGen blueprint artwork, not official logos or performance certification.

Sources: [FreeToken](https://github.com/FlashML-org/FreeToken) · [llama.cpp b11828](https://github.com/ggml-org/llama.cpp/releases/tag/b11828) · [OpenCode](https://opencode.ai/v2/docs/providers) · [Hermes](https://hermes-agent.nousresearch.com/docs/integrations/providers) · [OpenAI configuration](https://learn.chatgpt.com/docs/config-file/config-reference) · [Claude gateway](https://code.claude.com/docs/en/llm-gateway-connect).
