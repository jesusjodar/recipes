# Cómo interpretar las mediciones

## Procedencia

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
