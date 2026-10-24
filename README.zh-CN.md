![recipes — 本地 AI 推理实测配置](assets/recipes-blueprint.png)

# recipes

[English](README.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md)

我的本地推理配置，面向 **AMD Ryzen 5 5600X · RTX 3060 12 GiB · 32 GiB 内存**。包含模型权重来源、固定引擎版本、自动启动脚本、智能体客户端配置和实测性能。**仅文本，每次只运行一个生成请求。** 现已公开，包含脱敏证据和可复现的验证命令。

清点与满预算验证日期：**2026-10-24**。10 月 22–23 日的历史对比数据单独保留。这些是在本机已尝试配置中选出的方案，不代表已证明的全局最优值。

## 目录

- [模型与性能](#models)
- [硬件与适用范围](#hardware)
- [快速开始](#quick-start)
- [各模型配置](#recipes)
  - [Qwen 3.6](#qwen)
  - [Gemma 4](#gemma)
  - [GPT-OSS](#gpt-oss)
  - [Flint](#flint)
  - [Nemotron + DFlash](#nemotron)
- [OpenAI 兼容 API](#api)
- [OpenCode、Hermes、Codex 和 Claude Code](#clients)
- [FreeToken Desktop](#desktop)
- [日志与复现](#evidence)
- [仓库结构与许可证](#layout)

<a id="models"></a>
## 模型与性能

**上下文包括输入、历史消息、模板、推理和输出。** 2026-10-24 已对五个公开配置逐一使用全部输入预算，并**实际生成 8192 个输出 token**。主表改为这些长请求的结果，所有引擎采用相同的 HTTP 计时方法。每个长测量为预热后的一次运行，不是统计平均值。

| 模型 | 引擎 | 总上下文 | 输入预算¹ | 输出¹ | Drafter | Prefill² | Decode² | 实测负载 | 量化 | 来源 / 配置 |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen 3.6 35B A3B | FreeToken | 66560 | 58368 | 8192 | 无 | 1739.20 | 60.39 | 58368 + 8192 | NVFP4 ModelOpt （混合） | [原模型](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) · [权重](https://huggingface.co/nvidia/Qwen3.6-35B-A3B-NVFP4) · [配置](profiles/qwen3.6.json) |
| Gemma 4 26B A4B | FreeToken | 66560 | 58368 | 8192 | 无 | 884.26 | 30.20 | 58368 + 8192 | NVFP4 ModelOpt （混合） | [原模型](https://huggingface.co/google/gemma-4-26B-A4B-it) · [权重](https://huggingface.co/nvidia/Gemma-4-26B-A4B-NVFP4) · [配置](profiles/gemma4.json) |
| GPT-OSS 20B | FreeToken | 66560 | 58368 | 8192 | 无 | 1444.89 | 34.93 | 58368 + 8192 | MXFP4 | [原模型](https://huggingface.co/openai/gpt-oss-20b) · [权重](https://huggingface.co/openai/gpt-oss-20b) · [配置](profiles/gpt-oss.json) |
| Flint 39.8B A2.5B | FreeToken | 73728 | 65536 | 8192 | 无 | 1521.29 | 50.33 | 65536 + 8192 | NVFP4 GGUF 官方 | [原模型](https://huggingface.co/RecursiveSI/flint) · [权重](https://huggingface.co/RecursiveSI/flint-nvfp4-gguf) · [配置](profiles/flint.json) |
| NVIDIA Nemotron 3.5 Bolt E4B | llama.cpp | 65536 | 57344 | 8192 | BF16 DFlash | 1840.76 | 142.95 | 57344 + 8192 | Unsloth UD-Q8_K_XL GGUF （混合） | [原模型](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-BF16) · [权重](https://huggingface.co/unsloth/NVIDIA-Nemotron-3.5-Bolt-E4B-GGUF) · [配置](profiles/nemotron.json) |

¹ 输入包含系统指令、模板和工具开销。8192 也是日常默认输出预算；**仅在吞吐测试中**使用 `ignore_eos` 强制达到该长度，正常使用遵循 EOS。计数采用 API token usage，包含没有可见文本的特殊 token。Nemotron 物理分配 65792 槽位，内部预留 256，客户端可用 65536。

² 有效 prefill = **未缓存** prompt token 数 / 首个非空文本或推理事件前的时间；decode =（输出 token 数 − 1）/ 首个内容事件到最终 usage 事件的间隔，包含末尾未显示的 token。包含本地服务开销及 token/分块计数影响。提示词由本仓库源码和不同的合成前缀构成。相同计时方法不代表不同模型的 tokenizer 或负载完全相同。这些测试验证容量和服务行为，不是一般编程质量评估。

[完整结果、缓存复用、工具循环和 API 检查](docs/validation.md) · [结构化摘要](evidence/validation-2026-10-24.json) · [完整请求、SSE 时间线、服务日志和 GPU 记录](evidence/logs/validation-2026-10-24)。此前短提示词与引擎周期性统计保留在各模型证据中，作为独立历史系列。

<a id="hardware"></a>
## 硬件与适用范围

Ryzen 5 5600X，6 核 / 12 线程，标称 32 GiB 内存，RTX 3060 12 GiB（SM86），NVIDIA 驱动 615.78.08。FreeToken 在 CPU/GPU 之间卸载专家；Nemotron 的主模型和 drafter 则全部放入 3060。[硬件](evidence/hardware.json) · [带宽微基准](evidence/bandwidth.json)。

本机还安装了 RTX 2070 8 GiB。之前的双 GPU 实验受到热降频影响（88°C / 300 MHz），因此未将其结果列为优化配置。启动器按 UUID 选择 3060，并将其暴露为设备 0。在 Ampere 上使用 NVFP4 权重存储，并不意味着使用 Blackwell 原生 FP4 指令。

<a id="quick-start"></a>
## 快速开始

![从权重到工作流](assets/workflow-blueprint.png)

要求：Linux x86_64、Python 3.12+、用于 Triton 主机代码的 C/C++ 编译器、Git、兼容所选 CUDA 运行时的 NVIDIA 驱动，以及足够的磁盘和内存。FreeToken 还需要 [`uv`](https://docs.astral.sh/uv/getting-started/installation/)。FreeToken 使用固定的 CPython 3.12 wheel；未缓存的内核可能需要 CUDA 13 工具包。Nemotron 使用 llama.cpp b11828 的官方 CUDA 13.4 二进制及运行时压缩包，并验证 SHA-256。

```bash
gh repo clone jesusjodar/recipes
cd recipes
./recipes list

./recipes install
./recipes download gemma4
./recipes serve gemma4

# Nemotron 使用独立引擎，无需安装 FreeToken。
./recipes install --llama-cpp
./recipes download nemotron
./recipes serve nemotron
```

**每次只启动一个模型服务器**，等待 `LISTO` 后再连接客户端。先关闭其他模型服务器以释放显存。Ctrl+C 会清理启动器创建的进程。FreeToken 需要 API 端口及其下一端口；llama.cpp 只需要 API 端口。

```bash
./recipes serve gemma4 --port 22420
./recipes serve gemma4 --gpu GPU-YOUR-CARD-UUID
./recipes show gemma4
./recipes serve nemotron --print-command
```

默认权重目录为 `~/.freetoken/models`；可用 `RECIPES_MODEL_DIR` 指定其他目录。Nemotron 也会复用已存在且哈希正确的 `~/Desktop/AI/models` 文件，引擎压缩包可从 `~/Desktop/AI/bin` 复用。五个当前主模型均已完整计算 SHA-256，并与固定 Hub 版本的 blob 对照；历史运行仍保留独立日期。经过记录的完整性核验后复用本地分片。Nemotron 的 drafters 也已验证哈希。[清单](evidence/inventory.json) · [固定运行时版本](runtime.json)。

<a id="recipes"></a>
## 各模型配置

<a id="qwen"></a>
### Qwen 3.6 35B A3B

总上下文 66560，3328 个专家缓存槽，4 个 GDN/Mamba 状态槽，hybrid fetch 1。已完成 **58368 输入 + 8192 输出**。prefill 上限 8192 导致 GDN 工作区显存不足，因此验证后的配置改用 **2048**，保留上下文和专家缓存容量。先以 1024 个专家启动后重建。Desktop 的 `swaTokens=2048` 对该循环模型不起作用，不发送给 CLI 重建 API。采样：temperature 1、top-p 0.95、top-k 20。验证报告还记录长上下文工具循环及前缀复用。

```bash
./recipes install
./recipes download qwen3.6
./recipes serve qwen3.6
```

[配置](profiles/qwen3.6.json) · [证据](evidence/qwen3.6.json) · [客户端](clients/qwen3.6)

<a id="gemma"></a>
### Gemma 4 26B A4B

**禁用视觉和音频。** 总上下文 66560，448 个专家，hybrid fetch 1，prefill **1024**。CLI 保留初始 **13312** 的 SWA 池，Desktop 保存 **1024**，两者缓存几何不同。此前 prefill 上限 8192 的 OOM 日志保留。新测试已按公开 CLI 配置完成 **58368 输入 + 8192 输出**。常规采样：temperature 1、top-p 0.95、top-k 64。旧的 1425 专家配置无法容纳更大的上下文。

```bash
./recipes install
./recipes download gemma4
./recipes serve gemma4
```

[配置](profiles/gemma4.json) · [证据](evidence/gemma4.json) · [客户端](clients/gemma4)

<a id="gpt-oss"></a>
### GPT-OSS 20B

MXFP4，总上下文 66560，256 个专家，hybrid fetch 1。新测试已完成 **58368 输入 + 8192 输出**。此前 16K 上下文的 535 专家配置无法为更大上下文留出空间。CLI SWA 池为 **13312**，Desktop 为 **512**。引擎使用 Harmony 与 checkpoint 默认采样；吞吐测试使用 temperature 0。验证报告保留实际长工具循环及 API 检查结果。

```bash
./recipes install
./recipes download gpt-oss
./recipes serve gpt-oss
```

[配置](profiles/gpt-oss.json) · [证据](evidence/gpt-oss.json) · [客户端](clients/gpt-oss)

<a id="flint"></a>
### Flint 39.8B A2.5B

官方 NVFP4 GGUF，固定版本 `6ec43e19…`。**65536 输入 + 8192 输出**。最终缓存 3456 个专家，SWA 5120，prefill 分块 4096，memory ratio 0.90，启用 CUDA normalization 和 prefill D2D 命中。先以 1024 个专家启动，加载后重建。

```bash
./recipes install --flint
./recipes download flint
./recipes serve flint
```

支持代码已在 [FreeToken #797](https://github.com/FlashML-org/FreeToken/pull/797) 提出。安装器固定到评审后的 Python 提交 `6ee048e…`，并复用 wheel 原生扩展；**新的长上下文测试已在这个确切的安装提交上运行**。下表单独保留此前 `edfba5e…` 的历史测量以供对照。这不是从源码完整编译 CUDA 的安装方式。

| 历史负载 | 有效 prefill | Decode | 首 token 时间 |
|---|---:|---:|---:|
| 8192 + 256，冷前缀，三次平均 | 2783.31 | 66.53 | ≈2.94 秒 |
| 65536 + 8192，冷前缀，一次 | 1543.59 | 49.97 | 42.46 秒 |
| 65536 + 256，复用前缀 | 复用 65535 tokens | 50.38 | 0.88 秒 |

仅吞吐基准强制使用 `ignore_eos`；日常服务正常遵循 EOS。另外完成过一次 >64K 的工具调用循环，但不能据此断言一般编程质量。历史观测峰值显存约 10.61 GiB，含桌面；主机专家约占 19.8 GiB。采样：temperature 1、top-p 0.95、top-k 20。[配置](profiles/flint.json) · [结果](evidence/flint.json) · [参数扫描日志](evidence/logs/flint) · [客户端](clients/flint)。

研究目录还保存了 [FutureMLS-Lab Flint ModelOpt 导出](https://huggingface.co/FutureMLS-Lab/flint-nvfp4-coldgptq)，版本 `56f37fcf…`，本地重新整理成按层存放的 safetensors。该版本用于一致性、AIME 和缓存重建验证，服务容量为 8192；没有优化过的长上下文吞吐或输出目标。因此只记录在清单中，不作为另一份已优化配方宣传。[验证日志](evidence/logs/flint-validation)。

<a id="nemotron"></a>
### NVIDIA Nemotron 3.5 Bolt E4B + DFlash

**llama.cpp b11828 CUDA 13.4**，Unsloth **UD-Q8_K_XL** 主模型及 NVIDIA 官方 **BF16 GGUF DFlash** drafter。最多草拟 7 个 token（块大小 8），两者完整加载到 GPU，启用 Flash Attention、Jinja，单槽位，关闭 fitting，并**显式禁用 context shift**。物理分配 **65792**，包含 **256 个 DFlash 内部预留槽位**；客户端可用上下文 **65536**，已实测 **57344 输入 + 8192 实际输出**。不加载视觉 projector。常规 temperature 1、top-p 0.95；固定长度测试使用 temperature 0。

历史短编程任务在 64K 容量下达到 **1964.10 引擎 prefill / 108.04 引擎 decode / 106.86 API 输出 tok/s**，输入 277–411，输出 1242–1762。这些短上下文数字与新的满预算结果分开。四项 8K 测试中，BF16 为 **117.63 API / 121.63 引擎 decode**，下载的 Unsloth Q8_0 drafter 为 **85.34 / 87.52**，因此选用 BF16。这些不是原生 NVFP4 drafter 的结果。历史生成补丁未经过正确性验证。

新启动器端口为 **1919**。原 Desktop/AI 服务使用 **8000**；验证时仅在其空闲后暂时暂停，结束后恢复。

```bash
./recipes install --llama-cpp
./recipes download nemotron
./recipes serve nemotron
```

[配置](profiles/nemotron.json) · [证据](evidence/nemotron.json) · [客户端](clients/nemotron)

<a id="api"></a>
## OpenAI 兼容 API

所有启动器只绑定 `127.0.0.1`，不要求 API 密钥，也不公开暴露服务。模型 ID 为 `qwen3.6`、`gemma4`、`gpt-oss`、`flint`、`nemotron`。

```bash
curl --fail-with-body http://127.0.0.1:1919/v1/models
curl --fail-with-body http://127.0.0.1:1919/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"nemotron","messages":[{"role":"user","content":"请概述这个项目。"}],"max_tokens":8192,"stream":true}'
```

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:1919/v1", api_key="local-no-key")
r = client.chat.completions.create(
    model="nemotron", max_tokens=8192,
    messages=[{"role": "user", "content": "请总结这个 diff。"}],
)
print(r.choices[0].message.content)
```

`local-no-key` 是供 SDK 使用的公开占位符。FreeToken 环境已含 OpenAI SDK；若只安装 llama.cpp，需另行安装，例如 `uv run --with openai your_script.py`。两种引擎都提供 `/v1/responses` 和 `/v1/messages`；固定版本的 llama.cpp 说明见[这里](https://github.com/ggml-org/llama.cpp/blob/b11828/tools/server/README.md)。本地适配器不代表完全支持 OpenAI/Anthropic 的所有功能。FreeToken Responses 是无状态子集：需要重发历史与工具，不能依赖存储的响应、`previous_response_id` 或后台任务；必要时保留推理字段。

<a id="clients"></a>
## 智能体客户端

先启动模型。以下示例使用 **Nemotron**；切换模型时应同步修改模型 ID、客户端目录和上下文。每个模型在 `clients/` 下都有自己的配置。这里提供配置示例和端点检查结果，**没有声称每个客户端都已完成真实的完整编程会话验证**。

| 客户端 | 协议 | 文件 |
|---|---|---|
| OpenCode v2.1.4 | Chat Completions | [v2 JSON](clients/nemotron/opencode-v2.json) |
| OpenCode v1 | Chat Completions，配置格式不同 | [v1 JSON](clients/nemotron/opencode-v1.json) |
| Hermes Agent | Custom provider，Chat Completions | [YAML](clients/nemotron/hermes.yaml) |
| Codex CLI 0.164.0 | Responses | [启动脚本](clients/nemotron/codex.sh) · [TOML](clients/nemotron/codex.toml) |
| Claude Code 2.1.310 | Anthropic Messages 适配器 | [启动脚本](clients/nemotron/claude-code.sh) |

### OpenCode

将对应 JSON 合并进工作项目的 `opencode.json`，保留现有设置。v2 使用 `providers/package/settings`，v1 使用 `provider/npm/options`。在 `/models` 中选择 `recipes/nemotron`，或执行：

```bash
opencode run --model recipes/nemotron "请概述项目结构"
```

配置声明文本、工具、推理字段、上下文/输入/输出预算及 `max_tokens=8192`。

### Hermes

按[官方指南](https://hermes-agent.nousresearch.com/docs/getting-started/installation)安装后，用 `hermes model` 选择 Custom endpoint，或执行：

```bash
hermes config set model.provider custom
hermes config set model.default nemotron
hermes config set model.base_url http://127.0.0.1:1919/v1
hermes config set model.api_mode chat_completions
hermes config set model.context_length 65536
hermes chat
```

不要加入已废弃的 `model.max_tokens`。服务器默认输出为 8192。上下文分别为：Nemotron 65536；Qwen/Gemma/GPT 66560；Flint 73728。

### Codex

```bash
bash clients/nemotron/codex.sh
```

脚本仅为当前进程覆盖 provider，不修改全局登录或配置。使用 Responses，不要求 OpenAI 身份验证，也不启用 WebSockets；在输入预算耗尽前进行压缩。TOML 包含相同选项，供手动集成。

### Claude Code

```bash
bash clients/nemotron/claude-code.sh
```

使用**不含 `/v1`** 的根 URL；客户端会追加 `/v1/messages`。所有模型别名均指向同一本地模型。Anthropic **未正式支持非 Claude 模型**；行为取决于模型和适配器的兼容性。此处固定的两种引擎无需额外的 Chat Completions→Messages 代理。脚本保留审批控制。[详细说明及官方来源（西班牙语）](docs/clients.md)。

<a id="desktop"></a>
## FreeToken Desktop

```bash
./recipes desktop gemma4
# 应用前先关闭 Desktop。
./recipes desktop gemma4 --apply
```

默认预览；`--apply` 会先备份，再合并该模型的缓存配置和仅文本标志。不会安装 Flint 支持或更改全局选项、引擎、Downloads 卡片。**Nemotron 的实测配置使用 llama.cpp，没有 FreeToken Desktop 配置。** [全局配置及 CLI/Desktop 差异](docs/desktop.md)。

<a id="evidence"></a>
## 日志与复现

- [日志清单](evidence/logs/manifest.json)：恢复来源、SHA-256 与脱敏说明。移除个人目录、工作区路径、GPU UUID 和终端颜色；不包含私人对话、凭据、声音数据或网络信息。
- [Qwen](evidence/logs/qwen3.6)、[Gemma](evidence/logs/gemma4)、[GPT-OSS](evidence/logs/gpt-oss)：新的完整服务器日志和逐请求 SSE 捕获，并保留可恢复的历史终端输出。Gemma 的 8192-prefill 失败记录也保留。
- [Nemotron](evidence/logs/nemotron)：原始 JSON 测量、脚本和报告。历史完整服务器 stdout 未保留，不能根据摘要忠实重建。
- [Flint](evidence/logs/flint)：原始扫描日志、JSON 与 GPU 采样；另有[验证日志](evidence/logs/flint-validation)。
- [方法与限制](docs/measurements.md) · [恢复审计](docs/log-recovery.md) · [运行时版本](runtime.json) · [关键依赖约束](constraints.txt)。

原 Gemma/GPT 临时日志已丢失。终端捕获明确标为恢复材料，可能保留当时的截断；新测量单独记录，不冒充历史原件。`null` 表示未知。模型权重不上传。

复现时，按记录的缓存几何运行单个模型，保存 stdout/stderr，再用 FreeToken 环境运行合成基准：

```bash
./recipes serve gemma4 > /tmp/gemma4-server.log 2>&1
# 另开终端，等待 LISTO 后执行：
.venv/bin/python scripts/benchmark-freetoken.py gemma4 \
  --output /tmp/gemma4-new-measurement.json
```

应记录引擎版本、硬件、权重哈希、实际 token 数、缓存状态、EOS 策略、预热和全部样本。新基准仅为固定长度测试启用 `ignore_eos`。在宣称满上下文性能前，必须实测接近上限的输入和输出。安装器保存本地 `uv pip freeze`，并在 [constraints-validated.txt](constraints-validated.txt) 中固定全部 103 个 Python 包版本；新的独立 FreeToken 环境已经安装并用于这些测试，包含两个固定版本的 FlashInfer 二进制缓存包。

### 复现完整验证

先关闭其他模型服务以释放显存，然后运行：

```bash
.venv/bin/python scripts/validate-profiles.py --output /tmp/recipes-validation
python3 -m unittest discover -s tests -v
```

验证器依次启动各配置，通过服务器计数构建精确预算的合成提示词，生成 8192 个 token，重复前缀，执行自然工具调用循环，并检查 Responses/Messages。记录完整请求、带时间戳的 SSE、stdout/stderr 和 GPU 数据。`--models qwen3.6` 可只测试一个模型。本机可用 `--pause-user-service nemotron-e4b.service` 在服务空闲后暂停并于结束时恢复。包括失败检查在内的实际结果均见[验证报告](docs/validation.md)。

<a id="layout"></a>
## 仓库结构与许可证

```text
profiles/        模型、引擎、启动参数、上下文和输出策略
clients/         各模型的 OpenCode、Hermes、Codex、Claude 配置
evidence/        测量、清单和脱敏日志
scripts/         安装、下载、服务、Desktop 合并和基准
assets/          两张 ImageGen 原创蓝图风格横幅
docs/            方法、恢复、Desktop、客户端及图片来源
runtime.json     固定版本、压缩包/wheel 哈希和 Flint 提交
```

新增配方需要配置文件、固定权重来源、实际测量负载/日志、客户端示例和表格条目。必须区分预留容量、已测负载和目标输出。辅助文档主要为西班牙语；三个 README 均包含完整使用概览。

[MIT](LICENSE) 适用于原创配置和脚本；引擎与模型遵循各自许可证。Nemotron 采用 **OpenMDW-1.1**，请查阅上游模型卡。[横幅提示词与来源](docs/artwork.md)：ImageGen 生成的原创蓝图风格图片，不是官方标志，也不构成性能认证。

来源：[FreeToken](https://github.com/FlashML-org/FreeToken) · [llama.cpp b11828](https://github.com/ggml-org/llama.cpp/releases/tag/b11828) · [OpenCode](https://opencode.ai/v2/docs/providers) · [Hermes](https://hermes-agent.nousresearch.com/docs/integrations/providers) · [OpenAI 配置](https://learn.chatgpt.com/docs/config-file/config-reference) · [Claude 网关](https://code.claude.com/docs/en/llm-gateway-connect)。
