"""API de incidentes de red.

Endpoints:
  GET   /salud                      -> chequeo de que la API está viva
  GET   /incidentes                 -> lista con filtros (zona, tipo, estado, severidad)
  GET   /incidentes/{id}            -> un incidente
  POST  /incidentes                 -> crear un incidente
  PATCH /incidentes/{id}/resolver   -> marcarlo como resuelto
  GET   /estadisticas/zonas         -> cantidad y tiempo promedio de resolución por zona

Con IA (necesitan ANTHROPIC_API_KEY):
  POST  /ia/clasificar              -> clasifica un texto libre, sin guardarlo
  POST  /incidentes/desde-texto     -> clasifica un texto libre y lo guarda como incidente
  GET   /ia/resumen?dias=7          -> resumen ejecutivo de los últimos días
"""
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import ia, models, schemas
from .database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Monitor de Incidentes",
    description="API para registrar, consultar y analizar incidentes de red.",
    version="0.3.0",
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


# ---------- Endpoints con IA ----------

def get_cliente_ia():
    """Dependencia: el cliente de Claude. En los tests se reemplaza por uno falso."""
    try:
        return ia.crear_cliente()
    except ia.IAError as e:
        raise HTTPException(status_code=503, detail=str(e))


def _clasificar(descripcion: str, cliente) -> dict:
    try:
        return ia.clasificar(descripcion, cliente)
    except ia.IAError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/ia/clasificar", response_model=schemas.ClasificacionIA)
def clasificar_texto(datos: schemas.TextoIncidente, cliente=Depends(get_cliente_ia)):
    return _clasificar(datos.descripcion, cliente)


@app.post("/incidentes/desde-texto", response_model=schemas.IncidenteClasificado, status_code=201)
def crear_desde_texto(
    datos: schemas.IncidenteDesdeTexto,
    db: Session = Depends(get_db),
    cliente=Depends(get_cliente_ia),
):
    """Recibe la descripción como la escribiría un operador; la IA completa tipo y severidad."""
    clasificacion = _clasificar(datos.descripcion, cliente)
    incidente = models.Incidente(
        fecha_inicio=datos.fecha_inicio or datetime.now().replace(microsecond=0),
        zona=datos.zona,
        tipo=clasificacion["tipo"],
        severidad=clasificacion["severidad"],
        estado="abierto",
        descripcion=datos.descripcion,
    )
    db.add(incidente)
    db.commit()
    db.refresh(incidente)
    return {"incidente": incidente, "clasificacion": clasificacion}


def _sin_nan(valor):
    """Reemplaza NaN por None (JSON no admite NaN). Pasa, por ejemplo,
    con la mediana de un tipo de falla que todavía no tiene incidentes resueltos."""
    if isinstance(valor, dict):
        return {k: _sin_nan(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_sin_nan(v) for v in valor]
    if isinstance(valor, float) and valor != valor:
        return None
    return valor


@app.get("/ia/resumen", response_model=schemas.ResumenIA)
def resumen_con_ia(
    dias: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db),
    cliente=Depends(get_cliente_ia),
):
    """Calcula las estadísticas de los últimos `dias` días y pide a la IA un resumen ejecutivo."""
    import pandas as pd  # se importa acá para que la API arranque aunque pandas no esté disponible

    from . import analisis

    desde = datetime.now() - timedelta(days=dias)
    filas = db.scalars(select(models.Incidente).where(models.Incidente.fecha_inicio >= desde)).all()
    if not filas:
        raise HTTPException(status_code=404, detail=f"No hay incidentes en los últimos {dias} días")

    df = analisis.preparar(pd.DataFrame([{c: getattr(f, c) for c in analisis.COLUMNAS} for f in filas]))
    estadisticas = analisis.resumen(df)
    estadisticas["por_tipo"] = analisis.por_tipo(df).to_dict(orient="records")
    estadisticas = _sin_nan(estadisticas)

    try:
        texto = ia.resumir(estadisticas, cliente)
    except ia.IAError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"dias": dias, "estadisticas": estadisticas, "resumen": texto}
