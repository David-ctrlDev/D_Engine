"""Tool definitions the agent can call.

We send these to the provider as a ``tools=[...]`` parameter; the
model decides when to invoke one, our service layer routes the call
into :mod:`app.transforms`, and we hand the result back as a
``tool_result`` in the next turn.

For G2.2 we ship two tools — enough to prove the loop end-to-end with
``dedupe``:

* ``inspect_column`` — read-only stats for one column. The agent uses
  it to look at the data before proposing a mutation. The result lands
  in the chat as a histogram / value-count chart so the user can see
  what the agent is seeing.

* ``propose_dedupe`` — the agent *proposes* a dedupe. We turn this
  into a "pending action" card in the chat with [Aceptar / Rechazar]
  buttons. The mutation only runs after the user accepts (see
  :func:`app.agent.service.accept_pending_action`).

Tool spec shape
---------------

Anthropic tools take ``{name, description, input_schema}`` where the
schema is JSON-Schema-ish. We hand-write them rather than auto-
generating from Pydantic so the descriptions stay focused on *agent
prompting* (when to use, what each arg means in the user's words).
"""

from __future__ import annotations

from typing import Any

TOOLS: list[dict[str, Any]] = [
    {
        "name": "inspect_column",
        "description": (
            "Mira el contenido de una columna del dataset: distribución de "
            "valores, cantidad de nulos, estadísticos básicos. ÚSALA antes "
            "de proponer una operación que toque esa columna — así puedes "
            "darle al usuario un diagnóstico concreto antes de la "
            "aprobación. El resultado se muestra automáticamente al usuario "
            "como un gráfico inline (histograma para columnas numéricas, "
            "barras de valores más frecuentes para texto)."
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
        "name": "propose_dedupe",
        "description": (
            "Propone eliminar filas duplicadas según una o varias columnas. "
            "Esta tool NO ejecuta nada de inmediato — al invocarla, "
            "dataprep le muestra al usuario una tarjeta con [Aceptar / "
            "Rechazar] y un resumen de los duplicados encontrados. "
            "Solo si el usuario acepta, la ejecución real corre y verás un "
            "tool_result con el conteo final. ÚSALA cuando hayas confirmado "
            "que existen duplicados (con preview o con el análisis de "
            "calidad previo)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": (
                        "Columnas que definen 'duplicado'. Ej: ['email'] "
                        "elimina filas con el mismo email. ['nombre', "
                        "'apellido'] elimina filas con la misma "
                        "combinación de nombre y apellido."
                    ),
                },
                "keep": {
                    "type": "string",
                    "enum": ["first", "last"],
                    "description": (
                        "Cuál fila mantener de cada grupo duplicado. "
                        "'first' = la primera aparición (lo más común). "
                        "'last' = la última (útil cuando hay versiones "
                        "más recientes al final)."
                    ),
                },
                "normalize_text": {
                    "type": "boolean",
                    "description": (
                        "Si true, compara columnas de texto normalizadas "
                        "(minúsculas + sin espacios extra) — útil para "
                        "emails como 'Juan@correo.com' vs 'juan@correo.com'. "
                        "La fila que sobreviva mantiene su casing original."
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": (
                        "Explicación corta (1-2 frases) que el usuario "
                        "verá en la tarjeta de aprobación, en su idioma. "
                        "Ej: 'Hay 3 emails duplicados. Mantengo la "
                        "primera aparición de cada uno.'"
                    ),
                },
            },
            "required": ["columns", "reason"],
        },
    },
]


# Names of tools whose effect should produce a "pending action card"
# (rendered in the chat with Accept/Reject) rather than executing
# immediately. The agent service short-circuits these on receipt.
PENDING_ACTION_TOOLS: set[str] = {"propose_dedupe"}


__all__ = ["PENDING_ACTION_TOOLS", "TOOLS"]
