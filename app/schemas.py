"""Esquemas de Pydantic: validan lo que entra y lo que sale de la API."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severidad = Literal["baja", "media", "alta"]
Estado = Literal["abierto", "resuelto"]


class IncidenteCrear(BaseModel):
    fecha_inicio: datetime
    zona: str = Field(min_length=2, max_length=50)
    tipo: str = Field(min_length=2, max_length=50)
    severidad: Severidad
    descripcion: str = Field(min_length=5)


class IncidenteResolver(BaseModel):
    fecha_resolucion: datetime


class Incidente(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_inicio: datetime
    fecha_resolucion: datetime | None
    zona: str
    tipo: str
    severidad: Severidad
    estado: Estado
    descripcion: str


class ResumenZona(BaseModel):
    zona: str
    cantidad: int
    minutos_promedio_resolucion: float | None
