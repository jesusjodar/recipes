# FreeToken Desktop

Las recetas CLI y los perfiles Desktop son dos rutas de aplicación diferentes. El servidor CLI es la ruta reproducible principal: arranca el engine fijado en `runtime.json`, selecciona la RTX 3060 por su nombre/UUID y aplica sus argumentos. No toca tu aplicación instalada.

Para copiar **solo** la geometría guardada de un modelo a Desktop, ciérralo antes:

```bash
./recipes desktop gemma4          # muestra los campos previstos
./recipes desktop gemma4 --apply  # copia previa y escritura atómica
```

Admite `--config /ruta/desktop.json`. Mezcla únicamente ese modelo en `cacheProfiles` y `textOnlyModels`; conserva los demás perfiles y los ajustes globales. No modifica `lastActiveId`, puertos, GPU, concurrencia ni extraArgs. Los valores globales capturados están en [inventory.json](../evidence/inventory.json): `hybrid`, fetch 1, concurrencia 1, CPU auto, memoria 0,95. Deben coincidir si quieres aproximar el entorno original.

| Modelo | KV | Expertos | SWA | Mamba guardado |
|---|---:|---:|---:|---:|
| Qwen | 66560 | 3328 | 2048 | 4 |
| Gemma | 66560 | 448 | 1024 | 4, ignorado: no usa GDN |
| GPT-OSS | 66560 | 256 | 512 | 4, ignorado: no usa GDN |
| Flint | 73728 | 3456 | 5120 | 4, ignorado: no usa GDN |

**No confundir con las mediciones CLI:** Gemma/GPT se midieron con el pool SWA inicial por defecto del engine (13312), no después de reconstruir sus ventanas Desktop de 1024/512. Sus recetas CLI conservan esa condición. Qwen se captura de Desktop y no tiene una medición de generación conservada.

Flint depende del [PR #797](https://github.com/FlashML-org/FreeToken/pull/797), aún abierto al capturar este repositorio. Añadir un JSON a Desktop no instala su arquitectura ni su ficha de Downloads. Usa la receta CLI con `install --flint`; el parche local previo de Desktop no se distribuye aquí. El límite de salida de estas recetas (8192) se aplica en CLI/clientes; el JSON Desktop no configura ese límite.
