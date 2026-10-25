# Security policy

*[Español](#español) below.*

## Reporting a vulnerability

Please report vulnerabilities **privately** through GitHub:
*Security → Report a vulnerability* on this repository
(<https://github.com/Sebastardito/SwarmblyApp/security/advisories/new>).
Do not open a public issue for security problems.

Include what you found, how to reproduce it, the version (`swarmbly-app
status`) and your OS. You will get an acknowledgement within a week. Fixes are
released as soon as they are ready, with credit if you want it.

## Supported versions

Swarmbly App is alpha software. Only the latest release on `main` receives
security fixes.

## What the app defends

| Boundary | Defence |
|---|---|
| Local interface (`127.0.0.1:8765`) against other web pages | Host allowlist (DNS rebinding), Origin checks on changes and WebSockets, per-launch token, strict CSP, no framing |
| Peer identity | Ed25519 node keys; the handshake binds each identity to its TLS 1.3 certificate, so a man in the middle is detected |
| Messages between nodes | Fresh nonces, per-peer attempt-id window, frame size cap, peer cap, signed results checked before assembly |
| What workers see | Micro-task and minimal context only; never the session id or the complete request; sensitive lanes and the LOCAL tier never leave the device |
| What workers run | Every packet passes the worker's gates (role, pause, kinds, budget, deadline, concurrency, lane and tier, idle/power) |
| Untrusted text | Model and peer output rendered as text or escaped Markdown, never as HTML; remote images not loaded |
| Installs and downloads | Known Python packages into the app's own environment only; models only through Ollama after consent |

## Known gaps

Documented in [docs/LIMITATIONS.md](docs/LIMITATIONS.md): no mutual TLS yet
(the TRUSTED tier is answered locally), no Layer-1 verification commitment
upstream, no sampled audit, and consensus measures agreement rather than
correctness. Reports that sharpen these are welcome.

---

## Español

Reporta las vulnerabilidades **en privado** desde GitHub: *Security → Report a
vulnerability* en este repositorio; no abras un issue público. Incluye qué
encontraste, cómo reproducirlo, la versión (`swarmbly-app status`) y tu
sistema operativo. Recibirás respuesta en menos de una semana. Solo la última
versión en `main` recibe correcciones. Las defensas actuales y sus límites
están en las tablas anteriores y en [LIMITATIONS.md](docs/LIMITATIONS.md).
