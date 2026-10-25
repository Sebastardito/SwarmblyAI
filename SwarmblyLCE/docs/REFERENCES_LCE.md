---
status: current
lang: es+en
---
# Swarmbly LCE — Bibliografía anotada / Annotated bibliography

**Fecha de compilación / Compile date: 2026-10-04.**

## Alcance / Scope

Esta bibliografía es la base citable de la **Local Cognitive Extension (LCE)** de Swarmbly: memoria personal local, aprendizaje del modelo del usuario y transferencia ligera de conocimiento entre nodos. Complementa la bibliografía maestra del protocolo (`Swarmbly-AI/docs/REFERENCES.md`) y no la duplica: lo que trata sobre inferencia descentralizada, verificación, ensamblaje genómico y computación voluntaria se cita a través del whitepaper v2 [1].

This bibliography is the citable base for Swarmbly's **Local Cognitive Extension**. It complements the protocol's master bibliography and does not duplicate it. Numbering is the one used by `WHITEPAPER_LCE_ES.md`, `WHITEPAPER_LCE_EN.md`, `SPEC_LCE_ES.md` and `SPEC_LCE_EN.md`.

Cada entrada lleva una línea **Uso en LCE**: para qué se cita y qué decisión de diseño sostiene. Una referencia que no sostiene ninguna decisión no está en la lista.

## Leyenda de verificación / Verification legend

| Marca | Significado |
|---|---|
| *(sin marca)* | Verificada el 2026-10-03/04 contra la página del editor, del congreso, el registro DOI o arXiv. Se puede citar. |
| ⚠️ | Verificación parcial: la obra existe y el hallazgo citado se confirmó, pero un campo (lugar de publicación, páginas) no se confirmó. Revisar antes de publicar. |
| `[STD]` | Obra clásica citada según su registro bibliográfico estándar, sin cotejo en línea en esta compilación. |
| ⭐ | Cita de carga: puede decidir por sí sola un argumento a favor o en contra del diseño. |

## Índice / Table of contents

1. **[SWB]** Swarmbly · `[1]–[2]`
2. **[PER]** Personalización y memoria de agentes · `[3]–[11]`
3. **[KNW]** Inyección de conocimiento, PEFT y atribución · `[12]–[21]`
4. **[CLS]** Aprendizaje continuo y sistemas complementarios · `[22]–[27]`
5. **[COL]** Colapso, homogeneización y errores correlacionados · `[28]–[38]`
6. **[CUL]** Evolución cultural, poblaciones de LLM y conformismo · `[39]–[46]`
7. **[POP]** Genética de poblaciones y cuantitativa · `[47]–[51]`
8. **[HEB]** Plasticidad hebbiana y su control · `[52]–[54]`
9. **[EVA]** Evaluación adaptativa y pluralismo · `[55]–[56]`
10. **[PRV]** Privacidad, memorización, desaprendizaje y Sybil · `[57]–[61]`
11. **[DCL]** Aprendizaje descentralizado y computación voluntaria · `[62]–[65]`
12. **[V02]** Añadidas en la versión 0.2 del whitepaper / Added in whitepaper v0.2 · `[66]–[68]`

---

## 1. [SWB] Swarmbly

[1] ⭐ Espinoza-Ulloa, S. A. (2026). *Fragmentación semántica y ensamblaje estocástico, versión 2: Un protocolo de inferencia descentralizada de modelos de lenguaje sobre nodos voluntarios no confiables* (Whitepaper v2). Zenodo. https://doi.org/10.5281/zenodo.23031305

Uso en LCE: el protocolo que la extensión no debe deformar. Método de homologías (sección 3), principios P1–P11, verificación por capas (13.3), Sybil (13.6), vida media de host de 91 días (7.4), E12/E16/E17, L10.

[2] Espinoza-Ulloa, S. A. (2026). *Swarmbly AI* (Versión 2.0.0; especificación del protocolo v0.2 e implementación de referencia) [Software]. Zenodo. https://doi.org/10.5281/zenodo.21956743

