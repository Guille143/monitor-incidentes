"""Análisis de incidentes con pandas.

Todas las funciones reciben un DataFrame, así se pueden probar sin base de datos.
La única que toca la base es `cargar_incidentes`.
"""
import pandas as pd

COLUMNAS = ["id", "fecha_inicio", "fecha_resolucion", "zona", "tipo", "severidad", "estado"]


def cargar_incidentes(engine) -> pd.DataFrame:
    """Lee todos los incidentes de la base (MariaDB o SQLite)."""
    consulta = f"SELECT {', '.join(COLUMNAS)} FROM incidentes"
    return pd.read_sql(consulta, engine, parse_dates=["fecha_inicio", "fecha_resolucion"])


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas derivadas: duración en minutos, hora del día y fecha."""
    df = df.copy()
    df["fecha_inicio"] = pd.to_datetime(df["fecha_inicio"])
    df["fecha_resolucion"] = pd.to_datetime(df["fecha_resolucion"])
    df["duracion_min"] = (df["fecha_resolucion"] - df["fecha_inicio"]).dt.total_seconds() / 60
    df["hora"] = df["fecha_inicio"].dt.hour
    df["fecha"] = df["fecha_inicio"].dt.normalize()
    return df


def por_zona(df: pd.DataFrame) -> pd.DataFrame:
    """Cantidad de incidentes, abiertos y mediana de resolución por zona."""
    resultado = df.groupby("zona").agg(
        cantidad=("id", "count"),
        abiertos=("estado", lambda s: (s == "abierto").sum()),
        mediana_resolucion_min=("duracion_min", "median"),
    )
    resultado["porcentaje"] = (resultado["cantidad"] / len(df) * 100).round(1)
    resultado["mediana_resolucion_min"] = resultado["mediana_resolucion_min"].round(0)
    return resultado.sort_values("cantidad", ascending=False).reset_index()


def por_tipo(df: pd.DataFrame) -> pd.DataFrame:
    """Cantidad y tiempos de resolución (mediana y percentil 90) por tipo de falla.

    Usamos la mediana y no el promedio porque unos pocos incidentes muy largos
    distorsionan el promedio.
    """
    resultado = df.groupby("tipo").agg(
        cantidad=("id", "count"),
        mediana_resolucion_min=("duracion_min", "median"),
        p90_resolucion_min=("duracion_min", lambda s: s.quantile(0.9)),
    )
    return resultado.round(0).sort_values("mediana_resolucion_min", ascending=False).reset_index()


def por_hora(df: pd.DataFrame) -> pd.Series:
    """Cantidad de incidentes por hora del día (0 a 23, incluye horas sin incidentes)."""
    return df["hora"].value_counts().reindex(range(24), fill_value=0).sort_index()


def por_dia(df: pd.DataFrame, umbral_desvios: float = 2.0) -> pd.DataFrame:
    """Incidentes por día y marca de 'pico' cuando un día supera
    el promedio + `umbral_desvios` desvíos estándar."""
    diario = df.groupby("fecha").size()
    rango = pd.date_range(diario.index.min(), diario.index.max(), freq="D")
    diario = diario.reindex(rango, fill_value=0).rename_axis("fecha").rename("cantidad")
    limite = diario.mean() + umbral_desvios * diario.std()
    resultado = diario.reset_index()
    resultado["pico"] = resultado["cantidad"] > limite
    return resultado


def resumen(df: pd.DataFrame) -> dict:
    """Los hallazgos principales, en un diccionario fácil de mostrar o mandar a una IA."""
    zonas = por_zona(df)
    tipos = por_tipo(df)
    horas = por_hora(df)
    dias = por_dia(df)
    nocturnos = horas.loc[[22, 23, 0, 1, 2, 3, 4, 5]].sum()
    return {
        "total": int(len(df)),
        "abiertos": int((df["estado"] == "abierto").sum()),
        "periodo": f"{df['fecha'].min():%d/%m/%Y} al {df['fecha'].max():%d/%m/%Y}",
        "zona_mas_afectada": zonas.iloc[0]["zona"],
        "porcentaje_zona_mas_afectada": float(zonas.iloc[0]["porcentaje"]),
        "tipo_mas_lento": tipos.iloc[0]["tipo"],
        "mediana_tipo_mas_lento_min": float(tipos.iloc[0]["mediana_resolucion_min"]),
        "hora_pico": int(horas.idxmax()),
        "porcentaje_nocturno": round(nocturnos / len(df) * 100, 1),
        "dias_pico": [f"{f:%d/%m}" for f in dias.loc[dias["pico"], "fecha"]],
    }
