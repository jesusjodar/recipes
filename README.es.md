![recipes — configuraciones de IA local medidas](assets/recipes-blueprint.png)

# recipes

[English](README.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md)

Mis recetas de inferencia local para **AMD Ryzen 5 5600X · RTX 3060 12 GiB · 32 GiB RAM**: pesos, versiones de engines, lanzadores automáticos, clientes agénticos y rendimiento medido. **Solo texto y una generación simultánea.** Publicado con evidencias saneadas y comandos para reproducir las pruebas.

Inventario y validación de contexto completo: **24-10-2026**. Las comparativas históricas del 22–23 de octubre se conservan por separado. Son los perfiles elegidos entre los ajustes probados en este equipo; no demuestran un óptimo global.

## Índice

- [Modelos y rendimiento](#models)
- [Equipo y alcance](#hardware)
- [Inicio rápido](#quick-start)
- [Recetas por modelo](#recipes)
  - [Qwen 3.6](#qwen)
  - [Gemma 4](#gemma)
  - [GPT-OSS](#gpt-oss)
  - [Flint](#flint)
  - [Nemotron + DFlash](#nemotron)
- [API compatible con OpenAI](#api)
- [OpenCode, Hermes, Codex y Claude Code](#clients)
- [FreeToken Desktop](#desktop)
- [Logs y reproducción](#evidence)
- [Estructura y licencias](#layout)

<a id="models"></a>
## Modelos y rendimiento

**El contexto incluye entrada, historial, plantillas, razonamiento y salida.** Los cinco perfiles publicados se probaron con todo su presupuesto de entrada y **8192 tokens de salida reales** el 24-10-2026. La tabla principal muestra esas peticiones largas, con el mismo método HTTP para todos los engines. Cada medición larga es una ejecución tras calentamiento, no una media estadística.

| Modelo | Engine | Contexto total | Entrada reservando salida¹ | Salida¹ | Drafter | Prefill² | Decode² | Carga medida | Cuantización | Fuentes / config |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen 3.6 35B A3B | FreeToken | 66560 | 58368 | 8192 | No | 1739,20 | 60,39 | 58368 + 8192 | NVFP4 ModelOpt (mixto) | [Original](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) · [Pesos](https://huggingface.co/nvidia/Qwen3.6-35B-A3B-NVFP4) · [Config](profiles/qwen3.6.json) |
| Gemma 4 26B A4B | FreeToken | 66560 | 58368 | 8192 | No | 884,26 | 30,20 | 58368 + 8192 | NVFP4 ModelOpt (mixto) | [Original](https://huggingface.co/google/gemma-4-26B-A4B-it) · [Pesos](https://huggingface.co/nvidia/Gemma-4-26B-A4B-NVFP4) · [Config](profiles/gemma4.json) |
| GPT-OSS 20B | FreeToken | 66560 | 58368 | 8192 | No | 1444,89 | 34,93 | 58368 + 8192 | MXFP4 | [Original](https://huggingface.co/openai/gpt-oss-20b) · [Pesos](https://huggingface.co/openai/gpt-oss-20b) · [Config](profiles/gpt-oss.json) |
| Flint 39.8B A2.5B | FreeToken | 73728 | 65536 | 8192 | No | 1521,29 | 50,33 | 65536 + 8192 | NVFP4 GGUF oficial | [Original](https://huggingface.co/RecursiveSI/flint) · [Pesos](https://huggingface.co/RecursiveSI/flint-nvfp4-gguf) · [Config](profiles/flint.json) |
| NVIDIA Nemotron 3.5 Bolt E4B | llama.cpp | 65536 | 57344 | 8192 | BF16 DFlash | 1840,76 | 142,95 | 57344 + 8192 | Unsloth UD-Q8_K_XL GGUF (mixto) | [Original](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-BF16) · [Pesos](https://huggingface.co/unsloth/NVIDIA-Nemotron-3.5-Bolt-E4B-GGUF) · [Config](profiles/nemotron.json) |

¹ La entrada incluye sistema, plantilla y herramientas. La salida es el default habitual de 8192 y se forzó a esa longitud con `ignore_eos` **solo en el benchmark**. El uso normal respeta EOS. Se cuenta el uso de tokens del API, incluidos los especiales sin texto visible. Nemotron asigna 65792 slots físicos y reserva 256 internamente, dejando 65536 utilizables por los clientes.

² Prefill efectivo = tokens de prompt **no cacheados** / tiempo hasta el primer evento no vacío de texto o razonamiento; decode = (tokens de salida − 1) / intervalo desde el primer contenido hasta el evento final de uso, incluidos los tokens finales sin representación visible. Incluye el servidor local y los efectos de contabilidad de tokens/chunks. Los prompts contienen fuentes de este repositorio y prefijos sintéticos distintos. El mismo método no iguala los tokenizers ni las cargas entre modelos. Estas pruebas acreditan capacidad y comportamiento de serving, no calidad general de programación.

[Resultados, caché, ciclos de herramienta y API](docs/validation.md) · [Resumen estructurado](evidence/validation-2026-10-24.json) · [Peticiones, eventos SSE, logs y trazas GPU completos](evidence/logs/validation-2026-10-24). Las cifras cortas anteriores y las periódicas del engine se conservan como series históricas en las evidencias por modelo.

<a id="hardware"></a>
## Equipo y alcance

Ryzen 5 5600X, 6 núcleos / 12 hilos, 32 GiB nominales de RAM, RTX 3060 12 GiB (SM86), driver NVIDIA 615.78.08. FreeToken descarga expertos entre CPU/GPU; Nemotron y su drafter caben íntegramente en la 3060. [Hardware](evidence/hardware.json) · [Microbenchmarks de ancho de banda](evidence/bandwidth.json).

También hay una RTX 2070 de 8 GiB. Los experimentos anteriores con ambas GPU sufrieron throttling térmico (88 °C / 300 MHz); sus resultados no se publican como receta optimizada. Los lanzadores seleccionan la 3060 por UUID y la exponen como dispositivo 0. Almacenar NVFP4 en Ampere no implica instrucciones FP4 nativas de Blackwell.

<a id="quick-start"></a>
## Inicio rápido

![De los pesos al flujo de trabajo](assets/workflow-blueprint.png)

Requisitos: Linux x86_64, Python 3.12+, compilador C/C++ para los stubs de Triton, Git, driver NVIDIA compatible con el runtime CUDA elegido, espacio/RAM y [`uv`](https://docs.astral.sh/uv/getting-started/installation/) para FreeToken. FreeToken usa wheels CPython 3.12 fijados y puede necesitar toolkit CUDA 13 para kernels sin caché. Nemotron usa binarios/runtime oficiales de llama.cpp b11828 CUDA 13.4 con SHA-256 verificado.

```bash
gh repo clone jesusjodar/recipes
cd recipes
./recipes list

./recipes install
./recipes download gemma4
./recipes serve gemma4

# Engine independiente para Nemotron; no necesita instalar FreeToken.
./recipes install --llama-cpp
./recipes download nemotron
./recipes serve nemotron
```

Ejecuta **un servidor cada vez** y espera a `LISTO` antes de conectar el cliente. Detén otros servidores para liberar VRAM. Ctrl+C limpia los procesos iniciados por el lanzador. FreeToken necesita el puerto API y puerto + 1; llama.cpp solo el puerto API.

```bash
./recipes serve gemma4 --port 22420
./recipes serve gemma4 --gpu GPU-UUID-DE-TU-TARJETA
./recipes show gemma4
./recipes serve nemotron --print-command
```

La biblioteca predeterminada es `~/.freetoken/models`; usa `RECIPES_MODEL_DIR` para cambiarla. Nemotron también reutiliza los archivos de `~/Desktop/AI/models` si existen y sus hashes son correctos. Sus archivos de engine pueden reutilizarse desde `~/Desktop/AI/bin`. Los cinco modelos actuales tienen verificación SHA-256 completa contra los blobs del Hub de sus revisiones fijadas; las ejecuciones históricas mantienen su fecha separada. Se reutilizan los shards locales tras la comprobación registrada. Los drafters de Nemotron también están verificados. [Inventario](evidence/inventory.json) · [Versiones fijadas](runtime.json).

<a id="recipes"></a>
## Recetas por modelo

<a id="qwen"></a>
### Qwen 3.6 35B A3B

Contexto total 66560, 3328 plazas de expertos, cuatro slots GDN/Mamba, hybrid fetch 1. Completó **58368 de entrada + 8192 de salida**. El techo de prefill 8192 agotó el workspace GDN; la receta validada usa **2048** y mantiene contexto y caché de expertos. Arranca con 1024 expertos y reconstruye. El campo Desktop `swaTokens=2048` no se usa en este modelo recurrente y se omite del rebuild CLI. Muestreo: temperatura 1, top-p 0,95, top-k 20. La validación conserva la reutilización de prefijo y el ciclo largo de herramienta.

```bash
./recipes install
./recipes download qwen3.6
./recipes serve qwen3.6
```

[Perfil](profiles/qwen3.6.json) · [Evidencia](evidence/qwen3.6.json) · [Clientes](clients/qwen3.6)

<a id="gemma"></a>
### Gemma 4 26B A4B

**Sin visión ni audio.** Contexto total 66560, 448 expertos, hybrid fetch 1 y prefill **1024**. La CLI conserva el pool SWA inicial de **13312**; Desktop guarda **1024**, por lo que son geometrías distintas. Se conserva el OOM anterior con techo prefill 8192. La nueva prueba completó **58368 de entrada + 8192 de salida** con la configuración CLI publicada. Muestreo habitual: temperatura 1, top-p 0,95, top-k 64. El perfil antiguo de 1425 expertos no cabía con el contexto mayor.

```bash
./recipes install
./recipes download gemma4
./recipes serve gemma4
```

[Perfil](profiles/gemma4.json) · [Evidencia](evidence/gemma4.json) · [Clientes](clients/gemma4)

<a id="gpt-oss"></a>
### GPT-OSS 20B

MXFP4, contexto total 66560, 256 expertos, hybrid fetch 1. La nueva prueba completó **58368 de entrada + 8192 de salida**. El perfil previo de 535 expertos a 16K no dejaba espacio para el contexto mayor. Pool SWA CLI: **13312**; Desktop: **512**. El engine usa Harmony y los defaults de muestreo del checkpoint; los benchmarks piden temperatura 0. El informe registra los resultados reales del ciclo largo de herramienta y las API.

```bash
./recipes install
./recipes download gpt-oss
./recipes serve gpt-oss
```

[Perfil](profiles/gpt-oss.json) · [Evidencia](evidence/gpt-oss.json) · [Clientes](clients/gpt-oss)

<a id="flint"></a>
### Flint 39,8B A2,5B

GGUF NVFP4 oficial, revisión `6ec43e19…`. **65536 de entrada + 8192 de salida**. Caché final de 3456 expertos, SWA 5120, prefill 4096, memoria 0,90, normalización CUDA y hits D2D en prefill. Arranca con 1024 expertos y reconstruye tras cargar.

```bash
./recipes install --flint
./recipes download flint
./recipes serve flint
```

El soporte está propuesto en [FreeToken #797](https://github.com/FlashML-org/FreeToken/pull/797). El instalador fija el commit Python revisado `6ee048e…` y reutiliza las extensiones nativas del wheel; **la nueva prueba larga se ha ejecutado en este mismo commit instalado**. La tabla siguiente conserva las mediciones anteriores de `edfba5e…` como comparación histórica. No es una compilación CUDA limpia desde fuentes.

| Carga histórica | Prefill efectivo | Decode | TTFT |
|---|---:|---:|---:|
| 8192 + 256, frío, media de 3 | 2783,31 | 66,53 | ≈2,94 s |
| 65536 + 8192, frío, una ejecución | 1543,59 | 49,97 | 42,46 s |
| 65536 + 256, prefijo reutilizado | 65535 tokens recuperados | 50,38 | 0,88 s |

Solo el benchmark fuerza `ignore_eos`; el uso habitual respeta EOS. Se completó además un ciclo de herramienta a >64K, que no demuestra calidad general de programación. Pico histórico observado: 10,61 GiB de VRAM con escritorio; expertos en RAM: unos 19,8 GiB. Muestreo: temperatura 1, top-p 0,95, top-k 20. [Perfil](profiles/flint.json) · [Resultados](evidence/flint.json) · [Logs del barrido](evidence/logs/flint) · [Clientes](clients/flint).

También existe en investigación la exportación [Flint ModelOpt de FutureMLS-Lab](https://huggingface.co/FutureMLS-Lab/flint-nvfp4-coldgptq), revisión `56f37fcf…`, redistribuida localmente en safetensors por capa. Se usó para paridad, AIME y reconstrucción de caché con capacidad de serving 8192, sin throughput de contexto largo ni objetivo de salida optimizados. Está inventariada y no se anuncia como otra receta optimizada. [Logs de validación](evidence/logs/flint-validation).

<a id="nemotron"></a>
### NVIDIA Nemotron 3.5 Bolt E4B + DFlash

**llama.cpp b11828 CUDA 13.4**, modelo Unsloth **UD-Q8_K_XL** y drafter NVIDIA oficial **BF16 GGUF DFlash**. Draft máximo 7 (bloque de 8), ambos enteros en GPU, Flash Attention, Jinja, un slot, fitting desactivado y **context shift desactivado explícitamente**. Asignación física **65792**, con **256 slots internos para DFlash**; contexto utilizable por clientes **65536**, probado con **57344 de entrada + 8192 de salida reales**. Sin proyector visual. Muestreo habitual: temperatura 1 y top-p 0,95; la prueba de longitud fija pide temperatura 0.

Las tareas cortas históricas con capacidad 64K alcanzaron **1964,10 prefill del engine / 108,04 decode del engine / 106,86 salida API tok/s**, con 277–411 de entrada y 1242–1762 de salida. Son métricas cortas separadas del nuevo resultado de contexto completo. Las cuatro tareas a 8K dieron **117,63 API / 121,63 decode del engine** con BF16, frente a **85,34 / 87,52** con el drafter Unsloth Q8_0 descargado. Se elige BF16; no son resultados de drafter NVFP4 nativo. Los parches históricos generados no se verificaron como correctos.

El endpoint portable usa **1919**. El servicio previo de Desktop/AI usa **8000**; la batería lo pausó estando inactivo y lo restauró al finalizar.

```bash
./recipes install --llama-cpp
./recipes download nemotron
./recipes serve nemotron
```

[Perfil](profiles/nemotron.json) · [Evidencia](evidence/nemotron.json) · [Clientes](clients/nemotron)

<a id="api"></a>
## API compatible con OpenAI

Todos los lanzadores escuchan en `127.0.0.1`, sin exigir clave ni exponer el servidor públicamente. IDs: `qwen3.6`, `gemma4`, `gpt-oss`, `flint`, `nemotron`.

```bash
curl --fail-with-body http://127.0.0.1:1919/v1/models
curl --fail-with-body http://127.0.0.1:1919/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"nemotron","messages":[{"role":"user","content":"Resume este proyecto."}],"max_tokens":8192,"stream":true}'
```

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:1919/v1", api_key="local-no-key")
r = client.chat.completions.create(
    model="nemotron", max_tokens=8192,
    messages=[{"role": "user", "content": "Resume el diff."}],
)
print(r.choices[0].message.content)
```

`local-no-key` es un placeholder público. El SDK OpenAI viene en el entorno FreeToken; si solo instalas llama.cpp, instálalo aparte (`uv run --with openai tu_script.py`). Ambos engines exponen `/v1/responses` y `/v1/messages`; llama.cpp lo documenta [en esta versión fijada](https://github.com/ggml-org/llama.cpp/blob/b11828/tools/server/README.md). Los adaptadores locales no garantizan todas las funciones de OpenAI/Anthropic. Responses en FreeToken es sin estado: reenvía historial y herramientas, sin depender de respuestas almacenadas, `previous_response_id` ni tareas de fondo. Conserva los campos de razonamiento cuando corresponda.

<a id="clients"></a>
## Clientes agénticos

Arranca una receta antes. Los ejemplos usan **Nemotron**; cambia ID, carpeta y contexto al cambiar de modelo. Todos tienen archivos en `clients/`. Son ejemplos de configuración y comprobaciones de endpoints, **no sesiones completas de programación validadas con cada cliente**.

| Cliente | Protocolo | Archivos |
|---|---|---|
| OpenCode v2.1.4 | Chat Completions | [JSON v2](clients/nemotron/opencode-v2.json) |
| OpenCode v1 | Chat Completions, esquema distinto | [JSON v1](clients/nemotron/opencode-v1.json) |
| Hermes Agent | Proveedor custom, Chat Completions | [YAML](clients/nemotron/hermes.yaml) |
| Codex CLI 0.164.0 | Responses | [Lanzador](clients/nemotron/codex.sh) · [TOML](clients/nemotron/codex.toml) |
| Claude Code 2.1.310 | Adaptador Anthropic Messages | [Lanzador](clients/nemotron/claude-code.sh) |

### OpenCode

Mezcla el JSON adecuado en `opencode.json` del proyecto de trabajo, conservando los ajustes existentes. v2 usa `providers/package/settings`; v1, `provider/npm/options`. Elige `recipes/nemotron` en `/models`, o:

```bash
opencode run --model recipes/nemotron "Resume la estructura del proyecto"
```

Los archivos declaran texto, herramientas, campo de razonamiento, presupuestos de contexto/entrada/salida y `max_tokens=8192`.

### Hermes

Instálalo con la [guía oficial](https://hermes-agent.nousresearch.com/docs/getting-started/installation). Elige Custom endpoint en `hermes model`, o:

```bash
hermes config set model.provider custom
hermes config set model.default nemotron
hermes config set model.base_url http://127.0.0.1:1919/v1
hermes config set model.api_mode chat_completions
hermes config set model.context_length 65536
hermes chat
```

No añadas la opción obsoleta `model.max_tokens`. El servidor usa 8192 por defecto. Contextos: Nemotron 65536; Qwen/Gemma/GPT 66560; Flint 73728.

### Codex

```bash
bash clients/nemotron/codex.sh
```

El wrapper cambia el proveedor para ese proceso y conserva el login/config global. Usa Responses, sin autenticación OpenAI ni WebSockets, y compacta antes de agotar la entrada. El TOML contiene las mismas opciones para integrarlas a mano.

### Claude Code

```bash
bash clients/nemotron/claude-code.sh
```

Usa la URL raíz **sin `/v1`**; el cliente añade `/v1/messages`. Todos los aliases apuntan al modelo local. Anthropic **no soporta oficialmente modelos no Claude**; el resultado depende de la compatibilidad del adaptador y del modelo. Estas dos versiones de engine no necesitan un proxy Chat Completions→Messages adicional. Se mantienen los controles de aprobación. [Detalles y fuentes oficiales](docs/clients.md).

<a id="desktop"></a>
## FreeToken Desktop

```bash
./recipes desktop gemma4
# Cierra Desktop antes de aplicar.
./recipes desktop gemma4 --apply
```

Primero muestra el cambio; `--apply` crea una copia y mezcla solo el perfil de caché y modo texto del modelo. No instala soporte Flint ni cambia opciones globales, engine o fichas de Downloads. **La receta medida de Nemotron usa llama.cpp y no tiene perfil para FreeToken Desktop.** [Globals y diferencias CLI/Desktop](docs/desktop.md).

<a id="evidence"></a>
## Logs y reproducción

- [Manifiesto](evidence/logs/manifest.json): fuentes recuperadas, SHA-256 y saneamiento. Se retiran rutas personales, rutas de trabajo, UUID GPU y colores; se excluyen conversaciones privadas, credenciales, voces y datos de red.
- [Qwen](evidence/logs/qwen3.6), [Gemma](evidence/logs/gemma4), [GPT-OSS](evidence/logs/gpt-oss): nuevos logs completos y capturas SSE por petición, además de salidas históricas disponibles. Se conserva el fallo de Gemma con prefill 8192.
- [Nemotron](evidence/logs/nemotron): JSON, scripts e informes originales. No se conservó el stdout histórico completo del servidor; no se puede reconstruir fielmente a partir de resúmenes.
- [Flint](evidence/logs/flint): logs del barrido, JSON y muestras GPU; [validaciones separadas](evidence/logs/flint-validation).
- [Método y límites](docs/measurements.md) · [Auditoría de recuperación](docs/log-recovery.md) · [Versiones](runtime.json) · [Dependencias clave](constraints.txt).

Los archivos temporales originales de Gemma/GPT se perdieron. Las capturas de terminal se etiquetan como recuperadas y pueden conservar truncamientos de origen; las mediciones nuevas son evidencias separadas y no se hacen pasar por originales históricos. `null` significa desconocido. No se suben los pesos.

Para reproducir, sirve un modelo con la geometría registrada y guarda stdout/stderr; después ejecuta el benchmark sintético con el entorno FreeToken:

```bash
./recipes serve gemma4 > /tmp/gemma4-server.log 2>&1
# En otra terminal, después de LISTO:
.venv/bin/python scripts/benchmark-freetoken.py gemma4 \
  --output /tmp/gemma4-nueva-medicion.json
```

Registra revisión del engine, hardware, hashes de pesos, tokens reales, caché, política EOS, calentamiento y todas las muestras. Las pruebas nuevas usan `ignore_eos` solo para fijar la longitud. Antes de afirmar rendimiento de contexto completo, mide entrada/salida reales cerca del límite. El instalador guarda `uv pip freeze` local, con las 103 versiones de paquetes fijadas en [constraints-validated.txt](constraints-validated.txt); el nuevo entorno aislado de FreeToken se instaló y se usó para estas pruebas, con ambas cachés binarias de FlashInfer fijadas.

### Reproducir la validación completa

Detén otros servidores para liberar VRAM y ejecuta:

```bash
.venv/bin/python scripts/validate-profiles.py --output /tmp/recipes-validation
python3 -m unittest discover -s tests -v
```

La batería arranca cada perfil, construye un prompt sintético exacto mediante el contador del servidor, genera 8192 tokens, repite el prefijo, realiza un ciclo natural de herramienta y comprueba Responses/Messages. Guarda peticiones, eventos SSE con tiempos, stdout/stderr y telemetría GPU. `--models qwen3.6` selecciona un modelo. En este equipo, `--pause-user-service nemotron-e4b.service` pausa y restaura el servicio existente cuando está inactivo. El [informe de validación](docs/validation.md) contiene los resultados, incluidos los fallos de comprobación que se hayan producido.

<a id="layout"></a>
## Estructura y licencias

```text
profiles/        modelo, engine, argumentos, contexto y política de salida
clients/         ejemplos de OpenCode, Hermes, Codex y Claude por modelo
evidence/        mediciones, inventario y logs saneados
scripts/         instalación, descarga, serving, Desktop y benchmarks
assets/          dos banners blueprint originales generados con ImageGen
docs/            método, recuperación, Desktop, clientes y arte
runtime.json     versiones, hashes de archivos y commit Flint
```

Cada receta nueva necesita perfil, fuente fijada, carga real/logs, ejemplos de clientes y fila en la tabla. Mantén separadas capacidad reservada, carga medida y salida pretendida. Los documentos de apoyo están principalmente en español; los tres README incluyen la guía de uso completa.

La [MIT](LICENSE) cubre las recetas/scripts propios; engines y modelos mantienen sus licencias. Nemotron usa **OpenMDW-1.1**; consulta las fichas de cada modelo. [Prompts y procedencia de los banners](docs/artwork.md): arte blueprint original creado con ImageGen, sin logos oficiales ni certificación de rendimiento.

Fuentes: [FreeToken](https://github.com/FlashML-org/FreeToken) · [llama.cpp b11828](https://github.com/ggml-org/llama.cpp/releases/tag/b11828) · [OpenCode](https://opencode.ai/v2/docs/providers) · [Hermes](https://hermes-agent.nousresearch.com/docs/integrations/providers) · [Configuración OpenAI](https://learn.chatgpt.com/docs/config-file/config-reference) · [Gateway Claude](https://code.claude.com/docs/en/llm-gateway-connect).
