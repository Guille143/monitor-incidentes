"""Analiza los incidentes de la base y genera gráficos y tablas en la carpeta reportes/.

Uso:
    python -m scripts.analizar
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # genera imágenes sin abrir ventanas
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from app import analisis  # noqa: E402
from app.database import engine  # noqa: E402

CARPETA = Path("reportes")

# Estilo: un solo color para los datos, ejes y grillas discretos.
AZUL = "#2a78d6"
AZUL_CLARO = "#a9cbf3"
TEXTO = "#0b0b0b"
TEXTO_SECUNDARIO = "#52514e"
GRILLA = "#e4e3df"
FONDO = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": FONDO,
    "axes.facecolor": FONDO,
    "axes.edgecolor": GRILLA,
    "axes.labelcolor": TEXTO_SECUNDARIO,
    "axes.titlecolor": TEXTO,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRILLA,
    "grid.linewidth": 0.8,
    "xtick.color": TEXTO_SECUNDARIO,
    "ytick.color": TEXTO_SECUNDARIO,
    "font.size": 10,
})


def guardar(fig, nombre: str) -> Path:
    ruta = CARPETA / nombre
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)
    return ruta


def grafico_zonas(zonas):
    datos = zonas.sort_values("cantidad")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    barras = ax.barh(datos["zona"], datos["cantidad"], color=AZUL, height=0.6)
    ax.bar_label(barras, padding=4, color=TEXTO_SECUNDARIO)
    ax.set_title("Incidentes por zona")
    ax.set_xlabel("Cantidad de incidentes")
    ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)
    return guardar(fig, "incidentes_por_zona.png")


def grafico_tipos(tipos):
    datos = tipos.sort_values("mediana_resolucion_min")
    horas = datos["mediana_resolucion_min"] / 60
    fig, ax = plt.subplots(figsize=(8, 4))
    barras = ax.barh(datos["tipo"], horas, color=AZUL, height=0.6)
    ax.bar_label(barras, labels=[f"{h:.1f} h" for h in horas], padding=4, color=TEXTO_SECUNDARIO)
    ax.set_title("Tiempo de resolución por tipo de falla (mediana)")
    ax.set_xlabel("Horas")
    ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)
    return guardar(fig, "resolucion_por_tipo.png")


def grafico_horas(horas):
    nocturnas = {22, 23, 0, 1, 2, 3, 4, 5}
    colores = [AZUL if h in nocturnas else AZUL_CLARO for h in horas.index]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(horas.index, horas.values, color=colores, width=0.75)
    ax.set_title("Incidentes por hora del día (oscuro: 22 a 5 h)")
    ax.set_xlabel("Hora de inicio")
    ax.set_ylabel("Cantidad")
    ax.set_xticks(range(0, 24, 2))
    ax.grid(axis="x", visible=False)
    ax.set_axisbelow(True)
    return guardar(fig, "incidentes_por_hora.png")


def grafico_dias(dias):
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(dias["fecha"], dias["cantidad"], color=AZUL, linewidth=1.8)
    picos = dias[dias["pico"]]
    ax.scatter(picos["fecha"], picos["cantidad"], color=AZUL, s=40, zorder=3,
               edgecolor=FONDO, linewidth=1.5)
    for _, fila in picos.iterrows():
        ax.annotate(f"{fila['fecha']:%d/%m}", (fila["fecha"], fila["cantidad"]),
                    xytext=(0, 7), textcoords="offset points", ha="center",
                    fontsize=8, color=TEXTO_SECUNDARIO)
    ax.set_title("Incidentes por día (puntos: días pico)")
    ax.set_ylabel("Cantidad")
    ax.set_ylim(bottom=0)
    ax.grid(axis="x", visible=False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    return guardar(fig, "incidentes_por_dia.png")


def main():
    CARPETA.mkdir(exist_ok=True)
    df = analisis.cargar_incidentes(engine)
    if df.empty:
        print("No hay incidentes. Corré primero: python -m scripts.generar_datos")
        return
    df = analisis.preparar(df)

    zonas = analisis.por_zona(df)
    tipos = analisis.por_tipo(df)
    horas = analisis.por_hora(df)
    dias = analisis.por_dia(df)

    zonas.to_csv(CARPETA / "por_zona.csv", index=False)
    tipos.to_csv(CARPETA / "por_tipo.csv", index=False)
    graficos = [grafico_zonas(zonas), grafico_tipos(tipos), grafico_horas(horas), grafico_dias(dias)]

    r = analisis.resumen(df)
    print(f"\nPeríodo analizado: {r['periodo']}")
    print(f"Incidentes: {r['total']} ({r['abiertos']} abiertos)")
    print(f"Zona más afectada: {r['zona_mas_afectada']} ({r['porcentaje_zona_mas_afectada']}% del total)")
    print(f"Falla más lenta de resolver: {r['tipo_mas_lento']} "
          f"(mediana {r['mediana_tipo_mas_lento_min'] / 60:.1f} h)")
    print(f"Hora con más incidentes: {r['hora_pico']} h")
    print(f"Incidentes nocturnos (22 a 5 h): {r['porcentaje_nocturno']}%")
    print(f"Días pico: {', '.join(r['dias_pico']) or 'ninguno'}")
    print(f"\nGráficos y tablas guardados en: {CARPETA.resolve()}")
    for g in graficos:
        print(f"  - {g.name}")


if __name__ == "__main__":
    main()
