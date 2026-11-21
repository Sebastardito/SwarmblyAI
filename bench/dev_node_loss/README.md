# Node-loss battery · Batería de pérdida de nodo

**Language / Idioma:** [English](#english) · [Español](#español)

> **Pre-registration.** This file and `TEAM_STEPS` in `run_node_loss.py` are
> written before any run. The battery is open and fictitious; it is not a
> sealed bank.

---

<a name="english"></a>

## English

### What it measures

A three-step team runs on one loopback circle member:

1. a large-model step (`FIRSTSTEP`) that completes;
2. a **search** step that has no truthful local substitute;
3. a dependent large-model step.

The member's fake search endpoint holds the second step open; the harness stops
the member process while that request is in flight. The expected result is an
honest **partial** answer (or `failed` if nothing completed):

- the completed step stays in the answer;
- the missing step is named with reason `node_lost`;
- the dependent step is `blocked` by the missing step;
- the requester's receipt lists only what was really sent (the first fragment
  and the public query; never the dependent step).

A real-model run uses `--kill-after` seconds instead of the fake search
endpoint; the maintainer runs it on his machines. The harness never opens a
sealed bank and the cases are obviously fictitious.

### Run

```bash
# Deterministic, no model, CI smoke:
python3 bench/run_node_loss.py --model fake:7b --fake-ollama

# Real models on this machine:
python3 bench/run_node_loss.py --model qwen2.5:7b --kill-after 8
```

The result is written to `bench/dev_node_loss/ejecuciones/<run>/resultado.json`
and `resumen.md`. The six checks must all be true for a pass.

### Success criteria

| Check | What it means |
|---|---|
| `estado_parcial_o_fallido` | the answer is not silently complete |
| `paso_completado_presente` | completed work is kept |
| `paso_perdido_nombrado` | the lost step says `node_lost` |
| `dependiente_bloqueado` | the dependent step names the lost step |
| `recibo_solo_lo_enviado` | no receipt row for a step that was never sent |
| `motivo_node_lost` | the reason is the stable node-loss category |

---

<a name="español"></a>

## Español

### Qué mide

Un equipo de tres pasos corre en un miembro de círculo en loopback:

1. un paso de modelo grande (`FIRSTSTEP`) que se completa;
2. un paso de **búsqueda**, sin sustituto local honesto;
3. un paso de modelo grande que depende del anterior.

El buscador simulado del miembro mantiene abierto el segundo paso; el arnés
detiene el proceso del miembro mientras esa petición está en vuelo. El
resultado esperado es una respuesta **parcial** honesta (o `failed` si no se
completó nada):

- el paso completado permanece en la respuesta;
- el paso perdido se nombra con motivo `node_lost`;
- el paso dependiente queda `blocked` por el perdido;
- el recibo del solicitante solo lista lo que de verdad se envió (el primer
  fragmento y la consulta pública; nunca el paso dependiente).

La corrida con modelos reales usa `--kill-after` segundos en vez del buscador
simulado; la hace el mantenedor en sus máquinas. El arnés nunca abre un banco
sellado y los casos son obviamente ficticios.

### Ejecutar

```bash
# Determinista, sin modelo, humo de CI:
python3 bench/run_node_loss.py --model fake:7b --fake-ollama

# Modelos reales en esta máquina:
python3 bench/run_node_loss.py --model qwen2.5:7b --kill-after 8
```

El resultado queda en `bench/dev_node_loss/ejecuciones/<run>/resultado.json` y
`resumen.md`. Las seis comprobaciones deben ser verdaderas para aprobar.

### Criterios de éxito

| Comprobación | Qué significa |
|---|---|
| `estado_parcial_o_fallido` | la respuesta no se declara completa en silencio |
| `paso_completado_presente` | el trabajo completado se conserva |
| `paso_perdido_nombrado` | el paso perdido dice `node_lost` |
| `dependiente_bloqueado` | el paso dependiente nombra al perdido |
| `recibo_solo_lo_enviado` | no hay fila de recibo para un paso nunca enviado |
| `motivo_node_lost` | el motivo es la categoría estable de pérdida de nodo |
