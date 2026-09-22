---
status: current
lang: es
---
# tables-dev, segunda corrida — la hipótesis del costo está viva, la sucesora está muerta

**Corrida:** `results/tables-dev-20260827-095758`. La mitad dev de
`prompts/tables24.json`, digest congelado `0c5cb7e2…`, verificado antes de la
corrida. ρ = 3.5, N ∈ {2, 8}, k ∈ {1, 3}. Sin editor, sin acarreo tipado. Cinco
familias de modelos sobre Ollama, transporte `openai-sdk`, **0 reintentos**,
embeddings no degradados, `harness_validation_only: false`. τ_sem ajustado aquí
en **0.680**. 40 filas.

La primera corrida de esta celda tras dos correcciones: una métrica de
coherencia neutral entre brazos, y una directiva de tiempo verbal y registro en
el contrato. Las dos aterrizaron a la vez y no se pueden separar a partir de
estas dos corridas — eso se dice aquí en vez de pasarlo por alto.

---

## 1. La celda declarada ahora marca +1.6 %, y queda indecisa

**Declarado, sin cambios desde la preinscripción original:** `table_summary` a
ρ=3.5, N=2 cuesta menos de 5 %, con el *límite superior* de un intervalo
agrupado por prompt por debajo de 0.05.

| celda | punto | IC 95 % (sobre prompts) | veredicto |
|---|---|---|---|
| **N=2, k=1** | **+1.57 %** | **[−4.69 %, +7.26 %]** | indecisa |
| N=2, k=3 | +20.48 % | [+11.64 %, +30.57 %] | falla |
| N=8, k=1 *(control)* | +14.00 % | [+7.95 %, +19.23 %] | falla |
| N=8, k=3 *(control)* | +35.02 % | [+26.22 %, +44.59 %] | falla |

La misma celda, sobre la misma familia de corpus, marcaba **+22.9 %** antes de
que se corrigiera la métrica. Ahora marca **+1.6 %**, y **tres de ocho prompts
son negativos** — la respuesta fragmentada puntuó *mejor* que su baseline
monolítico:

| prompt | impuesto | sobre el puntaje completo |
|---|---|---|
| manifest | 0.0 % | −18.8 % |
| intake | +8.7 % | +4.4 % |
| consolidation | +12.5 % | +18.8 % |
| reconciliation | +4.3 % | +8.8 % |
| **drayage** | **−15.7 %** | −12.1 % |
| **groupage** | **−9.1 %** | +1.8 % |
| recall | +8.6 % | −1.6 % |
| staging | +3.2 % | −4.8 % |

Sobre el puntaje *completo* — clases de costura incluidas — la celda marca
**−0.44 %**. Fragmentar el resumen de una tabla en dos partes, con este
presupuesto de contexto, no cuesta prácticamente nada.

**Sigue fallando el criterio**, porque el criterio está escrito sobre el límite
superior y el límite superior es +7.26 %. Sobre **ocho prompts**. Ese es el
veredicto correcto y el interesante: por primera vez la celda queda indecisa en
la dirección *favorable*, y dieciséis prompts más reducirían el intervalo
aproximadamente a la mitad.

**Dos cambios aterrizaron juntos y esta corrida no los puede separar.** La
corrección de la métrica está demostrada de forma independiente — una misma
respuesta idéntica puntuó 0.9375 y 0.5000 según las convenciones de los dos
brazos — así que no está en duda que importó. Cuánto del movimiento restante es
la directiva de tiempo verbal no es recuperable a partir de dos corridas. Lo que
sí es recuperable: el instrumento *actual*, sobre el corpus *actual*, marca
+1.6 %.

## 2. El consenso ahora es inequívocamente caro

| | k=1 | k=3 |
|---|---|---|
| N=2 | **+1.6 %** | +20.5 % |
| N=8 | +14.0 % | +35.0 % |

En la corrida anterior k=3 *ayudaba* en N=2 (+16.0 % contra +20.6 %). Ahora
perjudica por diecinueve puntos. La dirección se dio vuelta, lo que sobre ocho
prompts significa que la lectura anterior era ruido, no que el consenso haya
cambiado de carácter.

Lo que sobrevive en las dos corridas es la interacción: **k=3 cuesta más cuanto
más fina la partición**. Tres réplicas de un fragmento de 56 tokens tienen muy
poco sobre lo cual converger, el medoide elige una lectura, y ocho de esas
elecciones ensambladas en secuencia producen algo mucho peor que una sola
generación de los mismos fragmentos.

## 3. El costo de costura, ahora en su propia columna

| celda | impuesto (comparable) | impuesto (completo) | errores de costura/oración | vs baseline |
|---|---|---|---|---|
| N=2 k=1 | +1.6 % | −0.4 % | 0.056 | **−0.024** |
| N=2 k=3 | +20.5 % | +21.6 % | 0.088 | +0.007 |
| N=8 k=1 | +14.0 % | +17.6 % | 0.109 | +0.029 |
| N=8 k=3 | +35.0 % | +52.7 % | 0.285 | +0.204 |

