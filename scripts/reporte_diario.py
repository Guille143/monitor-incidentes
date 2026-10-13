"""Genera el reporte diario de incidentes en HTML.

Uso:
    python -m scripts.reporte_diario

Deja el archivo en reportes/reporte_AAAA-MM-DD.html. Si hay ANTHROPIC_API_KEY,
incluye un resumen escrito por IA; si no, el reporte se genera igual sin él.
"""
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from app import analisis, ia, reporte
from app.database import engine
from scripts import analizar

CARPETA = Path("reportes")
DIAS_COMPARACION = 30


def main():
    CARPETA.mkdir(exist_ok=True)
    ahora = datetime.now().replace(second=0, microsecond=0)

    df = analisis.cargar_incidentes(engine)
    if df.empty:
        print("No hay incidentes. Corré primero: python -m scripts.generar_datos")
        return
    df = analisis.preparar(df)

    datos = reporte.construir_datos(df, ahora, DIAS_COMPARACION)

    # Gráficos de los últimos 30 días, en una carpeta temporal (después van embebidos en el HTML).
    recientes = df[df["fecha_inicio"] >= ahora - timedelta(days=DIAS_COMPARACION)]
    with tempfile.TemporaryDirectory() as carpeta_temporal:
        analizar.CARPETA = Path(carpeta_temporal)
        imagenes = [
            analizar.grafico_dias(analisis.por_dia(recientes)),
            analizar.grafico_zonas(analisis.por_zona(recientes)),
        ]

        try:
            resumen_ia = ia.resumir(reporte.para_ia(datos))
        except ia.IAError as e:
            print(f"Aviso: el reporte sale sin resumen de IA. {e}")
            resumen_ia = None

        html = reporte.renderizar_html(datos, imagenes, resumen_ia)

    ruta = CARPETA / f"reporte_{ahora:%Y-%m-%d}.html"
    ruta.write_text(html, encoding="utf-8")
    print(f"Reporte generado: {ruta.resolve()}")


if __name__ == "__main__":
    main()
