Arquitectura del sistema de catálogo de productos

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
