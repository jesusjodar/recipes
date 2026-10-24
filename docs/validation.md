# Full-context validation — 2026-10-24

These are new local tests, with full logs, using the published recipes. Earlier preserved benchmarks remain separate historical series.

## Long request measurements

Each row is **one measured request after a 1024-input / 64-output warmup**. The request fills the profile's input budget and generates **8192 actual tokens** using `ignore_eos=true`. The normal serving recipes respect EOS. Speeds are tokens/s, TTFT is seconds, VRAM is MiB and temperature is °C. Output counts include non-rendered special tokens, as reported by API usage.

| Model | Capacity | Input | Output | Cached input | Effective prefill | HTTP decode | TTFT | Peak VRAM | Peak GPU °C |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| qwen3.6 | 66560 | 58368 | 8192 | 0 | 1739.20 | 60.39 | 33.56 | 11292.00 | 78.00 |
| gemma4 | 66560 | 58368 | 8192 | 6 | 884.26 | 30.20 | 66.00 | 11741.00 | 80.00 |
| gpt-oss | 66560 | 58368 | 8192 | 0 | 1444.89 | 34.93 | 40.40 | 10540.00 | 77.00 |
| flint | 73728 | 65536 | 8192 | 0 | 1521.29 | 50.33 | 43.08 | 10935.00 | 74.00 |
| nemotron | 65536 | 57344 | 8192 | 7 | 1840.76 | 142.95 | 31.15 | 8737.00 | 78.00 |

Effective prefill is `(prompt_tokens - cached_tokens) / TTFT`. Decode is `(completion_tokens - 1) / (terminal_usage_time - first_content_time)`. Prefill uses the first nonempty **content or reasoning** event; decode ends at the terminal usage event, including trailing generated tokens without visible text. Both include local serving overhead. SSE chunking and special-token accounting can affect the rates. Common template tokens may be reused even for the otherwise fresh long request; the cached column reports that explicitly.

GPU telemetry samples once per second. Peak VRAM includes other desktop consumers and the server, rather than measuring only model allocations. The RTX 3060 is the only GPU selected by the model launchers.

## Prefix reuse, natural tool round trips and API checks

After the long request, the exact same prompt is requested again with 256 output tokens. A separate long prompt asks the model to call `lookup_codeword(key="recipe")`, then the tool response `BLUEPRINT-742` must appear in the final assistant text. Tool requests use temperature 0, normal EOS and a 1024-token output cap.

| Model | Reused prompt tokens | Reuse TTFT (s) | Tool call / follow-up input tokens | Tool cycle | Responses | Messages |
|---|---:|---:|---|---|---|---|
| qwen3.6 | 58304 | 2.91 | 56582 / 56667 | PASS | PASS | PASS |
| gemma4 | 58367 | 0.96 | 56370 / 56401 | PASS | PASS | PASS |
| gpt-oss | 58367 | 1.14 | 56375 / 56427 | PASS | PASS | PASS |
| flint | 65535 | 0.81 | 63611 / 63658 | PASS | PASS | PASS |
| nemotron | 57343 | 0.16 | 55341 / 55440 | PASS | PASS | PASS |

Chat Completions is exercised by all throughput and tool requests. Responses and Messages are separate short HTTP requests with schema checks. These are real protocol and model-tool tests; they are not full coding sessions through every third-party agent client or an evaluation of generated patch quality. Structured tool tokens do not all appear as text events, so a text-only decode rate is not inferred for a tool-call response.

## Environment and installation

- Ryzen 5 5600X, 32 GiB RAM, RTX 3060 12 GiB; one active generation.
- A new repository-local Python 3.12 environment was created and used for the FreeToken tests.
- FreeToken wheels, official FlashInfer cubin/JIT cache wheels and llama.cpp archives have pinned SHA-256 values in [runtime.json](../runtime.json).
- The installer now uses the **103 validated Python package versions** in [constraints-validated.txt](../constraints-validated.txt). The installed package inventory is included with the logs. System/compiler/driver prerequisites are outside that Python constraint file.
- Flint ran on the exact reviewed overlay commit **`6ee048e3cca92da2a85cdc9ca6fd21cceed527ad`**, using the pinned wheel's native extensions. The old `edfba5e…` throughput remains historical.
- All five current model weight sets were fully SHA-256 hashed against LFS blobs at their pinned Hugging Face revisions. Anonymous 1024-byte range downloads returned HTTP 206 and matched the local samples. This proves access and blob identity; the large model libraries were reused rather than downloaded again in full.

## Failures retained and fixes validated

1. The initial new FreeToken environment lacked `flashinfer-cubin` and `flashinfer-jit-cache`, causing attention graph setup to fall back to unavailable `nvcc`. Both official binary caches are now installed explicitly and checksum verified. [Initial bootstrap evidence](../evidence/logs/validation-2026-10-24-bootstrap-failed).
2. Reusing an API port immediately after shutdown hit TCP TIME_WAIT during the port guard. The guard now uses `SO_REUSEADDR`; the validator also uses a separate port pair per model.
3. Qwen's 8192 prefill ceiling caused GDN workspace CUDA OOM on the long request. The validated profile uses **2048**, preserving 66560 capacity, 3328 expert slots and four recurrent-state slots. [Failed attempt](../evidence/logs/validation-2026-10-24/qwen3.6-failed-chunk8192).
4. Gemma's earlier 8192 prefill ceiling OOM was already corrected to **1024**; the full-budget test now validates that profile. [Earlier failure](../evidence/logs/gemma4/failed-prefill8192-server.log).

5. Character truncation skipped exact prompt lengths for Flint and Nemotron. The builder now pads with verified single-token fillers and rechecks the server count. The validator can resume missing phases and archives failed requests, server logs and GPU traces.
6. Nemotron at 65536 physical context stopped after 8186 generated tokens because DFlash/decoder lookahead needed extra slots. Its recipe now allocates **65792 physical tokens**, reserving **256 internally** while keeping the full **65536-token client budget** (57344 input + 8192 output). Context shifting remains disabled; the failed attempt is retained.

A backend watchdog interrupts SSE reads if the owned backend fails after sending HTTP 200, preserving the failure log instead of waiting for a network timeout. Failed runs are retained alongside successful runs.

## Reproduce and inspect

```bash
./recipes install --flint
./recipes install --llama-cpp
# Download the selected models with ./recipes download MODEL first.
# Stop other model servers to free VRAM.
.venv/bin/python scripts/validate-profiles.py --output /tmp/recipes-validation
python3 -m unittest discover -s tests -v
python3 scripts/summarize-validation.py \
  --directory /tmp/recipes-validation --output /tmp/recipes-validation-summary.json
```

Use `--models gemma4` to select a subset. On the measured machine, the runner used `--pause-user-service nemotron-e4b.service`; it refused to interrupt a busy service and restored the initially active service afterward. The optional flag is not required on other systems.

[Structured summary](../evidence/validation-2026-10-24.json) · [Complete run directory](../evidence/logs/validation-2026-10-24) · [Log manifest](../evidence/logs/manifest.json) · [Measurement implementation](../scripts/validate-profiles.py) · [Metric recomputation](../scripts/summarize-validation.py).

Original historical temporary files that were lost cannot be regenerated as historical originals. The new tests provide independently dated complete evidence for the previously missing measurements.
