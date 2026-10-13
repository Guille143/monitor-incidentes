"""Tests del análisis. Usan un DataFrame armado a mano, sin base de datos."""
import pandas as pd

from app import analisis


def datos_de_prueba() -> pd.DataFrame:
    filas = [
        # id, inicio, resolución, zona, tipo, severidad, estado
        (1, "2026-10-01 02:00", "2026-10-01 06:00", "Zapala", "corte de fibra", "alta", "resuelto"),
        (2, "2026-10-01 03:00", "2026-10-01 05:00", "Zapala", "corte de fibra", "alta", "resuelto"),
        (3, "2026-10-02 14:00", "2026-10-02 14:30", "Plottier", "caída de equipo", "media", "resuelto"),
        (4, "2026-10-03 14:00", None, "Zapala", "caída de equipo", "media", "abierto"),
    ]
    df = pd.DataFrame(filas, columns=analisis.COLUMNAS)
    return analisis.preparar(df)


def test_preparar_calcula_duracion_y_hora():
    df = datos_de_prueba()
    assert df.loc[0, "duracion_min"] == 240
    assert df.loc[0, "hora"] == 2
    assert pd.isna(df.loc[3, "duracion_min"])


def test_por_zona():
    zonas = analisis.por_zona(datos_de_prueba())
    zapala = zonas.iloc[0]
    assert zapala["zona"] == "Zapala"
    assert zapala["cantidad"] == 3
    assert zapala["abiertos"] == 1
    assert zapala["porcentaje"] == 75.0
    assert zapala["mediana_resolucion_min"] == 180  # mediana de 240 y 120


def test_por_tipo_ordena_por_mas_lento():
    tipos = analisis.por_tipo(datos_de_prueba())
    assert tipos.iloc[0]["tipo"] == "corte de fibra"


def test_por_hora_tiene_24_horas():
    horas = analisis.por_hora(datos_de_prueba())
    assert len(horas) == 24
    assert horas[14] == 2
    assert horas[10] == 0


def test_por_dia_completa_dias_sin_incidentes():
    dias = analisis.por_dia(datos_de_prueba())
    assert len(dias) == 3
    assert dias["cantidad"].sum() == 4


def test_resumen():
    r = analisis.resumen(datos_de_prueba())
    assert r["total"] == 4
    assert r["abiertos"] == 1
    assert r["zona_mas_afectada"] == "Zapala"
    assert r["porcentaje_nocturno"] == 50.0
