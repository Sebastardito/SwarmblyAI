Memoria anual del sistema de catálogo, 2026

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
