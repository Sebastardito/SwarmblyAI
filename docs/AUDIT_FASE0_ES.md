---
status: current
lang: es
---
# Swarmbly App — Auditoría Fase 0 e informe de compatibilidad

**Fecha:** 12 de octubre de 2026 · **Alcance:** `SwarmblyApp` (local, commit `6e16bc5`),
`SwarmblyAI` (pin `51eb44e`, HEAD `c98ef1d`), `SwarmblyLCE` (pin = HEAD `fd8d97d`).
**Estado:** informe previo a cualquier modificación de código. Nada en este documento
cambia los repositorios originales.

---

## 0. Resumen ejecutivo

1. **La base existente es valiosa y se conserva.** SwarmblyApp ya tiene ~9 000 líneas
   con backend FastAPI, UI sin build, chat local con streaming, identidad Ed25519,
   códec de mensajes SPEC v0.2, gates de worker, StageTracker honesto, SQLite y 76
   pruebas que pasan. La arquitectura de "integrador delgado" (pins a commits, sin
   copiar código upstream) es correcta y se mantiene.
2. **Pero el objetivo de la v0.1 —dos computadoras que se descubren solas y completan
   una tarea distribuida real— no se cumple hoy.** El descubrimiento mDNS **nunca ha
   funcionado** (verificado: excepción silenciada en el callback de zeroconf), y la
   validación "2 y 5 nodos" se hizo en una sola máquina con conexión manual por
   loopback.
