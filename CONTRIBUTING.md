# Contributing · Contribuir

**Language / Idioma:** [English](#english) · [Español](#español)

## English

Thank you for helping. Where a contribution goes depends on what it changes:

| You want to change… | Go to |
|---|---|
| The protocol, specification, reference implementation, V0 harness or benchmark | this repository, folder `SwarmblyCore/` — see [`SwarmblyCore/CONTRIBUTING.md`](SwarmblyCore/CONTRIBUTING.md) |
| The local memory (LCE) | [github.com/Sebastardito/SwarmblyLCE](https://github.com/Sebastardito/SwarmblyLCE) |
| The application (interface, network node, evidence, search) | [github.com/Sebastardito/SwarmblyApp](https://github.com/Sebastardito/SwarmblyApp) |
| The installer, this documentation or the distribution tools | this repository (root, `installer/`, `docs/`, `scripts/`) |

**Never edit `SwarmblyLCE/` or `SwarmblyApp/` here.** They are mirrors; a pull request that changes them will fail the mirror check. Make the change in the component's repository; it reaches this distribution with the next synchronisation.

Proposals that change the protocol or a component's design go through a SWIP (see the issue template). Commits are signed off (`git commit -s`, Developer Certificate of Origin). Code and specification are AGPL-3.0-or-later.

## Español

Gracias por ayudar. Adónde va una contribución depende de lo que cambia:

| Quieres cambiar… | Ve a |
|---|---|
| El protocolo, la especificación, la implementación de referencia, el banco V0 o el benchmark | este repositorio, carpeta `SwarmblyCore/` (ver [`SwarmblyCore/CONTRIBUTING.md`](SwarmblyCore/CONTRIBUTING.md)) |
| La memoria local (LCE) | [github.com/Sebastardito/SwarmblyLCE](https://github.com/Sebastardito/SwarmblyLCE) |
| La aplicación (interfaz, nodo de red, evidencia, búsqueda) | [github.com/Sebastardito/SwarmblyApp](https://github.com/Sebastardito/SwarmblyApp) |
| El instalador, esta documentación o las herramientas de la distribución | este repositorio (raíz, `installer/`, `docs/`, `scripts/`) |

**Nunca edites aquí `SwarmblyLCE/` ni `SwarmblyApp/`.** Son espejos: una pull request que los cambie fallará la comprobación de espejos. Haz el cambio en el repositorio del componente; llegará a esta distribución con la siguiente sincronización.

Las propuestas que cambian el protocolo o el diseño de un componente pasan por un SWIP (ver la plantilla de incidencias). Los commits llevan firma de origen (`git commit -s`, Developer Certificate of Origin). El código y la especificación son AGPL-3.0-or-later.