El baseline monolítico lleva una tasa de costura de **0.081** pese a no tener
costuras — `dangling_reference` también se dispara en una oración sin
solapamiento de antecedente, cosa que cualquier texto puede tener. El nombre de
la clase es impreciso; la comparación no, porque la clase se excluye de los dos
brazos o se incluye en los dos.

En N=2, k=1 la respuesta fragmentada tiene **menos** de estos que el baseline. En
N=8, k=3 tiene tres veces y media más. Ese es el daño específico que hace el
ensamblado, y ahora es visible en vez de quedar plegado dentro de una razón de
coherencia.

## 4. La hipótesis sucesora falló su primera prueba independiente

Declarada el 26 de agosto, antes de que esta corrida existiera: *entre las
afirmaciones agregadas, marcar aquellas en las que menos de dos de tres réplicas
coincidieron identifica errores mejor que el azar, dentro de un prompt.*
Estimador: odds ratio de Mantel-Haenszel, prompt como estrato. Pasa si el límite
inferior supera 2.0.

| clase | corrida anterior | esta corrida | IC 95 % | estratos | marcadas |
|---|---|---|---|---|---|
| **agregado** *(bajo prueba)* | OR 3.47 | **OR 0.26** | [0.00, 3.25] | 5 / 8 | 8 / 83 |
| local *(control)* | OR 0.56 | OR 0.89 | [0.09, 4.79] | 8 / 8 | 63 / 215 |

**No replica. Se invierte.** Y la tabla de exactitud que era toda su
justificación ya no tiene la forma por la que se la nombró:

| acuerdo | corrida anterior | esta corrida |
|---|---|---|
| 0.00 | 0.000 (n=2) | *sin ítems* |
| 0.33 | 0.250 (n=8) | **0.875** (n=8) |
| 0.67 | 0.625 (n=40) | 0.692 (n=26) |
| 1.00 | 0.750 (n=44) | 0.796 (n=49) |
| | **monótona, rango 0.75** | no monótona, rango 0.18 |

El bin de menor acuerdo ahora contiene las afirmaciones *más exactas*. La
exactitud agregada subió de 63.8 % a 77.1 %, y el grupo marcado se encogió a
ocho ítems.

**Esto es la partición haciendo exactamente aquello para lo que existe.** Una
hipótesis con un mecanismo limpio, una curva monótona a lo largo de setenta y
cinco puntos de exactitud, y un control que falló en la dirección opuesta —
declarada con su estimador, su corte y su umbral fijos — murió en la mitad de
desarrollo a un costo de una hora, sin tocar nunca los dieciséis prompts
reservados para decidirla. Dos corridas de ocho prompts dieron signos opuestos.
**Con n = 8 esta medición es ruido, y también era ruido la primera vez.**

La conclusión honesta es la que V5-contra-V6 ya sugería y sobre la que no actué
con suficiente firmeza: el mapa de confianza ya falló en replicar tres veces
(V5→V6, dev-1→dev-2), y ninguna versión de él debería declararse otra vez hasta
que algo explique por qué se mueve.

## 5. Qué no cambió

- **El juez acepta el 100 %** de 761 unidades. Tercera corrida seguida. Sobre
  prosa fundamentada no es un instrumento.
- **ρ en N=8 es 3.90 contra un objetivo de 3.5** — 11.5 % por encima, sin
  cambios respecto de la corrida anterior. El control N=8 no corrió con el
  presupuesto que nombra su etiqueta. Es conservador para la conclusión que se
  saca de él (más contexto, peor resultado), pero hay que arreglar el
  empaquetador antes de usar N=8 como punto de comparación.
- N=2 queda en 3.38, −3.4 %, dentro de tolerancia.

## Qué sigue

1. **Correr la mitad final sobre la hipótesis del costo.** Es la preinscripción
   original — la celda, el umbral y el estimador nunca se movieron; lo que se
   movió fue un instrumento defectuoso, ahora corregido. La estimación puntual
   es +1.6 %, el intervalo es [−4.69 %, +7.26 %] sobre ocho prompts, y dieciséis
   más plausiblemente la deciden. Es la primera vez que la mitad final tiene una
   pregunta en la que vale la pena gastarla.
2. **No declarar otra vez el mapa de confianza.** Tres no replicaciones.
   Necesita una explicación antes de necesitar otra prueba.
3. **Arreglar la deriva de ρ en N=8** antes de que alguna corrida use N=8 como
   control.
4. **Separar la corrección de la métrica de la directiva de tiempo verbal** si
   la distinción alguna vez importa para una afirmación. No importa para la
   decisión de arriba.
5. **Retirar el juez sobre prosa fundamentada.** 100 % de aceptación, tercera
   corrida seguida.
