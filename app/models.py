"""Modelo de la tabla de incidentes."""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Incidente(Base):
    __tablename__ = "incidentes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime, index=True)
    fecha_resolucion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    zona: Mapped[str] = mapped_column(String(50), index=True)
    tipo: Mapped[str] = mapped_column(String(50), index=True)
    severidad: Mapped[str] = mapped_column(String(10))  # baja, media, alta
    estado: Mapped[str] = mapped_column(String(20), default="abierto")  # abierto, resuelto
    descripcion: Mapped[str] = mapped_column(Text)
