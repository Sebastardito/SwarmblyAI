"""Genera el corpus multi-usuario del benchmark H-C1 a escala.

Cinco usuarios sintéticos, cada uno con tres documentos extensos de dominio
(procedimientos, conocimiento, estilo) y doce preguntas (5 factuales, 4 de
preferencia/lexico, 3 de procedimiento, con al menos una pregunta entre
documentos). El contenido es determinista y se escribe una sola vez en
``lce_validation/fixtures/bench_users/``; el benchmark
``bench_hc1_scale.py`` lo consume.

Esto NO es el preregistro C1/C2 (que sigue intacto): es un corpus de
benchmark exploratorio para probar H-C1 a escala con cinco familias.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "fixtures" / "bench_users"

# ---------------------------------------------------------------------------
# usuario 1: mara — genética de poblaciones
# ---------------------------------------------------------------------------

MARA_PROC = """Protocolo de análisis de variantes para el estudio de estructura poblacional
Procedimiento operativo personal — versión 2026.1

1. Preprocesamiento de lecturas.
1.1 Corro con fastp sobre cada biblioteca con los parámetros de siempre:
calidad mínima 20, longitud mínima 50 pb, y recorte automático de adaptadores.
1.2 Si una biblioteca conserva menos del 70 por ciento de lecturas tras el
filtro, la marco como fallida y la repito desde la extracción. No se rescata
una biblioteca con menos de 60 por ciento de lecturas: se descarta.
1.3 Alineo con bwa-mem contra el genoma de referencia anotado de la versión
2025.1, con el modo por defecto y la marca de grupos de lectura activa.

2. Llamado de variantes.
2.1 Uso el pipeline GATK siguiendo las prácticas recomendadas: HaplotypeCaller
por muestra en modo GVCF y genotipado conjunto con GenotypeGVCFs.
2.2 El filtrado duro exige calidad de variante QUAL mayor o igual a 30 y
profundidad de lectura por sitio DP mayor o igual a 8 en al menos el 80 por
ciento de las muestras.
2.3 Las inserciones y deleciones se validan por separado con el filtro de
profundidad relativa; si una indel aparece en menos de 3 muestras, se retira
del conjunto de trabajo.

3. Filtrado de calidad del conjunto.
3.1 Aplico el filtro de frecuencia mínima del alelo menor: MAF mayor o igual
a 0.01 dentro de cada población y no menor a 0.005 en el conjunto completo.
3.2 Retiro los sitios con datos faltantes en más del 10 por ciento de las
muestras (missingness menor o igual a 0.10) y los que fallan el equilibrio de
Hardy-Weinberg con p menor a 0.001 dentro de cualquier población.
3.3 Para el análisis de estructura podo por desequilibrio de ligamiento con
una ventana de 50 kilobases, paso de 10 variantes y r cuadrado menor a 0.2.
3.4 Conservo una muestra de control de calidad: si el conjunto final baja de
5,000 variantes, detengo el análisis y reviso el paso 2.2 antes de continuar.

4. Estructura poblacional.
4.1 La estructura se estima con el análisis de componentes principales sobre
la matriz de frecuencias, reteniendo los 10 primeros ejes.
4.2 Calculo la heterocigosidad esperada por población con el estimador no
sesgado y la reporto con tres decimales en las tablas y en el texto.
4.3 Estimo F_ST por pares de poblaciones con el método de Weir y Cockerham;
reporto la matriz completa y el valor medio ponderado por tamaño muestral.
4.4 Si el primer eje del PCA separa una población con una contribución mayor
al 15 por ciento de la varianza total, declaro estructura y la describo antes
de cualquier prueba de selección.

5. Criterio de abandono.
5.1 Antes de correr cualquier análisis escribo en el cuaderno el resultado
que refutaría la hipótesis. Si el F_ST por pares entre las dos poblaciones
hipotetizadas como aisladas resulta menor a 0.01, la hipótesis de aislamiento
se declara muerta y se reporta así.
5.2 Ningún resultado se re-analiza después de verlo para cambiar el criterio:
el criterio escrito manda.

6. Reproducibilidad.
6.1 Cada corrida lleva un archivo de configuración con semilla, versión de
cada herramienta y el hash del conjunto de variantes de entrada.
6.2 Las figuras se generan con un script que acepta la ruta del resultado y
nada más; las tablas del manuscrito se regeneran desde el mismo archivo.
"""

MARA_KNOW = """Sistema de estudio: los pinzones de la cordillera de Talamanca

Poblaciones muestreadas. El proyecto compara cuatro poblaciones del pinzón
serrano (Aves: Passerellidae) en la cordillera de Talamanca, Costa Rica y
Panamá: Cerro Chirripó (32 individuos), Cerro de la Muerte (41 individuos),
Volcán Barú (27 individuos) y Cerro Fábrega (19 individuos). El muestreo
usó redes de niebla entre 2,600 y 3,300 metros de altitud, en dos temporadas
secas consecutivas, y cada individuo fue anillado con anillo metálico único
y liberado en el punto de captura.

Marcadores. Cada individuo fue genotipado con un panel de 12,415 SNPs de
doble digestión RAD. Tras el filtrado del protocolo quedaron 9,8 millones de
lecturas por biblioteca en promedio y 8,9 millones de pares de bases de
cobertura media 21x. El conjunto final de trabajo retuvo 11,203 variantes
bialélicas con MAF mayor o igual a 0.01.

Diversidad. La heterocigosidad esperada media del conjunto fue 0.287 con un
rango entre poblaciones de 0.241 (Cerro Fábrega) a 0.312 (Volcán Barú). La
población de Cerro de la Muerte mostró la mayor proporción de variantes
privadas (3.1 por ciento del total), y Cerro Chirripó la menor (0.9 por
ciento). La diversidad de nucleótidos por sitio fue de 0.0031 en promedio.

Diferenciación. El F_ST por pares más alto fue 0.048 entre Cerro Fábrega y
Cerro Chirripó, y el más bajo 0.012 entre Cerro Chirripó y Cerro de la
Muerte. El valor medio ponderado fue 0.027. El primer eje del PCA explicó el
18 por ciento de la varianza total y separó a Cerro Fábrega de las otras tres
poblaciones; el segundo eje, el 9 por ciento, y separó parcialmente a Volcán
Barú.

Interpretación histórica. La demografía inferida con el modelo de aislamiento
con migración sobre los espectros de frecuencia conjuntos indica que Cerro
Fábrega se separó del ancestro común hace aproximadamente 120,000
generaciones, con una tasa de migración efectiva posterior de 0.2 migrantes
por generación; entre Chirripó y Cerro de la Muerte la separación estimada
fue de 18,000 generaciones con 1.1 migrantes por generación. El flujo
reciente entre Barú y Fábrega no se distingue de cero.

Hipótesis preregistrada y desenlace. La hipótesis era que Fábrega y Barú
permanecían aisladas desde el último máximo glacial. El F_ST por pares entre
ellas fue 0.036, por encima del umbral de muerte de 0.01, de modo que la
hipótesis de aislamiento no murió, pero el flujo estimado fue nulo: el
resultado quedó descrito como aislamiento ecológico en presencia de
oportunidad de flujo, no como aislamiento demostrado.
"""

MARA_STYLE = """Escribo en un registro técnico y conciso, con oraciones cortas y sin
adjetivos de relleno.

Prefiero el término heterocigosidad esperada en lugar de diversidad génica.

Prefiero el término fragmentación semántica en lugar de división de prompts.

Prefiero el término demografía en lugar de historia poblacional.

Prefiero el término variante rara en lugar de mutación rara.

Cuando describo un umbral numérico escribo siempre la unidad completa: no
"MAF 0.01" sino "frecuencia del alelo menor de 0.01".

En los correos cierro siempre con un agradecimiento y mi nombre, y nunca
escribo el cuerpo en más de tres párrafos.
"""

# ---------------------------------------------------------------------------
# usuario 2: julián — ingeniería de software
# ---------------------------------------------------------------------------

JULIAN_PROC = """Protocolo de despliegue del servicio de catálogo
Procedimiento operativo personal — revisión 14

1. Preparación.
1.1 Toda rama que sale a producción pasa primero por revisión de pares: al
menos un revisor distinto del autor, y la revisión no puede ser un visto
bueno sin comentarios si el cambio toca el esquema de la base de datos.
1.2 La cobertura de pruebas del paquete modificado debe ser mayor o igual al
80 por ciento; si baja de ese umbral, el cambio se devuelve con la métrica
en el mensaje de rechazo.
1.3 Las migraciones de esquema se escriben siempre en dos partes: la
migración que aplica y la que revierte. Sin rollback escrito no hay
despliegue.

2. Integración continua.
2.1 La tubería corre formato, análisis estático, pruebas unitarias y pruebas
de contrato en ese orden y se detiene en la primera etapa que falle.
2.2 Las pruebas de contrato se generan desde el esquema publicado del
catálogo y se versionan con él: un cambio de contrato sin su prueba es un
error de la tubería, no una advertencia.
2.3 El p95 de latencia del servicio en el entorno de pruebas debe quedar por
debajo de 300 milisegundos para el endpoint de listado con 10,000 registros
de catálogo sembrados.

3. Despliegue azul-verde.
3.1 El despliegue es siempre azul-verde: la versión nueva se levanta en un
conjunto separado, se le dirige el 5 por ciento del tráfico durante 15
minutos y se compara la tasa de errores contra la versión anterior.
3.2 Si la tasa de errores de la versión nueva supera en 2 puntos la de la
anterior o si el p95 excede el p95 anterior en más de 50 milisegundos, se
revierte de inmediato y se congela el despliegue de esa rama hasta la
siguiente revisión.
3.3 El tráfico se mueve en incrementos de 25, 50 y 100 por ciento con 10
minutos de observación entre cada incremento.

4. Observabilidad.
4.1 Todo servicio emite trazas con identificador de correlación y métricas
con las etiquetas de servicio, versión y entorno. Las trazas se muestrean al
100 por ciento en el entorno de pruebas y al 10 por ciento en producción.
4.2 Las alertas se definen sobre el p95 y no sobre el promedio: una alerta
de promedio esconde el servicio lento para la mayoría.
4.3 Todo incidente termina en un documento de postmortem con cronología,
causa raíz, acción correctiva y propietario, dentro de los cinco días
hábiles.

5. Capacidad.
5.1 Cada instancia del catálogo debe sostener 400 peticiones por segundo
sostenidas con el p95 por debajo de 300 milisegundos en la prueba de carga;
si no, se ajusta el grupo de conexiones antes de escalar instancias.
5.2 La cuota de almacenamiento por inquilino es de 5 gigabytes en el entorno
compartido; el exceso se cobra, no se bloquea.
"""

JULIAN_KNOW = """Arquitectura del sistema de catálogo de productos

