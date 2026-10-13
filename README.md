# Monitor de Incidentes

API para registrar, consultar y analizar incidentes de red de un proveedor de telecomunicaciones.

Proyecto de portfolio basado en mi experiencia como analista de redes y automatización. Los datos son ficticios y se generan con un script que reproduce patrones realistas (zonas con más fallas, cortes de fibra que tardan más en resolverse, picos nocturnos).

**Stack:** Python · FastAPI · SQLAlchemy · MariaDB · pandas · matplotlib · Docker · pytest

## Resultados del análisis

Con los datos de prueba generados (500 incidentes en 90 días):

![Incidentes por zona](docs/img/incidentes_por_zona.png)
![Tiempo de resolución por tipo de falla](docs/img/resolucion_por_tipo.png)
![Incidentes por hora del día](docs/img/incidentes_por_hora.png)
![Incidentes por día](docs/img/incidentes_por_dia.png)

## Estado del proyecto

- [x] Etapa 1: API REST, base de datos MariaDB, Docker y generador de datos
- [x] Etapa 2: análisis de datos con pandas y gráficos
- [ ] Etapa 3: clasificación y resumen de incidentes con IA
- [ ] Etapa 4: reporte diario automático

## Cómo correrlo

### Con Docker (recomendado)

```bash
cp .env.example .env          # y cambiá las contraseñas
docker compose up -d --build
docker compose exec api python -m scripts.generar_datos
```

La API queda en http://localhost:8000 y la documentación interactiva en http://localhost:8000/docs.

### Sin Docker (usa SQLite)

```bash
python -m venv .venv
source .venv/bin/activate      # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.generar_datos
uvicorn app.main:app --reload
```

### Análisis de datos

```bash
python -m scripts.analizar
```

Muestra los hallazgos principales y guarda gráficos y tablas en la carpeta `reportes/`:

- incidentes por zona
- tiempo de resolución por tipo de falla (mediana)
- incidentes por hora del día
- incidentes por día, con detección automática de días pico

### Tests

```bash
pytest
```

## Endpoints

| Método | Ruta | Qué hace |
| --- | --- | --- |
| GET | `/salud` | Chequeo de que la API está viva |
| GET | `/incidentes` | Lista con filtros: `zona`, `tipo`, `estado`, `severidad`, `limite` |
| GET | `/incidentes/{id}` | Un incidente |
| POST | `/incidentes` | Crea un incidente |
| PATCH | `/incidentes/{id}/resolver` | Lo marca como resuelto |
| GET | `/estadisticas/zonas` | Cantidad y tiempo promedio de resolución por zona |

## Estructura

```
app/
  database.py    conexión a la base (MariaDB o SQLite según DATABASE_URL)
  models.py      tabla de incidentes
  schemas.py     validación de datos con Pydantic
  main.py        endpoints de la API
  analisis.py    funciones de análisis con pandas
scripts/
  generar_datos.py   carga incidentes ficticios
  analizar.py        genera gráficos y tablas
tests/
  test_api.py        tests de los endpoints
  test_analisis.py   tests del análisis
```
