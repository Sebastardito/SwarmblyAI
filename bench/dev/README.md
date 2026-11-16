# Open development battery · Batería abierta de desarrollo

**Language / Idioma:** [English](#english) · [Español](#español)

---

## English

Fictitious material (AcmeLabs, Ana Pérez, the island mockingbird *Mimus ficticius*) that anyone may read, discuss and use to tune Swarmbly. It is the instrument of version 3.2: every addition (F1, F2…) is measured here against the previous step before it is kept. The sealed banks stay the final measure, run once per version and never used for tuning.

| Folder / file | Content |
|---|---|
| `casos.json` | 33 cases: simple facts (S1), personal data (S2), compositions with length, tables and citations (S3), contradictions between documents (CX), follow-ups (FU), prompt injection inside a document (INJ), consent and approved search, also inside a composition (CO), privacy of public lookups and of Ollama cloud models (PR), glossary terms across languages (GL), memory (ME) and a question outside the sources (OUT) |
| `corpus/` | The user's documents: every case mounts all of them |
| `publico/` | The public snapshot served by the simulated registry (only when a search is approved) |
| `verificador.json` | 73 sentences with the paragraphs they cite and a gold label ("si": the paragraphs say everything the sentence states; "no": they do not, say a part, or say something else). 43 are answers of `qwen2.5:7b` in this battery, read by hand; 30 were written by hand over the same corpus. Measured with `bench/run_verifier.py` |
| `ejecuciones/` | Run folders (not versioned): every answer with its metadata, `resumen.md` and `resumen.json` |

Scoring is done by code and is coarse on purpose: key data found, forbidden content, length within the requested range, a table when asked, inline citations, sentences the app marks as unsupported, sends against the case's limits, claims of a lookup that did not happen, memory saved when asked.

```bash
# needs Ollama running with the model and nomic-embed-text; the script starts its own app instances
python3 bench/run_dev.py --model qwen2.5:7b --label f0
python3 bench/run_dev.py --model qwen2.5:7b --only S3-01,S3-02 --repeat 3
python3 bench/run_dev.py --model qwen2.5:7b --set some.flag=true --label f1 \
    --compare bench/dev/ejecuciones/<f0 run>
```

The model has no fixed seed: use `--repeat` before reading a small difference as a change.

The claim verifier (3.3) is measured apart, without starting the app: which unsupported sentences the code flags, which a model flags in one short job per sentence, and both together.

```bash
python3 bench/run_verifier.py --model qwen2.5:7b,qwen2.5:14b --label v1
```

---

## Español

Material ficticio (AcmeLabs, Ana Pérez, el cucuve isleño *Mimus ficticius*) que cualquiera puede leer, discutir y usar para ajustar Swarmbly. Es el instrumento de la versión 3.2: cada añadido (F1, F2…) se mide aquí contra el paso anterior antes de conservarlo. Los bancos sellados siguen siendo la medida final, se corren una vez por versión y nunca se usan para ajustar.

| Carpeta / archivo | Contenido |
|---|---|
| `casos.json` | 33 casos: datos simples (S1), datos personales (S2), composiciones con extensión, tablas y citas (S3), contradicciones entre documentos (CX), seguimientos (FU), inyección de instrucciones dentro de un documento (INJ), consentimiento y búsqueda aprobada, también dentro de una composición (CO), privacidad de las consultas públicas y de los modelos en la nube de Ollama (PR), términos del glosario entre idiomas (GL), memoria (ME) y una pregunta fuera de las fuentes (OUT) |
| `corpus/` | Los documentos del usuario: cada caso los monta todos |
| `publico/` | La instantánea pública que sirve el registro simulado (solo si se aprueba una búsqueda) |
| `verificador.json` | 73 frases con los párrafos que citan y una etiqueta de oro («si»: los párrafos dicen todo lo que la frase afirma; «no»: no lo dicen, dicen una parte o dicen otra cosa). 43 son respuestas de `qwen2.5:7b` en esta batería, leídas a mano; 30 se escribieron a mano sobre el mismo corpus. Se mide con `bench/run_verifier.py` |
| `ejecuciones/` | Carpetas de cada corrida (no se versionan): cada respuesta con sus metadatos, `resumen.md` y `resumen.json` |

La puntuación la hace el código y es gruesa a propósito: datos clave encontrados, contenido prohibido, extensión dentro del rango pedido, tabla cuando se pide, citas en línea, frases que la app marca sin respaldo, envíos frente a los límites del caso, afirmaciones de una consulta que no se hizo, memoria guardada cuando se pide.

```bash
# necesita Ollama con el modelo y nomic-embed-text; el script arranca sus propias instancias de la app
python3 bench/run_dev.py --model qwen2.5:7b --label f0
python3 bench/run_dev.py --model qwen2.5:7b --only S3-01,S3-02 --repeat 3
python3 bench/run_dev.py --model qwen2.5:7b --set algun.ajuste=true --label f1 \
    --compare bench/dev/ejecuciones/<corrida f0>
```

El modelo no tiene semilla fija: usa `--repeat` antes de leer una diferencia pequeña como un cambio.

El verificador de afirmaciones (3.3) se mide aparte, sin arrancar la app: qué frases sin respaldo marca el código, cuáles marca un modelo en una tarea corta por frase, y los dos juntos.

```bash
python3 bench/run_verifier.py --model qwen2.5:7b,qwen2.5:14b --label v1
```