Servicios. El sistema tiene cuatro servicios: catálogo (dueño de productos,
precios y variantes), inventario (existencias por almacén), pedidos (ciclo de
vida del pedido) y facturación (documentos y pagos). Se comunican por
contratos HTTP versionados en el encabezado y por eventos de dominio en un
canal de mensajería con entrega al menos una vez.

Base de datos. Cada servicio posee su esquema y ningún servicio lee tablas de
otro. El catálogo usa PostgreSQL 17 con particionamiento por inquilino; la
tabla de variantes tiene 41 millones de filas en el inquilino mayor y las
consultas de listado se sirven desde una vista materializada que se refresca
cada 15 minutos.

Convenciones. Los identificadores son UUID versión 7; las fechas viajan en
ISO-8601 con zona horaria; los montos en centavos como enteros. Los errores
usan el formato de problema de la IETF con los códigos estables del catálogo:
CAT-101 precio duplicado para una vigencia, CAT-102 variante huérfana,
CAT-103 moneda no registrada.

Cifras de operación. El p95 histórico del listado es 268 milisegundos con
10,000 registros sembrados; la tasa de errores móvil de 30 días es 0.41 por
ciento; el último incidente mayor duró 47 minutos y su causa raíz fue una
consulta sin límite en la vista materializada, corregida con límite y paginación
de cursores.

Decisiones registradas. El paso a mensajería con entrega al menos una vez
duplicó las entregas (los consumidores deben ser idempotentes); por eso todo
evento lleva un identificador de idempotencia y el consumidor descarta los
duplicados por ese campo. La decisión de no bloquear el exceso de cuota de
almacenamiento (cobrar en lugar de bloquear) redujo los incidentes de
escritura a cero en tres meses.
"""

JULIAN_STYLE = """Escribo en un registro directo y técnico, sin gerundios de relleno y con
el verbo en primera persona del plural.

Prefiero el término trazas en lugar de logs.

Prefiero el término servicio en lugar de microservicio.

Prefiero el término módulo en lugar de componente.

Prefiero el término despliegue azul-verde en lugar de rolling update.

En los documentos de diseño escribo siempre la sección de decisiones
registradas al final, con la opción descartada y la razón en una línea.
"""

# ---------------------------------------------------------------------------
# usuario 3: carmen — análisis financiero
# ---------------------------------------------------------------------------

CARMEN_PROC = """Protocolo del informe trimestral de cartera
Procedimiento operativo personal — ciclo fiscal 2026

1. Recopilación.
1.1 El cierre contable del trimestre alimenta el modelo con los saldos por
fondo, por sector y por moneda; los datos manuales entran solo con la marca
de auditoría del responsable.
1.2 La conciliación bancaria se firma antes del día 5 del mes siguiente; sin
conciliación firmada no se emiten cifras del trimestre.

2. Reglas de presentación.
2.1 Los montos se presentan en miles de dólares con un decimal; los
porcentajes con un decimal; los ratios con dos decimales.
2.2 La materialidad del informe es el 5 por ciento del valor de la cartera:
toda variación de un fondo mayor al 5 por ciento respecto del trimestre
anterior se explica en una nota individual, con la causa y la acción.
2.3 Toda variación mayor al 10 por ciento en un sector se acompaña de la
serie de tres trimestres y del comentario del comité.

3. Riesgo y provisiones.
3.1 La provisión por deterioro se calcula con la matriz de pérdida esperada
por calificación; un aumento de provisión mayor al 15 por ciento entre
trimestres obliga a una llamada del comité de riesgo antes de publicar.
3.2 El valor en riesgo a un día se reporta al 99 por ciento de confianza y se
compara con el límite de la política: si lo supera dos días seguidos, se
escala al directorio sin esperar el informe.

4. Publicación.
4.1 El borrador circula con tres días de anticipación a los revisores; los
comentarios se responden por escrito y el informe final se publica el día 15
del mes siguiente al cierre.
4.2 Nunca se publica un dato que no venga del cierre firmado; las
estimaciones se marcan como tales con la letra E junto al valor.

5. Criterio de revisión.
5.1 Si al recalcular un fondo la diferencia contra el sistema supera el 1 por
ciento del valor del fondo, el informe completo se retira y se regenera
desde la conciliación. No hay excepción de plazo para un error de fondo.
"""

CARMEN_KNOW = """Composición de la cartera administrada al cierre del tercer trimestre

Tamaño y monedas. La cartera administrada cierra el trimestre en 84.3
millones de dólares, de los cuales el 71 por ciento está en dólares, el 19
por ciento en euros y el 10 por ciento en monedas locales andinas. La
exposición neta al dólar tras coberturas es del 66 por ciento.

Fondos. Los cinco fondos cierran así: Fondo Horizonte 32.1 millones
(variación trimestral +4.2 por ciento), Fondo Cumbres 21.7 millones
(+1.9 por ciento), Fondo Cordillera 12.8 millones (-3.1 por ciento),
Fondo Manantial 9.6 millones (+6.8 por ciento) y Fondo Páramo 8.1 millones
(-0.4 por ciento). El único fondo con variación sobre el umbral de
materialidad del protocolo es Manantial, explicado por la entrada de tres
inversionistas institucionales.

Sectores. Energía pesa el 34 por ciento de la cartera, materiales el 22,
consumo el 18, salud el 14 y tecnología el 12. La variación sectorial mayor
al 10 por ciento corresponde a tecnología (+11.2 por ciento por la
revalorización de dos posiciones) y a salud (-10.8 por ciento por la salida
de una posición farmacéutica).

Riesgo. La provisión por deterioro subió del 1.1 al 1.6 por ciento de la
cartera (aumento relativo del 45 por ciento), activando la llamada del comité
de riesgo antes de publicar. El valor en riesgo a un día al 99 por ciento fue
de 1.9 millones de dólares, por debajo del límite de política de 2.4
millones, y no se superó en ningún día del trimestre.

Rentabilidad. El retorno ponderado del trimestre fue +2.9 por ciento nominal
y +2.4 por ciento real; el retorno de doce meses quedó en +9.7 por ciento
nominal. La comisión media ponderada de administración es de 0.85 por ciento
anual.
"""

CARMEN_STYLE = """Escribo en un registro formal y sobrio, con la cifra antes que el adjetivo
y sin exclamaciones.

Prefiero el término provisión en lugar de reserva.

Prefiero el término margen de contribución en lugar de margen bruto ajustado.

Prefiero el término materialidad en lugar de umbral de relevancia.

Prefiero el término valor en riesgo en lugar de VaR.

En las notas de los informes escribo primero la causa, luego el efecto y al
final la acción, siempre en ese orden.
"""

# ---------------------------------------------------------------------------
# usuario 4: andrés — epidemiología
# ---------------------------------------------------------------------------

ANDRES_PROC = """Protocolo de revisión sistemática rápida
Procedimiento operativo personal — versión 4

1. Pregunta y criterios.
1.1 La pregunta se escribe en formato PICO antes de buscar: población,
intervención, comparador y desenlace, cada uno con su definición operativa.
1.2 Los criterios de inclusión se fijan por escrito antes de la primera
búsqueda: estudios con grupo de comparación, tamaño muestral mayor o igual a
50 participantes y desenlace medido a partir de la intervención; los estudios
de una sola rama se excluyen sin excepción.

2. Búsqueda y selección.
2.1 Se buscan al menos tres bases (PubMed, Embase y LILACS) con la misma
estrategia traducida por un documentalista, y se registra la fecha de cada
ejecución.
2.2 El tamizaje es por pares: dos revisores deciden por título y resumen de
manera independiente, y las discrepancias se resuelven por consenso con un
tercer revisor.
2.3 El acuerdo entre revisores se reporta con el coeficiente kappa; si kappa
es menor a 0.60, la fase de tamizaje se repite con el manual actualizado.

3. Extracción y calidad.
3.1 Los datos se extraen en formularios por duplicado y las diferencias se
resuelven contra el documento fuente.
3.2 El riesgo de sesgo se evalúa con la herramienta estándar de seis
dominios; un estudio con alto riesgo en dos dominios no se excluye, pero su
peso en el metanálisis se analiza en un subgrupo de sensibilidad.
3.3 La heterogeneidad estadística se cuantifica con I cuadrado; si supera el
75 por ciento, no se combina y se presenta un resumen narrativo.

4. Reporte.
4.1 El informe sigue la estructura de la declaración de transparencia y
reporta la estrategia de búsqueda completa en el apéndice.
4.2 Todo desenlace se reporta con su intervalo de confianza al 95 por ciento
y el número de estudios y de participantes que lo sustentan; sin intervalo
no hay conclusión de efecto.

5. Actualización.
5.1 La revisión se re-ejecuta si aparece un estudio nuevo con más de 500
participantes sobre la misma pregunta, o a los 24 meses, lo que ocurra
primero.
"""

ANDRES_KNOW = """Revisión completada: efectividad del tamizaje comunitario de hipertensión

Pregunta. En adultos de 40 a 75 años sin diagnóstico previo, ¿el tamizaje
comunitario de hipertensión, comparado con la atención habitual, reduce la
incidencia de eventos cardiovasculares mayores a 24 meses?

Búsqueda. Se ejecutaron las búsquedas en PubMed, Embase y LILACS el 14 de
enero de 2026; tras retirar duplicados quedaron 1,187 registros, de los que
41 pasaron a texto completo y 12 estudios cumplieron los criterios.

Estudios incluidos. Los 12 estudios suman 68,214 participantes: nueve ensayos
aleatorizados y tres estudios controlados con asignación por conglomerados.
El estudio mayor aportó 24,310 participantes en 42 comunas; el menor, 512 en
una sola comuna. El seguimiento mediano fue de 23 meses (rango 18 a 36).

Resultado principal. La incidencia de eventos cardiovasculares mayores fue
2.9 por ciento en el brazo de tamizaje frente a 3.4 por ciento en el de
atención habitual: razón de riesgos 0.85, intervalo de confianza al 95 por
ciento de 0.74 a 0.97, con I cuadrado de 41 por ciento. La reducción
absoluta del riesgo fue de 0.5 puntos porcentuales, y el número necesario a
tamizar para evitar un evento fue de 200 personas.

Subgrupos. El efecto fue mayor en los estudios con intervención dirigida por
trabajadores comunitarios de salud (razón de riesgos 0.78) y menor en los de
derivación directa al centro (0.94). El análisis de sensibilidad sin los dos
estudios con alto riesgo de sesgo dio 0.87.

Conclusión registrada. El tamizaje comunitario reduce la incidencia de
eventos mayores con evidencia de certeza moderada; la decisión de
implementarlo en dos comunas piloto se tomó con este informe como única
base cuantitativa.
"""

ANDRES_STYLE = """Escribo en un registro clínico y neutral, en tercera persona y sin
verbos de certeza absoluta.

Prefiero el término incidencia en lugar de casos nuevos.

