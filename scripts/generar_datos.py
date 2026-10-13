"""Genera incidentes de red ficticios y los carga en la base.

Uso:
    python -m scripts.generar_datos            # 500 incidentes de los últimos 90 días
    python -m scripts.generar_datos --cantidad 2000 --dias 180 --semilla 7

Los datos son inventados pero tienen patrones realistas, para que el análisis
posterior encuentre algo interesante:
  - algunas zonas fallan más que otras
  - los cortes de fibra tardan más en resolverse que las caídas de equipos
  - hay más incidentes de noche y en días de tormenta
"""
import argparse
import random
from datetime import datetime, timedelta

from app.database import Base, SessionLocal, engine
from app.models import Incidente

# Peso relativo de cada zona: cuanto más alto, más incidentes.
ZONAS = {
    "Neuquén Capital": 5,
    "Cipolletti": 3,
    "Plottier": 2,
    "Centenario": 2,
    "Zapala": 3,
    "Cutral Có": 2,
    "San Martín de los Andes": 1,
}

# tipo: (peso, minutos mínimos de resolución, minutos máximos, descripciones posibles)
TIPOS = {
    "corte de fibra": (2, 180, 720, [
        "Corte de fibra óptica en tramo troncal, múltiples clientes sin servicio.",
        "Fibra dañada por obra vial, se coordina cuadrilla para empalme.",
        "Pérdida total de señal en enlace de fibra hacia nodo regional.",
    ]),
    "caída de equipo": (4, 20, 180, [
        "Equipo OLT sin respuesta, se reinicia en forma remota.",
        "Switch de distribución caído, alarma de pérdida de gestión.",
        "Router de borde reiniciado inesperadamente, servicio intermitente.",
    ]),
    "corte de energía": (3, 60, 360, [
        "Nodo sin energía eléctrica, operando con baterías.",
        "Corte de energía en sitio, grupo electrógeno no arrancó.",
        "Falla en rectificador del nodo, baja tensión en equipos.",
    ]),
    "degradación": (5, 30, 240, [
        "Alta latencia reportada por clientes en horario pico.",
        "Pérdida de paquetes intermitente en enlace de radio.",
        "Saturación de enlace, uso de ancho de banda sobre el 95%.",
    ]),
    "falla de configuración": (1, 15, 120, [
        "Cambio de configuración generó pérdida de rutas, se revierte.",
        "VLAN mal asignada deja sin servicio a un sector.",
    ]),
}

SEVERIDAD_POR_TIPO = {
    "corte de fibra": ["alta", "alta", "media"],
    "caída de equipo": ["alta", "media", "media"],
    "corte de energía": ["alta", "media"],
    "degradación": ["baja", "media", "media"],
    "falla de configuración": ["media", "baja"],
}


def hora_con_patron(rng: random.Random) -> int:
    """Más incidentes de noche (mantenimientos, tormentas) que de día."""
    if rng.random() < 0.4:
        return rng.choice([22, 23, 0, 1, 2, 3, 4, 5])
    return rng.randint(0, 23)


def generar(cantidad: int, dias: int, semilla: int) -> list[Incidente]:
    rng = random.Random(semilla)
    ahora = datetime.now().replace(second=0, microsecond=0)
    zonas, pesos_zona = zip(*ZONAS.items())
    tipos = list(TIPOS)
    pesos_tipo = [TIPOS[t][0] for t in tipos]

    # Algunos días de tormenta concentran más incidentes.
    dias_tormenta = set(rng.sample(range(dias), k=max(1, dias // 15)))

    incidentes = []
    for _ in range(cantidad):
        dia = rng.randrange(dias)
        if rng.random() < 0.25:
            dia = rng.choice(sorted(dias_tormenta))
        inicio = (ahora - timedelta(days=dia)).replace(
            hour=hora_con_patron(rng), minute=rng.randint(0, 59)
        )
        if inicio > ahora:
            inicio -= timedelta(days=1)

        tipo = rng.choices(tipos, weights=pesos_tipo)[0]
        _, minimo, maximo, descripciones = TIPOS[tipo]
        duracion = timedelta(minutes=rng.randint(minimo, maximo))
        fin = inicio + duracion

        # Los incidentes recientes que todavía no terminaron quedan abiertos.
        resuelto = fin <= ahora and rng.random() > 0.03

        incidentes.append(
            Incidente(
                fecha_inicio=inicio,
                fecha_resolucion=fin if resuelto else None,
                zona=rng.choices(zonas, weights=pesos_zona)[0],
                tipo=tipo,
                severidad=rng.choice(SEVERIDAD_POR_TIPO[tipo]),
                estado="resuelto" if resuelto else "abierto",
                descripcion=rng.choice(descripciones),
            )
        )
    return incidentes


def main():
    parser = argparse.ArgumentParser(description="Genera incidentes de prueba.")
    parser.add_argument("--cantidad", type=int, default=500)
    parser.add_argument("--dias", type=int, default=90)
    parser.add_argument("--semilla", type=int, default=42, help="Para obtener siempre los mismos datos")
    parser.add_argument("--borrar", action="store_true", help="Vacía la tabla antes de cargar")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if args.borrar:
            db.query(Incidente).delete()
        db.add_all(generar(args.cantidad, args.dias, args.semilla))
        db.commit()
        total = db.query(Incidente).count()
    print(f"Listo: se cargaron {args.cantidad} incidentes. Total en la base: {total}.")


if __name__ == "__main__":
    main()
