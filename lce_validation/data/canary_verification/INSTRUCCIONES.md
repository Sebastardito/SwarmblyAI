---
status: current
lang: es
---

# Verificación del conjunto canario (español de Ecuador)

Gracias por ayudar. Este formulario sirve para confirmar el significado de algunas palabras del español de Ecuador. Las palabras se usan **solo para medir** si un modelo de lenguaje pequeño conoce expresiones regionales poco frecuentes; nunca se usan para entrenar ningún modelo ni se publican asociadas a ninguna persona.

## Qué hay que hacer

Abra `plantilla_verificacion.csv` en Excel, Numbers o Google Sheets y complete, para cada fila, las columnas vacías:

| Columna | Qué poner |
|---|---|
| `lo_conoce` | **si** si conoce la palabra y la ha oído usar en Ecuador; **no** si no la conoce |
| `significado_correcto` | **si** si la glosa propuesta es correcta; **parcial** si es correcta pero incompleta; **no** si es incorrecta |
| `glosa_corregida_es` | si marcó *parcial* o *no*, el significado correcto en pocas palabras |
| `ofensivo_o_vulgar` | **si** si la palabra es ofensiva, vulgar o despectiva en algún uso común |
| `region_donde_se_usa` | Sierra, Costa, Amazonía, una ciudad concreta o "todo el país" |
| `notas` | cualquier matiz: ejemplo de uso, si es antigua, si es de jóvenes, etc. |

Las filas marcadas `current` son las ocho palabras del conjunto actual; las marcadas `candidate` son propuestas para ampliarlo. Si conoce otras palabras ecuatorianas poco comunes que un modelo probablemente no conozca, añádalas al final en filas nuevas con `estado` = `nueva`.

No hace falta buscar nada ni consultar a otras personas: lo valioso es su conocimiento directo. Si duda, marque *no* o déjelo en blanco.

## Privacidad

No escriba su nombre en el archivo. Guárdelo como `verificador_A.csv`, `verificador_B.csv`, etc., con la letra que le indique quien se lo envió. Solo se registra el número de personas que verificaron cada palabra y su región, nunca quiénes fueron.

## Cómo se usa el resultado

Se necesitan al menos tres personas, de preferencia de regiones distintas. Una palabra queda **verificada** si al menos dos personas la conocen y confirman su significado (*si*), y ninguna la marca como ofensiva. Las glosas corregidas se revisan a mano antes de incorporarse. El script `python -m lce_validation.canary_verify verificador_*.csv` aplica esa regla y escribe el conjunto actualizado.

---

*Formulario del proyecto Swarmbly LCE (github.com/Sebastardito/SwarmblyLCE). Texto bajo CC BY 4.0.*