3. **El plan distribuido no fragmenta el problema: fragmenta el texto.** El planner
   upstream es un *instrumento de medición* (honra N exactamente porque N es la
   variable independiente de los barridos). Usado como planner de producción con N=4
   forzado, corta el prompt de demostración en ventanas de palabras ("list of five
   items: apples, bridges,"), que es exactamente el defecto de
   `FINDING_2026-09-04` y lo que prohíbe SPEC §14b.7.
4. **Tres fallos de privacidad/seguridad confirmados empíricamente:** el `session_id`
   viaja dentro del texto de cada paquete (SPEC §4 lo prohíbe); la API local acepta
   cualquier Host/Origin y el WebSocket entrega el stream del chat a cualquier página
   web; y datos de anuncios remotos se inyectan sin escapar en el panel (XSS desde
   cualquier nodo de la LAN).
5. **El despacho es secuencial**, no paralelo: las microtareas de un mismo nivel se
   envían una tras otra. Esto anula la ventaja asíncrona que es la tesis del protocolo.
6. **Recomendación:** antes de construir funciones nuevas, una **Fase 1.5 de
   endurecimiento** (≈ 20 correcciones acotadas, sección 8) y luego la prueba física
   de aceptación de la Fase 2. Las funciones nuevas previstas (perfil optimizado
   explicado, multimodelo, gestor de dependencias, rendezvous) se construyen encima.

---

## 1. Método

- Lectura completa del código de SwarmblyApp (backend, P2P, motor, UI, pruebas, docs).
- Lectura normativa de `SPEC_EN.md` v0.2 (rev. 2), `WHITEPAPER_V2_EN.md` §8–§9, §12.4,
  §16, `STATUS.md` y `FINDING_2026-10-04` (SwarmblyAI); `SPEC_LCE_EN.md` 0.1,
  `WHITEPAPER_LCE_v0.2_EN.md` §11.7–§11.9 y `STATUS.md` (SwarmblyLCE).
- Entorno aislado (Linux, Python 3.13) con las dependencias instaladas desde los pins
  declarados; suite completa ejecutada.
- **Cada hallazgo marcado "verificado" se reprodujo con un script**; los marcados
  "código" se establecen por lectura directa sin ambigüedad; "análisis" indica un
  razonamiento de diseño que no se ejecutó.

Línea base: **76/76 pruebas pasan**, con tres señales: una corrutina nunca esperada en
el bus de eventos, tareas pendientes al cerrar, y ~10 s de *teardown* por prueba P2P.

---

## 2. Estado de las fuentes oficiales

### 2.1 SwarmblyAI

| Aspecto | Estado |
|---|---|
| Pin de la app | `51eb44e` (29-sep). HEAD público: `c98ef1d` (12-oct) |
| Cambios desde el pin | **Solo documentación**: `FINDING_2026-10-04` (errores correlacionados entre familias, propuesta L23) y README ampliado. El paquete `swarmbly_v0` no cambió → **el pin sigue siendo válido para código**. |
| Naturaleza de `swarmbly_v0` | Declarado "V0 coherence-tax harness". Es un arnés de medición, no un motor de producción. **No contiene red, verificación, ni clasificador de carril (lane).** |
| Norma vigente | SPEC v0.2 rev. 2 (normativa, draft). El whitepaper v2 §9 describe un v0.3 aún no normativo. |

**Discrepancias SPEC v0.2 ↔ whitepaper v2 (v0.3) que afectan a la app:**

| Tema | SPEC v0.2 (normativo) | WP v2 §9 (v0.3, propuesta) | Consecuencia para la app |
|---|---|---|---|
| N (fragmentos) | parámetro del plan | **derivado**: `N = ⌈material/L⌉`; L lo declara el nodo | "N máximo" debe ser un límite, no un objetivo |
| ρ | objetivo configurable | **derivado y reportado**, no configurado | ρ queda como ajuste avanzado, marcado así |
| k | un solo parámetro | **separado en tres**: `k_avail`, `k_verif`, `k_epist` (§12.4) | mapea limpio al "mínimo / máximo de respuestas" de la app (D10) |
| Paquete | sin `unique_here`, `flank` | añade ambos | no implementar hasta que v0.3 sea normativo |
| Resultado | — | añade `L_declared` | ídem |
| Triage | implícito | gate mecánico por nivel (M3) | etapa de pipeline nueva, opcional |
| Over-dispatch | — | `N+m` solo si subtareas intercambiables | no aplica a v0.1 |

**FINDING 2026-10-04 (L23):** la diversidad de familias atenúa la correlación de
errores, no la elimina. El monitor y `P2P_TESTING.md` presentan el "consenso entre
familias" sin esta salvedad; hay que añadirla.

### 2.2 SwarmblyLCE

| Aspecto | Estado |
|---|---|
| Pin | `fd8d97d` = HEAD (11-oct). Al día. |
| Norma | `SPEC_LCE` 0.1 (texto normativo sin cambios). |
| Evidencia (WP v0.2 §11.7) | **R13 confirmatoria:** la wiki digerida *pierde* contra recuperación directa sobre las fuentes (A3−A2 = −0.146). Memoria local sí ayuda (+0.500, exploratorio). Proyección en Γ transmite léxico (confirmatorio). Olvido verificable en estructura. **Digestión no reproducible** corrida a corrida. |
| R11 (capa 2 / C4) | **Sin veredicto** (confirmatoria rechazada por falla de manipulación). El mensaje del commit `9fd3a1a` dice "la capa 2 se retira"; la Enmienda 15 lo retractó. **Estado vigente: capa 2 abierta.** |
| Consecuencia de diseño (§11.8) | La recuperación por defecto corre **sobre las fuentes**; la wiki queda como capa de gobierno (procedencia, tipos, olvido, elegibilidad de entrenamiento). |

**Escalones LCE y su estado real:**

| Nivel | Añade | Requisito indicativo | Estado upstream | En la app hoy |
|---|---|---|---|---|
| C0 | nada (Swarmbly sin LCE) | el del protocolo | — | activo |
| C1 | fuentes, wiki, recuperación, proyección Γ, reportes | CPU, GB de disco | implementado; recuperación sobre fuentes validada | solo crea carpetas y política (no recupera ni proyecta) |
| C2 | digestión automática | el modelo local del cliente | implementado; **no reproducible** | no expuesto |
| C3 | caché social, afinidad, cápsulas | sin requisito adicional | implementado; **no validado en red real** | no expuesto |
| C4 | adaptador LoRA/QLoRA | "por medir" (SPEC §16) | experimental, `MLXLoRATrainer`; **sin veredicto** | no expuesto |

---

## 3. Matriz de madurez de la app (implementado / simulado / experimental / validado)

| Capacidad | Declarado en README | Realidad verificada |
|---|---|---|
| Backend + UI local, chat con streaming, historial, exportación | ✅ | **Implementado y probado** |
| Detección de hardware honesta | ✅ | Implementado; GPU Windows usa `wmic` (retirado en Win 11 24H2); memoria unificada de Apple Silicon no modelada |
| Detección de modelos Ollama / OpenAI-compat | ✅ | Implementado |
| Identidad Ed25519, códec SPEC v0.2, firmas de resultados | ✅ | **Implementado y probado** |
| Handshake + TLS 1.3 | ✅ | Implementado, **pero sin binding al canal TLS** (H9) |
| Descubrimiento mDNS | ✅ | **No funciona** (H1, H2) |
| Ejecución distribuida LAN | ✅ "real, not simulated" | Real entre procesos, **secuencial** (H6) y con **plan no conforme** (H3) |
| Consenso k>1 | ✅ | Real pero con selección no diversa (H12), umbrales placeholder y embedder léxico (H21) |
| Verificación capa 1 | reportada "no disponible" | Correcto y honesto |
| Swarm Monitor / salud / contribución | ✅ | Implementado; eventos P2P no llegan a la UI (H16); contribución mezcla métricas (H22) |
| LCE C1 | "prepared" | Solo andamiaje |
| Instalable (`pip install`) | implícito | **El wheel no incluye la UI** (H17) |

---

## 4. Hallazgos

Severidad: **C** = bloquea la prueba real o rompe una garantía de privacidad/seguridad;
**A** = incorrecto respecto a la SPEC o a la intención del producto; **M** = honestidad,
calidad o mantenimiento.

### 4.1 Críticos

| ID | Hallazgo | Evidencia | Corrección propuesta |
|---|---|---|---|
| H1 | **mDNS nunca descubre nada.** El callback llama a `get_service_info` (bloqueante) desde el loop de zeroconf → `RuntimeError: Use AsyncServiceInfo.async_request from the event loop`, silenciado por `except`. | verificado (control con API async correcta: descubre en <1 s en el mismo entorno) | Reescribir con `AsyncServiceInfo.async_request` |
| H2 | `DiscoveredNode.expired` es `@property` con parámetro y se invoca como función → `TypeError` en `entries()` en cuanto la caché tiene un nodo; rompe `/api/swarm` y `/api/monitor`. | verificado | Convertir en método |
| H3 | **Plan no conforme:** el planner upstream, llamado sin backend y con N forzado, cae a corte por tokens para listas no etiquetadas y produce subsolicitudes parciales ("comets, drums, electrons. List 5"). Viola SPEC §14b.7 y repite `FINDING_2026-09-04`. | verificado con el prompt de `P2P_TESTING.md` | **Política de admisión de plan** (D1): solo particiones estructurales; si no, ruta local |
| H4 | **`session_id` en el cable.** `packing._contract_header` escribe `session: <id>` y ese texto viaja en `task.instruction`. Además el id es `BLAKE2b(prompt)`: determinista, idéntico entre usuarios para el mismo prompt → identificador de enlace entre fragmentos. Viola SPEC §4. La documentación de la app afirma lo contrario. | verificado | Renderizar el paquete desde campos estructurados (D2), sin texto empaquetado upstream |
| H5 | **Sin descontextualización:** `Γ.objective` = el prompt completo, y viaja a cada worker. Cada nodo ve la solicitud entera. | verificado | Γ mínimo (D2): objetivo = operación/preámbulo, nunca el material completo (SPEC §5 SHOULD minimize) |
| H6 | **Despacho secuencial.** `_dispatch_and_resolve` itera tareas y réplicas con `generate()` bloqueante; el docstring dice "en paralelo". Además el worker atiende la tarea dentro del bucle de lectura → bloqueo de cabeza de línea por conexión. | código | Scheduler asíncrono por nivel (D3) |
| H7 | **API local sin defensa de origen.** Desde Host/Origin ajenos: `GET /api/config` 200, `PUT /api/config` cambia el tier a GLOBAL y activa el worker, y `/ws` entrega `chat.delta` (texto del chat) a cualquier página. Vulnerable a DNS rebinding y a cualquier web abierta en el navegador. | verificado | Allowlist de Host, verificación de Origin en WS y rutas mutantes, token de sesión por arranque, CSP (D5) |
| H8 | **XSS desde la LAN.** `monitor.js` inserta `m.family` del anuncio de un peer en `innerHTML` sin escapar. Cualquier nodo que complete el handshake (no requiere confianza) ejecuta script en el panel, que tiene acceso total a la API. | código | `textContent` / escape sistemático; validación de anuncios con longitudes y charset |
| H9 | **Handshake no ligado al canal.** Cliente TLS con `CERT_NONE`; las firmas Ed25519 cubren nonces e ids, no el certificado. Un atacante en la LAN termina TLS en ambos lados, retransmite el handshake intacto y lee/altera paquetes (los paquetes no van firmados). | análisis | Firmar la huella del certificado TLS dentro del handshake (modelo host-key de SSH) (D4) |

### 4.2 Altos

| ID | Hallazgo | Evidencia |
|---|---|---|
| H10 | `_machine_idle()` llama `psutil.cpu_percent(interval=0.3)` dentro del loop P2P → congela toda la red 300 ms por tarea | código |
| H11 | `deadline_ms` se envía como **época absoluta** y el worker la compara con su reloj → falla con desfase de relojes entre máquinas. El ejemplo de la SPEC (`20000`) es una duración. El worker tampoco corta la generación al vencer | código |
| H12 | Réplicas asignadas por round-robin consecutivo, no maximizando diversidad de familias (SPEC §11.2 MUST). `k_max` se guarda pero el motor nunca lo usa. El bloque de consenso se sobrescribe por tarea (solo queda la última) | código |
| H13 | Sin *hedging* al p95 (SPEC §11.3: timeout fijo es no conforme). Debe implementarse o declararse | código |
| H14 | El nodo no filtra su propio anuncio mDNS → se conectaría a sí mismo por su IP de LAN (el filtro solo cubre 127.0.0.1) | código |
| H15 | Dos instancias `AsyncZeroconf`: la de anuncio queda huérfana, nunca se des-registra (sin *goodbye*) | código |
| H16 | Eventos publicados desde el hilo P2P (`node.connected`, `task.dispatched`…) **no llegan a la UI** | verificado |
| H17 | El wheel no incluye `web/` (está fuera del paquete) → instalación no editable sin interfaz | verificado |
| H18 | `cli.py` llama `state.close()`; `AppState` solo define `stop()` → `AttributeError` al salir; P2P y DB no se cierran | código |
| H19 | Activar LAN en la UI no inicia el descubrimiento hasta reiniciar | código |
| H20 | El orquestador se cachea con el primer modelo/backend; cambiarlos después no lo afecta | código |

### 4.3 Medios

| ID | Hallazgo |
|---|---|
| H21 | Embedder por defecto `hash` (léxico, no semántico) para costuras y consenso; τ_sem = 0.5 y α fijos. Están etiquetados como placeholder, pero la UI debe decir "similitud léxica", no "semántica" |
| H22 | "Contribución" suma `gen_ms` del chat local con el servido a terceros; el worker reporta `tokens_out = 0`; "tasks completed" cuenta solicitudes |
| H23 | `rescan()` solo refresca marcas de tiempo; no re-consulta (contradice el principio de honestidad) |
| H24 | En rutas locales, la etapa VERIFICATION queda `pending` en vez de `skipped` |
| H25 | `lane` fijado a `PUBLIC` sin clasificar. Upstream no tiene clasificador de carril; `swarmbly_lce.projection.HeuristicClassifier` sí (reutilizable). El tier manual se reconstruye a mano en vez de pasar `manual=` a `swarmbly_v0.classify` |
| H26 | Conexiones duplicadas A↔B cuando ambos se descubren (sin regla de desempate) |
| H27 | Clave TLS escrita con permisos por defecto (la Ed25519 sí usa 0600) |
| H28 | `E_POLICY` no existe en SPEC §20; documentarlo como extensión de la app |
| H29 | El asistente inicial es informativo: no genera perfil optimizado con explicaciones, no permite elegir modelo, no pide permiso de red, no gestiona dependencias |
| H30 | Docs desalineadas: README ES dice "Fase 2 en desarrollo"; README cita una carpeta `audit/` inexistente; README marca mDNS como ✅ |

### 4.4 Lo que está bien y se reutiliza tal cual

Códec de mensajes y canonicalización; identidad Ed25519 persistente; gates de política
del worker (kind, presupuesto, concurrencia, LANE/TIER); integración `WorkerGuard`
(invariante I2); StageTracker con estados honestos (`skipped`/`not_available`);
reporte de "verificación no disponible"; escape HTML del Markdown del chat;
adaptadores Ollama/OpenAI-compat; SQLite; directorio de datos por SO; CLI headless;
i18n EN/ES.

---

## 5. Decisiones arquitectónicas propuestas

**D1 — Política de admisión de plan (adaptador, upstream intacto).** Se fragmenta solo
si `swarmbly_v0` produce una partición **estructural** (lote enumerado o mapa
pregunta→material). Si el único camino es el corte por tokens, la solicitud va a
ejecución local con la razón visible en el monitor. N = `suggest_n_tasks`, acotado por
workers disponibles y por "N máximo". Para listas en línea sin etiquetas, una
normalización local (convertir "a, b, c" en ítems etiquetados) se evalúa aparte y con
prueba.

**D2 — Paquete desde campos estructurados.** El paquete SPEC §8 se construye con Γ
mínimo + bloque de tarea + *carry* tipado, en vez de enviar el texto empaquetado
upstream. Elimina H4 y permite minimizar Γ (H5). ρ sigue midiéndose con la función
upstream sobre lo que realmente viaja.

**D3 — Scheduler asíncrono.** Despacho concurrente por nivel topológico; selección que
maximiza familias distintas por réplica; `k_min` réplicas al inicio; *hedge* hasta
`k_max` al p95 observado por (kind, presupuesto), con *fallback* declarado a timeout
fijo mientras no haya datos. El worker ejecuta fuera del bucle de lectura (cola por
conexión). Cancelación registrada como "lento", no "deshonesto".

**D4 — Binding de canal.** El certificado TLS autofirmado se liga a la identidad
firmando su huella SHA-256 dentro del handshake (ambos sentidos; el iniciador presenta
certificado de cliente). Sin dependencias nuevas. mTLS con whitelist para TRUSTED sigue
diferido (SPEC §15c).

**D5 — Endurecimiento de la API local.** Allowlist de Host (`127.0.0.1`, `localhost`,
`[::1]`), Origin obligatorio y propio en WS y métodos mutantes, token aleatorio por
arranque entregado al abrir el navegador, CSP estricta. La interfaz y el servicio P2P
mantienen límites independientes.

**D6 — Descubrimiento.** Una sola instancia zeroconf; `AsyncServiceInfo`; filtrar el
propio `node_id`; manejar *Removed*; caché con descubierto/última verificación/
vencimiento; **re-consulta activa mDNS por solicitud** (cubre la "búsqueda activa
antes de cada solicitud" sin escanear puertos ni dispositivos, conforme a §7.1);
arranque/parada en caliente al cambiar la configuración; conexión manual
`host:puerto` siempre disponible.

**D7 — Proceso y empaquetado.** Un proceso con motor y UI desacoplados por la API
(`headless` ya existe). `web/` se mueve dentro del paquete Python para que cualquier
instalación incluya la interfaz.

**D8 — Rendezvous (Fase 3).** Ver sección 6.

**D9 — LCE.** C1 productivo = recuperación sobre fuentes crudas (R13) + proyección en Γ
con doble clasificación + reporte de costo cognitivo. C2 opcional con advertencia de no
reproducibilidad. C3 oculto tras "experimental". C4 visible pero bloqueado como
"experimental, sin veredicto (R11)", con entrenamiento desactivado por defecto.

**D10 — Parámetros de "respuestas por microtarea".** Mínimo = `k_min` (réplicas
epistémicas despachadas desde el inicio: lo que alimenta el mapa de divergencias).
Máximo = `k_max` (techo total incluyendo *hedges* y reintentos: disponibilidad). Es
exactamente la separación `k_epist` / `k_avail` del WP v2 §12.4, y se muestra con
la salvedad L23 (acuerdo ≠ verdad).

**D11 — Multimodelo.** Un nodo puede anunciar varios modelos (la SPEC §12 ya lo admite)
y servir réplicas de familias distintas. Para que el orquestador pida una familia
concreta hace falta una pista en el paquete; propongo `constraints.model_family`
(extensión MINOR, ignorable por la regla §3) y llevarlo como SWIP. En local, el modo
multimodelo permite consenso entre familias en una sola máquina, con presupuesto de
memoria calculado.

**D12 — Descargas.** Hoy la app nunca descarga modelos (decisión Q4). La nueva
especificación permite descargas con autorización explícita. Propuesta: la app pide a
Ollama que descargue (`/api/pull`) tras mostrar tamaño, origen, licencia y espacio
libre; nunca descarga pesos por su cuenta.

---

## 6. Punto de encuentro por internet: ¿Raspberry Pi?

Una Raspberry Pi sirve sobradamente como rendezvous (registro firmado de corta vida,
sin inferencia, sin contenido): la carga es de kilobytes por nodo. El problema no es la
Pi, es **dónde está conectada**:

- En casa necesita IP pública estable (o DNS dinámico) y reenvío de puerto. Con
  **CGNAT** (frecuente en fibra y móvil) no es alcanzable desde fuera en absoluto.
- Expone la IP residencial como punto fijo de la red.

**Recomendación:** un VPS pequeño como rendezvous primario (IP fija, sin depender del
router de casa) y la Pi como secundario; la app admite varios puntos de encuentro y la
caída de uno no corta conexiones directas ya establecidas. El rendezvous separa
registro, negociación, transporte directo y *relay* opcional. Para NAT: primero directo
(con UPnP/NAT-PMP opcional y consentido), después *relay* que solo reenvía bytes TLS de
extremo a extremo (con D4 el relay no puede leer). La perforación de NAT (mejor sobre
UDP/QUIC que sobre TCP) queda experimental y no se declara compatibilidad universal.
Alternativa a evaluar: una superposición autoalojada tipo Headscale/WireGuard, a costa
de una dependencia más.

---

## 7. Arquitectura objetivo

```
SwarmblyApp
├── swarmbly_app/
│   ├── api/            REST + WS (loopback, Host/Origin/token)          [D5]
│   ├── web/            UI sin build, dentro del paquete                  [D7]
│   ├── setup/          detección, perfil recomendado explicado, deps     [nuevo]
│   ├── inference/      Ollama, OpenAI-compat (llama.cpp, vLLM)
│   ├── engine/
│   │   ├── admission   política de plan (D1)                             [nuevo]
│   │   ├── packets     render SPEC §8 desde campos (D2)                  [nuevo]
│   │   ├── scheduler   async, diversidad, k_min/k_max, hedge (D3)        [nuevo]
│   │   └── orchestrator  composición del pipeline upstream
│   ├── p2p/            discovery (D6), transport+binding (D4), node, worker
│   ├── lce_adapter     C1 productivo (D9)
│   └── rendezvous/     servicio separado, Fase 3                         [nuevo]
└── (deps fijadas)  swarmbly-v0 @51eb44e · swarmbly-lce @fd8d97d
```

---

## 8. Plan por fases (revisado)

| Fase | Contenido | Criterio de aceptación reproducible |
|---|---|---|
| **1.5 — Endurecimiento** | H1–H20, H24, H27, H30; pruebas de regresión para cada una (incluye prueba de descubrimiento mDNS real entre dos procesos y prueba de que ningún paquete contiene `session_id` ni el prompt completo) | Suite verde; script `two_nodes_demo` **sin** IPs; auditoría de seguridad de la API pasa |
| **2 — Swarm LAN (física)** | D1–D4, D6, monitor con eventos P2P, reportes | Dos computadoras físicas, sin configurar IPs, completan una microtarea real; el reporte muestra etapas, nodos, ρ, costuras y verificación "no disponible" |
| **2.5 — Experiencia** | Asistente con perfil recomendado y explicado; gestor de dependencias con consentimiento; multimodelo (D11); descargas vía Ollama (D12); preferencias completas | Usuario sin conocimientos instala, elige modelo y conversa; cada parámetro recomendado muestra su razón |
| **3 — Internet experimental** | Rendezvous (VPS + Pi), directo, relay; pruebas en redes distintas | Dos redes distintas completan una solicitud bajo condiciones documentadas |
| **4 — LCE C1–C3** | D9 | LCE activable sin cambiar el comportamiento del worker ni exponer memoria |
| **5 — Experimental** | C4, modo laboratorio, métricas de diversidad, empaquetado nativo | Cada función etiquetada con su madurez |

Las funciones adicionales previstas encajan así: *Swarm Health* y *Contribution* (ya
existen, se corrigen en 1.5), *Transparency / "Explorar procesamiento"* (Fase 2),
*Modo laboratorio* (Fase 5, aunque su base de reportes comparables llega en la 2),
*Headless* (ya existe; se valida en Raspberry Pi en la Fase 3).

---

## 9. Decisiones resueltas (12-oct-2026)

| Cuestión | Decisión |
|---|---|
| Orden de trabajo | Fase 1.5 de endurecimiento antes de funciones nuevas |
| Descargas de modelos | Vía Ollama, con permiso explícito y confirmación por modelo (D12) |
| Multimodelo | Extensión `constraints.model_family` en la app y SWIP posterior (D11) |
| Punto de encuentro por internet | VPS como principal y Raspberry Pi como secundario (D8, Fase 3) |
| Pin de SwarmblyAI | Se mantiene `51eb44e`; `c98ef1d` no cambia código, solo la referencia documental (L23) |
| Prueba física de la Fase 2 | Procedimiento en `docs/P2P_TESTING.md` |

---

## 10. Estado de los hallazgos (Fase 1.5, 12-oct-2026)

Decisiones aplicadas: las de la sección 9.

| ID | Estado | Prueba de regresión |
|---|---|---|
| H1, H2, H14, H15, H19, H23 | corregidos | `TestDiscoveryWithoutIPs` (mDNS real entre nodos, sin IPs) |
| H3 | corregido (admisión de planes) | `test_unstructured_prose_is_not_fragmented`, demo `--fake` |
| H4, H5 | corregidos (paquetes desde campos, Γ mínimo, autocomprobación) | `test_workers_never_see_session_or_whole_request` |
| H6 | corregido (planificador asíncrono) | `test_parallel_not_sequential` |
| H7 | corregido (Host/Origin/token/CSP) | `tests/test_security.py` |
| H8 | corregido (escape sistemático, validación de anuncios) | `test_markup_in_family_rejected` |
| H9 | corregido (handshake ligado al certificado TLS) | `test_mitm_certificate_rejected` |
| H10, H11 | corregidos | `test_epoch_deadline_rejected_as_schema_error` |
| H12, H13 | corregidos (diversidad, k_min/k_max, p95 con respaldo declarado) | `test_family_diverse_consensus`, `test_failed_worker_is_retried_elsewhere` |
| H16 | corregido | `test_p2p_thread_events_reach_the_ui` |
| H17 | corregido (UI dentro del paquete) | wheel verificado con la UI servida |
| H18, H20, H22, H24, H25, H26, H27, H28, H30 | corregidos | suite completa |
| H21 | etiquetado ("similitud léxica"); calibración de τ_sem pendiente | — |
| H29 | corregido en 0.2.0 (configuración recomendada explicada, asistente de primer arranque) | `tests/test_advisor.py` |

Suite tras la Fase 1.5: **113 pruebas** en ~10 s (antes 76 en ~45 s), sin
advertencias de corrutinas pendientes. Tras la Fase 2.5 (0.2.0): **140 pruebas**.
