# Diagnosis of digestion and projection (qwen2.5:3b)

Exploratory; decides nothing.

## corpus
- **offsets**: 12 claims, 4 anchored, 8 rejected for support, 0 malformed, 0 quotes not found
  - [user_claim, NOT anchored] Ayer hablé con el equipo sobre el cronograma del proyecto y acordamos revisar los datos la semana pasada.  ⟵ span: «Ayer hablé con el equipo sobre el cronograma del proyecto y»
  - [fact, NOT anchored] cierra a las seis de la tarde los viernes  ⟵ span: «El laboratorio cierr»
  - [fact, NOT anchored] El tamaño efectivo de población puede ser mucho menor que el tamaño censal cuando la proporción de sexos está sesgada.  ⟵ span: «El tamaño efectivo de población puede ser mucho menor que el tamaño c»
  - [fact, anchored] La regla de un migrante por generación corresponde a un F_ST cercano a 0.2 en el modelo de islas.  ⟵ span: «La regla de un migrante por generación corresponde a un F_ST cercano a 0.2 en el »
  - [user_claim, NOT anchored] el café mejora la concentración en todos los casos.  ⟵ span: «café mejora la co»
  - [procedure, NOT anchored] Primero filtro las variantes por calidad, luego calculo la heterocigosidad esperada y finalmente estimo F_ST por pares de poblaciones.  ⟵ span: «Primero filtro las variantes por calidad, luego calculo la heter»
  - [procedure, anchored] Para revisar un manuscrito, primero leo las figuras, luego la discusión y al final los métodos.  ⟵ span: «Para revisar un manuscrito, primero leo las figuras, luego »
  - [procedure, anchored] Cuando preparo un experimento, primero escribo el criterio de abandono y luego diseño las corridas.  ⟵ span: «Cuando preparo un experimento, primero escribo el criterio »
  - [user_claim, NOT anchored] cierro con un agradecimiento breve  ⟵ span: «do y profesio»
  - [user_claim, NOT anchored] Prefiero el término fragmentación semántica en lugar de división de prompts.  ⟵ span: «Prefiero el término fragmentación semánti»
  - [user_claim, NOT anchored] Prefiero el término heterocigosidad esperada en lugar de diversidad génica.  ⟵ span: «Prefiero el término heterocigosidad esperada»
  - [user_claim, anchored] Suelo explicar un concepto nuevo con una analogía biológica antes de dar la definición formal.  ⟵ span: «Suelo explicar un concepto nuevo con una analogía biológica»
- **quote**: 12 claims, 12 anchored, 0 rejected for support, 0 malformed, 0 quotes not found
  - [user_claim, anchored] Ayer hablé con el equipo sobre el cronograma del proyecto y acordamos revisar los datos la semana pasada.  ⟵ span: «Ayer hablé con el equipo sobre el cronograma del proyecto y acordamos revisar los datos la»
  - [fact, anchored] El laboratorio cierra a las seis de la tarde los viernes.  ⟵ span: «El laboratorio cierra a las seis de la tarde los viernes.»
  - [fact, anchored] El tamaño efectivo de población puede ser mucho menor que el tamaño censal cuando la proporción de sexos está sesgada.  ⟵ span: «El tamaño efectivo de población puede ser mucho menor que el tamaño censal cuando la propo»
  - [fact, anchored] La regla de un migrante por generación corresponde a un F_ST cercano a 0.2 en el modelo de islas.  ⟵ span: «La regla de un migrante por generación corresponde a un F_ST cercano a 0.2 en el modelo de»
  - [user_claim, anchored] Creo que el café mejora la concentración en todos los casos.  ⟵ span: «Creo que el café mejora la concentración en todos los casos.»
  - [procedure, anchored] Primero filtro las variantes por calidad, luego calculo la heterocigosidad esperada y finalmente estimo F_ST por pares de poblaciones.  ⟵ span: «Primero filtro las variantes por calidad, luego calculo la heterocigosidad esperada y fina»
  - [procedure, anchored] Para revisar un manuscrito, primero leo las figuras, luego la discusión y al final los métodos.  ⟵ span: «Para revisar un manuscrito, primero leo las figuras, luego la discusión y al final los mét»
  - [procedure, anchored] Cuando preparo un experimento, primero escribo el criterio de abandono y luego diseño las corridas.  ⟵ span: «Cuando preparo un experimento, primero escribo el criterio de abandono y luego diseño las »
  - [user_claim, anchored] cierro con un agradecimiento breve  ⟵ span: «cierro con un agradecimiento breve»
  - [user_claim, anchored] Prefiero el término fragmentación semántica en lugar de división de prompts.  ⟵ span: «Prefiero el término fragmentación semántica en lugar de división de prompts.»
  - [user_claim, anchored] Prefiero el término heterocigosidad esperada en lugar de diversidad génica.  ⟵ span: «Prefiero el término heterocigosidad esperada en lugar de diversidad génica.»
  - [procedure, anchored] Suelo explicar un concepto nuevo con una analogía biológica antes de dar la definición formal.  ⟵ span: «Suelo explicar un concepto nuevo con una analogía biológica antes de dar la definición for»

