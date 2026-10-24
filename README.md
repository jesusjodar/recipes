![recipes — local AI measured configurations](assets/recipes-blueprint.png)

# recipes

Mis configuraciones de inferencia local para **AMD Ryzen 5 5600X + NVIDIA RTX 3060 12 GiB + 32 GiB RAM**. Perfiles orientados al rendimiento, contexto utilizable y trabajo con agentes, con comandos reproducibles y evidencias de las mediciones que se conservan.

**FreeToken · CPU/GPU hybrid offload · solo texto · una generación simultánea.** Repositorio privado durante su preparación. Inventario capturado el **24 de octubre de 2026**; mediciones de generación del **22 de octubre de 2026**.

## Índice

- [Modelos y rendimiento](#modelos-y-rendimiento)
- [Equipo y alcance](#equipo-y-alcance)
- [Inicio rápido](#inicio-rápido)
- [Recetas por modelo](#recetas-por-modelo)
  - [Qwen 3.6](#qwen-36-35b-a3b)
  - [Gemma 4](#gemma-4-26b-a4b)
  - [GPT-OSS 20B](#gpt-oss-20b)
  - [Flint](#flint-398b-a25b)
- [API compatible con OpenAI](#api-compatible-con-openai)
- [OpenCode, Hermes, Codex y Claude Code](#clientes-agénticos)
- [Aplicar a FreeToken Desktop](#aplicar-a-freetoken-desktop)
- [Mediciones y reproducción](#mediciones-y-reproducción)
- [Estructura y nuevas recetas](#estructura-y-nuevas-recetas)
- [Fuentes y licencias](#fuentes-y-licencias)

## Modelos y rendimiento

Contexto = **entrada + historial + plantilla + razonamiento + salida**. Todas las cifras son tokens, y las velocidades son tokens/s. Ninguna receta usa drafter ni decodificación especulativa.

| Modelo | Contexto total configurado | Entrada con salida reservada¹ | Salida por respuesta¹ | Drafter | Prefill | Decode | Carga realmente medida | Cuantización | Original / pesos / configuración |
|---|---:|---:|---:|:---:|---:|---:|---|---|---|
| Qwen 3.6 35B A3B | 66.560 | 58.368 | 8.192 | No | N/D | N/D | Perfil Desktop; sin log de generación recuperado | NVFP4 ModelOpt, mixto | [Original](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) · [Pesos](https://huggingface.co/nvidia/Qwen3.6-35B-A3B-NVFP4) · [Config](profiles/qwen3.6.json) |
| Gemma 4 26B A4B | 66.560 | 58.368 | 8.192 | No | 328,21² | ≈41,24² | 4.096 entrada + 200 salida | NVFP4 ModelOpt, mixto | [Original](https://huggingface.co/google/gemma-4-26B-A4B-it) · [Pesos](https://huggingface.co/nvidia/Gemma-4-26B-A4B-NVFP4) · [Config](profiles/gemma4.json) |
| GPT-OSS 20B | 66.560 | 58.368 | 8.192 | No | 307,26² | ≈65,15² | 4.096 entrada + 200 salida | MXFP4 | [Original y pesos](https://huggingface.co/openai/gpt-oss-20b) · [Config](profiles/gpt-oss.json) |
| Flint 39,8B A2,5B | 73.728 | 65.536 | 8.192 | No | 1.543,59³ | 49,97³ | **65.536 entrada + 8.192 salida** | NVFP4 GGUF oficial | [Original](https://huggingface.co/RecursiveSI/flint) · [Pesos](https://huggingface.co/RecursiveSI/flint-nvfp4-gguf) · [Config](profiles/flint.json) |

¹ Las recetas fijan un **valor predeterminado** de salida de 8.192 para clientes agentes; no es el máximo teórico del modelo ni un límite duro del servidor frente a peticiones explícitas. En Qwen/Gemma/GPT es una elección nueva del catálogo: antes no había override y el adaptador usaba 32.768 por defecto. Solo Flint tiene una generación conservada de 8.192 tokens. El razonamiento también consume este presupuesto. El presupuesto de entrada incluye sistema, herramientas y plantilla; no equivale al tamaño de un archivo de usuario.

² Logs del motor, una petición por modelo. Decode es la media de los tres intervalos sostenidos después del primero, que incluía prefill. La reserva de 66.560 se asignó, pero **no se midió una entrada de esa longitud**. No son cifras comparables directamente con las de Flint. [Gemma](evidence/gemma4.json) · [GPT-OSS](evidence/gpt-oss.json).

³ Streaming HTTP local, prefijo frío, una petición larga; TTFT **42,46 s**, total **206,39 s**. En 8.192 + 256, el mismo perfil dio una media de **2.783,31 / 66,53 tok/s**, tres muestras. [Evidencia y barrido](evidence/flint.json).

**“Optimizado” significa la configuración seleccionada entre las probadas en este equipo.** No se demuestra un óptimo global. Qwen queda como perfil capturado, con rendimiento pendiente. No se han vuelto a ejecutar inferencias ni benchmarks al montar este repositorio, ni se ha validado de extremo a extremo el nuevo instalador o cada cliente.

## Equipo y alcance

| Componente | Configuración |
|---|---|
| CPU | AMD Ryzen 5 5600X, 6 núcleos / 12 hilos, AVX2 |
| GPU de las recetas | NVIDIA GeForce RTX 3060, 12 GiB, SM 8.6 |
| RAM | 32 GiB nominales; unos 31 GiB disponibles al sistema |
| Engine medido | FreeToken `0.2.0+gfe5a5ec9c`; Flint usó un snapshot de desarrollo del PR #797 |
| NVIDIA / Python / PyTorch | 615.78.08 / 3.12.14 / 2.14.1+cu130 |
| Estrategia | `hybrid`, fetch máximo 1; expertos en RAM y caché en GPU |
| CPU MoE | `0` = automático; Flint observó 5 hilos |
| Concurrencia | 1 generación; sin drafter |

La RTX 2070 de 8 GiB también está instalada, pero **no forma parte de estas recetas principales**. Las pruebas mixtas requirieron parches experimentales y sufrieron limitación térmica; no se publica un perfil dual de 128k como validado. [Alcance del hardware](evidence/hardware.json).

## Inicio rápido

![From weights to workflow](assets/workflow-blueprint.png)

Requisitos: Linux x86_64, `python3`, `git`, [`uv`](https://docs.astral.sh/uv/getting-started/installation/), driver NVIDIA compatible con CUDA 13 y espacio para los pesos, el entorno y expertos en RAM. La ruta usa wheels CPython 3.12; puede requerir toolkit CUDA 13 para kernels no cubiertos por la caché.

```bash
gh repo clone jesusjodar/recipes
cd recipes
./recipes list

# Instala engine y kernels fijados en .venv/, sin cambiar FreeToken Desktop.
./recipes install

# Reutiliza la descarga completa de ~/.freetoken/models si existe.
./recipes download gemma4
./recipes serve gemma4
```

Espera a **`LISTO`**. `serve` detecta la RTX 3060 y la aísla mediante UUID; cuando el perfil lo requiere, espera al servidor y aplica `/v1/cache/rebuild` antes de anunciarlo listo. Ctrl+C detiene el proceso que inició. Cierra el servidor de Desktop si ocupa el puerto o la VRAM. Los puertos API y rendezvous (puerto + 1) deben estar libres.

```bash
./recipes serve gemma4 --port 22420
./recipes serve gemma4 --gpu GPU-UUID-DE-TU-TARJETA
./recipes show gemma4
```

En este equipo las rutas de los cuatro modelos ya existen. Para otra biblioteca, define `RECIPES_MODEL_DIR=/ruta/modelos`. La descarga incompleta se completa con Hugging Face Hub; los commits para **nuevas descargas** están fijados en cada perfil. Para Qwen/Gemma/GPT se conoce la coincidencia del `config.json`, pero **no se ha certificado la revisión de sus pesos históricos**. Flint sí conserva su revisión. [Inventario](evidence/inventory.json).

## Recetas por modelo

### Qwen 3.6 35B A3B

Perfil persistente de Desktop: KV **66.560**, **3.328** plazas MoE, SWA **2.048**, **4** slots de estado GDN/Mamba. Usa la CPU y la RTX 3060, en texto. No hay drafter descargado/configurado para esta receta y no se ha recuperado una medición de generación de Qwen.

```bash
./recipes install
./recipes download qwen3.6
./recipes serve qwen3.6
```

El lanzador arranca con una caché de expertos menor y reconstruye la geometría capturada. Este nuevo flujo de arranque queda pendiente de validación en hardware. Conserva muestreo del checkpoint: temperatura 1, top-p 0,95 y top-k 20. La salida explícita de 8.192 es la política del catálogo.

[Configuración](profiles/qwen3.6.json) · [Evidencia y pendientes](evidence/qwen3.6.json) · [Clientes](clients/qwen3.6) · [Modelo original](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) · [Checkpoint](https://huggingface.co/nvidia/Qwen3.6-35B-A3B-NVFP4).

### Gemma 4 26B A4B

**Sin visión ni audio.** La caché original de 1.425 expertos no cabía con 66.560 tokens; se seleccionaron **448**. El comando medido usó el pool SWA inicial del engine (**13.312**), mientras Desktop guarda **1.024**; ambos quedan identificados, y la receta CLI conserva el primero. La memoria disponible era ajustada.

```bash
./recipes install
./recipes download gemma4
./recipes serve gemma4
```

Medición: **328,21 tok/s de prefill**, intervalos de decode **41,31 / 40,95 / 41,46 tok/s**, 4.096 + 200 tokens. La petición completa tardó **6,566 s**; ese tiempo no equivale al inverso del throughput periódico. Se compararon variantes de offload/hybrid; el contexto largo exigió reducir expertos. No se midió 58k + 8k ni se demuestra capacidad agéntica a ese límite. Muestreo del checkpoint: temperatura 1, top-p 0,95, top-k 64; el throughput histórico usó temperatura 0.

[Configuración](profiles/gemma4.json) · [Logs recuperados](evidence/gemma4.json) · [Clientes](clients/gemma4) · [Original](https://huggingface.co/google/gemma-4-26B-A4B-it) · [Checkpoint](https://huggingface.co/nvidia/Gemma-4-26B-A4B-NVFP4).

### GPT-OSS 20B

Pesos **MXFP4**, texto, KV **66.560** y **256** plazas de expertos. Las 535 plazas del perfil previo de 16k no dejaban sitio para el contexto mayor. El pool SWA del comando medido era **13.312**; Desktop guarda **512**.

```bash
./recipes install
./recipes download gpt-oss
./recipes serve gpt-oss
```

Medición: **307,26 tok/s de prefill**, decode sostenido **66,00 / 64,87 / 64,59 tok/s**, 4.096 + 200 tokens; petición completa **4,900 s**. No es una medición de 66k de entrada ni de 8k de salida. El engine usa el protocolo Harmony y los defaults del checkpoint; el catálogo no inventa temperatura ni top-p ausentes. La medición histórica usó temperatura 0.

[Configuración](profiles/gpt-oss.json) · [Logs recuperados](evidence/gpt-oss.json) · [Clientes](clients/gpt-oss) · [Modelo y pesos oficiales](https://huggingface.co/openai/gpt-oss-20b).

### Flint 39,8B A2,5B

Perfil de **65.536 entrada + 8.192 salida**. GGUF NVFP4 oficial, revisión `6ec43e19b565fc8d560e2d04985d7724f20673bf`. Caché final **3.456** expertos, SWA **5.120**, prefill **4.096**, memoria **0,90**, normalización CUDA y hits D2D en prefill. Arranca con 1.024 expertos y reconstruye las cachés.

```bash
# Además de los wheels, prepara el código Python de Flint en .runtime/.
./recipes install --flint
./recipes download flint
./recipes serve flint
```

El soporte está en el [PR FreeToken #797](https://github.com/FlashML-org/FreeToken/pull/797), abierto al capturar esta receta. El instalador fija el commit revisado `6ee048e`, con extensiones de los wheels. **Las cifras de velocidad pertenecen al snapshot anterior `edfba5e…`**, no a una repetición en ese commit; el nuevo instalador no se ha ejecutado aquí. [Pins y alcance](runtime.json).

| Petición | Prefill efectivo | Decode | TTFT |
|---|---:|---:|---:|
| 8.192 + 256, frío, media de 3 | 2.783,31 | 66,53 | ≈2,94 s |
| 65.536 + 8.192, frío, 1 muestra | 1.543,59 | 49,97 | 42,46 s |
| 65.536 + 256, mismo prefijo | 65.535 tokens recuperados | 50,38 | 0,88 s |

Se completaron 8.192 tokens forzando `ignore_eos` **solo en el benchmark**. La receta de uso conserva EOS normal. Una prueba aparte con más de 64k pidió una herramienta y reutilizó su resultado en la siguiente respuesta. Eso verifica ese ciclo, no la calidad general de programación. Muestreo: temperatura 1, top-p 0,95, top-k 20. Máximo observado: 10,61 GiB de VRAM incluyendo escritorio; expertos en host, unos 19,8 GiB.

[Configuración portable](profiles/flint.json) · [Resultados completos](evidence/flint.json) · [Perfil histórico](evidence/flint-profile-measured.json) · [Clientes](clients/flint) · [Original](https://huggingface.co/RecursiveSI/flint) · [GGUF oficial](https://huggingface.co/RecursiveSI/flint-nvfp4-gguf).

### Otros artefactos locales de investigación

También está descargada la exportación [FutureMLS-Lab/flint-nvfp4-coldgptq](https://huggingface.co/FutureMLS-Lab/flint-nvfp4-coldgptq), revisión `56f37fcf…`, en el área de investigación. Sus safetensors locales se redistribuyeron por capa; no son un índice de descarga original del Hub. Se usó para validar Flint (paridad, AIME y reconstrucción de caché), **sin un perfil optimizado de contexto largo ni throughput comparable conservado**. Para uso optimizado se seleccionó el GGUF oficial de la receta anterior. La copia/enlace adicional de ese GGUF en investigación no cuenta como otro modelo.

| Variante adicional | Contexto en pruebas de serving | Objetivo de salida optimizado | Prefill / decode | Configuración |
|---|---:|---|---|---|
| Flint ModelOpt NVFP4 | 8.192 | No fijado como receta optimizada | N/D | [Procedencia y alcance](evidence/inventory.json) · [Validación del PR](https://github.com/FlashML-org/FreeToken/pull/797) |

## API compatible con OpenAI

El servidor es local, `127.0.0.1`, sin clave ni exposición pública. Cada receta sirve **un modelo cada vez** bajo su ID (`qwen3.6`, `gemma4`, `gpt-oss` o `flint`).

```bash
curl --fail-with-body http://127.0.0.1:1919/v1/models

curl --fail-with-body http://127.0.0.1:1919/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gemma4","messages":[{"role":"user","content":"Explica este proyecto en tres frases."}],"max_tokens":8192,"stream":true}'
```

En Python, con el SDK incluido en el entorno:

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:1919/v1", api_key="local-no-key")
result = client.chat.completions.create(
    model="gemma4", max_tokens=8192,
    messages=[{"role": "user", "content": "Resume los cambios del diff."}],
)
print(result.choices[0].message.content)
```

`local-no-key` es un placeholder público para SDKs, no una credencial. El engine también expone `/v1/responses` para Codex y `/v1/messages` para Claude Code. Responses es un **subconjunto sin estado**: no depende de `previous_response_id`, almacenamiento o tareas en background. Los clientes deben reenviar historial y herramientas; conserva `reasoning_content` cuando corresponda. [API y clientes](docs/clients.md).

## Clientes agénticos

Arranca primero la receta y espera a `LISTO`. Los ejemplos siguientes usan **Gemma**; cambia `gemma4` por el ID y la carpeta del modelo que sirves. Son configuraciones basadas en documentación y código, **sin validar sesiones reales completas de esos cinco clientes durante esta publicación**.

| Cliente | Conexión | Configuración |
|---|---|---|
| OpenCode v2.1.4 | Chat Completions `/v1` | [JSON v2](clients/gemma4/opencode-v2.json) |
| OpenCode v1 | Chat Completions `/v1` | [JSON v1](clients/gemma4/opencode-v1.json), esquema distinto |
| Hermes Agent | Proveedor `custom`, `/v1` | [YAML](clients/gemma4/hermes.yaml) |
| Codex CLI 0.164.0 | Responses `/v1` | [Lanzador](clients/gemma4/codex.sh) · [TOML](clients/gemma4/codex.toml) |
| Claude Code 2.1.310 | Adaptador Anthropic, URL **sin** `/v1` | [Lanzador](clients/gemma4/claude-code.sh) |

### OpenCode

Mezcla el JSON **v2** en `opencode.json` del proyecto donde trabajarás; conserva tus otras opciones. Si no existe, puedes copiarlo. Arranca OpenCode en ese proyecto, elige `recipes/gemma4` en `/models`, o usa:

```bash
opencode run --model recipes/gemma4 "Resume la estructura del proyecto"
```

La configuración declara texto, herramientas, límites y `reasoning_content`. OpenCode v1 usa `provider/npm/options`; v2 usa `providers/package/settings`. No intercambies ambos archivos. [Guía detallada](docs/clients.md#opencode).

### Hermes

Instala Hermes por su [guía oficial](https://hermes-agent.nousresearch.com/docs/getting-started/installation). Configura mediante `hermes model` → Custom endpoint, o aplica estas opciones con su CLI:

```bash
hermes config set model.provider custom
hermes config set model.default gemma4
hermes config set model.base_url http://127.0.0.1:1919/v1
hermes config set model.api_mode chat_completions
hermes config set model.context_length 66560
hermes chat
```

No añadas `model.max_tokens`, que la versión actual ya no utiliza. El default del servidor es 8.192. Para cambiar de modelo, vuelve a fijar su contexto; para Flint es 73.728. [Configuración y limitaciones](docs/clients.md#hermes).

### Codex

```bash
bash clients/gemma4/codex.sh
```

El wrapper pasa un proveedor local por argumentos sin sobrescribir tu login/config global. Usa `wire_api="responses"`, sin autenticación OpenAI y sin WebSockets; el TOML contiene los mismos valores para quien prefiera integrarlos. La compactación comienza antes de agotar el presupuesto de entrada. [OpenAI Docs y alcance](docs/clients.md#codex).

### Claude Code

```bash
bash clients/gemma4/claude-code.sh
```

Se conecta al adaptador Messages de FreeToken, y sus aliases apuntan al mismo modelo local. **No es una integración oficialmente soportada por Anthropic para modelos no Claude**; dependerá de la compatibilidad del adaptador y del modelo. No hace falta un proxy Chat-Completions→Messages adicional en esta ruta. El wrapper no desactiva aprobaciones. [Detalles](docs/clients.md#claude-code).

## Aplicar a FreeToken Desktop

```bash
./recipes desktop gemma4
# Cierra Desktop antes de escribir su archivo.
./recipes desktop gemma4 --apply
```

Hace una copia previa y mezcla solo el perfil y modo texto del modelo. No instala soporte Flint ni modifica engine, preferencias globales o ficha de Downloads. Los globals capturados y las diferencias SWA CLI/Desktop están en [docs/desktop.md](docs/desktop.md).

## Mediciones y reproducción

- [Método, revisiones y diferencias entre métricas](docs/measurements.md).
- [Evidencias por modelo](evidence), con muestras, tokens y campos `null` para datos desconocidos.
- [Wheels y commit Flint fijados](runtime.json), con SHA-256 de los assets oficiales.
- [Dependencias clave](constraints.txt); el instalador guarda `uv pip freeze` localmente. No se afirma un lock transitivo completo ni una compilación CUDA limpia.
- [Guía de clientes y fuentes oficiales](docs/clients.md).

Los pesos no se suben al repositorio. Los JSON históricos de Flint se han saneado para retirar rutas privadas y UUID de hardware. La evidencia Gemma/GPT contiene exclusivamente las líneas de medición recuperadas, no el historial del chat.

## Estructura y nuevas recetas

```text
profiles/        argumentos, geometría, modelo, contexto, salida y estado
clients/         ejemplos por modelo y cliente
evidence/        mediciones e inventario saneados
scripts/         instalación, descarga y aplicación de perfiles
assets/          dos banners originales generados con ImageGen
docs/            método, Desktop, clientes y procedencia visual
runtime.json     wheels, hashes y commit del soporte Flint
```

Para añadir otro modelo: crea su JSON en `profiles/`, registra checkpoint/revisión, guarda la carga y método de medición en `evidence/`, añade ejemplos de clientes y actualiza esta tabla. Separa siempre **capacidad reservada**, **carga probada** y **objetivo de salida**. No rellenes velocidades de otra GPU ni extrapoles un prompt de 4k a 64k.

## Fuentes y licencias

[FreeToken](https://github.com/FlashML-org/FreeToken) · [Instalación](https://github.com/FlashML-org/FreeToken/blob/main/docs/install.md) · [Flint #797](https://github.com/FlashML-org/FreeToken/pull/797) · [OpenCode v2](https://opencode.ai/v2/docs/providers) · [Hermes](https://hermes-agent.nousresearch.com/docs/integrations/providers) · [OpenAI Docs](https://learn.chatgpt.com/docs/config-file/config-reference) · [Claude Code](https://code.claude.com/docs/en/llm-gateway-connect).

Las recetas y scripts propios se ofrecen con [licencia MIT](LICENSE); los engines y modelos mantienen sus propias licencias. Los banners se crearon con la herramienta integrada ImageGen en estilo blueprint; [prompts y procedencia](docs/artwork.md). No son logotipos oficiales ni diagramas que certifiquen rendimiento.
