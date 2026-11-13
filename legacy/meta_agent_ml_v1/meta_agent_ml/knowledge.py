"""Base de conocimiento por dominio para el backend heurístico."""

from __future__ import annotations

# El orden importa: lo más específico va primero.
DOMAIN_KEYWORDS: list[tuple[str, str, tuple[str, ...]]] = [
    (
        "fraude",
        "detección de fraude",
        ("fraude", "fraud", "aml", "lavado de dinero", "transaccion sospechosa",
         "tarjeta clonada", "chargeback"),
    ),
    (
        "credito",
        "riesgo de crédito",
        ("credito", "credit scoring", "scoring crediticio", "otorgamiento",
         "morosidad", "default", "prestamo", "capacidad de pago"),
    ),
    (
        "salud",
        "salud y diagnóstico",
        ("diagnostico", "clinico", "clinica", "paciente", "hospital", "medico",
         "radiograf", "ehr", "salud", "healthcare", "hipaa"),
    ),
    (
        "recomendacion",
        "sistemas de recomendación",
        ("recomend", "ranking de productos", "catalogo personalizado",
         "siguiente articulo", "content based", "colaborativ"),
    ),
    (
        "series_temporales",
        "series temporales y pronóstico",
        ("serie temporal", "series de tiempo", "pronostic", "forecast",
         "demanda", "inventario", "estacional", "rezago", "ventas historicas",
         "prediccion de ventas"),
    ),
    (
        "vision",
        "visión por computadora",
        ("imagen", "vision", "camara", "detectar objetos", "segmentacion",
         "ocr", "video", "pixel", "fotograf", "yolo", "cnn"),
    ),
    (
        "audio",
        "audio y voz",
        ("audio", "voz", "speech", "transcripcion", "wav", "microfono",
         "diarizacion", "asr"),
    ),
    (
        "nlp",
        "lenguaje natural",
        ("nlp", "texto", "lenguaje natural", "chatbot", "llm", "clasificar documentos",
         "sentimiento", "embeddings de texto", "rag", "resumen automatico",
         "traduccion"),
    ),
    (
        "aprendizaje_por_refuerzo",
        "aprendizaje por refuerzo",
        ("refuerzo", "reinforcement", "recompensa", "politica de control",
         "agente de control", "rl ", "bandit"),
    ),
    (
        "anomalias",
        "detección de anomalías",
        ("anomalia", "outlier", "en serie no supervisad", "deteccion de incidentes",
         "intrusion"),
    ),
    (
        "clustering",
        "agrupación no supervisada",
        ("cluster", "agrupar", "segmentacion de clientes", "no supervisad",
         "kmeans", "k-means"),
    ),
    (
        "clasificacion",
        "clasificación",
        ("clasific", "etiquet", "binari", "multiclase", "categoria"),
    ),
    (
        "regresion",
        "regresión",
        ("regresion", "predecir un valor", "estimar el precio", "forecast de un numero"),
    ),
]


