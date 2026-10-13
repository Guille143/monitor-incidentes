"""API de incidentes de red.

Endpoints:
  GET   /salud                      -> chequeo de que la API está viva
  GET   /incidentes                 -> lista con filtros (zona, tipo, estado, severidad)
  GET   /incidentes/{id}            -> un incidente
  POST  /incidentes                 -> crear un incidente
  PATCH /incidentes/{id}/resolver   -> marcarlo como resuelto
  GET   /estadisticas/zonas         -> cantidad y tiempo promedio de resolución por zona
"""
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models, schemas
from .database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Monitor de Incidentes",
    description="API para registrar, consultar y analizar incidentes de red.",
    version="0.1.0",
)


@app.get("/salud")
def salud():
    return {"estado": "ok"}


@app.get("/incidentes", response_model=list[schemas.Incidente])
def listar_incidentes(
    zona: str | None = None,
    tipo: str | None = None,
    estado: schemas.Estado | None = None,
    severidad: schemas.Severidad | None = None,
    limite: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    consulta = select(models.Incidente)
    if zona:
        consulta = consulta.where(models.Incidente.zona == zona)
    if tipo:
        consulta = consulta.where(models.Incidente.tipo == tipo)
    if estado:
        consulta = consulta.where(models.Incidente.estado == estado)
    if severidad:
        consulta = consulta.where(models.Incidente.severidad == severidad)
    consulta = consulta.order_by(models.Incidente.fecha_inicio.desc()).limit(limite)
    return db.scalars(consulta).all()


@app.get("/incidentes/{incidente_id}", response_model=schemas.Incidente)
def obtener_incidente(incidente_id: int, db: Session = Depends(get_db)):
    incidente = db.get(models.Incidente, incidente_id)
    if incidente is None:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    return incidente


@app.post("/incidentes", response_model=schemas.Incidente, status_code=201)
def crear_incidente(datos: schemas.IncidenteCrear, db: Session = Depends(get_db)):
    incidente = models.Incidente(**datos.model_dump(), estado="abierto")
    db.add(incidente)
    db.commit()
    db.refresh(incidente)
    return incidente


@app.patch("/incidentes/{incidente_id}/resolver", response_model=schemas.Incidente)
def resolver_incidente(
    incidente_id: int, datos: schemas.IncidenteResolver, db: Session = Depends(get_db)
):
    incidente = db.get(models.Incidente, incidente_id)
    if incidente is None:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    if incidente.estado == "resuelto":
        raise HTTPException(status_code=409, detail="El incidente ya está resuelto")
    if datos.fecha_resolucion < incidente.fecha_inicio:
        raise HTTPException(
            status_code=422, detail="La resolución no puede ser anterior al inicio"
        )
    incidente.fecha_resolucion = datos.fecha_resolucion
    incidente.estado = "resuelto"
    db.commit()
    db.refresh(incidente)
    return incidente


@app.get("/estadisticas/zonas", response_model=list[schemas.ResumenZona])
def estadisticas_por_zona(db: Session = Depends(get_db)):
    """Cantidad de incidentes y tiempo promedio de resolución por zona.

    El promedio se calcula en Python para que funcione igual en SQLite y MariaDB.
    """
    filas = db.execute(
        select(
            models.Incidente.zona,
            models.Incidente.fecha_inicio,
            models.Incidente.fecha_resolucion,
        )
    ).all()

    por_zona: dict[str, list] = {}
    for zona, inicio, fin in filas:
        por_zona.setdefault(zona, []).append(
            (fin - inicio).total_seconds() / 60 if fin else None
        )

    resumen = []
    for zona, duraciones in por_zona.items():
        resueltas = [d for d in duraciones if d is not None]
        promedio = round(sum(resueltas) / len(resueltas), 1) if resueltas else None
        resumen.append(
            schemas.ResumenZona(
                zona=zona, cantidad=len(duraciones), minutos_promedio_resolucion=promedio
            )
        )
    return sorted(resumen, key=lambda r: r.cantidad, reverse=True)
