"""Integración con la API de Claude.

Dos usos:
  - clasificar(): lee la descripción libre de un incidente y devuelve tipo,
    severidad, causa probable y acción sugerida, en un formato fijo.
  - resumir(): convierte las estadísticas del período en un resumen ejecutivo
    en español, como el que leería un jefe de operaciones.

Necesita la variable de entorno ANTHROPIC_API_KEY. Se puede poner en un
archivo .env en la raíz del proyecto (ese archivo no se sube a GitHub).
El modelo se puede cambiar con CLAUDE_MODEL (por defecto, Haiku: rápido y barato).
"""
import json
import os

from dotenv import load_dotenv

load_dotenv()  # lee el archivo .env si existe

MODELO = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")

TIPOS = ["corte de fibra", "caída de equipo", "corte de energía", "degradación", "falla de configuración"]
SEVERIDADES = ["baja", "media", "alta"]


class IAError(Exception):
    """Error al usar la IA (sin API key, respuesta inválida, etc.)."""


def crear_cliente():
    """Crea el cliente de Anthropic. Se importa acá para que el resto
    del proyecto funcione aunque la librería no esté instalada."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise IAError("Falta la variable de entorno ANTHROPIC_API_KEY.")
    import anthropic

    return anthropic.Anthropic()


# La IA responde llamando a esta "herramienta": así la salida siempre
# tiene la misma estructura y la podemos validar.
HERRAMIENTA_CLASIFICAR = {
    "name": "registrar_clasificacion",
    "description": "Registra la clasificación de un incidente de red.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tipo": {"type": "string", "enum": TIPOS},
            "severidad": {"type": "string", "enum": SEVERIDADES},
            "causa_probable": {"type": "string", "description": "Una oración."},
            "accion_sugerida": {"type": "string", "description": "Una oración, el primer paso a seguir."},
        },
        "required": ["tipo", "severidad", "causa_probable", "accion_sugerida"],
    },
}

INSTRUCCIONES_CLASIFICAR = """Sos un analista de un centro de operaciones de red (NOC) de un proveedor de telecomunicaciones.
Clasificá el incidente que te pasan y registralo con la herramienta registrar_clasificacion.

Criterios de severidad:
- alta: muchos clientes sin servicio, o un enlace troncal o nodo caído.
- media: servicio degradado o un sector acotado afectado.
- baja: impacto menor, sin cortes de servicio.

Respondé en español rioplatense, breve y técnico."""


def _llamar(cliente, **parametros):
    """Llama a la API y convierte sus errores (key inválida, sin crédito, etc.)
    en IAError, para que la API devuelva un mensaje claro y no un error 500."""
    try:
        return cliente.messages.create(**parametros)
    except Exception as e:
        raise IAError(f"Error de la API de Claude ({type(e).__name__}): {e}") from e


def clasificar(descripcion: str, cliente=None) -> dict:
    cliente = cliente or crear_cliente()
    respuesta = _llamar(
        cliente,
        model=MODELO,
        max_tokens=1024,
        system=INSTRUCCIONES_CLASIFICAR,
        tools=[HERRAMIENTA_CLASIFICAR],
        messages=[{"role": "user", "content": f"Incidente: {descripcion}"}],
    )
    for bloque in respuesta.content:
        if getattr(bloque, "type", None) == "tool_use" and bloque.name == HERRAMIENTA_CLASIFICAR["name"]:
            datos = dict(bloque.input)
            if datos.get("tipo") not in TIPOS or datos.get("severidad") not in SEVERIDADES:
                raise IAError(f"La IA devolvió valores inválidos: {datos}")
            return datos
    raise IAError("La IA no devolvió una clasificación.")


INSTRUCCIONES_RESUMIR = """Sos un analista de un centro de operaciones de red (NOC).
Con las estadísticas que te pasan, escribí un resumen ejecutivo en español rioplatense para el jefe de operaciones:
- Un párrafo de 3 o 4 oraciones con lo más importante, usando los números.
- Después, hasta 3 recomendaciones concretas, en viñetas.
No inventes datos que no estén en las estadísticas. Sin títulos ni saludos."""


def resumir(estadisticas: dict, cliente=None) -> str:
    cliente = cliente or crear_cliente()
    respuesta = _llamar(
        cliente,
        model=MODELO,
        max_tokens=2048,
        system=INSTRUCCIONES_RESUMIR,
        messages=[{
            "role": "user",
            "content": "Estadísticas del período:\n" + json.dumps(estadisticas, ensure_ascii=False, indent=2),
        }],
    )
    texto = "".join(b.text for b in respuesta.content if getattr(b, "type", None) == "text").strip()
    if not texto:
        raise IAError("La IA no devolvió texto.")
    return texto
