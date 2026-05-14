"""Tool definitions the agent can call.

We send these to the provider as a ``tools=[...]`` parameter; the
model decides when to invoke each one, our service layer routes the
call into :mod:`app.transforms`, and we hand the result back as a
``tool_result`` in the next turn.

Design notes
------------

The product position is that **the agent is the data scientist** —
it decides what to run and runs it. The user gives business context
("voy a entrenar un modelo de churn"), the agent picks the cleaning
pipeline. So almost every tool here is *auto-run*: the agent invokes,
the platform executes, the result lands in the chat as a visual.

The original ``propose_*`` pattern (chat card with [Aceptar /
Rechazar]) is reserved for genuinely irreversible / costly actions —
we'll bring it back when we have one. For routine cleaning the
agent just acts; the user can always undo a step from the journal.

Working-copy safety net
-----------------------

Every transform writes to the user's working copy, not the source
dataset. So even a mistaken op is recoverable — we keep the
``before`` snapshot for each row in ``dataset_operations`` and an
"Undo" surface lives in the frontend.

Tool spec shape
---------------

Anthropic tools take ``{name, description, input_schema}`` where
``input_schema`` is JSON-Schema-ish. We hand-write them so the
description is tuned for *agent prompting* (when to use, what each
arg means in the user's words) rather than auto-generated from
Pydantic.
"""

from __future__ import annotations

from typing import Any

