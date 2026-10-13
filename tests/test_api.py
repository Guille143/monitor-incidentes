"""Tests de la API. Usan una base SQLite en memoria, sin Docker.

Correr con:  pytest
"""
import os

os.environ["DATABASE_URL"] = "sqlite://"  # en memoria

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
SesionTest = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)


def get_db_test():
    db = SesionTest()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = get_db_test
cliente = TestClient(app)

EJEMPLO = {
    "fecha_inicio": "2026-10-01T03:15:00",
    "zona": "Zapala",
    "tipo": "corte de fibra",
    "severidad": "alta",
    "descripcion": "Corte de fibra en tramo troncal.",
}


def test_salud():
    assert cliente.get("/salud").json() == {"estado": "ok"}


def test_crear_y_obtener():
    creado = cliente.post("/incidentes", json=EJEMPLO)
    assert creado.status_code == 201
    datos = creado.json()
    assert datos["estado"] == "abierto"

    obtenido = cliente.get(f"/incidentes/{datos['id']}")
    assert obtenido.status_code == 200
    assert obtenido.json()["zona"] == "Zapala"


def test_severidad_invalida():
    malo = {**EJEMPLO, "severidad": "urgentísima"}
    assert cliente.post("/incidentes", json=malo).status_code == 422


def test_resolver():
    id_ = cliente.post("/incidentes", json=EJEMPLO).json()["id"]
    r = cliente.patch(f"/incidentes/{id_}/resolver", json={"fecha_resolucion": "2026-10-01T07:15:00"})
    assert r.status_code == 200
    assert r.json()["estado"] == "resuelto"

    # No se puede resolver dos veces.
    otra = cliente.patch(f"/incidentes/{id_}/resolver", json={"fecha_resolucion": "2026-10-01T08:00:00"})
    assert otra.status_code == 409


def test_resolucion_anterior_al_inicio():
    id_ = cliente.post("/incidentes", json=EJEMPLO).json()["id"]
    r = cliente.patch(f"/incidentes/{id_}/resolver", json={"fecha_resolucion": "2026-09-30T00:00:00"})
    assert r.status_code == 422


def test_filtro_por_zona():
    cliente.post("/incidentes", json={**EJEMPLO, "zona": "Plottier"})
    resultado = cliente.get("/incidentes", params={"zona": "Plottier"}).json()
    assert resultado and all(i["zona"] == "Plottier" for i in resultado)


def test_no_encontrado():
    assert cliente.get("/incidentes/99999").status_code == 404


def test_estadisticas():
    zonas = cliente.get("/estadisticas/zonas").json()
    zapala = next(z for z in zonas if z["zona"] == "Zapala")
    assert zapala["cantidad"] >= 1
    assert zapala["minutos_promedio_resolucion"] == 240.0
