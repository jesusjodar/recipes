# Auditoría de recuperación de logs — 24-10-2026

## Qué se recuperó

- **Nemotron:** once archivos originales del directorio de benchmarks: cuatro comparativas cortas, dos series de tareas de código con capacidad 64K, resumen JSON, dos informes y dos scripts. No incluyen conversaciones personales. Los archivos de inferencia y runtime fueron comprobados mediante SHA-256 completo contra los blobs HF y assets oficiales del release.
- **Flint:** 27 archivos de barridos, intento inicial del generador de prompts, prueba larga, CSV GPU y logs del driver. Once archivos adicionales documentan validaciones AIME, caché y routing del PR, separados del throughput.
- **Gemma/GPT:** trece salidas de terminal históricas recuperadas. Algunas pertenecen a exploraciones anteriores de Gemma, no al perfil final. Los timestamps distinguen las ejecuciones. No son los archivos temporales originales, y pueden contener truncamiento que ya existía en la captura.

## Qué se obtuvo de nuevo

- **Qwen:** log de rechazo del campo SWA no aplicable, log completo de arranque y rebuild correcto, una petición de calentamiento y tres mediciones con 4106 tokens de prompt y 200 de salida, con eventos SSE completos.
- **Gemma:** log íntegro del intento fallido con techo prefill 8192 (CUDA OOM), su warmup capturado y una serie completa nueva con techo 1024: una petición de calentamiento y tres de 4109 + 200.
- **GPT-OSS:** arranque/shutdown completos, calentamiento y tres peticiones de 4163 + 200.
- **Nemotron:** log completo del nuevo lanzador portable, carga de modelo/drafter y respuestas cortas HTTP 200 de Chat Completions, Responses y Messages. No constituye una nueva medición de velocidad ni de 64K activos. Se usa el mismo checkpoint y engine verificados de los benchmarks conservados.

El script `scripts/benchmark-freetoken.py` permite repetir el protocolo sintético de las nuevas series. La captura de ejecución ad hoc se conserva saneada como `evidence/logs/benchmark-runner.snapshot.py`; controla temporalmente el servicio local durante las mediciones, mientras que el script portable deja esa gestión al usuario. Los prefijos incluyen timestamps para evitar reutilizar el prefijo completo. Los logs del engine confirman cero tokens cacheados en las tres muestras de cada FreeToken. La salida de uso normal no fuerza EOS; el benchmark sí fija 200 tokens con `ignore_eos`.

## Archivos que no existen

No se han recuperado los archivos temporales completos originales de Gemma/GPT ni stdout completo de los benchmarks históricos de Nemotron. No se inventaron ni se reconstruyeron como si fueran originales. Los JSON originales de Nemotron sí conservan timings, tokens y resultados; sus informes complementan esos datos. Los nuevos logs de FreeToken son una serie fechada aparte.

Tampoco hay mediciones completas del contexto activo máximo para Qwen/Gemma/GPT/Nemotron, ni sesiones de programación completas verificadas con todos los clientes. Ese dato no se deduce de la reserva KV. La salida de 8192 sigue siendo una política nueva de estos perfiles salvo Flint.

## Integridad y privacidad

`evidence/logs/manifest.json` enumera todos los archivos de evidencia y SHA-256 del contenido publicado. Cuando se conserva, registra también el hash del archivo fuente anterior al saneamiento. Se sustituyen rutas HOME/workspace y UUID GPU, y se retiran secuencias de color. No se copian chats completos, claves, detalles de Tailscale ni embeddings de voz. Los registros conservan métricas, comandos técnicos y mensajes de error necesarios para interpretar los resultados.

El servicio Nemotron que estaba activo antes de las mediciones quedó restaurado. La nueva receta no modifica su unidad de servicio ni la red privada. Las configuraciones de clientes apuntan al servidor portable en localhost:1919, no al endpoint privado del equipo.