Uso en LCE: contrato Γ (campos `audience`, `register`, `lexicon`, `entities`, `style_seed`), anuncio de perfil de nodo, carriles y niveles de privacidad, regla de ignorar campos desconocidos (compatibilidad MINOR).

---

## 2. [PER] Personalización y memoria de agentes

[3] Zhang, Z., Rossi, R. A., Kveton, B., Shao, Y., et al. (2025). Personalization of large language models: A survey. *Transactions on Machine Learning Research*. https://arxiv.org/abs/2411.00027

Uso en LCE: taxonomía del campo (granularidad, técnicas, evaluación). Sitúa a la LCE como personalización por usuario con recuperación más PEFT.

[4] Salemi, A., Mysore, S., Bendersky, M., & Zamani, H. (2024). LaMP: When large language models meet personalization. En *Proceedings of the 62nd Annual Meeting of the ACL* (pp. 7370–7392). https://doi.org/10.18653/v1/2024.acl-long.399

Uso en LCE: referencia de evaluación de personalización por recuperación; candidato a benchmark externo del experimento local.

[5] ⭐ Tan, Z., Zeng, Q., Tian, Y., Liu, Z., Yin, B., & Jiang, M. (2024). Democratizing large language models via personalized parameter-efficient fine-tuning. En *Proceedings of EMNLP 2024* (pp. 6476–6491). https://doi.org/10.18653/v1/2024.emnlp-main.372

Uso en LCE: OPPU, "un PEFT por usuario" combinado con recuperación. Es el arte previo más cercano a la capa local y confirma la división del trabajo entre módulo paramétrico (comportamiento) y recuperación (conocimiento cambiante).

[6] Tan, Z., Liu, Z., & Jiang, M. (2024). Personalized pieces: Efficient personalized large language models through collaborative efforts. En *Proceedings of EMNLP 2024* (pp. 6459–6475). https://doi.org/10.18653/v1/2024.emnlp-main.371

Uso en LCE: arte previo de compartir piezas PEFT entre usuarios. La LCE toma la dirección contraria por defecto (compartir conocimiento escrito, no parámetros) y lo justifica en la sección de alternativas descartadas.

[7] Karpathy, A. (2026, 4 de abril). *llm-wiki.md* [GitHub Gist]. https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

Uso en LCE: patrón de wiki mantenida por un LLM con tres operaciones (ingerir, consultar, revisar contradicciones). Base de la capa 1.

[8] Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. En *Proceedings of UIST 2023*. https://doi.org/10.1145/3586183.3606763

Uso en LCE: flujo de memoria en lenguaje natural con reflexión periódica; antecedente del ciclo de consolidación.

[9] Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S. G., Stoica, I., & Gonzalez, J. E. (2023). MemGPT: Towards LLMs as operating systems. *arXiv*. https://arxiv.org/abs/2310.08560

Uso en LCE: memoria por niveles gestionada por el propio modelo; antecedente de la separación contexto / memoria recuperable.

[10] Xu, W., Liang, Z., Mei, K., Gao, H., Tan, J., & Zhang, Y. (2025). A-MEM: Agentic memory for LLM agents. En *Advances in Neural Information Processing Systems 38 (NeurIPS 2025)*. https://arxiv.org/abs/2502.12110

Uso en LCE: memoria tipo Zettelkasten con enlaces y evolución de notas; antecedente directo del grafo de la wiki.

[11] Kleppmann, M., Wiggins, A., van Hardenberg, P., & McGranaghan, M. (2019). Local-first software: You own your data, in spite of the cloud. En *Proceedings of Onward! 2019* (pp. 154–178). ACM. https://doi.org/10.1145/3359591.3359737

Uso en LCE: los principios local-first (propiedad, funcionamiento sin red, longevidad de los datos) que la LCE adopta como principio rector. Páginas, editorial y DOI confirmados en Crossref (4 oct. 2026).

---

## 3. [KNW] Inyección de conocimiento, PEFT y atribución

