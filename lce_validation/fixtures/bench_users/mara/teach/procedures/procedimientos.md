Protocolo de análisis de variantes para el estudio de estructura poblacional
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