## u1
- **offsets**: 2 claims, 0 anchored, 2 rejected for support, 0 malformed, 0 quotes not found
  - [style, NOT anchored] Escribo en un registro técnico y conciso.  ⟵ span: «Escribo en un registr»
  - [user_claim, NOT anchored] Prefiero el término inferencia descentralizada en lugar de computación distribuida.  ⟵ span: «Prefiero el término inferencia descentralizada en»
  - projection from claim text: {}
  - projection from anchored span: {}
- **quote**: 2 claims, 2 anchored, 0 rejected for support, 0 malformed, 0 quotes not found
  - [style, anchored] Escribo en un registro técnico y conciso.  ⟵ span: «Escribo en un registro técnico y conciso.»
  - [user_claim, anchored] Prefiero el término inferencia descentralizada en lugar de computación distribuida.  ⟵ span: «Prefiero el término inferencia descentralizada en lugar de computación distribuida.»
  - projection from claim text: {'register': 'técnico y conciso'}
  - projection from anchored span: {'register': 'técnico y conciso'}

## u2
- **offsets**: 2 claims, 0 anchored, 2 rejected for support, 0 malformed, 0 quotes not found
  - [style, NOT anchored] Escribo en un registro divulgativo y cercano.  ⟵ span: «Escribo en un registr»
  - [user_claim, NOT anchored] Prefiero el término modelo pequeño en lugar de SLM.  ⟵ span: «Prefiero el término modelo pequ»
  - projection from claim text: {}
  - projection from anchored span: {}
- **quote**: 2 claims, 2 anchored, 0 rejected for support, 0 malformed, 0 quotes not found
  - [style, anchored] Escribo en un registro divulgativo y cercano.  ⟵ span: «Escribo en un registro divulgativo y cercano.»
  - [user_claim, anchored] Prefiero el término modelo pequeño en lugar de SLM.  ⟵ span: «Prefiero el término modelo pequeño en lugar de SLM.»
  - projection from claim text: {'register': 'divulgativo y cercano'}
  - projection from anchored span: {'register': 'divulgativo y cercano'}

## u3
- **offsets**: 2 claims, 0 anchored, 2 rejected for support, 0 malformed, 0 quotes not found
  - [style, NOT anchored] Escribo en un registro académico y formal.  ⟵ span: «Escribo en un registro »
  - [user_claim, NOT anchored] Prefiero el término evolución cultural en lugar de aprendizaje social.  ⟵ span: «Prefiero el término evolución cultural en»
  - projection from claim text: {}
  - projection from anchored span: {}
- **quote**: 2 claims, 2 anchored, 0 rejected for support, 0 malformed, 0 quotes not found
  - [style, anchored] Escribo en un registro académico y formal.  ⟵ span: «Escribo en un registro académico y formal.»
  - [user_claim, anchored] Prefiero el término evolución cultural en lugar de aprendizaje social.  ⟵ span: «Prefiero el término evolución cultural en lugar de aprendizaje social.»
  - projection from claim text: {'register': 'académico y formal'}
  - projection from anchored span: {'register': 'académico y formal'}