[12] Lewis, P., Perez, E., Piktus, A., et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. En *Advances in Neural Information Processing Systems 33*. https://arxiv.org/abs/2005.11401 `[STD]`

Uso en LCE: el mecanismo de recuperación por defecto para hechos.

[13] ⭐ Ovadia, O., Brief, M., Mishaeli, M., & Elisha, O. (2024). Fine-tuning or retrieval? Comparing knowledge injection in LLMs. En *Proceedings of EMNLP 2024* (pp. 237–250). https://doi.org/10.18653/v1/2024.emnlp-main.15

Uso en LCE: la recuperación supera de forma consistente al ajuste no supervisado para inyectar conocimiento, también conocimiento nuevo. Sostiene la invariante I1.

[14] ⭐ Gekhman, Z., Yona, G., Aharoni, R., Eyal, M., Feder, A., Reichart, R., & Herzig, J. (2024). Does fine-tuning LLMs on new knowledge encourage hallucinations? En *Proceedings of EMNLP 2024* (pp. 7765–7784). https://doi.org/10.18653/v1/2024.emnlp-main.444

Uso en LCE: el conocimiento nuevo se aprende despacio y, una vez aprendido, aumenta linealmente la tendencia a alucinar. Sostiene I1 y la condición de abstención de la compuerta.

[15] Yang, Z., Band, N., Li, S., Candès, E., & Hashimoto, T. (2025). Synthetic continued pretraining. En *ICLR 2025*. https://arxiv.org/abs/2409.07431 `[STD]`

Uso en LCE: EntiGraph como vía explícita y costosa para fijar un hecho en parámetros, aditiva a la recuperación.

[16] Hu, E. J., Shen, Y., Wallis, P., et al. (2022). LoRA: Low-rank adaptation of large language models. En *ICLR 2022*. https://arxiv.org/abs/2106.09685 `[STD]`

Uso en LCE: mecanismo de adaptador por defecto (capa 2).

[17] Dettmers, T., Pagnoni, A., Holtzman, A., & Zettlemoyer, L. (2023). QLoRA: Efficient finetuning of quantized LLMs. En *Advances in Neural Information Processing Systems 36*. https://arxiv.org/abs/2305.14314 `[STD]`

Uso en LCE: hace viable el tier C4 en hardware de consumo.

[18] ⭐ Biderman, D., Portes, J., González Ortiz, J. J., Paul, M., Greengard, P., Jennings, C., King, D., Havens, S., Chiley, V., Frankle, J., Blakeney, C., & Cunningham, J. P. (2024). LoRA learns less and forgets less. *Transactions on Machine Learning Research*. https://arxiv.org/abs/2405.09673

Uso en LCE: LoRA aprende menos y olvida menos que el ajuste completo: el compromiso correcto para un adaptador personal.

[19] Rafailov, R., Sharma, A., Mitchell, E., Ermon, S., Manning, C. D., & Finn, C. (2023). Direct preference optimization: Your language model is secretly a reward model. En *NeurIPS 2023*. https://arxiv.org/abs/2305.18290 `[STD]`

Uso en LCE: las correcciones del usuario como pares de preferencia, la única supervisión del sistema.

[20] Min, S., Krishna, K., Lyu, X., Lewis, M., et al. (2023). FActScore: Fine-grained atomic evaluation of factual precision in long form text generation. En *Proceedings of EMNLP 2023*. https://arxiv.org/abs/2305.14251

Uso en LCE: descomponer en afirmaciones atómicas y medir cuántas están soportadas por una fuente. Es el instrumento de la regla de anclaje. Dato: ChatGPT obtuvo 58 % en biografías.

[21] Gao, T., Yen, H., Yu, J., & Chen, D. (2023). Enabling large language models to generate text with citations. En *Proceedings of EMNLP 2023*. https://arxiv.org/abs/2305.14627

Uso en LCE: incluso los mejores modelos carecen de soporte completo de cita la mitad de las veces (ELI5). Justifica verificar el anclaje con código y no confiarlo al digestor.

