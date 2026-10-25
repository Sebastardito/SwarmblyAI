# Components and maintenance · Componentes y mantenimiento

**Language / Idioma:** [English](#english) · [Español](#español)

---

## English

### Versions in this distribution

The source of truth is [`components.lock`](../components.lock). Distribution **3.0.0**:

| Component | Version | Source | Commit | DOI |
|---|---|---|---|---|
| SwarmblyCore | `swarmbly-v0` 0.1.0 | in this repository | — | [10.5281/zenodo.21956743](https://doi.org/10.5281/zenodo.21956743) |
| SwarmblyLCE | 0.2.0.dev0 | mirror of [SwarmblyLCE](https://github.com/Sebastardito/SwarmblyLCE) | `5fb70b9` | [10.5281/zenodo.23289041](https://doi.org/10.5281/zenodo.23289041) |
| SwarmblyApp | 0.3.0 | mirror of [SwarmblyApp](https://github.com/Sebastardito/SwarmblyApp) | `e6af928` | [10.5281/zenodo.23322638](https://doi.org/10.5281/zenodo.23322638) |

### Rules

1. **SwarmblyCore is edited here.** It has no repository of its own; its releases are this repository's releases.
2. **Mirrors are never edited here.** A change to SwarmblyLCE or SwarmblyApp is made, tested and committed in its own repository, then synchronised. `scripts/check_components.py` (and continuous integration) fails if a mirror folder differs from the commit in the lock.
3. **`main` takes releases; `edge` takes the latest.** On `main`, mirrors move only to a component's tag. On `edge`, they may follow the component's `main` branch.
4. **One distribution, one set of versions.** A release of Swarmbly AI records, in `components.lock` and `CHANGELOG.md`, which component versions it contains and that they were tested together.

### Workflow

```bash
# a component released a new version (tagged in its own repository)
python scripts/sync_components.py SwarmblyApp v0.3.0        # subtree pull + lock + commit
python scripts/check_components.py                          # mirrors = lock
python installer/install.py --quick --yes --dev --skip ollama,models,pdf,searxng,shortcuts
cd SwarmblyApp && ../.venv/bin/python -m pytest -q           # and the LCE and Core suites

# edge branch: follow the latest commits
git switch edge
python scripts/sync_components.py SwarmblyLCE main
python scripts/sync_components.py SwarmblyApp main

# release of the distribution (from main)
#   1. update components.lock "distribution", CHANGELOG.md, CITATION.cff, .zenodo.json
#   2. tag vX.Y.Z and publish a GitHub release; Zenodo mints the version DOI
```

`sync_components.py` can also pull from a local clone with `--repo ../SwarmblyApp`. A squashed subtree keeps this repository's history short; the component's full history stays in its own repository.

### Releasing a component

Each component releases on its own (tag, GitHub release, Zenodo DOI), as before. A component that depends on SwarmblyCore declares it by name and version range; this distribution's installer installs the three folders together, so pip never fetches another copy.

---

## Español

### Versiones de esta distribución

La fuente de verdad es [`components.lock`](../components.lock). Distribución **3.0.0**:

| Componente | Versión | Origen | Commit | DOI |
|---|---|---|---|---|
| SwarmblyCore | `swarmbly-v0` 0.1.0 | en este repositorio | — | [10.5281/zenodo.21956743](https://doi.org/10.5281/zenodo.21956743) |
| SwarmblyLCE | 0.2.0.dev0 | espejo de [SwarmblyLCE](https://github.com/Sebastardito/SwarmblyLCE) | `5fb70b9` | [10.5281/zenodo.23289041](https://doi.org/10.5281/zenodo.23289041) |
| SwarmblyApp | 0.3.0 | espejo de [SwarmblyApp](https://github.com/Sebastardito/SwarmblyApp) | `e6af928` | [10.5281/zenodo.23322638](https://doi.org/10.5281/zenodo.23322638) |

### Reglas

1. **SwarmblyCore se edita aquí.** No tiene repositorio propio; sus versiones son las de este repositorio.
2. **Los espejos nunca se editan aquí.** Un cambio en SwarmblyLCE o SwarmblyApp se hace, se prueba y se confirma en su propio repositorio, y después se sincroniza. `scripts/check_components.py` (y la integración continua) falla si una carpeta espejo difiere del commit del lock.
3. **`main` recibe versiones; `edge`, lo último.** En `main`, los espejos solo se mueven a un tag del componente. En `edge` pueden seguir la rama `main` del componente.
4. **Una distribución, un conjunto de versiones.** Cada versión de Swarmbly AI anota, en `components.lock` y en `CHANGELOG.md`, qué versiones de los componentes contiene y que se probaron juntas.

### Flujo de trabajo

```bash
# un componente publicó una versión (con tag en su propio repositorio)
python scripts/sync_components.py SwarmblyApp v0.3.0        # subtree pull + lock + commit
python scripts/check_components.py                          # espejos = lock
python installer/install.py --quick --yes --dev --skip ollama,models,pdf,searxng,shortcuts
cd SwarmblyApp && ../.venv/bin/python -m pytest -q           # y las suites de LCE y Core

# rama edge: seguir los últimos commits
git switch edge
python scripts/sync_components.py SwarmblyLCE main
python scripts/sync_components.py SwarmblyApp main

# versión de la distribución (desde main)
#   1. actualizar "distribution" en components.lock, CHANGELOG.md, CITATION.cff, .zenodo.json
#   2. tag vX.Y.Z y release en GitHub; Zenodo asigna el DOI de la versión
```

`sync_components.py` también puede traer desde un clon local con `--repo ../SwarmblyApp`. El subtree comprimido (squash) mantiene corta la historia de este repositorio; la historia completa del componente queda en su repositorio.

### Versiones de un componente

Cada componente publica por su cuenta (tag, release en GitHub, DOI en Zenodo), como hasta ahora. Un componente que depende de SwarmblyCore lo declara por nombre y rango de versión; el instalador de esta distribución instala las tres carpetas juntas, así que pip nunca descarga otra copia.