DOMAINS: dict[str, dict] = {
    "fraude": {
        "modelos": [
            "línea base: reglas + árbol / gradient boosting sobre features de transacción",
            "modelo de contraste: red para secuencias de eventos",
            "ensemble con calibración de probabilidad y umbral por costo de error",
        ],
        "metricas_default": ["recall en fraude", "precision", "AUC-PR", "pérdida esperada"],
        "datos": [
            "historial de transacciones con etiqueta de fraude y chargeback",
            "features de dispositivo, monto, frecuencia y contraparte",
            "cuidado con el desbalance extremo y el retraso de las etiquetas",
        ],
        "riesgos": [
            "deriva de adversarios que adaptan el ataque al modelo",
            "falsos positivos que friccionan al cliente legítimo",
            "fuga de información si se usan features post-autorización",
        ],
        "herramientas": [
            "calculadora de umbral por costo",
            "monitor de drift de monto y dispositivo",
            "simulador de ataques conocidos",
            "cola de revisión humana",
        ],
        "mlops": "servicio de baja latencia en la ruta de autorización, con retraining frecuente y shadow mode",
    },
    "credito": {
        "modelos": [
            "scorecard interpretable (regresión logística / WoE)",
            "gradient boosting calibrado, con explicación por cliente",
            "modelo de rechazo inferido para sesgo de selección",
        ],
        "metricas_default": ["AUC", "KS", "Gini", "pérdida esperada", "estabilidad poblacional"],
        "datos": [
            "bureau, comportamiento de pago e ingresos declarados/estimados",
            "ventanas temporales de desempeño (12–24 meses)",
            "muestra de rechazados para no entrenar solo con otorgados",
        ],
        "riesgos": [
            "discriminación indirecta por variables proxy",
            "incumplimiento regulatorio si el modelo no es explicable",
            "sobreajuste a un ciclo económico particular",
        ],
        "herramientas": [
            "explainer local (SHAP / reason codes)",
            "monitor de PSI y de morosidad temprana",
            "validador de políticas de exclusión",
        ],
        "mlops": "despliegue con gobernanza de modelo, versionado de políticas y auditoría de decisiones",
    },
    "salud": {
        "modelos": [
            "línea base clínica (reglas / score validado) como referencia",
            "modelo supervisado sobre señales estructuradas o imagen, según el dato",
            "asistencia al clínico, no decisión automática de tratamiento",
        ],
        "metricas_default": ["sensibilidad", "especificidad", "AUC", "calibración"],
        "datos": [
            "historias clínicas, estudios o señales, con consentimiento y minimización",
            "separación por paciente/institución, no solo por fila",
            "etiquetado clínico revisado; evitar fugas del informe que ya contiene el diagnóstico",
        ],
        "riesgos": [
            "daño al paciente por un falso negativo o un falso positivo",
            "sesgo entre poblaciones e instituciones",
            "privacidad (PHI) y uso fuera de la indicación prevista",
        ],
        "herramientas": [
            "anonimizador / de-identificador",
            "validador de splits por paciente",
            "interfaz de revisión clínica",
            "registro de consentimiento",
        ],
        "mlops": "entorno controlado, trazabilidad de inferencias y umbral acordado con clínicos",
    },
    "recomendacion": {
        "modelos": [
            "popularidad / item-to-item como línea base",
            "filtrado colaborativo o two-tower",
            "re-ranking con reglas de negocio, diversidad y stock",
        ],
        "metricas_default": ["nDCG", "Recall@K", "MAP", "diversidad", "tasa de clic"],
        "datos": [
            "eventos implícitos (clic, vista, compra) y catálogo",
            "tratamiento del sesgo de exposición y del cold start",
        ],
        "riesgos": [
            "cámaras de eco y sesgo de popularidad",
            "recomendaciones inapropiadas o que violan política",
            "fuga de interacciones futuras en el entrenamiento",
        ],
        "herramientas": [
            "generador de candidatos",
            "re-ranker de negocio",
            "filtro de políticas",
            "exploración controlada (bandit)",
        ],
        "mlops": "pipeline de features en tiempo real, evaluación offline + prueba A/B",
    },
    "series_temporales": {
        "modelos": [
            "línea base estadística (ETS, Prophet o media móvil estacional)",
            "gradient boosting sobre rezagos, calendario y exógenas",
            "modelo de redes (N-BEATS / TFT) solo si hay volumen y regularidad",
        ],
        "metricas_default": ["MAPE", "sMAPE", "RMSE", "sesgo de pronóstico"],
        "datos": [
            "serie regular con calendario, festivos y rupturas de stock",
            "exógenas (precio, promoción, precio de competencia) alineadas en el tiempo",
            "splits temporales; nunca barajar filas",
        ],
        "riesgos": [
            "fuga temporal por normalizar con el futuro o usar ventas ya afectadas por quiebre",
            "cambio de régimen (temporada, inflación, nueva tienda)",
            "optimizar el error y no la decisión de inventario",
        ],
        "herramientas": [
            "validador de split temporal",
            "simulador de inventario y quiebre",
            "monitor de sesgo y drift estacional",
        ],
        "mlops": "reentrenamiento programado, predicción por horizonte y monitoreo del sesgo acumulado",
    },
    "vision": {
        "modelos": [
            "clasificador o detector preentrenado (transferencia) como línea base",
            "ajuste fino del backbone con aumento de datos acorde al dominio",
            "conjunto de modelos o distillación si hay restricción de latencia o dispositivo",
        ],
        "metricas_default": ["mAP", "IoU", "F1", "sensibilidad por clase"],
        "datos": [
            "imágenes etiquetadas con guía de anotación y acuerdo entre anotadores",
            "variación de iluminación, cámara y contexto real de despliegue",
            "separación por fuente/cámara para no inflar el resultado",
        ],
        "riesgos": [
            "degradación ante cambio de cámara o condiciones no vistas",
            "sesgo si el etiquetado está concentrado en un solo contexto",
            "privacidad de rostros o escenas sensibles",
        ],
        "herramientas": [
            "revisión de anotaciones",
            "suite de aumentos y pruebas de robustez",
            "filtro de PII visual",
        ],
        "mlops": "versión de pesos + preprocesado acoplados; monitoreo de confianza y drift de imagen",
    },
    "audio": {
        "modelos": [
            "modelo ASR o clasificador de audio preentrenado, adaptado al acento y al canal",
            "pipeline de diarización + transcripción + tarea posterior (si aplica)",
        ],
        "metricas_default": ["WER", "CER", "F1", "latencia de streaming"],
        "datos": [
            "grabaciones del canal real (teléfono, micrófono de piso, ruido)",
            "transcripciones revisadas; cuidado con datos de personas no consentidas",
        ],
        "riesgos": [
            "error alto en acentos o ruido no representados",
            "privacidad de voz como dato biométrico",
        ],
        "herramientas": [
            "normalizador de audio",
            "evaluador WER",
            "redactor de PII en transcripciones",
        ],
        "mlops": "servicio por lotes o streaming, con control de calidad de audio a la entrada",
    },
    "nlp": {
        "modelos": [
            "línea base clásica (TF-IDF + modelo lineal) para medir el piso",
            "encoder o LLM con ajuste / RAG, según haya o no corpus interno",
            "guardrails de salida y citas cuando se genera texto",
        ],
        "metricas_default": ["F1", "exactitud", "exactitud de citas", "toxicidad"],
        "datos": [
            "corpus etiquetado o documentos internos con control de acceso",
            "separación por documento/fuente; limpieza de PII",
        ],
        "riesgos": [
            "alucinación y citas inventadas",
            "fuga de documentos internos en el prompt o en el fine-tune",
            "sesgo e instrucciones inyectadas en el texto de entrada",
        ],
        "herramientas": [
            "buscador / retriever",
            "validador de citas",
            "filtro de PII e inyección de prompt",
        ],
        "mlops": "trazas de prompt, versión del índice y evaluación continua del retriever",
    },
    "aprendizaje_por_refuerzo": {
        "modelos": [
            "línea base de control clásico o política heurística",
            "contextual bandit si la acción es puntual",
            "RL completo solo con simulador fiable o con exploración muy limitada",
        ],
        "metricas_default": ["recompensa acumulada", "arrepentimiento", "seguridad de la política"],
        "datos": [
            "trazas de estado-acción-recompensa y, si existe, un simulador validado",
        ],
        "riesgos": [
            "exploración que causa daño en el entorno real",
            "recompensa mal especificada que el agente explota",
        ],
        "herramientas": [
            "simulador",
            "límites de acción (guardrails)",
            "evaluador off-policy",
        ],
        "mlops": "política versionada, canary y interruptor de reversión a la política segura",
    },
    "anomalias": {
        "modelos": [
            "línea base estadística (z-score, isolation forest, autoencoder simple)",
            "modelo temporal si la señal es una serie",
            "reglas de negocio superpuestas para eventos ya conocidos",
        ],
        "metricas_default": ["precision en alertas", "recall", "tiempo de detección"],
        "datos": [
            "telemetría o transacciones en ventanas temporales",
            "etiqueta demorada o solo de incidentes confirmados",
        ],
        "riesgos": [
            "alerta excesiva que se ignora (fatiga)",
            "concept drift que vuelve normal lo que antes era raro",
        ],
        "herramientas": [
            "consola de alerta",
            "monitor de tasa de alertas",
            "feedback del analista",
        ],
        "mlops": "umbrales adaptativos y retraining ante cambio de volumen o de régimen",
    },
    "clustering": {
        "modelos": [
            "k-means / k-prototipos como línea base",
            "mezclas gaussianas o clustering jerárquico según la forma de los grupos",
            "validación con indicadores internos y revisión de negocio",
        ],
        "metricas_default": ["silueta", "estabilidad", "utilidad de negocio de los segmentos"],
        "datos": [
            "features comparables, tratamiento de outliers y de escalas",
        ],
        "riesgos": [
            "segmentos inestables en el tiempo",
            "interpretación causal de un grupo que solo es correlacional",
        ],
        "herramientas": [
            "perfilador de segmentos",
            "prueba de estabilidad",
        ],
        "mlops": "re-segmentación periódica y seguimiento de migración entre grupos",
    },
    "clasificacion": {
        "modelos": [
            "modelo lineal o árbol como línea base",
            "gradient boosting o encoder, según el tipo de dato",
            "calibración de probabilidades y umbral según el costo de error",
        ],
        "metricas_default": ["F1", "precision", "recall", "AUC"],
        "datos": [
            "etiquetas confiables, manejo de desbalance y de clases raras",
        ],
        "riesgos": [
            "umbral inadecuado al costo real del error",
            "sesgo entre grupos si hay decisión de impacto",
        ],
        "herramientas": [
            "curva de umbral",
            "reporte de equidad",
            "monitor de drift de entrada",
        ],
        "mlops": "servicio de inferencia con registro de probabilidad y de decisión",
    },
    "regresion": {
        "modelos": [
            "regresión lineal / regularizada como línea base",
            "gradient boosting o redes, si hay no linealidad clara",
        ],
        "metricas_default": ["RMSE", "MAE", "R²", "sesgo por segmento"],
        "datos": [
            "variables numéricas y categóricas alineadas al momento de la predicción",
        ],
        "riesgos": [
            "extrapolación fuera del rango de entrenamiento",
            "objetivos que se filtran en las features",
        ],
        "herramientas": [
            "análisis de residuales",
            "monitor de sesgo",
        ],
        "mlops": "reentrenamiento ante cambio de distribución del objetivo",
    },
    "general": {
        "modelos": [
            "empezar por una línea base simple y medible",
            "subir complejidad solo si gana en validación honesta",
            "separar el problema en datos, modelo, decisión y monitoreo",
        ],
        "metricas_default": ["métrica de tarea", "costo", "latencia"],
        "datos": [
            "definir la unidad de decisión, la etiqueta y el momento en que cada feature está disponible",
        ],
        "riesgos": [
            "construir un modelo antes de tener un problema y una métrica claros",
            "falta de trazabilidad de decisiones",
        ],
        "herramientas": [
            "evaluador de métricas",
            "registro de experimentos",
            "monitor básico de entradas y salidas",
        ],
        "mlops": "experimento reproducible, umbral de aceptación y plan de monitoreo",
    },
}