---

## 4. [CLS] Aprendizaje continuo y sistemas complementarios

[22] ⭐ McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). Why there are complementary learning systems in the hippocampus and neocortex. *Psychological Review, 102*(3), 419–457. https://doi.org/10.1037/0033-295X.102.3.419 `[STD]`

Uso en LCE: la homología de la arquitectura local (wiki rápida, adaptador lento, repaso intercalado).

[23] McCloskey, M., & Cohen, N. J. (1989). Catastrophic interference in connectionist networks: The sequential learning problem. *Psychology of Learning and Motivation, 24*, 109–165. https://doi.org/10.1016/S0079-7421(08)60536-8 `[STD]`

Uso en LCE: el modo de fallo de la homología CLS.

[24] Kumaran, D., Hassabis, D., & McClelland, J. L. (2016). What learning systems do intelligent agents need? Complementary learning systems theory updated. *Trends in Cognitive Sciences, 20*(7), 512–534. https://doi.org/10.1016/j.tics.2016.05.004

Uso en LCE: la actualización de CLS para agentes artificiales; puente entre la teoría y el diseño.

[25] Kirkpatrick, J., et al. (2017). Overcoming catastrophic forgetting in neural networks. *Proceedings of the National Academy of Sciences, 114*(13), 3521–3526. https://doi.org/10.1073/pnas.1611835114

Uso en LCE: alternativa por regularización (EWC) al repaso; se descarta por defecto porque exige estado del adaptador anterior, incompatible con regenerar desde base + wiki.

[26] Luo, Y., Yang, Z., Meng, F., Li, Y., Zhou, J., & Zhang, Y. (2023). An empirical study of catastrophic forgetting in large language models during continual fine-tuning. *arXiv*. https://arxiv.org/abs/2308.08747

Uso en LCE: el olvido catastrófico aparece en LLM de 1B a 7B, el rango de Swarmbly.

[27] Scialom, T., Chakrabarty, T., & Muresan, S. (2022). Fine-tuned language models are continual learners. En *Proceedings of EMNLP 2022* (pp. 6107–6122). https://doi.org/10.18653/v1/2022.emnlp-main.410

Uso en LCE: el aprendizaje continuo con repaso conserva las tareas previas en modelos ajustados por instrucciones; respaldo empírico del repaso intercalado.

---

## 5. [COL] Colapso, homogeneización y errores correlacionados

[28] ⭐ Shumailov, I., Shumaylov, Z., Zhao, Y., Papernot, N., Anderson, R., & Gal, Y. (2024). AI models collapse when trained on recursively generated data. *Nature, 631*(8022), 755–759. https://doi.org/10.1038/s41586-024-07566-y

Uso en LCE: el modo de fallo central del aprendizaje entre nodos; las colas desaparecen primero.

[29] ⭐ Gerstgrasser, M., Schaeffer, R., Dey, A., Rafailov, R., Sleight, H., Hughes, J., Korbak, T., Agrawal, R., Pai, D., Gromov, A., Roberts, D. A., Yang, D., Donoho, D. L., & Koyejo, S. (2024). Is model collapse inevitable? Breaking the curse of recursion by accumulating real and synthetic data. En *COLM 2024*. https://arxiv.org/abs/2404.01413

Uso en LCE: acumular acota el error; reemplazar colapsa. Sostiene la invariante I3.

[30] Alemohammad, S., Casco-Rodriguez, J., Luzi, L., Humayun, A. I., Babaei, H., LeJeune, D., Siahkoohi, A., & Baraniuk, R. G. (2024). Self-consuming generative models go MAD. En *ICLR 2024*. https://arxiv.org/abs/2307.01850

Uso en LCE: sin datos reales nuevos en cada generación, la calidad o la diversidad decaen. Respaldo de la variación anclada (evidencia humana nueva).

[31] Bertrand, Q., Bose, A. J., Duplessis, A., Jiralerspong, M., & Gidel, G. (2024). On the stability of iterative retraining of generative models on their own data. En *ICLR 2024*. https://arxiv.org/abs/2310.00429

