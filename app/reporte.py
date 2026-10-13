"""Reporte diario de incidentes.

`construir_datos` calcula todo lo que va en el reporte a partir de un DataFrame
y `renderizar_html` lo convierte en un HTML autocontenido (los gráficos van
embebidos), listo para abrir en el navegador o mandar por mail.
"""
import base64
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

import pandas as pd


def construir_datos(df: pd.DataFrame, ahora: datetime, dias_comparacion: int = 30) -> dict:
    """Compara las últimas 24 horas contra el promedio diario de los días anteriores."""
    inicio_24h = ahora - timedelta(hours=24)
    inicio_historico = inicio_24h - timedelta(days=dias_comparacion)

    ultimas = df[(df["fecha_inicio"] >= inicio_24h) & (df["fecha_inicio"] <= ahora)]
    historico = df[(df["fecha_inicio"] >= inicio_historico) & (df["fecha_inicio"] < inicio_24h)]

    promedio = len(historico) / dias_comparacion
    variacion = round((len(ultimas) - promedio) / promedio * 100) if promedio else None

    abiertos = df[df["estado"] == "abierto"].copy()
    abiertos["horas_abierto"] = ((ahora - abiertos["fecha_inicio"]).dt.total_seconds() / 3600).round(1)
    abiertos = abiertos.sort_values(["severidad", "horas_abierto"], key=_orden_severidad, ascending=[True, False])

    return {
        "fecha": ahora,
        "dias_comparacion": dias_comparacion,
        "total_24h": int(len(ultimas)),
        "promedio_diario": round(promedio, 1),
        "variacion_pct": variacion,
        "alta_24h": int((ultimas["severidad"] == "alta").sum()),
        "abiertos": abiertos[["id", "zona", "tipo", "severidad", "horas_abierto"]].to_dict("records"),
        "por_zona_24h": ultimas["zona"].value_counts().to_dict(),
        "por_tipo_24h": ultimas["tipo"].value_counts().to_dict(),
    }


def _orden_severidad(columna: pd.Series) -> pd.Series:
    """Ordena alta > media > baja; el resto de las columnas se ordena normal."""
    if columna.name == "severidad":
        return columna.map({"alta": 0, "media": 1, "baja": 2})
    return columna


def para_ia(datos: dict) -> dict:
    """Versión resumida de los datos para mandarle a la IA (sin fechas ni textos largos)."""
    return {
        "incidentes_ultimas_24h": datos["total_24h"],
        f"promedio_diario_ultimos_{datos['dias_comparacion']}_dias": datos["promedio_diario"],
        "variacion_porcentual": datos["variacion_pct"],
        "severidad_alta_ultimas_24h": datos["alta_24h"],
        "abiertos_ahora": len(datos["abiertos"]),
        "abiertos_mas_de_12_horas": sum(1 for a in datos["abiertos"] if a["horas_abierto"] > 12),
        "por_zona_ultimas_24h": datos["por_zona_24h"],
        "por_tipo_ultimas_24h": datos["por_tipo_24h"],
    }


