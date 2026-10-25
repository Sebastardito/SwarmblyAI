#!/bin/bash
# Inicia el servidor Ollama con las variables de entorno del proyecto.
# La ventana por defecto (65536) puede ajustarse aquí o por-request con num_ctx.
export OLLAMA_MODELS="/Volumes/Workdrive/Models"
export OLLAMA_FLASH_ATTENTION="1"
export OLLAMA_KV_CACHE_TYPE="q8_0"
export OLLAMA_CONTEXT_LENGTH=65536
export OLLAMA_HOST="127.0.0.1:11434"
exec ollama serve