Uso en LCE: el reentrenamiento iterativo es estable si el modelo inicial aproxima bien los datos y la proporción de datos limpios es suficientemente grande. Base formal de "lo social siempre minoritario".

[32] Dohmatob, E., Feng, Y., Yang, P., Charton, F., & Kempe, J. (2024). A tale of tails: Model collapse as a change of scaling laws. En *Proceedings of ICML 2024*, PMLR 235, 11165–11197. https://proceedings.mlr.press/v235/dohmatob24b.html

Uso en LCE: el colapso empieza por la pérdida de las colas y cambia las leyes de escala. Justifica el conjunto canario como medida de colas.

[33] Padmakumar, V., & He, H. (2024). Does writing with language models reduce content diversity? En *ICLR 2024*. https://arxiv.org/abs/2309.05196

Uso en LCE: escribir con un modelo ajustado con retroalimentación reduce la diversidad entre autores. Riesgo de homogeneización del propio usuario.

[34] Wu, F., Black, E., & Chandrasekaran, V. (2025). Generative monoculture in large language models. En *ICLR 2025*. https://arxiv.org/abs/2407.02209

Uso en LCE: los LLM estrechan su diversidad respecto de los datos de entrenamiento, y cambiar el muestreo o el prompt no basta.

[35] ⭐ Jiang, L., Chai, Y., Li, M., Liu, M., Fok, R., Dziri, N., Tsvetkov, Y., Sap, M., Albalak, A., & Choi, Y. (2025). Artificial hivemind: The open-ended homogeneity of language models (and beyond). En *NeurIPS 2025, Datasets and Benchmarks*. https://arxiv.org/abs/2510.22954

Uso en LCE: homogeneidad entre modelos distintos en tareas abiertas (Infinity-Chat, 26 000 consultas). Limita lo que la diversidad de familia puede aportar a la respuesta plural.

[36] ⭐ Kim, E. M., Garg, A., Peng, K., & Garg, N. (2025). Correlated errors in large language models. En *Proceedings of ICML 2025*, PMLR 267, 30038–30066. https://proceedings.mlr.press/v267/kim25e.html

Uso en LCE: sobre más de 350 modelos, en un leaderboard dos modelos coinciden el 60 % de las veces cuando ambos fallan, y los modelos más capaces correlacionan sus errores aun con arquitecturas y desarrolladores distintos. Es la evidencia adversa más fuerte contra el supuesto de independencia de E12, y la LCE la hereda.

[37] Kleinberg, J., & Raghavan, M. (2021). Algorithmic monoculture and social welfare. *Proceedings of the National Academy of Sciences, 118*(22), e2018340118. https://doi.org/10.1073/pnas.2018340118 ⚠️

Uso en LCE: que todos usen el mismo algoritmo puede empeorar el resultado colectivo aun si el algoritmo es mejor individualmente. Argumento de bienestar para preservar diversidad. ⚠️ volumen y número según registro estándar.

[38] Santurkar, S., Durmus, E., Ladhak, F., Lee, C., Liang, P., & Hashimoto, T. (2023). Whose opinions do language models reflect? En *ICML 2023*. https://arxiv.org/abs/2303.17548

Uso en LCE: desalineación sustancial con 60 grupos demográficos que persiste al dirigir el modelo. Motiva que la voz cultural venga del usuario y no del modelo base.

---

## 6. [CUL] Evolución cultural, poblaciones de LLM y conformismo

[39] ⭐ Cavalli-Sforza, L. L., & Feldman, M. W. (1981). *Cultural transmission and evolution: A quantitative approach* (Monographs in Population Biology 16). Princeton University Press.

Uso en LCE: transmisión vertical, oblicua y horizontal con dinámicas distintas; contabilidad de la vía de llegada (R1).

[40] ⭐ Boyd, R., & Richerson, P. J. (1985). *Culture and the evolutionary process*. University of Chicago Press. `[STD]`

