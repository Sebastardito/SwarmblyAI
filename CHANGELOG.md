# Changelog — Swarmbly AI (distribution)

Each component keeps its own changelog: [SwarmblyCore](SwarmblyCore/), [SwarmblyLCE](SwarmblyLCE/), [SwarmblyApp](SwarmblyApp/docs/CHANGELOG.md).

## 3.0.0 — Integrated distribution (unreleased)

- **The repository becomes the umbrella of Swarmbly AI.** Everything that was here (protocol, specification, reference implementation, V0 harness, benchmark, documents) moves unchanged into `SwarmblyCore/`. Project-wide documents (licence, notice, governance, trademark) stay at the root.
- **Mirrors of SwarmblyLCE and SwarmblyApp** (`git subtree --squash`) at the commits recorded in `components.lock`: SwarmblyLCE 0.2.0.dev0 (`b659ac4`), SwarmblyApp 0.3.0 (`b0ad09f`). The components keep their own repositories, releases and DOIs.
- **Interactive installer** for macOS, Linux and Windows (`install.sh`, `install.command`, `install.ps1`, `install.bat`, `installer/install.py`, standard library only): quick install (explained once, no further questions; steps that need an administrator password are listed at the end) or custom install (step by step). Isolated environment, the three components, Ollama and models that fit the computer, pdftotext and SearXNG as extras, launcher, shortcuts, `swarmbly doctor`, uninstall.
- **Documentation for the whole project:** README (English and Spanish), architecture, installation, components and maintenance, roadmap.
- **Maintenance tools:** `scripts/sync_components.py` (update a mirror to a tag or branch and record it), `scripts/check_components.py` (a mirror must equal its recorded commit), continuous integration for mirrors, installation on three systems and the three test suites.
- SwarmblyCore: links to `GOVERNANCE.md`, `TRADEMARK.md` and the SWIP template point one level up; the documentation-boundary test also looks there.

Earlier releases of this repository (v1, v2) are the protocol releases now inside SwarmblyCore; their DOIs remain valid.
