# Cómo interpretar las mediciones

## Series históricas de la primera publicación

Esta sección conserva el alcance original. Para las series nuevas y la configuración actual consulta «Actualización del 24 de octubre», más abajo.

### Procedencia

Los cuatro checkpoints principales están descargados en la biblioteca local de FreeToken. Los perfiles Desktop se capturaron el 24-10-2026. Las cifras de generación proceden de ejecuciones del 22-10-2026; al crear este repositorio no se repitieron ni se ejecutaron benchmarks nuevos.

| Evidencia | Qué conserva | Qué no demuestra |
|---|---|---|
| `qwen3.6.json` | Geometría Desktop capturada | Throughput, generación a contexto completo u óptimo global |
| `gemma4.json` / `gpt-oss.json` | Líneas reales del motor recuperadas de la sesión local; tokens y tiempo de petición | Entrada de 66k, salida de 8k o agentes completos |
| `flint.json` | Resultados estructurados del barrido y prueba larga | Velocidad del commit revisado actual o de otro hardware |
| `flint-profile-measured.json` | Argumentos y geometría del lanzador histórico validado | Una instalación limpia desde cero |
| `bandwidth.json` | Microbenchmarks CPU/PCIe/expertos | Prefill/decode de generación de Qwen |

Las configs HF de Qwen, Gemma y GPT coinciden con los pins remotos elegidos para **nuevas descargas**. No se conserva su revisión histórica de pesos ni se han calculado hashes de todos sus shards. Por eso no se les atribuye falsamente una revisión de pesos validada. Los archivos se reutilizan si ya están completos; `download` comprueba el índice y existencia de shards, no certifica su contenido. Flint conserva revisión y tamaño de archivo, pero el tamaño tampoco es una firma criptográfica.

## Gemma y GPT-OSS

Una petición por modelo, 4096 tokens de prompt y `max_tokens=200`, temperatura 0. Contexto reservado: 66560; híbrido, fetch 1, memoria 0,95, 448/256 plazas de expertos y una petición simultánea. El prefill es el campo `input throughput` del motor. El decode publicado promedia los tres intervalos sostenidos posteriores al primero: el primer intervalo incluye el prefill y no mide decode aislado.

Se registraron peticiones completas de 6,566 s y 4,900 s, respectivamente. No se divide la salida por esos tiempos para presentarlo como decode: incluyen otras fases. El prefill de GPT no debe reconstruirse como `4096 / tiempo_total`, porque ese intervalo también tiene generación y fases del cliente.

La CLI histórica dejó `swa_full_tokens_ratio=0.2`: pool inicial de 13312 tokens. El JSON Desktop guarda ventanas menores (1024/512). Las recetas CLI no reconstruyen esas ventanas después, para conservar esa condición del comando medido. No se atribuyen sus cifras al perfil Desktop exacto. El nuevo default de salida de 8192 no estuvo presente en aquellas peticiones, que pidieron 200 tokens.

## Flint

GPU RTX 3060 y CPU 5600X. Barrido de nueve perfiles completos, 23 muestras cortas, warmups excluidos. Hybrid fetch 1, bloque 4096 y D2D ofreció el equilibrio elegido; bloque 8192 dio mayor prefill corto pero decode más lento y variable. No se aisló cada parámetro ni se exploró todo el espacio.

El prefill efectivo es `(prompt_tokens - cached_tokens) / tiempo_hasta_primer_evento_de_texto`; incluye HTTP local, tokenización, scheduler y primer token. Decode es `(completion_tokens - 1) / tiempo_entre_primer_y_último_evento_de_texto`. No son tiempos puros de kernels ni métricas directamente comparables a los logs de Gemma/GPT.

La petición fría larga procesó 65536 + 8192 tokens, TTFT 42,456968 s, decode 49,966027 tok/s. La salida se forzó con `ignore_eos=true` para medir todo el presupuesto. Las recetas de uso no activan esa opción. Se conserva además un ciclo de herramienta con 65686/65737 tokens de prompt y reutilización de prefijo; no es un benchmark de programación.

El árbol del snapshot medido era `edfba5e13d4ff2fae6f50208d4d58c1433b20cf8`. El instalador ofrece el commit revisado `6ee048e3cca92da2a85cdc9ca6fd21cceed527ad`, que cambió routing y otros detalles. Las cifras históricas no se presentan como una repetición en ese commit. El reviewer verificó corrección sobre `711a86e` en su propia GPU, no un throughput equivalente en la RTX 3060.

## Reproducción futura

1. Registra hardware, driver, engine, dependencias y revisión exacta del checkpoint.
2. Usa un solo modelo, misma geometría, texto, sampling y estado de caché; anota procesos que consumen VRAM.
3. Distingue warmup, prefijo frío, prefijo caliente y reconstrucción de caché. Conserva contadores `usage` y EOS/`ignore_eos`.
4. Mide varias peticiones y publica muestras, no únicamente el pico. Si cambias el método, crea una serie nueva.
5. Para afirmar capacidad de contexto, ejecuta una entrada y salida reales cercanas al objetivo; reservar KV no basta.

`runtime.json` fija los wheels originales y sus hashes oficiales; `constraints.txt` fija dependencias clave y `install` guarda el freeze resultante en `.runtime/installed-packages.txt`. No hay lock completo transitivo, y no se validó una instalación limpia del nuevo bootstrap. Flint reutiliza extensiones del wheel mediante symlinks para su overlay Python. En caso de incompatibilidad ABI, construye una versión coherente del engine y publica mediciones nuevas: no las sustituyas por las antiguas.

