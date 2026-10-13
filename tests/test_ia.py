"""Tests de la integración con IA. Usan un cliente falso: no llaman a la API real
ni gastan créditos."""
from types import SimpleNamespace

import pytest

from app import ia


class ClienteFalso:
    """Imita a anthropic.Anthropic(): guarda lo que se le pide y devuelve una respuesta armada."""

    def __init__(self, contenido):
        self.contenido = contenido
        self.pedidos = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.pedidos.append(kwargs)
        return SimpleNamespace(content=self.contenido)


def respuesta_herramienta(**datos):
    return [SimpleNamespace(type="tool_use", name="registrar_clasificacion", input=datos)]


CLASIFICACION = {
    "tipo": "corte de fibra",
    "severidad": "alta",
    "causa_probable": "Daño físico en el tendido por obra.",
    "accion_sugerida": "Enviar cuadrilla de empalme al tramo afectado.",
}


def test_clasificar_devuelve_los_datos_de_la_herramienta():
    cliente = ClienteFalso(respuesta_herramienta(**CLASIFICACION))
    resultado = ia.clasificar("Se cortó la fibra por una obra en ruta 22", cliente)
    assert resultado == CLASIFICACION
    pedido = cliente.pedidos[0]
    assert pedido["model"] == ia.MODELO
    assert "ruta 22" in pedido["messages"][0]["content"]


def test_clasificar_rechaza_tipo_inventado():
    cliente = ClienteFalso(respuesta_herramienta(**{**CLASIFICACION, "tipo": "ovnis"}))
    with pytest.raises(ia.IAError):
        ia.clasificar("Algo raro pasó en el nodo", cliente)


def test_clasificar_sin_herramienta_falla():
    cliente = ClienteFalso([SimpleNamespace(type="text", text="No sé")])
    with pytest.raises(ia.IAError):
        ia.clasificar("Texto ambiguo de prueba", cliente)


def test_resumir_devuelve_texto():
    cliente = ClienteFalso([SimpleNamespace(type="text", text="  Hubo 10 incidentes.  ")])
    texto = ia.resumir({"total": 10}, cliente)
    assert texto == "Hubo 10 incidentes."
    assert '"total": 10' in cliente.pedidos[0]["messages"][0]["content"]


def test_sin_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ia.IAError):
        ia.crear_cliente()


def test_error_de_la_api_se_convierte_en_iaerror():
    class ClienteQueFalla:
        def __init__(self):
            self.messages = SimpleNamespace(create=self._create)

        def _create(self, **kwargs):
            raise RuntimeError("invalid x-api-key")

    with pytest.raises(ia.IAError):
        ia.clasificar("Texto de prueba del incidente", ClienteQueFalla())