def _imagen(ruta: Path) -> str:
    codigo = base64.b64encode(ruta.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{codigo}" alt="{escape(ruta.stem.replace("_", " "))}">'


def _parrafos(texto: str) -> str:
    """Convierte el texto de la IA (párrafos y viñetas con '-' o '•') en HTML."""
    html, en_lista = [], False
    for linea in texto.splitlines():
        linea = linea.strip()
        es_item = linea[:1] in {"-", "•", "*"}
        if es_item and not en_lista:
            html.append("<ul>")
            en_lista = True
        if not es_item and en_lista:
            html.append("</ul>")
            en_lista = False
        if es_item:
            html.append(f"<li>{escape(linea[1:].strip())}</li>")
        elif linea:
            html.append(f"<p>{escape(linea)}</p>")
    if en_lista:
        html.append("</ul>")
    return "\n".join(html)


def renderizar_html(datos: dict, imagenes: list[Path], resumen_ia: str | None) -> str:
    variacion = datos["variacion_pct"]
    if variacion is None:
        texto_variacion = "sin datos para comparar"
    else:
        texto_variacion = f"{'+' if variacion > 0 else ''}{variacion}% vs. promedio de {datos['promedio_diario']}/día"

    filas = "\n".join(
        f"<tr><td>{a['id']}</td><td>{escape(a['zona'])}</td><td>{escape(a['tipo'])}</td>"
        f"<td><span class=\"sev sev-{a['severidad']}\">{a['severidad']}</span></td>"
        f"<td class=\"num\">{a['horas_abierto']:.1f}</td></tr>"
        for a in datos["abiertos"]
    ) or '<tr><td colspan="5">No hay incidentes abiertos.</td></tr>'

    bloque_ia = (
        _parrafos(resumen_ia)
        if resumen_ia
        else '<p class="nota">Resumen con IA no disponible (falta ANTHROPIC_API_KEY o la API falló).</p>'
    )

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reporte de incidentes {datos['fecha']:%d/%m/%Y}</title>
<style>
  body {{ margin: 0; background: #f4f4f2; color: #0b0b0b; font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
  main {{ max-width: 860px; margin: 0 auto; padding: 32px 16px 48px; }}
  h1 {{ font-size: 24px; margin: 0; }}
  .fecha {{ color: #52514e; margin: 4px 0 24px; }}
  h2 {{ font-size: 17px; margin: 32px 0 12px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
  .kpi {{ background: #fff; border: 1px solid #e4e3df; border-radius: 8px; padding: 16px; }}
  .kpi .valor {{ font-size: 32px; font-weight: 700; line-height: 1.1; }}
  .kpi .etiqueta {{ color: #52514e; font-size: 13px; }}
  .kpi .detalle {{ color: #52514e; font-size: 13px; margin-top: 4px; }}
  .caja {{ background: #fff; border: 1px solid #e4e3df; border-radius: 8px; padding: 16px 20px; }}
  .caja p {{ margin: 0 0 10px; }} .caja ul {{ margin: 0; padding-left: 20px; }}
  .nota {{ color: #52514e; font-style: italic; }}
  .tabla {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e4e3df; border-radius: 8px; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #eeedea; white-space: nowrap; }}
  th {{ font-size: 13px; color: #52514e; font-weight: 600; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .sev {{ font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 10px; }}
  .sev-alta {{ background: #fde3e1; color: #a1150c; }}
  .sev-media {{ background: #fdf0d5; color: #7a4e00; }}
  .sev-baja {{ background: #e5efe5; color: #1f5f1f; }}
  img {{ width: 100%; height: auto; display: block; background: #fff; border: 1px solid #e4e3df; border-radius: 8px; margin-bottom: 12px; }}
  footer {{ color: #52514e; font-size: 13px; margin-top: 32px; }}
</style>
</head>
<body>
<main>
  <h1>Reporte diario de incidentes de red</h1>
  <p class="fecha">Generado el {datos['fecha']:%d/%m/%Y a las %H:%M} · últimas 24 horas</p>

  <div class="kpis">
    <div class="kpi"><div class="etiqueta">Incidentes en 24 h</div><div class="valor">{datos['total_24h']}</div><div class="detalle">{texto_variacion}</div></div>
    <div class="kpi"><div class="etiqueta">Severidad alta en 24 h</div><div class="valor">{datos['alta_24h']}</div></div>
    <div class="kpi"><div class="etiqueta">Abiertos ahora</div><div class="valor">{len(datos['abiertos'])}</div></div>
  </div>

  <h2>Resumen</h2>
  <div class="caja">{bloque_ia}</div>

  <h2>Incidentes abiertos</h2>
  <div class="tabla"><table>
    <thead><tr><th>ID</th><th>Zona</th><th>Tipo</th><th>Severidad</th><th class="num">Horas abierto</th></tr></thead>
    <tbody>{filas}</tbody>
  </table></div>

  <h2>Últimos {datos['dias_comparacion']} días</h2>
  {''.join(_imagen(i) for i in imagenes)}

  <footer>Monitor de Incidentes · datos de prueba generados automáticamente.</footer>
</main>
</body>
</html>
"""