FEATURE_TERMS = [
    "precio", "precios", "promocion", "promociones", "descuento", "ventas",
    "inventario", "stock", "demanda", "edad", "ingreso", "ingresos", "genero",
    "ubicacion", "gps", "latitud", "imagen", "imagenes", "foto", "fotos",
    "texto", "comentario", "reviews", "audio", "voz", "transaccion",
    "monto", "fecha", "timestamp", "hora", "dia", "semana", "mes",
    "dispositivo", "ip", "historial", "clicks", "vistas", "sesiones",
    "temperatura", "sensor", "laboratorio", "sintoma", "diagnostico",
    "score", "bureau", "morosidad", "plazo", "tasa", "categoria",
]

CONSTRAINT_PATTERNS: list[tuple[str, str]] = [
    (r"presupuesto(?:\s+(?:limitado|bajo|reducido|acotado|pequeño|pequeno))?", "presupuesto"),
    (r"barato|bajo costo|costo limitado|sin presupuesto", "presupuesto limitado"),
    (r"latenc\w*\s*(?:menor a|menor que|menor de|de menos de|inferior a)?\s*\d+\s*ms|menos de \d+\s*ms", "latencia acotada"),
    (r"tiempo real|en linea|online|streaming", "tiempo real / baja latencia"),
    (r"privacidad|gdpr|lfpdppp|datos personales|phi\b|hipaa", "privacidad y protección de datos"),
    (r"on[- ]?prem|on premise|sin nube|local(?:mente)?|no (?:usar |salir a )?la nube", "despliegue on-premise o local"),
    (r"sin gpu|solo cpu|cpu only", "sin GPU"),
    (r"interpretab\w+|explicab\w+|reason codes|xai\b", "interpretabilidad"),
    (r"en \d+\s*(?:dias|semanas|meses)|plazo de|antes de", "plazo de entrega"),
    (r"multilingual|espanol|multilenguaje", "requerimiento de idioma"),
    (r"regulator\w+|cumplimiento|auditor\w+", "restricción regulatoria"),
]

RESOURCE_PATTERNS: list[tuple[str, str]] = [
    (r"kaggle|dataset publico|datos abiertos", "dataset público"),
    (r"data warehouse|data lake|warehouse|snowflake|bigquery|redshift", "almacén de datos"),
    (r"\d+\s*gpu|cluster|spark|kubernetes|sagemaker", "capacidad de cómputo"),
    (r"equipo de \d+|data scientist|cientificos de datos|ml engineer", "equipo de datos / ML"),
    (r"api de [\w\-]+|openai|anthropic|ollama|modelo propio", "API o modelo ya disponible"),
    (r"anotador|labeler|etiquetadores", "capacidad de etiquetado"),
]

METRIC_TERMS = [
    "accuracy", "exactitud", "precision", "precisión", "recall", "sensibilidad",
    "especificidad", "f1", "f1-score", "auc", "roc", "rmse", "mae", "mape",
    "smape", "ndcg", "map", "wer", "iou", "map@", "latencia", "p95", "p99",
    "costo", "gini", "ks", "r2", "r²", "calibracion", "calibración",
]
