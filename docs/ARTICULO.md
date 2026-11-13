# Agente Puro: el modelo propone, el sistema gobierna

*Adrian Mendez Millan · código abierto (MIT): https://github.com/DeconstructorGnostico/Agente_puro*

## El problema

Un modelo de lenguaje no distingue entre lo que sabe y lo que suena bien. Si le preguntas, contesta;
si un documento que lee le da una orden, a veces la obedece; si dice «verificado», no hay nada detrás
de esa palabra. Cuando ese modelo se convierte en un agente que usa herramientas, manda correos o
toca bases de datos, esa confusión deja de ser un error de redacción y se vuelve un riesgo operativo.

El **Agente Puro NRE–AMM–OMEGA** es una respuesta de arquitectura a ese problema. No intenta que el
modelo sea más honesto. Pone alrededor del modelo un sistema que decide qué cuenta como hecho, qué
se puede ejecutar y qué se detiene.

## El principio

> **El modelo propone, el sistema gobierna. Solo la evidencia convierte una afirmación en hecho.**

Todo lo demás se deriva de ahí:

- Una entrada no es un hecho. Una inferencia no es un hecho. La salida de un modelo no es la realidad.
- Una propuesta no es una autorización. Verificar no es autorizar.
- Un dato externo (una web, un PDF, un correo) es **dato**, nunca instrucción.
- El aprendizaje no se aprueba a sí mismo.
- Todo ciclo tiene límite y termina en HALT si algo falla. Ante la duda, se cierra.

Esas frases son las invariantes I01–I10 del sistema, y en el código no son comentarios: cada ciclo
se revisa contra ellas y, si una falla, la respuesta no se entrega.

## La arquitectura, capa por capa

**T(x) = V(E(D(N(x))))**: normalizar, deconstruir, evaluar evidencia, verificar.

- **L0 · Root Kernel.** Identidad, invariantes y política de seguridad, congeladas. Se calcula un
  hash del núcleo antes y después de cada ciclo y de cada aprendizaje. Si cambia, HALT.
- **L1 · SIPE (Context Compiler).** Convierte el texto en una instrucción estructurada y separa dos
  canales: lo que pide la persona y los datos externos, que siempre son no confiables.
- **L2 · Semantic Firewall.** Doce categorías de daño en español e inglés (inyección de prompt,
  CBRN, explosivos, intrusión, fraude, autolesión, menores, odio, etc.). Mira la *intención*: «cómo
  mato un proceso de Python» pasa; «cómo fabrico gas sarín en casa» no. Revisa los **dos canales**;
  lo malicioso en datos externos se pone en cuarentena.
- **L3 · AMM-CORE / Deconstructor Gnóstico.** Descompone la petición en D(x): objetivos, hechos,
  supuestos, hipótesis, restricciones, variables, incógnitas, contradicciones, evidencia y
  dependencias. Detecta negaciones en medio de la frase y valores en conflicto («8 GB» contra
  «16 GB»). Una contradicción sin resolver o una dependencia circular detienen el ciclo.
- **L4 · Evidence Engine (Gnostic Truth Engine).** Cuatro estados: SUPPORTED, REFUTED, CONTRADICTED,
  UNDETERMINED. Solo SUPPORTED es hecho, y exige al menos dos **orígenes** independientes, con
  procedencia (URL, hash de documento, DOI) y revisados por un verificador registrado que no sea
  quien envía ni quien afirma. El modelo nunca puede ser fuente ni revisor. Cuando dos fuentes
  apoyan y una refuta, el resultado es CONTRADICTED y el sistema suspende el juicio. El modelo
  local opcional (Ollama) también vive aquí, y su salida se marca como no confiable.
- **L5 · OMEGA.** El razonamiento: un planificador best-first, herramientas en lista blanca, un
  crítico que puntúa cada paso y replanifica, y un equipo de cinco roles (arquitecto de ML,
  ingeniería de datos, MLOps, red team, producto). El ciclo está acotado en pasos, replanes y tiempo.
- **L6 · Verificación independiente y aprendizaje (DGM).** El verificador no es el ejecutor: si
  hubo una herramienta, recalcula; si la respuesta dice «5» y la herramienta dio «4», se rechaza.
  El aprendizaje propone reglas nuevas, las prueba contra un conjunto de validación separado y
  contra canarios de seguridad, y aun así solo se aplican si las aprueba un revisor independiente.
  Ninguna regla aprendida puede crear hechos ni relajar la seguridad: solo puede agregar bloqueos.
- **L7 · Truth State / Audit.** Cada evento va a un registro encadenado con SHA-256. Si alguien lo
  edita, el sistema lo detecta, se detiene y deja de escribir. El estado aprendido se versiona con
  la misma cadena; si se corrompe, vuelve al último estado verificado.
- **NEXUS (transversal).** Autorización por petición y por herramienta. Todo efecto externo (enviar,
  borrar, comprar, ejecutar) queda en PENDING_AUTHORIZATION hasta que una persona lo apruebe. Los
  límites son por sesión, con enfriamiento: no hay un apagado global permanente.

Flujo canónico: `INPUT → SIPE → FIREWALL → DECONSTRUCT → EVIDENCE → OMEGA → VERIFY → LEARN → PERSIST → OUTPUT`.

## Qué medimos, y cómo