Uso en LCE: transmisión conformista, Δp = D·p(1−p)(2p−1). Modo de fallo de "aprender lo que muchos repiten" (I5).

[41] Henrich, J., & Boyd, R. (1998). The evolution of conformist transmission and the emergence of between-group differences. *Evolution and Human Behavior, 19*(4), 215–241. https://doi.org/10.1016/S1090-5138(98)00018-X

Uso en LCE: el conformismo reduce la variación dentro de los grupos y aumenta la diferencia entre grupos.

[42] Brinkmann, L., Baumann, F., Bonnefon, J.-F., Derex, M., Müller, T. F., Nussberger, A.-M., Czaplicka, A., Acerbi, A., Griffiths, T. L., Henrich, J., Leibo, J. Z., McElreath, R., Oudeyer, P.-Y., Stray, J., & Rahwan, I. (2023). Machine culture. *Nature Human Behaviour, 7*(11), 1855–1868. https://doi.org/10.1038/s41562-023-01742-2

Uso en LCE: las máquinas alteran la variación, la transmisión y la selección culturales. Marco para leer la red como población con memoria cultural.

[43] Perez, J., Léger, C., Ovando-Tellez, M., Foulon, C., Dussauld, J., Oudeyer, P.-Y., & Moulin-Frier, C. (2024). Cultural evolution in populations of large language models. *arXiv*. https://arxiv.org/abs/2403.08882

Uso en LCE: marco abierto para simular evolución cultural en poblaciones de LLM variando red, personalidad y agregación. Candidato a arnés del experimento social.

[44] Vallinder, A., & Hughes, E. (2025). Cultural evolution of cooperation among LLM agents: Extended abstract. En *Proceedings of the 24th International Conference on Autonomous Agents and Multiagent Systems (AAMAS 2025)* (pp. 2771–2773). IFAAMAS. https://arxiv.org/abs/2412.10270

Uso en LCE: las normas que emergen en sociedades de LLM dependen fuertemente del modelo base. Resumen extendido de 3 páginas en las actas; la versión completa está en arXiv. Páginas confirmadas en las actas de AAMAS 2025 (4 oct. 2026).

[45] ⭐ Weng, Z., Chen, G., & Wang, W. (2025). Do as we do, not as you think: The conformity of large language models. En *ICLR 2025*. https://arxiv.org/abs/2501.13381

Uso en LCE: los LLM muestran conformismo medible (BenchForm), creciente con el tamaño de la mayoría y el tiempo de interacción. Confirma que el modo de fallo de R1 existe en LLM, no solo en humanos.

[46] Chuang, Y.-S., Goyal, A., Harlalka, N., et al. (2024). Simulating opinion dynamics with networks of LLM-based agents. En *Findings of NAACL 2024*. https://arxiv.org/abs/2311.09618

Uso en LCE: redes de agentes LLM convergen hacia el consenso fáctico por un sesgo propio del modelo; con sesgo de confirmación inducido se fragmentan. El resultado de una red depende de los sesgos de sus agentes, no solo de su topología.

---

## 7. [POP] Genética de poblaciones y cuantitativa

[47] ⭐ Wright, S. (1931). Evolution in Mendelian populations. *Genetics, 16*(2), 97–159. https://doi.org/10.1093/genetics/16.2.97 `[STD]`

Uso en LCE: modelo de islas, F_ST ≈ 1/(1+4Nm); presupuesto de migración.

[48] ⭐ Whitlock, M. C., & McCauley, D. E. (1999). Indirect measures of gene flow and migration: F_ST ≠ 1/(4Nm+1). *Heredity, 82*(2), 117–125. https://doi.org/10.1038/sj.hdy.6884960 `[STD]`

Uso en LCE: el modo de fallo del instrumento de Wright; por qué la banda de Nm es punto de partida y no valor.

[49] Mills, L. S., & Allendorf, F. W. (1996). The one-migrant-per-generation rule in conservation and management. *Conservation Biology, 10*(6), 1509–1518. https://doi.org/10.1046/j.1523-1739.1996.10061509.x

