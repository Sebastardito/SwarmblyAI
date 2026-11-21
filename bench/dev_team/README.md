# Team versus local battery · Batería equipo frente a local

**Language / Idioma:** [English](#english) · [Español](#español)

> **Pre-registration, written before any run.** This is an open battery with
> fictitious material; it is not a sealed bank. The maintainer runs it on his
> own machines with real models.

---

<a name="english"></a>

## English

### Question

Does the same stored team produce a complete answer with less wall time, and
with the intended roles placed on the workers, when it runs on 2–3 loopback
nodes instead of one node's local pool? Does the answer remain materially the
same?

### Hypotheses

1. **Completion:** both modes complete the steps; the distributed mode does not
   lose a step merely because it crossed a circle.
2. **Placement:** in distributed mode the role steps are actually placed on a
   member (the receipt names a `CIRCLE` destination), not silently kept local.
3. **Time:** with real models and more than one machine, distributed wall time
   is lower for the same team; on a single laptop the loopback members share
   the same CPU, so this is not expected and is reported as-is.
4. **Agreement:** local and distributed answers overlap substantially; the
   metric is word overlap, not correctness.

### Cases

Three neutral, fictitious prompts in `casos.json` (`TEAM-01` explanation,
`TEAM-02` comparison, `TEAM-03` procedure). They contain no personal data and
no real organisation.

### Metrics

| Metric | Definition |
|---|---|
| Wall time | seconds from sending the team request to the final answer |
| Step completion | `steps_completed / steps_total` from the App's metadata |
| Role placement | for each step, the role and node from `metadata.attempts`; local or member |
| Remote steps | steps whose attempt node is not the requester |
| Answer agreement | Jaccard over content words between the local and distributed answer of the same case |
| Receipts | observed sends, `CIRCLE` sends and passages to peers |

### What counts as success

- **Technical:** all rows have a real `estado`, a step list and a receipt; no
  technical failure. A mode that cannot start a member is a failed observation,
  not a silent pass.
- **Completion:** at least 2/3 cases complete all steps in each mode.
- **Placement:** at least one role step in distributed mode names a member; if
  the local model wins every step, that is recorded as a finding (the harness
  must not claim distribution it did not observe).
- **Agreement:** mean word overlap ≥ 0.35 between modes. This is a coarse
  guard against a different answer, not a correctness claim.
- **Privacy:** every `CIRCLE` send in the receipt names the circle and the
  member; the non-member is refused when the run includes one.

A result below a threshold is reported, not hidden. The run is repeated only
for a technical failure, never to select a favourable result.

### Run

```bash
# One node, then two loopback members; real Ollama models:
python3 bench/run_team.py --model qwen2.5:7b --local --distributed --members 2

# Real machines: create/accept the circle first, then give the peers:
python3 bench/run_team.py --model qwen2.5:7b --distributed \
  --invitation "<code>" --peer 192.0.2.10:9765 --peer 192.0.2.11:9765

# Deterministic smoke, no model (CI):
python3 bench/run_team.py --model fake:7b --fake-ollama --local --distributed
```

Results: `bench/dev_team/ejecuciones/<run>/resultados.csv` and `resumen.md`.

---

<a name="español"></a>

## Español

### Pregunta

¿El mismo equipo guardado produce una respuesta completa con menos tiempo de
pared, y con los roles previstos colocados en los nodos, cuando corre en 2–3
nodos de loopback en vez del pool local de un solo nodo? ¿La respuesta sigue
siendo materialmente la misma?

### Hipótesis

1. **Finalización:** ambos modos completan los pasos; el modo distribuido no
   pierde un paso solo por cruzar un círculo.
2. **Colocación:** en el modo distribuido los pasos con rol se colocan de
   verdad en un miembro (el recibo nombra un destino `CIRCLE`), no se quedan
   locales en silencio.
3. **Tiempo:** con modelos reales y más de una máquina, el tiempo de pared
   distribuido baja para el mismo equipo; en un solo portátil los miembros de
   loopback comparten CPU, así que no se espera y se informa tal cual.
4. **Acuerdo:** las respuestas local y distribuida se solapan bastante; la
   métrica es solapamiento de palabras, no corrección.

### Casos

Tres consignas neutras y ficticias en `casos.json` (`TEAM-01` explicación,
`TEAM-02` comparación, `TEAM-03` procedimiento). No contienen datos personales
ni organizaciones reales.

### Métricas

| Métrica | Definición |
|---|---|
| Tiempo de pared | segundos desde el envío del equipo hasta la respuesta final |
| Finalización de pasos | `steps_completed / steps_total` de los metadatos de la App |
| Colocación de rol | por paso, rol y nodo de `metadata.attempts`; local o miembro |
| Pasos remotos | pasos cuyo intento no está en el solicitante |
| Acuerdo de respuesta | Jaccard sobre palabras de contenido entre la respuesta local y la distribuida del mismo caso |
| Recibos | envíos observados, envíos `CIRCLE` y pasajes a pares |

### Qué cuenta como éxito

- **Técnico:** todas las filas tienen un `estado` real, lista de pasos y recibo;
  ningún fallo técnico. Un modo que no arranca un miembro es una observación
  fallida, no un aprobado silencioso.
- **Finalización:** al menos 2/3 casos completan todos los pasos en cada modo.
- **Colocación:** al menos un paso con rol en el modo distribuido nombra a un
  miembro; si el modelo local gana todos los pasos, se registra como hallazgo
  (el arnés no debe afirmar una distribución que no observó).
- **Acuerdo:** solapamiento medio de palabras ≥ 0,35 entre modos. Es una
  guarda gruesa contra una respuesta distinta, no una afirmación de corrección.
- **Privacidad:** cada envío `CIRCLE` del recibo nombra el círculo y el
  miembro; el no miembro se rechaza cuando la corrida incluye uno.

Un resultado por debajo del umbral se informa, no se oculta. La corrida se
repite solo por un fallo técnico, nunca para elegir un resultado favorable.

### Ejecutar

```bash
# Un nodo y luego dos miembros de loopback; modelos reales de Ollama:
python3 bench/run_team.py --model qwen2.5:7b --local --distributed --members 2

# Máquinas reales: crea/acepta el círculo y pasa los pares:
python3 bench/run_team.py --model qwen2.5:7b --distributed \
  --invitation "<código>" --peer 192.0.2.10:9765 --peer 192.0.2.11:9765

# Humo determinista, sin modelo (CI):
python3 bench/run_team.py --model fake:7b --fake-ollama --local --distributed
```

Resultados: `bench/dev_team/ejecuciones/<run>/resultados.csv` y `resumen.md`.