En la RTX 3060, NVFP4 no implica instrucciones FP4 nativas de Blackwell. El backend puede usar rutas compatibles con activaciones de mayor precisión. No extrapoles las cifras de una RTX PRO 6000/5090 ni de una pareja de GPUs a esta receta.

## Actualización del 24 de octubre: logs completos y Nemotron

La descripción anterior recoge la primera publicación. Ahora Qwen, Gemma y GPT-OSS tienen **series nuevas de tres peticiones HTTP**, después de una petición de calentamiento. Se conserva stdout/stderr completo y cada evento SSE. El contenido sintético se trunca a 4096 tokens antes de aplicar la plantilla: el uso real es 4106 / 4109 / 4163 tokens respectivamente, con 200 de salida. El log del engine registra cero tokens cacheados en cada muestra medida. `ignore_eos=true` se usa solo en este benchmark, con temperatura 0.

Prefill efectivo = `usage.prompt_tokens / TTFT`, midiendo hasta el primer evento con `content` **o** `reasoning_content`. Decode HTTP = `(completion_tokens - 1) / (t_último - t_primero)` de esos eventos. Son tasas operativas con overhead de servidor y posibles efectos de agrupación/tokens especiales; no tiempos puros de kernels. Flint histórico usó primer evento de texto, por lo que sigue siendo una serie distinta. Los promedios y todas las muestras están en cada JSON.

- Qwen: rebuild correcto con 3328 expertos, 66560 páginas y cuatro slots GDN. Se omitió `num_swa_pages`, porque no tiene pool SWA y el API rechazó ese campo. Se preserva el rechazo inicial.
- Gemma: el primer intento con techo prefill 8192 terminó en CUDA OOM. Se bajó a 1024 sin cambiar contexto, expertos ni SWA. La nueva serie completa usa esa configuración; no es una repetición exacta del comando histórico. Se conserva el traceback.
- GPT-OSS: serie nueva con los argumentos publicados, sin reconstrucción adicional.
- Nemotron: llama.cpp b11828 CUDA 13.4, target UD-Q8_K_XL, DFlash oficial BF16, 65536 de capacidad, tres tareas de código con 277–411 tokens de entrada. El prefill es la media de `timings.prompt_per_second` para tokens **no cacheados**; cada petición recuperó 38 tokens. Decode es la media de `timings.predicted_per_second`. La tasa API es `completion_tokens / elapsed_s`, incluye prefill y no es decode puro. Ninguna de estas tareas llena 64K de historial. Los parches generados no fueron validados como correctos.

Los pesos de Nemotron, drafter BF16 y drafter alternativo Q8_0 se han hasheado completos y coinciden con los blobs Hub fijados. Los dos archivos de engine coinciden con los hashes oficiales del release. El instalador llama.cpp se ejecutó aquí reutilizando esos archivos y verificándolos; el nuevo lanzador se comprobó con peticiones cortas a Chat Completions, Responses y Messages. No se validaron sesiones completas de cada agente ni una descarga nueva desde cero. Nemotron no usa FreeToken en la receta medida.

La geometría reservada sigue sin demostrar throughput con todo el contexto activo. El default de salida 8192 sigue siendo una política de uso del catálogo; las nuevas peticiones FreeToken solo generan 200 tokens. El servicio Nemotron que estaba activo se restauró después de cada medición.

## Batería de contexto completo y corrección del intervalo de decode

La batería nueva de `scripts/validate-profiles.py` usa los perfiles publicados, un calentamiento de 1024 + 64 y una petición que ocupa el presupuesto de entrada más 8192 tokens de salida reales. Conserva peticiones exactas, SSE con timestamps, stdout/stderr y telemetría GPU. A continuación repite el prefijo con 256 de salida y realiza un ciclo natural de herramienta con un prompt largo, además de comprobar Responses y Messages. [Informe completo](validation.md).

La salida forzada puede incluir tokens especiales sin texto visible. Esto se observó especialmente en el final de GPT-OSS. Por tanto el **decode efectivo HTTP de la batería nueva** se recalcula como `(completion_tokens - 1) / (t_evento_usage_final - t_primer_contenido_o_razonamiento)`, incluyendo la cola de tokens no renderizados. Usar únicamente el último fragmento visible inflaría la tasa. Se conserva `decode_visible_span_tok_s` como dato de auditoría; la tabla principal utiliza el intervalo hasta el evento final de uso. Prefill efectivo descuenta los tokens realmente cacheados; un prefijo nuevo puede compartir unos pocos tokens de plantilla con el calentamiento.

Los campos de salida estructurada de herramienta no aparecen todos como contenido/razonamiento. No se infiere una tasa de decode de texto para esas respuestas. Su tiempo total, uso de tokens y resultado funcional sí se registran. `scripts/summarize-validation.py` recompone las métricas desde los eventos guardados y separa estas situaciones.

El instalador incorpora ahora las cachés binarias oficiales FlashInfer cubin y JIT, con SHA-256 fijado. La instalación aislada y las pruebas de inferencia se realizaron en el nuevo entorno del repositorio. `constraints-validated.txt` fija sus 103 versiones de paquetes Python; `runtime.json` conserva las URLs/hashes de los cuatro wheels de engine/cachés y el commit del overlay. La compilación limpia desde fuentes CUDA y los componentes del sistema operativo siguen fuera del alcance de ese archivo de restricciones Python.
