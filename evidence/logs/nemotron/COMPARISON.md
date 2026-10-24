# Local DFlash comparison

Machine: NVIDIA RTX 3060 12 GB, llama.cpp b11828 CUDA 13.4, target Q8_K_XL, CUDA0, one sequence, Flash Attention, DFlash n-max=7, context=8192. Both drafters used the same four agentic software prompts, thinking enabled, max output 256 tokens, one warm-up request. Measured 4 requests per drafter, concurrency 1.

| Drafter loaded in llama.cpp | Mean API output rate | Mean llama.cpp decode rate | Accepted / drafted proposals |
|---|---:|---:|---:|
| NVIDIA BF16 GGUF (`dflash-nvidia-BF16.gguf`; official GGUF associated with the NVIDIA NVFP4 checkpoint) | 117.63 tok/s | 121.63 tok/s | 37.9% |
| Unsloth Q8_0 (`dflash-unsloth-Q8_0.gguf`) | 85.34 tok/s | 87.52 tok/s | 32.6% |

NVIDIA's BF16 GGUF was 37.9% faster by mean API rate in this small run. The NVIDIA draft also had a higher proposal acceptance ratio. This is a comparison of runtime-ready GGUFs; it is not a native NVFP4-vs-Q8 comparison. The RTX 3060 is Ampere and the NVFP4 safetensors checkpoint is not a direct llama.cpp GGUF input. The official downloadable NVIDIA draft GGUF is BF16.

## Tuning checks with NVIDIA BF16 GGUF

| Context | n-max | Mean API output rate |
|---:|---:|---:|
| 8192 | 7 | 117.63 tok/s |
| 16384 | 7 | 114.41 tok/s |
| 8192 | 4 | 111.93 tok/s |

In these prompts, n-max 7 and 8K context were fastest. The 16K context run was only about 2.7% slower and offers more room for agent history. The recommendation is 8K for peak speed or 16K when the extra working context is more useful. These are short synthetic samples, not a broad benchmark; real throughput varies with context length, prompt reuse, generated response length, GPU occupancy, and sampling.

Raw JSON responses are in this directory as `unsloth.json`, `nvidia-bf16.json`, `nvidia-bf16-16k-n7.json`, and `nvidia-bf16-8k-n4.json`.
