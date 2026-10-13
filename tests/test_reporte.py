"""Tests del reporte diario."""
from datetime import datetime

import pandas as pd

from app import analisis, reporte

AHORA = datetime(2026, 10, 13, 9, 0)


def datos_de_prueba() -> pd.DataFrame:
    filas = [
        # Últimas 24 horas: 3 incidentes, 2 de severidad alta, 1 abierto
        (1, "2026-10-13 02:00", "2026-10-13 05:00", "Zapala", "corte de fibra", "alta", "resuelto"),
        (2, "2026-10-12 20:00", None, "Zapala", "corte de energía", "alta", "abierto"),
        (3, "2026-10-12 12:00", "2026-10-12 13:00", "Plottier", "degradación", "baja", "resuelto"),
        # Días anteriores: 3 incidentes en los 30 días de comparación (promedio 0.1 por día)
        (4, "2026-10-10 10:00", "2026-10-10 11:00", "Cipolletti", "caída de equipo", "media", "resuelto"),
        (5, "2026-10-01 10:00", None, "Cipolletti", "degradación", "media", "abierto"),
        (6, "2026-09-20 10:00", "2026-09-20 11:00", "Zapala", "degradación", "baja", "resuelto"),
    ]
    return analisis.preparar(pd.DataFrame(filas, columns=analisis.COLUMNAS))


def test_construir_datos():
    datos = reporte.construir_datos(datos_de_prueba(), AHORA, dias_comparacion=30)
    assert datos["total_24h"] == 3
    assert datos["alta_24h"] == 2
    assert datos["promedio_diario"] == 0.1
    assert datos["variacion_pct"] == 2900  # 3 contra 0.1 por día
    assert datos["por_zona_24h"] == {"Zapala": 2, "Plottier": 1}


def test_abiertos_ordenados_por_severidad():
    abiertos = reporte.construir_datos(datos_de_prueba(), AHORA)["abiertos"]
    assert [a["id"] for a in abiertos] == [2, 5]  # primero el de severidad alta
    assert abiertos[0]["horas_abierto"] == 13.0


def test_html_sin_ia():
    datos = reporte.construir_datos(datos_de_prueba(), AHORA)
    html = reporte.renderizar_html(datos, [], None)
    assert "Reporte diario de incidentes" in html
    assert "Resumen con IA no disponible" in html
    assert "13/10/2026" in html


def test_html_con_ia_escapa_y_arma_lista():
    datos = reporte.construir_datos(datos_de_prueba(), AHORA)
    html = reporte.renderizar_html(datos, [], "Día complicado en <Zapala>.\n- Revisar energía\n- Reforzar guardia")
    assert "&lt;Zapala&gt;" in html
    assert "<li>Revisar energía</li>" in html


def test_para_ia():
    resumen = reporte.para_ia(reporte.construir_datos(datos_de_prueba(), AHORA))
    assert resumen["incidentes_ultimas_24h"] == 3
    assert resumen["abiertos_mas_de_12_horas"] == 2
