# Contributing to Swarmbly App

Thank you for helping. *[Español](#español) below.*

## Set up

```bash
git clone https://github.com/Sebastardito/SwarmblyApp.git
cd SwarmblyApp
./launch.sh --setup-only --dev        # .venv + packages + pytest
.venv/bin/python -m pytest -W error::RuntimeWarning
```

The suite runs in about 15 seconds, without models: real nodes talk over
loopback (mDNS, TLS, handshake, scheduling) with canned backends. To look at
the interface with a fake swarm: `.venv/bin/python scripts/ui_preview.py`.

## Ground rules

These keep the app honest; pull requests are reviewed against them.

1. **Never present the simulated as real.** Canned answers, placeholders and
   estimates are labelled as such in the interface, the reports and the docs.
   A stage that did not run is *skipped*, not *completed*.
2. **Every number carries its nature**: *measured*, *estimated* or
   *unknown*.
3. **Reuse, don't copy.** Protocol logic lives in
   [SwarmblyAI](https://github.com/Sebastardito/SwarmblyAI) and
   [SwarmblyLCE](https://github.com/Sebastardito/SwarmblyLCE), installed as
   pinned packages. If the app needs a protocol change, propose it upstream
   (a SWIP), as in `docs/SWIP-DRAFT-model-family-hint.md`.
4. **Privacy first.** Nothing leaves the device without the user's permission
   and a privacy tier that allows it. Packets never carry the session id or
   the complete request. New network features ask before acting.
5. **Never install or download silently.** Installs and model downloads need
   explicit consent showing what, where and how large.
6. **Untrusted text stays text.** Anything from a model or a peer is rendered
   with `textContent` or escaped Markdown, never as HTML.
7. **Both languages.** Every interface string exists in `web/i18n/en.json`
   and `web/i18n/es.json` with the same keys.

## Layout

| Path | Contents |
|---|---|
| `swarmbly_app/engine/` | Plan admission, packets, scheduler, local model pool, orchestrator |
| `swarmbly_app/p2p/` | Discovery (mDNS), transport (TLS), handshake, node manager, worker |
| `swarmbly_app/api/` | FastAPI app and the local security guard |
| `swarmbly_app/web/` | Interface: vanilla HTML, CSS and JS, no build step |
| `swarmbly_app/*.py` | Configuration, state, chat, hardware, models, advisor, doctor, reports |
| `scripts/` | Launcher, demos, interface preview |
| `tests/` | pytest suite |

## Pull requests

- One topic per pull request; include tests for behaviour changes.
- Run the full suite with `-W error::RuntimeWarning` before pushing.
- For interface changes, attach a screenshot from `scripts/ui_preview.py`
  (desktop and phone width).
- Update `docs/CHANGELOG.md` and, if behaviour or limits change,
  `docs/LIMITATIONS.md`.

By contributing you agree that your contribution is licensed under
AGPL-3.0-or-later, the license of this project.

## Reporting bugs

Open an issue with your OS, Python version, `./launch.sh --check` output and,
for request problems, the report from *Explore processing* (choose the
*minimal* detail level if the conversation is private). Security issues go
through [SECURITY.md](SECURITY.md), not public issues.

---

## Español

Prepara el entorno con `./launch.sh --setup-only --dev` y ejecuta las
pruebas con `.venv/bin/python -m pytest -W error::RuntimeWarning` (unos 15 s,
sin modelos). Reglas: nunca presentar lo simulado como real; cada número
indica si es medido, estimado o desconocido; reutilizar SwarmblyAI y
SwarmblyLCE en vez de copiarlos (los cambios de protocolo se proponen
upstream como SWIP); privacidad primero; nada se instala ni se descarga sin
consentimiento; el texto de modelos o pares nunca se interpreta como HTML; y
toda cadena de la interfaz existe en inglés y en español. Un tema por pull
request, con pruebas, captura de la interfaz si cambia, y entradas en
`CHANGELOG.md` y `LIMITATIONS.md` cuando corresponda. Las contribuciones se
licencian bajo AGPL-3.0-or-later. Los problemas de seguridad se reportan según
[SECURITY.md](SECURITY.md).