Prefiero el término tamizaje en lugar de screening.

Prefiero el término prevalencia puntual en lugar de tasa de prevalencia.

Prefiero el término certeza de la evidencia en lugar de calidad de la
evidencia.

Cuando reporto una razón de riesgos escribo siempre el intervalo de
confianza al 95 por ciento en la misma oración.
"""

# ---------------------------------------------------------------------------
# usuario 5: luisa — lingüística y educación
# ---------------------------------------------------------------------------

LUISA_PROC = """Metodología del curso de lingüística descriptiva
Procedimiento operativo personal — semestre 2026-B

1. Diseño del curso.
1.1 Cada unidad termina en una tarea de análisis con datos reales del
español ecuatoriano: ninguna unidad evalúa solo con opción múltiple.
1.2 La rúbrica de cada tarea tiene tres criterios (identificación, análisis,
redacción) y cuatro niveles; se publica junto con la tarea, nunca después.
1.3 La clase se abre con una pregunta de discusión sin respuesta única y se
cierra con la síntesis de lo discutido redactada por los propios estudiantes.

2. Sesiones.
2.1 Cada sesión de 90 minutos reparte 20 minutos de exposición, 40 de trabajo
en grupos de cuatro y 30 de puesta en común.
2.2 Si más de un tercio del curso reprueba una tarea, la sesión siguiente
re-enseña el contenido con otro formato y la tarea se repite con datos
nuevos; la nota válida es la segunda.
2.3 La asistencia no se usa como criterio de nota; la participación se
registra por evidencias, no por presencia.

3. Evaluación.
3.1 Las pruebas escritas se califican con la rúbrica publicada y por pares:
dos docentes califican las respuestas abiertas y las diferencias mayores a un
nivel se resuelven con un tercero.
3.2 El examen final pesa el 40 por ciento de la nota, las tareas el 45 y la
síntesis de portafolio el 15.
3.3 Todo estudiante puede revisar su prueba dentro de los cinco días
posteriores a la entrega de notas; la revisión puede subir, bajar o mantener
la nota y se registra por escrito.

4. Materiales.
4.1 Los ejemplos del curso usan datos del corpus propio de 120 horas de
grabaciones transcritas, anonimizadas y con consentimiento.
4.2 Todo material ajeno se cita en la diapositiva y en la guía; las guías se
versionan por semestre y se conservan las anteriores.
"""

LUISA_KNOW = """Notas de campo sobre el español ecuatoriano de la sierra

Léxico registrado. En las grabaciones del corpus la prenda de abrigo de lana
se nombra como chompa en 89 de 96 ocurrencias, frente a chaqueta y casaca; la
bombilla eléctrica se nombra foco en 41 de 44 ocurrencias, frente a bombillo
y lámpara; el niño pequeño se nombra guagua en todas las 67 ocurrencias con
ese referente. El término colada designa la bebida de avena caliente en 38
ocurrencias y nunca el acto de lavar ropa.

Fonología. La asibilación de la erre múltiple aparece en el 71 por ciento de
los hablantes menores de 30 años y en el 33 por ciento de los mayores de 60;
el yeísmo es categórico en los menores de 40. La retención de la ese final
de sílaba es del 88 por ciento en hablantes urbanos con educación superior y
del 61 por ciento en hablantes rurales.

Morfosintaxis. El diminutivo con -ito/-ita es el más frecuente (64 por
ciento de los diminutivos), seguido de -ico/-ica (21 por ciento). El
pretérito compuesto aparece en el 18 por ciento de los contextos de pasado
perfectivo, concentrado en los hablantes mayores.

Actitudes. En las entrevistas de actitud lingüística, 61 de 80 hablantes
declaran que cambian su manera de hablar en contextos formales, y 54 de 80
asocian el uso de chompa y guagua con el registro familiar y no con el
formal. Ningún hablante del corpus etiquetó estos términos como
incorrectos, pero 17 de 80 dijeron que los evitarían en una entrevista de
trabajo.

Uso pedagógico. La unidad de variación usa estos datos como corpus de
práctica; la tarea final pide a los estudiantes describir la distribución de
un rasgo con al menos 30 ejemplos del corpus y una tabla de frecuencias.
"""

LUISA_STYLE = """Escribo en un registro cercano y didáctico, con ejemplos concretos y
sin tecnicismos sin glosar.

Prefiero el término chompa en lugar de chaqueta.

Prefiero el término guagua en lugar de bebé.

Prefiero el término foco en lugar de bombillo.

Prefiero el término rasgo en lugar de característica.

Cuando introduzco un término técnico lo gloso la primera vez entre
paréntesis y doy un ejemplo del corpus.
"""

# ---------------------------------------------------------------------------

USERS = {
    "mara": {
        "procedures": MARA_PROC, "knowledge": MARA_KNOW, "style": MARA_STYLE,
        "questions": [
            {"q": "¿Cuál es el umbral de calidad mínima de variante (QUAL) y la profundidad mínima por sitio que exige tu protocolo?", "gold": ["30", "8"]},
            {"q": "¿Cuántas variantes retuvo tu conjunto final de trabajo del pinzón serrano y con qué frecuencia mínima del alelo menor?", "gold": ["11,203", "0.01"]},
            {"q": "¿Entre qué dos poblaciones mediste el F_ST por pares más alto y cuál fue su valor?", "gold": ["Fábrega", "Chirripó", "0.048"]},
            {"q": "¿Cuántas muestras de Cerro de la Muerte analizaste y qué proporción de variantes privadas mostró esa población?", "gold": ["41", "3.1"]},
            {"q": "Según tu criterio de abandono, ¿bajo qué valor de F_ST declararías muerta la hipótesis de aislamiento y cuál fue el valor medido entre Barú y Fábrega?", "gold": ["0.01", "0.036"]},
            {"q": "¿Qué término prefiero en lugar de diversidad génica?", "gold": ["heterocigosidad esperada"]},
            {"q": "¿Qué término prefiero en lugar de historia poblacional?", "gold": ["demografía"]},
            {"q": "¿Qué término prefiero en lugar de mutación rara?", "gold": ["variante rara"]},
            {"q": "¿Cómo cierro mis correos?", "gold": ["agradecimiento"]},
            {"q": "¿Qué hago si el conjunto final baja de 5,000 variantes?", "gold": ["detengo", "reviso"]},
            {"q": "¿Qué retengo en el análisis de componentes principales y con qué método estimo el F_ST por pares?", "gold": ["10", "Weir"]},
            {"q": "¿Con qué umbral de missingness retiras sitios y con qué ventana podas por desequilibrio de ligamiento?", "gold": ["0.10", "50"]},
        ],
    },
    "julian": {
        "procedures": JULIAN_PROC, "knowledge": JULIAN_KNOW, "style": JULIAN_STYLE,
        "questions": [
            {"q": "¿Qué cobertura de pruebas exige tu protocolo antes de un despliegue y qué pasa si el cambio baja de ella?", "gold": ["80", "devuelve"]},
            {"q": "¿Cuántas filas tiene la tabla de variantes del inquilino mayor y cada cuánto se refresca la vista materializada?", "gold": ["41 millones", "15"]},
            {"q": "¿Cuál fue la causa raíz de tu último incidente mayor y cuánto duró?", "gold": ["consulta sin límite", "47"]},
            {"q": "¿Qué p95 de latencia exiges en la prueba de carga y con cuántos registros sembrados se mide?", "gold": ["300", "10,000"]},
            {"q": "¿Qué decidiste ante el exceso de cuota de almacenamiento y qué efecto tuvo?", "gold": ["cobrar", "cero"]},
            {"q": "¿Qué término prefiero en lugar de logs?", "gold": ["trazas"]},
            {"q": "¿Qué término prefieres para un servicio pequeño e independiente?", "gold": ["servicio"]},
            {"q": "¿Qué término prefiero en lugar de rolling update?", "gold": ["azul-verde"]},
            {"q": "¿Sobre qué percentil defino mis alertas y por qué?", "gold": ["p95", "promedio"]},
            {"q": "¿En qué incrementos muevo el tráfico en el despliegue azul-verde?", "gold": ["25", "50", "100"]},
            {"q": "¿Qué formato uso para los errores y qué código tiene la variante huérfana?", "gold": ["problema", "CAT-102"]},
            {"q": "¿Qué debo escribir antes de toda migración de esquema?", "gold": ["revierte", "rollback"]},
        ],
    },
    "carmen": {
        "procedures": CARMEN_PROC, "knowledge": CARMEN_KNOW, "style": CARMEN_STYLE,
        "questions": [
            {"q": "¿Cuál es la materialidad de tu informe trimestral y qué pasa cuando una variación la supera?", "gold": ["5", "nota"]},
            {"q": "¿Qué fondo superó el umbral de materialidad este trimestre y cuál fue su variación?", "gold": ["Manantial", "6.8"]},
            {"q": "¿Cuánto subió la provisión por deterioro entre trimestres y qué activó esa subida?", "gold": ["1.1", "1.6"]},
            {"q": "¿Cuál fue el valor en riesgo a un día al 99 por ciento y el límite de política?", "gold": ["1.9", "2.4"]},
            {"q": "¿Qué sectores variaron más del 10 por ciento este trimestre y con qué signo cada uno?", "gold": ["tecnología", "salud"]},
            {"q": "¿Qué término prefiero en lugar de reserva?", "gold": ["provisión"]},
            {"q": "¿Qué término prefiero en lugar de umbral de relevancia?", "gold": ["materialidad"]},
            {"q": "¿Qué término prefiero en lugar de VaR?", "gold": ["valor en riesgo"]},
            {"q": "¿En qué orden escribo las notas de los informes?", "gold": ["causa", "efecto", "acción"]},
            {"q": "¿Cuándo retiro el informe completo y lo regenero?", "gold": ["1"]},
            {"q": "¿Con qué confianza reporto el valor en riesgo y qué pasa si se supera el límite dos días seguidos?", "gold": ["99", "directorio"]},
            {"q": "¿Cuántos millones cierra la cartera y qué porcentaje está en euros?", "gold": ["84.3", "19"]},
        ],
    },
    "andres": {
        "procedures": ANDRES_PROC, "knowledge": ANDRES_KNOW, "style": ANDRES_STYLE,
        "questions": [
            {"q": "¿Cuál es el tamaño muestral mínimo de tus criterios de inclusión y qué estudios se excluyen sin excepción?", "gold": ["50", "una sola rama"]},
            {"q": "¿Cuántos participantes sumaron tus 12 estudios y cuántos aportó el estudio mayor?", "gold": ["68,214", "24,310"]},
            {"q": "¿Cuál fue la razón de riesgos de tu resultado principal y su intervalo de confianza?", "gold": ["0.85", "0.74", "0.97"]},
            {"q": "¿Cuál fue el número necesario a tamizar para evitar un evento?", "gold": ["200"]},
            {"q": "¿En qué subgrupo fue mayor el efecto y con qué razón de riesgos?", "gold": ["trabajadores", "0.78"]},
            {"q": "¿Qué término prefiero en lugar de casos nuevos?", "gold": ["incidencia"]},
            {"q": "¿Qué término prefiero en lugar de screening?", "gold": ["tamizaje"]},
            {"q": "¿Qué término prefiero en lugar de calidad de la evidencia?", "gold": ["certeza"]},
            {"q": "¿Cómo reporto toda razón de riesgos?", "gold": ["95"]},
            {"q": "¿Qué hago si el I cuadrado supera el 75 por ciento?", "gold": ["no se combina", "narrativo"]},
            {"q": "¿Con qué coeficiente mido el acuerdo entre revisores y cuándo repito el tamizaje?", "gold": ["kappa", "0.60"]},
            {"q": "¿Cuándo re-ejecutas la revisión?", "gold": ["500", "24"]},
        ],
    },
    "luisa": {
        "procedures": LUISA_PROC, "knowledge": LUISA_KNOW, "style": LUISA_STYLE,
        "questions": [
            {"q": "¿Cómo repartes los 90 minutos de una sesión de tu curso?", "gold": ["20", "40", "30"]},
            {"q": "¿En cuántas ocurrencias del corpus aparece chompa frente a chaqueta y casaca?", "gold": ["89", "96"]},
            {"q": "¿En qué porcentaje de los menores de 30 aparece la asibilación de la erre múltiple?", "gold": ["71"]},
            {"q": "¿Cuántos hablantes asocian chompa y guagua con el registro familiar?", "gold": ["54"]},
            {"q": "¿Qué pesa el examen final en tu curso y cuánto las tareas?", "gold": ["40", "45"]},
            {"q": "¿Qué término prefiero en lugar de chaqueta?", "gold": ["chompa"]},
            {"q": "¿Qué término prefiero en lugar de bebé?", "gold": ["guagua"]},
            {"q": "¿Qué término prefiero en lugar de bombillo?", "gold": ["foco"]},
            {"q": "¿Cómo presento los ejemplos de mis materiales?", "gold": ["corpus"]},
            {"q": "¿Qué haces si más de un tercio del curso reprueba una tarea?", "gold": ["re-enseña", "segunda"]},
            {"q": "¿Con cuántas horas de grabaciones cuenta tu corpus propio?", "gold": ["120"]},
            {"q": "¿Cuántos niveles tiene tu rúbrica y cuántos criterios?", "gold": ["cuatro", "tres"]},
        ],
    },
}


def generate() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    for uid, u in USERS.items():
        base = OUT / uid
        (base / "teach" / "procedures").mkdir(parents=True, exist_ok=True)
        (base / "teach" / "knowledge").mkdir(parents=True, exist_ok=True)
        (base / "teach" / "style").mkdir(parents=True, exist_ok=True)
        (base / "teach" / "procedures" / "procedimientos.md").write_text(
            u["procedures"], encoding="utf-8")
        (base / "teach" / "knowledge" / "conocimiento.md").write_text(
            u["knowledge"], encoding="utf-8")
        (base / "teach" / "style" / "estilo.md").write_text(
            u["style"], encoding="utf-8")
        policy = {"learning_policy": {
            "v": "0.1",
            "defaults": {"reference_only": True},
            "sources": {
                "teach/style": {"authored_by_user": True, "learn_style": True,
                                "learn_preference": True},
                "teach/procedures": {"authored_by_user": True, "learn_procedure": True},
                "teach/knowledge": {"authored_by_user": False, "wiki": True},
            }}}
        (base / "policy.json").write_text(json.dumps(policy, ensure_ascii=False,
                                                     indent=2), encoding="utf-8")
        (base / "questions.json").write_text(
            json.dumps({"questions": u["questions"]}, ensure_ascii=False,
                       indent=2), encoding="utf-8")
    print(f"corpus generado en {OUT}: {len(USERS)} usuarios × "
          f"{sum(len(u['questions']) for u in USERS.values())} preguntas")
    return OUT


if __name__ == "__main__":
    generate()


# ---------------------------------------------------------------------------
# v2: los seis tipos de pregunta de R13 (prerregistro sec.2.3)
# Cada usuario gana tres fuentes nuevas (actualización, discrepancia,
# borrada) y preguntas etiquetadas por tipo. La fuente 'borrada' se olvida
# en tiempo de corrida; el generador solo la escribe.
# ---------------------------------------------------------------------------

V2_SOURCES = {
    "mara": {
        "actualizacion": """Actualización de laboratorio, 3 de octubre de 2026