Uso en LCE: la regla de un migrante por generación (F_ST ≈ 0.2).

[50] Ayala, F. J., & Campbell, C. A. (1974). Frequency-dependent selection. *Annual Review of Ecology and Systematics, 5*, 115–138. https://doi.org/10.1146/annurev.es.05.110174.000555

Uso en LCE: la selección dependiente de la frecuencia negativa mantiene polimorfismos; base de la persistencia ponderada por rareza (R3).

[51] Falconer, D. S., & Mackay, T. F. C. (1996). *Introduction to quantitative genetics* (4.ª ed.). Longman. `[STD]`

Uso en LCE: ecuación del criador, respuesta correlacionada e índice de selección restringido (R7).

---

## 8. [HEB] Plasticidad hebbiana y su control

[52] Hebb, D. O. (1949). *The organization of behavior: A neuropsychological theory*. Wiley. `[STD]`

[53] Oja, E. (1982). Simplified neuron model as a principal component analyzer. *Journal of Mathematical Biology, 15*(3), 267–273. https://doi.org/10.1007/BF00275687 `[STD]`

[54] Turrigiano, G. G., Leslie, K. R., Desai, N. S., Rutherford, L. C., & Nelson, S. B. (1998). Activity-dependent scaling of quantal amplitude in neocortical neurons. *Nature, 391*(6670), 892–896. https://doi.org/10.1038/36103 `[STD]`

Uso en LCE de [52]–[54]: la homología neuronal aporta solo su modo de fallo (crecimiento sin cota) y la forma de su control (normalización y escalado homeostático), que se traduce en afinidad con decaimiento y normalización por dominio.

---

## 9. [EVA] Evaluación adaptativa y pluralismo

[55] Dwork, C., Feldman, V., Hardt, M., Pitassi, T., Reingold, O., & Roth, A. (2015). The reusable holdout: Preserving validity in adaptive data analysis. *Science, 349*(6248), 636–638. https://doi.org/10.1126/science.aaa9375

Uso en LCE: reutilizar un conjunto de validación en decisiones sucesivas invalida sus estimaciones; prueba nueva por generación de adaptador.

[56] Sorensen, T., Moore, J., Fisher, J., Gordon, M., Mireshghallah, N., Rytting, C. M., Ye, A., Jiang, L., Lu, X., Dziri, N., Althoff, T., & Choi, Y. (2024). Position: A roadmap to pluralistic alignment. En *Proceedings of ICML 2024*. https://arxiv.org/abs/2402.05070

Uso en LCE: pluralismo de Overton; marco de la respuesta plural (R6).

---

## 10. [PRV] Privacidad, memorización, desaprendizaje y Sybil

[57] Carlini, N., Tramèr, F., Wallace, E., Jagielski, M., et al. (2021). Extracting training data from large language models. En *30th USENIX Security Symposium*. https://arxiv.org/abs/2012.07805

Uso en LCE: los modelos devuelven ejemplos de entrenamiento verbatim, incluida información personal. Un adaptador personal es información personal comprimida y no se publica (I2).

[58] Mireshghallah, F., Uniyal, A., Wang, T., Evans, D., & Berg-Kirkpatrick, T. (2022). An empirical analysis of memorization in fine-tuned autoregressive language models. En *Proceedings of EMNLP 2022* (pp. 1816–1826). https://doi.org/10.18653/v1/2022.emnlp-main.119

Uso en LCE: los adaptadores pequeños son menos vulnerables a extracción que ajustar la cabeza, pero no inmunes. Atenúa el riesgo sin eliminarlo.

[59] ⚠️ Maini, P., Feng, Z., Schwarzschild, A., Lipton, Z. C., & Kolter, J. Z. (2024). TOFU: A task of fictitious unlearning for LLMs. *arXiv*. https://arxiv.org/abs/2401.06121

Uso en LCE: ninguno de los métodos base de desaprendizaje logra un olvido efectivo. ⚠️ lugar de publicación final no confirmado.