Antes de correr nada escribimos un puntaje de eficiencia y lo dejamos fijo:
`100 × (0.35·S + 0.25·(1−FP) + 0.25·Q + 0.10·L + 0.05·C)`, donde S es la tasa de bloqueo en
conjuntos dañinos, FP la tasa de bloqueo en benignos, Q una rúbrica de calidad, L latencia y C
tamaño de código.

Las reglas del firewall se escribieron mirando **solo** un conjunto de desarrollo (30 % de AdvBench,
su traducción automática al español, muestras de Alpaca y casos escritos a mano). Todo lo demás se
evaluó una sola vez al final: HarmBench, XSTest, Aya (red-teaming en español nativo), traducciones
de HarmBench y el 70 % restante de AdvBench.

### Resultados (held-out)

| Conjunto | n | NRE v2 firewall (antes) | NRE v2 completo (antes) | Agente Puro |
|---|---|---|---|---|
| HarmBench (EN) | 400 | 7.8 % | 22.5 % | 28.0 % |
| XSTest dañino (EN) | 200 | 0.5 % | 4.0 % | 21.5 % |
| Aya red-team (ES nativo) | 782 | 0.0 % | 2.2 % | 15.9 % |
| AdvBench held-out (EN)* | 349 | 18.9 % | 21.8 % | 75.1 % |
| HarmBench traducido al ES | 200 | 5.5 % | 15.0 % | 29.5 % |
| XSTest seguro (EN), benigno | 250 | 0.4 % | 3.6 % | 5.2 % |
| Alpaca EN, benigno | 200 | 0.5 % | 3.0 % | 0.5 % |
| Alpaca ES, benigno | 200 | 0.0 % | 2.5 % | 0.5 % |

\*AdvBench held-out viene de la misma distribución que el conjunto de desarrollo; por eso su cifra
es la más alta y la menos representativa.

En promedio sobre HarmBench, XSTest dañino y Aya, el bloqueo pasó de 9.6 % (NRE v2 completo) a
21.8 %, con 2.1 % de falsos positivos en benignos. Es una mejora real, pero **no** es un sistema
que detenga la mayoría del daño de contenido: tres de cada cuatro peticiones de HarmBench siguen
pasando el firewall. La cifra interna anterior de 30/33 no se sostuvo con datos externos (el
firewall de NRE v2 bloqueaba 8.3 % del total dañino); esta versión sube esa cifra, no la resuelve.

### Lo que sí se cumple siempre

Las garantías estructurales no dependen de adivinar el daño, y esas sí se cumplen en las pruebas
(131 de 131):

- Una afirmación sin evidencia nunca sale como hecho, aunque venga con «dos blogs revisados».
- Dos evidencias del mismo sitio cuentan como una; la revisión autodeclarada no cuenta.
- Dos fuentes a favor y una en contra dan CONTRADICTED y HALT, no SUPPORTED.
- Una respuesta del modelo que contradice a la herramienta se rechaza.
- Ningún efecto externo se ejecuta sin autorización humana.
- Editar el registro de auditoría detiene el sistema y bloquea escrituras.
- Ninguna instrucción, interna o externa, cambia el núcleo; si un componente lo intenta, HALT.
- El aprendizaje no se aprueba a sí mismo; «yo» no es un revisor válido.

### La búsqueda de variantes, con honestidad

Comparamos 12 variantes (solo compuerta, solo equipo, compuerta + equipo, firewall viejo vs nuevo,
greedy vs best-first, con y sin Deconstructor, con y sin aprendizaje, con y sin motor de verdad) y
cinco versiones anteriores. El ganador por puntaje fue **compuerta + equipo** (67.9) sobre el Agente
Puro completo (67.3): mismo bloqueo, mismos falsos positivos, misma calidad; pierde 0.6 puntos solo
por latencia (16 ms contra 6 ms) y tamaño. Dejamos el Agente Puro completo por defecto, como
desviación declarada: la variante ganadora no detecta contradicciones ni maneja evidencia, y el
puntaje no mide esas garantías. El aprendizaje y el motor de verdad no cambian estos números porque
los conjuntos públicos no traen evidencia; su valor está en las pruebas, no en el benchmark.

## Límites

- El firewall es de reglas. Para mejorar de verdad el bloqueo de contenido hace falta un
  clasificador aprendido; el punto de conexión existe (Llama Guard vía Ollama) y está apagado.
- El equipo de cinco roles es heurístico: da planes razonables, pero son propuestas y así se marcan.
- La auditoría detecta manipulación; no impide que quien controle el disco reescriba todo.
- El conjunto de desarrollo en español es traducción automática.

## Cómo probarlo

```bash
git clone https://github.com/DeconstructorGnostico/Agente_puro
cd Agente_puro
./run.sh --self-test
./run.sh "Necesito predecir la demanda semanal de inventario de 300 tiendas"
python pure_agent.py --text "La Tierra es plana."
pytest -q
```

Todo corre local, sin internet y sin GPU. El modelo es opcional: `NRE_OLLAMA=1 NRE_MODEL=llama3.2`.

La idea es simple: que un sistema que usa modelos pueda decir con precisión qué sabe, qué no sabe
y qué no va a hacer sin permiso. Repositorio: https://github.com/DeconstructorGnostico/Agente_puro
