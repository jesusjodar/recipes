# Agentic coding speed at 64K context capacity

Tested on the RTX 3060 12 GB using llama.cpp b11828 / CUDA 13.4, Q8_K_XL target, NVIDIA official BF16 DFlash GGUF, DFlash n-max 7, one sequence, Flash Attention, and `-c 65536`.

| Task | Input tokens | Output tokens | Client rate | llama.cpp decode rate |
|---|---:|---:|---:|---:|
| Python API idempotency fix (patch + tests) | 411 | 1,242 | 103.29 tok/s | 104.73 tok/s |
| TypeScript CSV streaming export (patch + tests) | 277 | 1,721 | 115.24 tok/s | 116.34 tok/s |
| Concurrent worker bug (fix + regression tests + rollout) | 337 | 1,762 | 102.05 tok/s | 103.05 tok/s |
| **Mean** | **342** | **1,575** | **106.86 tok/s** | **108.04 tok/s** |

All three generations ended normally (`finish_reason=stop`), rather than hitting the output token limit. Across the requests, DFlash accepted 3,278 of 10,108 drafted tokens (32.4%). The server reported 65,536 context tokens per slot. VRAM usage after loading was about 8.6 GiB, leaving about 3.3 GiB on the 3060.

Important scope: the server was configured for 64K capacity, but the test prompts themselves were 277–411 tokens. This measures normal coding requests on a 64K-configured server; it does not measure decode speed after filling nearly all 64K with prior conversation/repository context. Long active context can reduce speed and consume more KV memory.

Start this profile with `~/Desktop/AI/start-nvidia-64k.sh`. For peak speed with shorter context, use `~/Desktop/AI/start-nvidia.sh` (8K).