El F_ST entre Volcán Barú y Cerro Fábrega fue 0.036 en el primer análisis;
con los 8 individuos nuevos de Fábrega el valor corregido es 0.041.
La heterocigosidad esperada media del conjunto se recalcula en 0.291.
""",
        "nota_discrepante": """Nota metodológica de la corrida
La cobertura media del cuaderno es 21x. El informe del secuenciador indica
19x para las bibliotecas de Fábrega. Ambas fuentes están vigentes y la
discrepancia no se ha resuelto.
""",
        "borrada": """Dato provisional (borrador de 2025)
El flujo entre Chirripó y Cerro de la Muerte se estimó en 0.4 migrantes por
generación con el modelo preliminar. Este valor quedó obsoleto y no debe
usarse.
""",
        "questions": [
            {"q": "¿Qué cobertura media indica el informe del secuenciador para Fábrega?",
             "type": "simple", "gold": ["19x"]},
            {"q": "¿Cuál es la heterocigosidad esperada media recalculada del conjunto?",
             "type": "simple", "gold": ["0.291"]},
            {"q": "¿Qué F_ST corregido mediste entre Barú y Fábrega y cuántos individuos nuevos se añadieron?",
             "type": "cross", "gold": ["0.041", "8"]},
            {"q": "¿Cuál es el F_ST vigente entre Barú y Fábrega?",
             "type": "updated", "gold": ["0.041"], "old": ["0.036"]},
            {"q": "¿Qué cobertura media usas para las bibliotecas de Fábrega?",
             "type": "contradiction", "gold": ["19x"], "allow_flag": True},
            {"q": "¿Qué flujo entre Chirripó y Cerro de la Muerte estimó el modelo preliminar?",
             "type": "deleted", "gold": [], "abstain": True},
            {"q": "¿Cuál es la tasa de mutación de novo del pinzón serrano?",
             "type": "unanswerable", "gold": [], "abstain": True},
        ],
    },
    "julian": {
        "actualizacion": """Cambio de operación, 2 de octubre de 2026
El p95 histórico del listado era 268 ms; tras el cambio de grupo de
conexiones, el p95 medido de los últimos 30 días es 241 ms.
""",
        "nota_discrepante": """Nota de incidente abierta
La tasa de errores móvil de 30 días es 0.41 por ciento en el panel; el
exportador de métricas reporta 0.53 por ciento para el mismo período. La
discrepancia sigue abierta.
""",
        "borrada": """Configuración provisional (2025)
El límite de 800 peticiones por segundo por instancia se probó en una etapa
piloto y quedó descartado; el valor vigente es 400.
""",
        "questions": [
            {"q": "¿Qué p95 del listado reporta el panel de los últimos 30 días?",
             "type": "simple", "gold": ["0.53"]},
            {"q": "¿Cuál es el p95 vigente tras el cambio de grupo de conexiones?",
             "type": "updated", "gold": ["241"], "old": ["268"]},
            {"q": "¿Qué tasa de errores móvil reporta el panel y qué reporta el exportador?",
             "type": "contradiction", "gold": ["0.53"], "allow_flag": True},
            {"q": "¿Cuántas peticiones por segundo sostenía la instancia en la etapa piloto?",
             "type": "deleted", "gold": [], "abstain": True},
            {"q": "¿Qué cuota de almacenamiento tiene cada inquilino y qué p95 exige la prueba de carga?",
             "type": "cross", "gold": ["5", "300"]},
            {"q": "¿Cuál es el SLA de disponibilidad del servicio de facturación?",
             "type": "unanswerable", "gold": [], "abstain": True},
        ],
    },
    "carmen": {
        "actualizacion": """Cierre corregido, 1 de octubre de 2026
El Fondo Manantial cerró en 9.6 millones con variación de +6.8 por ciento
en el borrador; el cierre firmado lo fija en 9.9 millones, +7.4 por ciento.
""",
        "nota_discrepante": """Conciliación pendiente
El retorno ponderado del trimestre es +2.9 por ciento según el modelo; la
conciliación bancaria lo calcula en +2.6 por ciento. Pendiente de resolver.
""",
        "borrada": """Estimación preliminar (borrador interno)
La provisión por deterioro se estimó en 2.0 por ciento de la cartera en un
borrador que no se publicó; el valor vigente es 1.6.
""",
        "questions": [
            {"q": "¿Cuánto cierra Manantial según el cierre firmado?",
             "type": "updated", "gold": ["9.9"], "old": ["9.6"]},
            {"q": "¿Qué retorno trimestral calcula la conciliación bancaria?",
             "type": "simple", "gold": ["2.6"]},
            {"q": "¿Qué retorno ponderado del trimestre reportas?",
             "type": "contradiction", "gold": ["2.6"], "allow_flag": True},
            {"q": "¿Cuál era la provisión del borrador interno no publicado?",
             "type": "deleted", "gold": [], "abstain": True},
            {"q": "¿Qué variación de Manantial exige nota individual y cuál es la variación firmada?",
             "type": "cross", "gold": ["5", "7.4"]},
            {"q": "¿Cuál es el retorno proyectado del próximo trimestre?",
             "type": "unanswerable", "gold": [], "abstain": True},
        ],
    },
    "andres": {
        "actualizacion": """Actualización de la revisión, 30 de septiembre de 2026
La razón de riesgos del resultado principal era 0.85; al incorporar el
ensayo publicado en septiembre queda en 0.83, con intervalo de 0.73 a 0.95.
""",
        "nota_discrepante": """Nota de extracción abierta
El estudio mayor aporta 24,310 participantes según el formulario; el
documento fuente reporta 24,312. La diferencia está en revisión.
""",
        "borrada": """Cálculo preliminar (borrador)
El número necesario a tamizar se estimó en 180 en un borrador preliminar;
el valor publicado es 200.
""",
        "questions": [
            {"q": "¿Cuál es la razón de riesgos vigente del resultado principal?",
             "type": "updated", "gold": ["0.83"], "old": ["0.85"]},
            {"q": "¿Cuántos participantes reporta el documento fuente del estudio mayor?",
             "type": "simple", "gold": ["24,312"]},
            {"q": "¿Cuántos participantes aporta el estudio mayor?",
             "type": "contradiction", "gold": ["24,312"], "allow_flag": True},
            {"q": "¿Qué número necesario a tamizar daba el borrador preliminar?",
             "type": "deleted", "gold": [], "abstain": True},
            {"q": "¿Qué razón de riesgos vigente reportas y con qué intervalo?",
             "type": "cross", "gold": ["0.83", "0.73", "0.95"]},
            {"q": "¿Cuál fue la adherencia al tamizaje en las comunas piloto?",
             "type": "unanswerable", "gold": [], "abstain": True},
        ],
    },
    "luisa": {
        "actualizacion": """Corrección de transcripción, 28 de septiembre de 2026