[60] ⭐ Shi, W., Lee, J., Huang, Y., Malladi, S., Zhao, J., et al. (2025). MUSE: Machine unlearning six-way evaluation for language models. En *ICLR 2025*. https://arxiv.org/abs/2407.06460

Uso en LCE: los algoritmos de desaprendizaje degradan la utilidad y no soportan solicitudes sucesivas. El único olvido verificable en pesos es regenerar el adaptador.

[61] Douceur, J. R. (2002). The Sybil attack. En *Peer-to-Peer Systems (IPTPS 2002)*, LNCS 2429 (pp. 251–260). Springer. https://doi.org/10.1007/3-540-45748-8_24 ⚠️

Uso en LCE: por qué la distancia epistémica no se convierte en confianza transitiva. ⚠️ páginas según registro estándar.

---

## 11. [DCL] Aprendizaje descentralizado y computación voluntaria

[62] McMahan, B., Moore, E., Ramage, D., Hampson, S., & Agüera y Arcas, B. (2017). Communication-efficient learning of deep networks from decentralized data. En *Proceedings of AISTATS 2017*, PMLR 54, 1273–1282. https://arxiv.org/abs/1602.05629 `[STD]`

Uso en LCE: aprendizaje federado, alternativa descartada (exige un modelo global y rondas sincronizadas).

[63] Hegedűs, I., Danner, G., & Jelasity, M. (2021). Decentralized learning works: An empirical comparison of gossip learning and federated learning. *Journal of Parallel and Distributed Computing, 148*, 109–124. https://doi.org/10.1016/j.jpdc.2020.10.006

Uso en LCE: el gossip learning es competitivo con el federado; se descarta igualmente por tráfico permanente y por converger a un modelo común, contrario a I7.

[64] Huang, C., Liu, Q., Lin, B. Y., Pang, T., Du, C., & Lin, M. (2024). LoraHub: Efficient cross-task generalization via dynamic LoRA composition. En *COLM 2024*. https://arxiv.org/abs/2307.13269

Uso en LCE: componer adaptadores es posible, pero exige misma familia y versión de modelo; queda como optimización posterior, no como mecanismo base.

[65] Anderson, D. P., & Fedak, G. (2006). The computational and storage potential of volunteer computing. En *CCGRID'06* (pp. 73–80). IEEE. https://doi.org/10.1109/CCGRID.2006.101

Uso en LCE: vida media de host de 91 días; base del cálculo de r_memory.

---

## 12. [V02] Añadidas en la versión 0.2 del whitepaper / Added in whitepaper v0.2

*Añadidas el 2026-10-11. / Added 2026-10-11.*

[66] Wu, D., Wang, H., Yu, W., Zhang, Y., Chang, K.-W., & Yu, D. (2025). LongMemEval: Benchmarking chat assistants on long-term interactive memory. *arXiv*. https://arxiv.org/abs/2410.10813 ⚠️

Uso en LCE: subconjunto público (licencia MIT, 8 preguntas) de la confirmatoria de R13 (Enmienda 8), para comprobar que la dirección de A3 − A2 no es un artefacto del corpus sintético. ⚠️ lugar de publicación final no confirmado (versión 2 de arXiv, 2025-03-04).

[67] Espinoza-Ulloa, S. A. (2026). *Swarmbly LCE: reference implementation, validation harness and pre-registered runs* (Version 0.1.1) [Software]. Zenodo. https://doi.org/10.5281/zenodo.23289041

Uso en LCE: registro del software con las salidas crudas de las corridas hasta el 10 de octubre de 2026.

[68] Espinoza-Ulloa, S. A. (2026). *Local cognition and anchored transmission: A local-first cognitive extension for Swarmbly* (Version 0.1, draft). Zenodo. https://doi.org/10.5281/zenodo.23150478

Uso en LCE: la versión 0.1 del whitepaper, publicada sin resultados; la versión 0.2 la sustituye en contenido y la conserva congelada.