TOOLS: list[dict[str, Any]] = [
    # ----- Inspection -----------------------------------------------------
    {
        "name": "inspect_column",
        "description": (
            "USA ESTA TOOL para mirar el contenido de una columna del "
            "dataset. Devuelve la distribución de valores, estadísticos "
            "básicos y el porcentaje de nulos. El resultado se renderiza "
            "automáticamente como un gráfico que el usuario ve inline "
            "(histograma para numéricas, barras horizontales para "
            "texto, donut con el % de nulos). **Llámala al inicio de "
            "casi cualquier análisis** — es la forma de ver qué hay sin "
            "tener que pedirle nada al usuario. Llamarla varias veces, "
            "una por columna interesante, es lo esperado."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "column": {
                    "type": "string",
                    "description": "Nombre exacto de la columna (sensible a mayúsculas).",
                },
            },
            "required": ["column"],
        },
    },
    {
        "name": "preview_duplicates",
        "description": (
            "Sin eliminar nada, encuentra cuántos duplicados habría si "
            "deduplicaras por una o varias columnas. Útil para reportar "
            "al usuario qué encontraste antes de ejecutar ``dedupe``, o "
            "para validar tu propuesta interna."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
            },
            "required": ["columns"],
        },
    },
    # ----- Mutating ops (all auto-run, no approval card) -----------------
    {
        "name": "dedupe",
        "description": (
            "EJECUTA la eliminación de filas duplicadas según una o "
            "varias columnas. Esta tool corre la operación real — no "
            "es una propuesta, no requiere aprobación. El original "
            "queda intacto en la copia de trabajo del usuario y el "
            "cambio queda en el journal por si quiere deshacerlo. "
            "Llámala apenas detectes una columna con identidad clara "
            "(email, id, customer_id, etc.)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": (
                        "Columnas que definen 'duplicado'. ['email'] elimina "
                        "filas con el mismo email; ['nombre', 'apellido'] "
                        "compara la combinación."
                    ),
                },
                "keep": {
                    "type": "string",
                    "enum": ["first", "last"],
                    "description": "Cuál fila de cada grupo duplicado conservar.",
                },
                "normalize_text": {
                    "type": "boolean",
                    "description": (
                        "Comparar texto normalizado (minúsculas + sin "
                        "espacios extra) — útil para 'Juan@correo.com' vs "
                        "'juan@correo.com'."
                    ),
                },
            },
            "required": ["columns"],
        },
    },
    {
        "name": "fillna",
        "description": (
            "EJECUTA el relleno de valores nulos / faltantes. Cuando "
            "omites 'columns' actúa sobre todas las que tienen nulos — "
            "que es lo más común. ``strategy='auto'`` (default) es lo "
            "que vas a querer casi siempre: mediana para numéricas, "
            "moda para texto. Solo usa ``strategy='drop_row'`` si los "
            "nulos son tantos que imputar arruinaría el análisis. "
            "Llámala cerca del final del pipeline, después de que las "
            "demás transformaciones hayan ocurrido."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Omite para auto-detectar todas las columnas con nulos.",
                },
                "strategy": {
                    "type": "string",
                    "enum": ["auto", "median", "mean", "mode", "constant", "drop_row"],
                    "description": (
                        "'auto' = mediana para numéricas, moda para texto "
                        "(default seguro). 'constant' requiere 'constant'. "
                        "'drop_row' elimina filas con muchos nulos."
                    ),
                },
                "constant": {
                    "description": (
                        "Valor literal para strategy='constant' (str, int, float)."
                    ),
                },
                "min_pct_to_drop": {
                    "type": "number",
                    "description": (
                        "Solo aplica con strategy='drop_row'. Fracción mínima "
                        "(0-1) de columnas nulas en una fila para eliminarla. "
                        "Default 0.5."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "normalize_text",
        "description": (
            "EJECUTA la limpieza de variantes de texto: casing "
            "inconsistente, espacios extra, acentos. Default sensible: "
            "'title' case + strip + collapse_spaces. Llámala apenas "
            "veas columnas con 'España'/'españa'/'ESPAÑA' o con "
            "espacios sueltos — es seguro y rápido."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
                "case": {
                    "type": "string",
                    "enum": ["lower", "upper", "title", "preserve"],
                    "description": "Casing final. 'preserve' solo arregla espacios/acentos.",
                },
                "strip": {"type": "boolean"},
                "collapse_spaces": {"type": "boolean"},
                "remove_accents": {
                    "type": "boolean",
                    "description": (
                        "false por default — el español a veces necesita acentos. "
                        "Actívalo cuando el dataset tenga 'Mexico' / 'México' "
                        "como variantes."
                    ),
                },
            },
            "required": ["columns"],
        },
    },
    {
        "name": "parse_dates",
        "description": (
            "EJECUTA la conversión de columnas de texto con fechas a "
            "datetime tipado. Prueba varios formatos comunes en orden y "
            "se queda con el que más filas reconozca. Llámala apenas "
            "veas una columna que parezca fecha pero esté tipada como "
            "texto (algo como 'fecha_registro', 'created_at', etc.)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
                "formats": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Lista opcional de formatos strftime para probar en "
                        "orden. Omite para usar el set default que cubre "
                        "ISO, dd/mm/yyyy, mm/dd/yyyy, con y sin hora."
                    ),
                },
            },
            "required": ["columns"],
        },
    },
    {
        "name": "normalize_numeric",
        "description": (
            "EJECUTA la conversión de strings como '1,234.56' / '$ 1.200' / "
            "'45%' a números reales. Detecta el separador decimal "
            "automáticamente. Llámala apenas veas una columna que debería "
            "ser numérica pero llegó como texto con símbolos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
                "decimal": {
                    "type": "string",
                    "enum": ["auto", ".", ","],
                    "description": (
                        "'auto' detecta por frecuencia. '.' fuerza punto "
                        "decimal (estilo US). ',' fuerza coma decimal "
                        "(estilo EU)."
                    ),
                },
            },
            "required": ["columns"],
        },
    },
]


# Reserved for future irreversible / costly ops. Empty for the current
# slice — every tool above is auto-run and the user controls outcomes
# via the undo journal, not by approving each step.
PENDING_ACTION_TOOLS: set[str] = set()


__all__ = ["PENDING_ACTION_TOOLS", "TOOLS"]