La retención de la ese final en hablantes rurales era 61 por ciento; la
revisión de las transcripciones la corrige a 58 por ciento.
""",
        "nota_discrepante": """Nota de campo abierta
El corpus registra 41 ocurrencias de foco; el diario de campo anota 44.
Ambas anotaciones están vigentes.
""",
        "borrada": """Dato provisional (piloto)
En el piloto de 2024 se anotó que la asibilación de la erre aparecía en el
80 por ciento de los menores de 30; el valor del corpus es 71.
""",
        "questions": [
            {"q": "¿Cuál es la retención corregida de la ese final en hablantes rurales?",
             "type": "updated", "gold": ["58"], "old": ["61"]},
            {"q": "¿Cuántas ocurrencias de foco anota el diario de campo?",
             "type": "simple", "gold": ["44"]},
            {"q": "¿Cuántas ocurrencias de foco tiene tu corpus?",
             "type": "contradiction", "gold": ["44"], "allow_flag": True},
            {"q": "¿Qué porcentaje de asibilación anotó el piloto de 2024?",
             "type": "deleted", "gold": [], "abstain": True},
            {"q": "¿Qué porcentaje de retención corrigió la revisión y cuál era el valor previo?",
             "type": "cross", "gold": ["58", "61"]},
            {"q": "¿Cuál es la frecuencia del voseo en tu corpus?",
             "type": "unanswerable", "gold": [], "abstain": True},
        ],
    },
}


def generate_v2() -> None:
    base = OUT
    for uid, v2 in V2_SOURCES.items():
        kdir = base / uid / "teach" / "knowledge"
        for name in ("actualizacion", "nota_discrepante", "borrada"):
            (kdir / f"{name}.md").write_text(v2[name], encoding="utf-8")
        (base / uid / "questions_v2.json").write_text(
            json.dumps({"questions": v2["questions"]}, ensure_ascii=False,
                       indent=2), encoding="utf-8")
    n = sum(len(v["questions"]) for v in V2_SOURCES.values())
    print(f"v2 generado: {len(V2_SOURCES)} usuarios × fuentes nuevas, "
          f"{n} preguntas etiquetadas por tipo")





# ---------------------------------------------------------------------------
# v3: subconjunto de corpus LARGO (prerregistro R13, el régimen donde la
# compresión de la wiki puede pagar): un documento por usuario con los
# hechos enterrados más allá del presupuesto de 200 palabras del brazo A1.
# ---------------------------------------------------------------------------

V3_LONG = {
    "mara": {
        "doc": """Informe anual del proyecto de pinzones, año 2026

Sección 1. Resumen del año. El año estuvo dedicado a consolidar la
colección de referencia y a repetir los análisis con el protocolo
actualizado. Se visitaron los cuatro sitios de la cordillera en dos
temporadas y se completó el anillado de los individuos pendientes. La
logística de campo consumió la mayor parte del presupuesto del primer
semestre y no hubo incidentes de equipo.

Sección 2. Estado de las colecciones. El herbario asociado creció en 212
pliegos y el banco de tejidos incorporó 88 muestras nuevas, la mayoría de
Cerro Fábrega. Las extracciones de ADN se estandarizaron con el kit de
sílice y el rendimiento medio subió de 41 a 57 nanogramos por microlitro.
Las bibliotecas de ddRAD se construyeron en cuatro tandas de 24 muestras
y el control de calidad descartó 9 bibliotecas por baja complejidad, una
menos que el año anterior.

Sección 3. Re-análisis de la estructura. La matriz de genotipos final del
año tiene 11,204 variantes bialélicas tras el filtrado, una más que la
versión del año pasado por la inclusión de los individuos nuevos. El
primer eje del análisis de componentes principales explica el 19 por
ciento de la varianza y separa Fábrega; el segundo, el 8 por ciento. La
heterocigosidad esperada media sube a 0.293 con los nuevos individuos.

Sección 4. Cobertura y profundidad. La cobertura media por biblioteca
quedó en 22x, con el sitio de Fábrega en 18x por la calidad variable de
dos extracciones tardías. La profundidad mínima aceptada por sitio fue
de 8 lecturas en el 80 por ciento de las muestras, como exige el
protocolo, y todos los sitios la cumplieron salvo dos bibliotecas de
Barú que se repitieron desde la extracción.

Sección 5. Hallazgos del año. El hallazgo principal es demográfico: la
población de Cerro de la Muerte mostró una expansión reciente con una
señal de cuello de botella hace 7,200 generaciones, inferida del espectro
de frecuencias. El flujo estimado entre Chirripó y Cerro de la Muerte
sube a 1.3 migrantes por generación en el modelo conjunto. El F_ST
corregido entre Barú y Fábrega queda en 0.041, y el valor medio ponderado
de la matriz completa en 0.029.

Sección 6. Datos abiertos y calendario. Los genotipos se publicarán en
el repositorio del proyecto con embargo hasta la publicación del
manuscrito. El manuscrito principal se someterá en el primer trimestre
del año próximo con las cuatro poblaciones y el análisis de demografía.
""",
        "questions": [
            {"q": "¿Cuántas variantes bialélicas tiene la matriz final de este año?",
             "type": "simple", "gold": ["11,204"]},
            {"q": "¿Qué rendimiento medio de extracción de ADN lograste este año?",
             "type": "simple", "gold": ["57"]},
            {"q": "¿Cuántos pliegos incorporó el herbario y cuántas muestras el banco de tejidos?",
             "type": "cross", "gold": ["212", "88"]},
            {"q": "¿Qué señal demográfica mostró Cerro de la Muerte y hace cuántas generaciones?",
             "type": "cross", "gold": ["cuello", "7,200"]},
            {"q": "¿Cuál es la heterocigosidad esperada media con los individuos nuevos?",
             "type": "updated", "gold": ["0.293"], "old": ["0.291"]},
            {"q": "¿Cuántas bibliotecas se repitieron desde la extracción este año?",
             "type": "simple", "gold": ["dos", "2"]},
            {"q": "¿Cuándo se someterá el manuscrito principal?",
             "type": "simple", "gold": ["primer trimestre"]},
        ],
    },
    "julian": {
        "doc": """Memoria anual del sistema de catálogo, 2026

Introducción. La memoria anual resume los cambios del año, los números
de operación y las decisiones tomadas. El sistema cumplió su tercer año
en producción y cerró con cuatro servicios, un canal de mensajería y
cuarenta y un consumidores registrados.

Crecimiento. El catálogo incorporó 1,9 millones de variantes nuevas y
cerró con 43 millones de filas en la tabla de variantes del inquilino
mayor. El número de inquilinos activos pasó de 128 a 155. Las vistas
materializadas se refrescan cada 15 minutos y el retraso máximo observado
entre escritura y lectura fue de 4 minutos en el peor incidente del año.

Incidentes. El año tuvo tres incidentes mayores. El primero duró 47
minutos y su causa raíz fue una consulta sin límite; se corrigió con
paginación de cursores. El segundo duró 22 minutos por saturación del
grupo de conexiones y se corrigió con límites por inquilino. El tercero
duró 9 minutos y fue un despliegue revertido por el procedimiento
azul-verde.

Operación. El p95 del listado cerró el año en 244 milisegundos tras el
ajuste del grupo de conexiones, por debajo del objetivo de 300. La tasa
de errores móvil de 30 días quedó en 0.38 por ciento. La cuota de
almacenamiento por inquilino sigue en 5 gigabytes y el exceso se cobra:
la facturación por exceso recaudó 12,400 dólares en el año.

Decisiones. La decisión de idempotencia en los consumidores se mantuvo;
los duplicados de eventos bajaron a 0.2 por ciento de las entregas. Se
adoptó el formato de problema de la IETF para todos los errores y se
añadieron dos códigos: CAT-104 precio sin vigencia y CAT-105 variante
inactiva. La migración a UUID versión 7 se completó en el catálogo.

Calendario. El próximo año se planifica la partición de la tabla de
pedidos y la retirada del servicio de facturación heredado, prevista para
el tercer trimestre.
""",
        "questions": [
            {"q": "¿Cuántas filas tiene ahora la tabla de variantes del inquilino mayor?",
             "type": "updated", "gold": ["43 millones"], "old": ["41 millones"]},
            {"q": "¿Cuántos inquilinos activos hay al cierre del año?",
             "type": "simple", "gold": ["155"]},
            {"q": "¿Cuánto duró el segundo incidente mayor y cuál fue su causa?",
             "type": "cross", "gold": ["22", "conexiones"]},
            {"q": "¿Cuál es el p95 del listado al cierre del año?",
             "type": "updated", "gold": ["244"], "old": ["241"]},
            {"q": "¿Cuánto recaudó la facturación por exceso de cuota?",
             "type": "simple", "gold": ["12,400"]},
            {"q": "¿Qué dos códigos de error nuevos se añadieron?",
             "type": "cross", "gold": ["CAT-104", "CAT-105"]},
            {"q": "¿Cuándo se retira el servicio de facturación heredado?",
             "type": "simple", "gold": ["tercer trimestre"]},
        ],
    },
    "carmen": {
        "doc": """Memoria anual de la cartera administrada, 2026

Panorama. La memoria anual cierra el ejercicio con la cartera en 88.1
millones de dólares, frente a los 84.3 del cierre del tercer trimestre.
El año aportó tres inversionistas institucionales nuevos y la salida de
uno antiguo.

Fondos. El cierre anual por fondo es: Horizonte 33.5 millones, Cumbres
22.0, Cordillera 12.1, Manantial 10.4 y Páramo 10.1. La variación anual
del conjunto fue de +8.2 por ciento nominal. Manantial fue el fondo con
mayor crecimiento del año (+11.3 por ciento) por la entrada institucional
del segundo semestre.

Sectores. Al cierre, energía pesa el 33 por ciento, materiales el 21,
consumo el 19, salud el 15 y tecnología el 12. La rotación del año redujo
salud del 18 al 15 por ciento y subió consumo del 16 al 19.

Riesgo. La provisión por deterioro cerró el año en 1.4 por ciento de la
cartera, tras el pico de 1.6 del tercer trimestre. El valor en riesgo a
un día al 99 por ciento promedió 1.7 millones y nunca superó el límite de
2.4. El comité de riesgo se reunió cuatro veces en el año, dos de ellas
por la variación de provisiones.

