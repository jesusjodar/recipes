# Clientes locales

Ejemplos preparados para el engine y la API de este repositorio. La sintaxis se contrastó con documentación oficial el 24-10-2026 y, donde está instalado, con el `--help` local. **No se han ejecutado sesiones completas de los agentes al crear el repo.** Hermes no estaba instalado en este equipo.

Arranca `./recipes serve MODELO` y espera a `LISTO`. Los snippets usan puerto 1919; si eliges otro, cambia las URLs del cliente. El ID del modelo tiene que coincidir con `/v1/models`. Los cuatro perfiles usan exclusivamente texto y una generación simultánea.

## OpenCode

La versión instalada era **v2.1.4**. Su configuración es `providers`, `package` y `settings`; los ejemplos v1 se incluyen por separado para versiones antiguas.

Mezcla `clients/MODELO/opencode-v2.json` en el `opencode.json` del proyecto. Si no existe un archivo de configuración, copia el snippet allí. No reemplaces un archivo que ya tenga tus ajustes. Ejecuta OpenCode desde ese proyecto, selecciona `/models` → `recipes/MODELO` o usa `opencode run --model recipes/MODELO "mensaje"`.

Los snippets fijan `limit.context`, `limit.input` y `limit.output`; declaran herramientas y texto, y `compatibility.reasoningField="reasoning_content"`. Usan Chat Completions mediante `@opencode/ai/providers/openai-compatible`.

Fuentes: [proveedores v2](https://opencode.ai/v2/docs/providers), [modelos y capabilities](https://opencode.ai/v2/docs/models), [configuración de proyecto](https://opencode.ai/v2/docs/config), [proveedores v1](https://opencode.ai/docs/providers).

## Hermes

Usa `hermes model` → **Custom endpoint** y configura URL `/v1`, modelo y contexto. Para una configuración manual, mezcla `clients/MODELO/hermes.yaml` en `~/.hermes/config.yaml`; los comandos `hermes config set` del README hacen lo mismo por claves.

`model.context_length` representa entrada y salida juntas. El YAML no añade el obsoleto `model.max_tokens`; para estos endpoints Hermes usa el default del servidor cuando omite el límite. Nuestro default es 8192. Al cambiar de modelo, vuelve a fijar su contexto; no configures el máximo teórico del checkpoint si tu servidor reservó menos.

Si Hermes tiene un proveedor remoto previo, revisa sus auxiliares y fallbacks para que las tareas de compresión/títulos no sigan dirigiéndose allí. Eso depende de tu configuración, no del engine. El snippet no copia credenciales ni cambia permisos de herramientas.

Fuentes: [custom endpoints](https://hermes-agent.nousresearch.com/docs/integrations/providers#custom--self-hosted-llm-providers), [contexto y salida](https://hermes-agent.nousresearch.com/docs/integrations/providers#context-length-detection), [configuración](https://hermes-agent.nousresearch.com/docs/user-guide/configuration).

## Codex

Versión instalada: **codex-cli 0.164.0**. Ejecuta `bash clients/MODELO/codex.sh` desde tu proyecto. El script usa overrides `-c` y no modifica tu cuenta de ChatGPT ni `~/.codex/config.toml`. El TOML contiguo es una alternativa para mezclar manualmente.

El proveedor local usa `wire_api="responses"`, `requires_openai_auth=false` y `supports_websockets=false`. El contexto se fija a la reserva de la receta; la compactación comienza 2048 tokens antes del presupuesto de entrada con salida reservada. Es una política conservadora nueva, no una medición de calidad de compactación. No se inventa una opción `model_max_output_tokens`.

FreeToken implementa un subconjunto Responses **sin estado**. Los campos de almacenamiento, continuidad por `previous_response_id` y background no equivalen al servicio OpenAI. No se afirma paridad de todas las funciones de Codex con este endpoint.

Fuentes: [OpenAI Docs: configuración](https://learn.chatgpt.com/docs/config-file/config-reference), [adaptador Responses de FreeToken](https://github.com/FlashML-org/FreeToken/blob/507a8bfa81d5c305e047661576165a74068e5ab0/python/freetoken/server/responses_api.py).

## Claude Code

Versión instalada: **2.1.310**. Ejecuta `bash clients/MODELO/claude-code.sh`. El wrapper usa `ANTHROPIC_BASE_URL=http://127.0.0.1:1919`, sin `/v1`, porque el cliente añade `/v1/messages`. El valor `local-no-key` de `ANTHROPIC_AUTH_TOKEN` es un placeholder para el servidor local sin auth. Los aliases Opus/Sonnet/Haiku y el modelo de subagentes se dirigen al mismo ID local; no son modelos Claude.

El wrapper elimina solo del proceso hijo las credenciales Anthropic heredadas, fija salida 8192 y conserva los controles de aprobación. La ventana de contexto de modelos arbitrarios puede no detectarse como en Claude: vigila el tamaño de historial y usa `/compact` antes de alcanzar el presupuesto de entrada. No declares que un modelo local admite 200k/1M por el alias del cliente.

Anthropic **no da soporte oficial a Claude Code con modelos no Claude**. La receta usa el adaptador comunitario de FreeToken; herramientas, razonamiento y compactación pueden diferir. Su existencia no prueba una sesión agéntica completa.

Fuentes: [conectar a un gateway](https://code.claude.com/docs/en/llm-gateway-connect), [alcance oficial de gateways](https://code.claude.com/docs/en/llm-gateway), [adaptador Messages](https://github.com/FlashML-org/FreeToken/blob/507a8bfa81d5c305e047661576165a74068e5ab0/python/freetoken/server/anthropic_api.py).

## API y comprobación manual

Para comprobar tu instalación, sin involucrar un cliente agente:

```bash
curl --fail-with-body http://127.0.0.1:1919/v1/models
curl --fail-with-body http://127.0.0.1:1919/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gemma4","max_tokens":64,"messages":[{"role":"user","content":"Responde con un saludo breve."}]}'
```

Son comandos para que el usuario los ejecute, no resultados de pruebas nuevas. Para agentes, prueba también una herramienta real y su respuesta, repetición de historial y cancelación. La prueba de herramienta larga conservada en `evidence/flint.json` corresponde a Flint y al snapshot histórico; no certifica los demás modelos/clientes.
