Protocolo de despliegue del servicio de catálogo
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