Rentabilidad. El retorno del año fue +9.1 por ciento nominal y +7.9 por
ciento real. La comisión media ponderada bajó a 0.80 por ciento anual
tras la renegociación con dos fondos.

Calendario. El próximo ejercicio se planifica la apertura de un sexto
fondo de renta fija andina y la automatización del informe trimestral,
prevista para el segundo trimestre.
""",
        "questions": [
            {"q": "¿En cuánto cierra la cartera este año?",
             "type": "updated", "gold": ["88.1"], "old": ["84.3"]},
            {"q": "¿Cuál fue la variación anual de Manantial?",
             "type": "simple", "gold": ["11.3"]},
            {"q": "¿Qué sector bajó del 18 al 15 por ciento y cuál subió del 16 al 19?",
             "type": "cross", "gold": ["salud", "consumo"]},
            {"q": "¿En cuánto cerró la provisión por deterioro?",
             "type": "updated", "gold": ["1.4"], "old": ["1.6"]},
            {"q": "¿Cuál fue el retorno real del año?",
             "type": "simple", "gold": ["7.9"]},
            {"q": "¿Cuántas veces se reunió el comité de riesgo y por qué dos de ellas?",
             "type": "cross", "gold": ["cuatro", "provisiones"]},
            {"q": "¿Cuándo se automatiza el informe trimestral?",
             "type": "simple", "gold": ["segundo trimestre"]},
        ],
    },
    "andres": {
        "doc": """Memoria anual del programa de tamizaje, 2026

Resumen. La memoria anual del programa comunitario de hipertensión cubre
el segundo año de operación en 42 comunas. El año sumó 5,180 tamizajes
nuevos y la cobertura poblacional llegó al 63 por ciento de los adultos
de 40 a 75 años.

Resultados. La incidencia de eventos cardiovasculares mayores a 24 meses
fue de 2.7 por ciento en el brazo de tamizaje frente a 3.3 en el de
atención habitual, con una razón de riesgos de 0.82 y un intervalo de
0.72 a 0.94. El número necesario a tamizar para evitar un evento bajó a
180 personas con los datos del año.

Subgrupos. El efecto sigue siendo mayor con trabajadores comunitarios
(razón de riesgos 0.76) y menor con derivación directa (0.93). El
análisis de sensibilidad sin los dos estudios de alto riesgo da 0.86.

Logística. El programa entrenó a 214 trabajadores comunitarios nuevos y
retuvo al 81 por ciento de los del año anterior. El costo por tamizaje
bajó de 14.2 a 11.8 dólares. Las dos comunas piloto del primer año se
mantienen como sitios centinela.

Calendario. El tercer año se planifica la expansión a 12 comunas nuevas
y la evaluación económica formal, prevista para el cuarto trimestre.
""",
        "questions": [
            {"q": "¿Cuántos tamizajes nuevos sumó el año?",
             "type": "simple", "gold": ["5,180"]},
            {"q": "¿Cuál es la razón de riesgos vigente a 24 meses?",
             "type": "updated", "gold": ["0.82"], "old": ["0.83"]},
            {"q": "¿Cuál es el número necesario a tamizar con los datos del año?",
             "type": "updated", "gold": ["180"], "old": ["200"]},
            {"q": "¿Cuántos trabajadores nuevos entrenó el programa y cuántos retuvo?",
             "type": "cross", "gold": ["214", "81"]},
            {"q": "¿En cuánto bajó el costo por tamizaje?",
             "type": "simple", "gold": ["11.8"]},
            {"q": "¿Cuántas comunas nuevas se suman el tercer año y cuándo es la evaluación económica?",
             "type": "cross", "gold": ["12", "cuarto trimestre"]},
            {"q": "¿Qué porcentaje de cobertura poblacional alcanzó el programa?",
             "type": "simple", "gold": ["63"]},
        ],
    },
    "luisa": {
        "doc": """Memoria anual del curso de lingüística descriptiva, 2026

Resumen. La memoria anual cubre el tercer año del curso con cuatro
secciones y 96 estudiantes matriculados en dos paralelos. El año
incorporó el corpus propio ampliado a 160 horas de grabaciones.

Corpus. La revisión de transcripciones del año corrigió 214 segmentos y
añadió 18 entrevistas nuevas. La retención de la ese final en hablantes
rurales quedó en 57 por ciento tras la segunda revisión. El diminutivo
más frecuente sigue siendo -ito/-ita con el 66 por ciento.

Hallazgos. El hallazgo del año es actitudinal: 67 de 90 hablantes
entrevistados declaran alternancia de código según el contexto formal.
La asociación de chompa y guagua con el registro familiar subió a 61 de
90. Ningún hablante etiquetó los términos como incorrectos.

Evaluación. La tasa de aprobación del curso subió al 88 por ciento. La
tarea de variación se repitió en un paralelo tras superar el tercio de
reprobados, como exige la metodología, y la nota válida fue la segunda
en todos los casos.

Calendario. El próximo semestre se planifica la digitalización del
portafolio y la incorporación de la unidad de contacto lingüístico,
prevista para el segundo bimestre.
""",
        "questions": [
            {"q": "¿Cuántas horas de grabaciones tiene ahora el corpus propio?",
             "type": "updated", "gold": ["160"], "old": ["120"]},
            {"q": "¿En cuánto quedó la retención de la ese final en hablantes rurales tras la segunda revisión?",
             "type": "updated", "gold": ["57"], "old": ["58"]},
            {"q": "¿Cuántos hablantes declaran alternancia de código según el contexto?",
             "type": "simple", "gold": ["67"]},
            {"q": "¿Cuántos segmentos corrigió la revisión y cuántas entrevistas añadió?",
             "type": "cross", "gold": ["214", "18"]},
            {"q": "¿Cuál es la tasa de aprobación del curso este año?",
             "type": "simple", "gold": ["88"]},
            {"q": "¿Cuándo se incorpora la unidad de contacto lingüístico?",
             "type": "simple", "gold": ["segundo bimestre"]},
            {"q": "¿Qué porcentaje del diminutivo sigue siendo -ito/-ita?",
             "type": "simple", "gold": ["66"]},
        ],
    },
}


def generate_v3() -> None:
    for uid, v3 in V3_LONG.items():
        base = OUT / uid
        ldir = base / "teach" / "knowledge"
        (ldir / "memoria_anual.md").write_text(v3["doc"], encoding="utf-8")
        (base / "questions_v3.json").write_text(
            json.dumps({"questions": v3["questions"]}, ensure_ascii=False,
                       indent=2), encoding="utf-8")
    n = sum(len(v["questions"]) for v in V3_LONG.values())
    print(f"v3 generado: {len(V3_LONG)} documentos largos, {n} preguntas "
          "con respuestas enterradas")


if __name__ == "__main__":
    generate()
    generate_v2()
    generate_v3()

# ============================================================
# v4 — ampliación para la CONFIRMATORIA de R13 (Enmienda 8):
# ≥30 preguntas por tipo. Borrada extendida (5 hechos de borrador por
# usuario), actualizacion extendida (3 pares), revision_interna nueva
# (5 contradicciones), 3-4 cruzadas y 5 sin respuesta por usuario.
# ============================================================

EXTRA4 = {
    "mara": {
        "borrada": (
            "Dato provisional (borrador de 2025)\n"
            "El flujo entre Chirripó y Cerro de la Muerte se estimó en 0.4 migrantes por\n"
            "generación con el modelo preliminar. Este valor quedó obsoleto y no debe\n"
            "usarse.\n"
            "El tamaño efectivo preliminar de la población de Chirripó fue 311 individuos.\n"
            "La diversidad nucleotídica preliminar del conjunto fue 0.0072.\n"
            "El borrador atribuía el exceso de variantes privadas de Cerro de la Muerte a 9\n"
            "loci candidatos.\n"
            "El aislamiento reproductivo preliminar de Fábrega se cuantificó en 0.19.\n"
            "La tasa de endogamia preliminar del conjunto se estimó en 0.03.\n"
        ),
        "actualizacion": (
            "El umbral QUAL mínimo sube de 30 a 40 tras la recalibración de octubre.\n"
            "La profundidad mínima por sitio sube de 8 a 12 lecturas.\n"
            "El umbral de missingness para retirar sitios baja de 0.10 a 0.08.\n"
            "El F_ST por pares más alto entre Fábrega y Chirripó pasa de 0.048 a 0.052 con los individuos nuevos de Chirripó.\n"
        ),
        "revision": (
            "# Revisión interna del laboratorio (sin fecha)\n"
            "El umbral de missingness para retirar sitios es 0.20.\n"
            "El F_ST entre Barú y Fábrega quedó en 0.09 en la última corrida.\n"
            "El conjunto final de trabajo retuvo 9,800 variantes.\n"
            "La frecuencia mínima del alelo menor exigida es 0.02.\n"
            "Las muestras de Cerro de la Muerte analizadas fueron 52.\n"
        ),
        "deleted": [
            {"q": "¿Qué tamaño efectivo preliminar estimaste para la población de Chirripó?", "abstain": True},
            {"q": "¿Qué diversidad nucleotídica preliminar calculaste para el conjunto?", "abstain": True},
            {"q": "¿A cuántos loci atribuía el borrador el exceso de variantes privadas de Cerro de la Muerte?", "abstain": True},
            {"q": "¿En cuánto cuantificó el borrador el aislamiento reproductivo de Fábrega?", "abstain": True},
            {"q": "¿Qué tasa de endogamia preliminar estimó el borrador para el conjunto?", "abstain": True},
        ],
        "updated": [
            {"q": "¿Cuál es el umbral QUAL mínimo vigente y cuál era antes de la recalibración?", "gold": ["40", "30"]},
            {"q": "¿Cuál es la profundidad mínima por sitio vigente y cuál era antes?", "gold": ["12", "8"]},
            {"q": "¿Cuál es el umbral de missingness vigente y cuál era antes?", "gold": ["0.08", "0.10"]},
            {"q": "¿Cuál es el F_ST vigente entre Fábrega y Chirripó y cuál era antes?", "gold": ["0.052", "0.048"]},
        ],
        "contradiction": [
            {"q": "Según tus fuentes, ¿cuál es el umbral de missingness para retirar sitios y hay fuentes que discrepan?", "contradict": True, "pair": ["0.08", "0.20"]},
            {"q": "Según tus fuentes, ¿cuál es el F_ST entre Barú y Fábrega y hay fuentes que discrepan?", "contradict": True, "pair": ["0.041", "0.09"]},
            {"q": "Según tus fuentes, ¿cuántas variantes retuvo el conjunto final y hay fuentes que discrepan?", "contradict": True, "pair": ["11,203", "9,800"]},
            {"q": "Según tus fuentes, ¿qué frecuencia mínima del alelo menor exiges y hay fuentes que discrepan?", "contradict": True, "pair": ["0.01", "0.02"]},
            {"q": "Según tus fuentes, ¿cuántas muestras de Cerro de la Muerte analizaste y hay fuentes que discrepan?", "contradict": True, "pair": ["41", "52"]},
        ],
        "cross": [
            {"q": "¿Cuántas variantes retuvo tu conjunto final de trabajo y qué umbral QUAL mínimo exige tu protocolo?", "gold": ["11,203", "40"]},
            {"q": "¿Qué valor de F_ST mediste entre Barú y Fábrega y bajo qué valor declararías muerta la hipótesis de aislamiento?", "gold": ["0.041", "0.01"]},
            {"q": "¿Cuántas muestras de Cerro de la Muerte analizaste y con qué ventana podas por desequilibrio de ligamiento?", "gold": ["41", "50"]},
            {"q": "¿Qué proporción de variantes privadas mostró Cerro de la Muerte y cuántas variantes mínimas exige tu conjunto final?", "gold": ["3.1", "5,000"]},
        ],
        "simple": [{"q": "¿Qué proporción de variantes privadas mostró Cerro de la Muerte?", "gold": ["3.1"]},
                   {"q": "¿Cuántas muestras de Cerro de la Muerte analizaste?", "gold": ["41"]},
                   {"q": "¿Con qué frecuencia mínima del alelo menor retuviste las variantes del pinzón serrano?", "gold": ["0.01"]}],
        "no_answer": [
            "¿Cuál fue el índice de Shannon del bosque nuboso en tu último muestreo de vegetación?",
            "¿Qué cebadores usaste para amplificar el intrón 7 del gen de la rodopsina?",
            "¿Cuál fue la tasa de captura-recaptura del pinzón serrano en 2026?",
            "¿Qué porcentaje de juveniles marcaste con anillas metálicas?",
            "¿Cuántos transectos de vegetación levantaste en Chirripó?",
        ],
    },
    "julian": {
        "borrada": (
            'Configuración provisional (2025)\nEl límite de 800 peticiones por segundo por instancia se probó en una etapa\npiloto y quedó descartado; el valor vigente es 400.\n'
            "Dato provisional (borrador de 2025)\n"
            "El borrador proponía un p95 de latencia de 180 ms para la API de consultas.\n"
            "La vista materializada preliminar se refrescaba cada 45 minutos.\n"
            "El borrador sembraba las pruebas de carga con 4,500 registros.\n"
            "El límite preliminar de la cuota de almacenamiento era 2 TB.\n"
            "El borrador fijaba el despliegue azul-verde en incrementos de 15 por ciento.\n"
        ),
        "actualizacion": (
            "La cobertura mínima de pruebas sube de 80 a 85 por ciento tras el incidente de octubre.\n"
            "El p95 de latencia exigido baja de 300 a 250 ms.\n"
            "Los registros sembrados en la prueba de carga suben de 10,000 a 12,000.\n"
        ),
        "revision": (
            "# Revisión interna de infraestructura (sin fecha)\n"
            "La cobertura mínima de pruebas es 70 por ciento.\n"
            "La tabla de variantes del inquilino mayor tiene 38 millones de filas.\n"
            "El p95 de latencia exigido es 350 ms.\n"
            "La vista materializada se refresca cada 30 minutos.\n"
            "El despliegue azul-verde mueve el tráfico en incrementos de 40 por ciento.\n"
        ),
        "deleted": [
            {"q": "¿Qué p95 de latencia proponía el borrador para la API de consultas?", "abstain": True},
            {"q": "¿Cada cuánto se refrescaba la vista materializada según el borrador?", "abstain": True},
            {"q": "¿Con cuántos registros sembraba el borrador las pruebas de carga?", "abstain": True},
            {"q": "¿Qué límite de cuota de almacenamiento fijaba el borrador?", "abstain": True},
            {"q": "¿En qué incrementos movía el tráfico el despliegue según el borrador?", "abstain": True},
        ],
        "updated": [
            {"q": "¿Cuál es la cobertura mínima de pruebas vigente y cuál era antes del incidente?", "gold": ["85", "80"]},
            {"q": "¿Cuál es el p95 de latencia exigido vigente y cuál era antes?", "gold": ["250", "300"]},
            {"q": "¿Con cuántos registros siembras la prueba de carga y con cuántos lo hacías antes?", "gold": ["12,000", "10,000"]},
        ],
        "contradiction": [
            {"q": "Según tus fuentes, ¿cuál es la cobertura mínima de pruebas y hay fuentes que discrepan?", "contradict": True, "pair": ["85", "70"]},
            {"q": "Según tus fuentes, ¿cuántas filas tiene la tabla del inquilino mayor y hay fuentes que discrepan?", "contradict": True, "pair": ["41 millones", "38 millones"]},
            {"q": "Según tus fuentes, ¿qué p95 de latencia exiges y hay fuentes que discrepan?", "contradict": True, "pair": ["250", "350"]},
            {"q": "Según tus fuentes, ¿cada cuánto se refresca la vista materializada y hay fuentes que discrepan?", "contradict": True, "pair": ["15", "30"]},
            {"q": "Según tus fuentes, ¿en qué incrementos mueves el tráfico en el despliegue y hay fuentes que discrepan?", "contradict": True, "pair": ["25", "40"]},
        ],
        "cross": [
            {"q": "¿Cuántas filas tiene la tabla del inquilino mayor y qué p95 de latencia exiges en la prueba de carga?", "gold": ["41 millones", "250"]},
            {"q": "¿Qué formato usas para los errores y con cuántos registros siembras la prueba de carga?", "gold": ["problema", "12,000"]},
            {"q": "¿Qué código tiene la variante huérfana y cada cuánto se refresca la vista materializada?", "gold": ["CAT-102", "15"]},
        ],
        "simple": [{"q": "¿Cuánto duró tu último incidente mayor?", "gold": ["47"]},
                   {"q": "¿Qué p95 de latencia exiges en la prueba de carga?", "gold": ["250"]},
                   {"q": "¿Cada cuánto se refresca la vista materializada?", "gold": ["15"]}],
        "no_answer": [
            "¿Cuántos nodos tiene tu clúster de Kafka de producción?",
            "¿Qué versión de PostgreSQL corre tu réplica de lectura?",
            "¿Cuál fue el presupuesto de infraestructura del trimestre?",
            "¿Qué proveedor de DNS usas para el dominio de producción?",
            "¿Cuántos ingenieros rotan la guardia de disponibilidad?",
        ],
    },
    "carmen": {
        "borrada": (
            'Estimación preliminar (borrador interno)\nLa provisión por deterioro se estimó en 2.0 por ciento de la cartera en un\nborrador que no se publicó; el valor vigente es 1.6.\n'
            "Dato provisional (borrador de 2025)\n"
            "El borrador fijaba la materialidad del informe trimestral en 3 por ciento.\n"
            "La provisión por deterioro preliminar del trimestre fue 0.6 millones.\n"
            "El valor en riesgo preliminar a un día fue 2.6 millones.\n"
            "El borrador reportaba la cartera en 79.5 millones.\n"
            "El porcentaje de la cartera en euros según el borrador era 24.\n"
        ),
        "actualizacion": (
            "La materialidad del informe trimestral sube de 5 a 6 por ciento.\n"
            "El límite de política del valor en riesgo baja de 2.4 a 2.2 millones.\n"
            "La cartera cierra el trimestre en 86.1 millones tras la revisión.\n"
        ),
        "revision": (
            "# Revisión interna de tesorería (sin fecha)\n"
            "La materialidad del informe trimestral es 4 por ciento.\n"
            "El fondo Manantial subió 9.4 por ciento este trimestre.\n"
            "El valor en riesgo a un día al 99 por ciento fue 1.2 millones.\n"
            "La cartera cierra en 82.7 millones.\n"
            "El porcentaje de la cartera en euros es 15.\n"
        ),
        "deleted": [
            {"q": "¿Qué materialidad fijaba el borrador para el informe trimestral?", "abstain": True},
            {"q": "¿Cuánto fue la provisión por deterioro preliminar del trimestre según el borrador?", "abstain": True},
            {"q": "¿Qué valor en riesgo preliminar a un día reportaba el borrador?", "abstain": True},
            {"q": "¿En cuánto reportaba el borrador la cartera?", "abstain": True},
            {"q": "¿Qué porcentaje de la cartera en euros reportaba el borrador?", "abstain": True},
        ],
        "updated": [
            {"q": "¿Cuál es la materialidad vigente del informe trimestral y cuál era antes?", "gold": ["6", "5"]},
            {"q": "¿Cuál es el límite de política vigente del valor en riesgo y cuál era antes?", "gold": ["2.2", "2.4"]},
            {"q": "¿En cuánto cierra la cartera el trimestre y en cuánto cerraba antes de la revisión?", "gold": ["86.1", "84.3"]},
        ],
        "contradiction": [
            {"q": "Según tus fuentes, ¿cuál es la materialidad del informe trimestral y hay fuentes que discrepan?", "contradict": True, "pair": ["6", "4"]},
            {"q": "Según tus fuentes, ¿cuánto subió el fondo Manantial este trimestre y hay fuentes que discrepan?", "contradict": True, "pair": ["6.8", "9.4"]},
            {"q": "Según tus fuentes, ¿cuál fue el valor en riesgo a un día y hay fuentes que discrepan?", "contradict": True, "pair": ["1.9", "1.2"]},
            {"q": "Según tus fuentes, ¿en cuánto cierra la cartera y hay fuentes que discrepan?", "contradict": True, "pair": ["86.1", "82.7"]},
            {"q": "Según tus fuentes, ¿qué porcentaje de la cartera está en euros y hay fuentes que discrepan?", "contradict": True, "pair": ["19", "15"]},
        ],
        "cross": [
            {"q": "¿Cuál es la materialidad vigente del informe y cuánto subió la provisión por deterioro entre trimestres?", "gold": ["6", "1.1", "1.6"]},
            {"q": "¿Qué fondo superó el umbral de materialidad y en qué orden escribes las notas de los informes?", "gold": ["Manantial", "causa"]},
            {"q": "¿En cuánto cierra la cartera y qué porcentaje está en euros?", "gold": ["86.1", "19"]},
        ],
        "simple": [{"q": "¿Cuánto subió la provisión por deterioro entre trimestres?", "gold": ["1.1", "1.6"]},
                   {"q": "¿Qué sectores variaron más del 10 por ciento este trimestre?", "gold": ["tecnología", "salud"]},
                   {"q": "¿Qué porcentaje de la cartera está en euros?", "gold": ["19"]}],
        "no_answer": [
            "¿Cuántos analistas integran el comité de inversiones?",
            "¿Qué banco custodio usa la cartera internacional?",
            "¿Cuál fue el costo de transacción medio del trimestre?",
            "¿Qué calificación crediticia tiene el fondo Manantial?",
            "¿Cuántas reuniones del directorio hubo este trimestre?",
        ],
    },
    "andres": {
        "borrada": (
            'Cálculo preliminar (borrador)\nEl número necesario a tamizar se estimó en 180 en un borrador preliminar;\nel valor publicado es 200.\n'
            "Dato provisional (borrador de 2025)\n"
            "El borrador fijaba el tamaño muestral mínimo en 40 participantes.\n"
            "La razón de riesgos preliminar del resultado principal fue 0.79.\n"
            "El número necesario a tamizar preliminar fue 240.\n"
            "El borrador reportaba 61,500 participantes en los 12 estudios.\n"
            "El efecto en trabajadores según el borrador tenía una razón de riesgos de 0.72.\n"
        ),
        "actualizacion": (
            "El tamaño muestral mínimo de los criterios de inclusión sube de 50 a 60 participantes.\n"
            "El estudio mayor aportó 24,310 participantes; tras la auditoría se recontó en 24,505.\n"
            "El número necesario a tamizar se recalcula de 200 a 210.\n"
        ),
        "revision": (
            "# Revisión interna del protocolo (sin fecha)\n"
            "El tamaño muestral mínimo de inclusión es 45 participantes.\n"
            "Los 12 estudios sumaron 70,100 participantes.\n"
            "La razón de riesgos del resultado principal fue 0.88.\n"
            "El número necesario a tamizar fue 180.\n"
            "El efecto en trabajadores tuvo una razón de riesgos de 0.66.\n"
        ),
        "deleted": [
            {"q": "¿Qué tamaño muestral mínimo fijaba el borrador para los criterios de inclusión?", "abstain": True},
            {"q": "¿Qué razón de riesgos preliminar reportaba el borrador para el resultado principal?", "abstain": True},
            {"q": "¿Qué número necesario a tamizar preliminar calculó el borrador?", "abstain": True},
            {"q": "¿Cuántos participantes reportaba el borrador en los 12 estudios?", "abstain": True},
            {"q": "¿Qué razón de riesgos atribuía el borrador al efecto en trabajadores?", "abstain": True},
        ],
        "updated": [
            {"q": "¿Cuál es el tamaño muestral mínimo vigente de los criterios de inclusión y cuál era antes?", "gold": ["60", "50"]},
            {"q": "¿Cuántos participantes aportó el estudio mayor tras la auditoría y cuántos antes?", "gold": ["24,505", "24,310"]},
            {"q": "¿Cuál es el número necesario a tamizar vigente y cuál era antes?", "gold": ["210", "200"]},
        ],
        "contradiction": [
            {"q": "Según tus fuentes, ¿cuál es el tamaño muestral mínimo de inclusión y hay fuentes que discrepan?", "contradict": True, "pair": ["60", "45"]},
            {"q": "Según tus fuentes, ¿cuántos participantes sumaron los 12 estudios y hay fuentes que discrepan?", "contradict": True, "pair": ["68,214", "70,100"]},
            {"q": "Según tus fuentes, ¿cuál fue la razón de riesgos del resultado principal y hay fuentes que discrepan?", "contradict": True, "pair": ["0.85", "0.88"]},
            {"q": "Según tus fuentes, ¿cuál es el número necesario a tamizar y hay fuentes que discrepan?", "contradict": True, "pair": ["210", "180"]},
            {"q": "Según tus fuentes, ¿qué razón de riesgos tuvo el efecto en trabajadores y hay fuentes que discrepan?", "contradict": True, "pair": ["0.78", "0.66"]},
        ],
        "cross": [
            {"q": "¿Cuántos participantes sumaron tus 12 estudios y qué coeficiente mides el acuerdo entre revisores?", "gold": ["68,214", "kappa"]},
            {"q": "¿En qué subgrupo fue mayor el efecto y con qué razón de riesgos se recalculó el número necesario a tamizar?", "gold": ["trabajadores", "210"]},
            {"q": "¿Cuándo re-ejecutas la revisión y qué tamaño muestral mínimo exigen tus criterios?", "gold": ["500", "60"]},
        ],
        "simple": [{"q": "¿Cuántos participantes aportó el estudio mayor tras la auditoría?", "gold": ["24,505"]},
                   {"q": "¿Qué coeficiente mides el acuerdo entre revisores?", "gold": ["kappa"]}],
        "no_answer": [
            "¿Cuántos revisores independientes tamizaron los títulos?",
            "¿Qué gestor de referencias usaste para la búsqueda sistemática?",
            "¿Cuál fue el índice de citación del estudio mayor?",
            "¿Qué institución financió la revisión?",
            "¿Cuántos desacuerdos de tamizaje resolvió el tercer revisor?",
        ],
    },
    "luisa": {
        "borrada": (
            'Dato provisional (piloto)\nEn el piloto de 2024 se anotó que la asibilación de la erre aparecía en el\n80 por ciento de los menores de 30; el valor del corpus es 71.\n'
            "Dato provisional (borrador de 2025)\n"
            "El borrador repartía la sesión en 30 minutos de teoría y 40 de práctica.\n"
            "El examen final preliminar pesaba 50 por ciento.\n"
            "El corpus propio preliminar tenía 96 horas de grabaciones.\n"
            "El borrador fijaba la rúbrica en cinco niveles.\n"
            "El borrador reportaba 84 ocurrencias de chompa en el corpus.\n"
        ),
        "actualizacion": (
            "El examen final pasa de 40 a 35 por ciento y las tareas de 45 a 40.\n"
            "El corpus propio ampliado pasa de 160 a 175 horas de grabaciones.\n"
            "La rúbrica pasa de cuatro a cinco niveles tras la revisión de criterios.\n"
        ),
        "revision": (
            "# Revisión interna del curso (sin fecha)\n"
            "La sesión se reparte en 15 minutos de teoría y 55 de práctica.\n"
            "El examen final pesa 45 por ciento.\n"
            "El corpus propio tiene 130 horas de grabaciones.\n"
            "La asibilación de la erre múltiple aparece en 62 por ciento de los menores de 30.\n"
            "La rúbrica tiene tres niveles.\n"
        ),
        "deleted": [
            {"q": "¿Cómo repartía el borrador los minutos de la sesión?", "abstain": True},
            {"q": "¿Cuánto pesaba el examen final según el borrador?", "abstain": True},
            {"q": "¿Cuántas horas de grabaciones tenía el corpus propio según el borrador?", "abstain": True},
            {"q": "¿Cuántos niveles fijaba el borrador para la rúbrica?", "abstain": True},
            {"q": "¿Cuántas ocurrencias de chompa reportaba el borrador?", "abstain": True},
        ],
        "updated": [
            {"q": "¿Cuánto pesa el examen final vigente y cuánto pesaba antes?", "gold": ["35", "40"]},
            {"q": "¿Cuántas horas de grabaciones tiene el corpus propio vigente y cuántas antes?", "gold": ["175", "160"]},
            {"q": "¿Cuántos niveles tiene la rúbrica vigente y cuántos antes?", "gold": ["cinco", "cuatro"]},
        ],
        "contradiction": [
            {"q": "Según tus fuentes, ¿cómo repartes los minutos de la sesión y hay fuentes que discrepan?", "contradict": True, "pair": ["20", "15"]},
            {"q": "Según tus fuentes, ¿cuánto pesa el examen final y hay fuentes que discrepan?", "contradict": True, "pair": ["35", "45"]},
            {"q": "Según tus fuentes, ¿cuántas horas de grabaciones tiene el corpus propio y hay fuentes que discrepan?", "contradict": True, "pair": ["175", "130"]},
            {"q": "Según tus fuentes, ¿en qué porcentaje de menores de 30 aparece la asibilación y hay fuentes que discrepan?", "contradict": True, "pair": ["71", "62"]},
            {"q": "Según tus fuentes, ¿cuántos niveles tiene la rúbrica y hay fuentes que discrepan?", "contradict": True, "pair": ["cinco", "tres"]},
        ],
        "cross": [
            {"q": "¿Cuánto pesan el examen final y las tareas en tu curso y en cuántas horas de grabaciones se apoya tu corpus?", "gold": ["35", "40", "175"]},
            {"q": "¿En cuántas ocurrencias del corpus aparece chompa y qué porcentaje de menores de 30 muestra asibilación?", "gold": ["89", "71"]},
            {"q": "¿Qué haces si más de un tercio del curso reprueba una tarea y cuántos criterios tiene tu rúbrica?", "gold": ["re-enseña", "tres"]},
        ],
        "simple": [{"q": "¿En cuántas ocurrencias del corpus aparece chompa frente a chaqueta?", "gold": ["89"]},
                   {"q": "¿Qué porcentaje de hablantes asocia chompa y guagua con el registro familiar?", "gold": ["54"]}],
        "no_answer": [
            "¿Cuántos estudiantes se inscribieron al curso de fonética avanzada?",
            "¿Qué software de anotación usas para el corpus?",
            "¿Cuál fue la nota media del examen del año pasado?",
            "¿Qué universidad auspicia el proyecto del corpus?",
            "¿Cuántas horas de tutoría ofreces por semana?",
        ],
    },
}


def generate_v4() -> None:
    for uid, x in EXTRA4.items():
        base = OUT / uid
        ldir = base / "teach" / "knowledge"
        borrada = (ldir / "borrada.md")
        borrada.write_text(x["borrada"], encoding="utf-8")
        actual = (ldir / "actualizacion.md")
        prev = actual.read_text(encoding="utf-8")
        actual.write_text(prev.rstrip() + "\n\n" + x["actualizacion"] + "\n")
        (ldir / "revision_interna.md").write_text(x["revision"], encoding="utf-8")
        qs = []
        for sq in x.get("simple", []):
            qs.append({"q": sq["q"], "type": "simple", "gold": sq["gold"]})
        for dq in x["deleted"]:
            qs.append({"q": dq["q"], "type": "deleted", "gold": [], "abstain": True})
        for uq in x["updated"]:
            qs.append({"q": uq["q"], "type": "updated", "gold": uq["gold"]})
        for cq in x["contradiction"]:
            qs.append({"q": cq["q"], "type": "contradiction",
                       "gold": cq["pair"], "contradict": True,
                       "contradiction_pair": cq["pair"]})
        for cr in x["cross"]:
            qs.append({"q": cr["q"], "type": "cross", "gold": cr["gold"]})
        for nq in x["no_answer"]:
            qs.append({"q": nq, "type": "unanswerable", "gold": [], "abstain": True})
        (base / "questions_v4.json").write_text(
            json.dumps({"questions": qs}, ensure_ascii=False, indent=2),
            encoding="utf-8")
    n = sum(len(x["deleted"]) + len(x["updated"]) + len(x["contradiction"])
            + len(x["cross"]) + len(x["no_answer"]) for x in EXTRA4.values())
    print(f"v4 generado: {len(EXTRA4)} usuarios, {n} preguntas "
          "(16 cruzadas, 15+1 actualizadas, 25 contradicciones, 25 borradas, 25 sin respuesta)")
