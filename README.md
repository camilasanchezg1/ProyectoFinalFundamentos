# Proyecto Final – Fundamentos de Integración

Pipeline en Python que diagnostica, limpia, transforma e integra dos tablas sucias de la base de datos Northwind (`orders` y `order_details`) y genera un dataset consolidado y verificable para analizar ventas.

Universidad de Ibagué · Profesora: Mariana Millán Meneses

## 1. Descripción y objetivo

Los registros de pedidos de Northwind tienen errores de captura y formato: valores faltantes, duplicados, tipos incorrectos, fechas en varios formatos, categorías escritas de distintas maneras, valores fuera de rango y caracteres mal codificados. Estos errores impiden calcular métricas de ventas confiables.

El objetivo es obtener un conjunto de datos consolidado, consistente y verificable:

- Diagnosticar la calidad de las fuentes originales.
- Aplicar transformaciones justificadas (ver [`docs/registro_decisiones.md`](docs/registro_decisiones.md)).
- Integrar las dos tablas mediante `order_id`.
- Validar de forma automática que la integración no pierda ni duplique registros.

## 2. Fuentes de datos

**Sales Analysis on Northwind Database** (Kaggle): <https://www.kaggle.com/datasets/emmanueltugbeh/northwind-orders-and-order-details>

Northwind es una base de datos de ejemplo creada por Microsoft. Se usan dos archivos, incluidos en `data/raw/` para que el proyecto no dependa de conexión a internet:

| Archivo | Contenido | Filas | Columnas |
|---|---|---|---|
| `data/raw/orders.csv` | Un registro por pedido | 865 | 14 |
| `data/raw/order_details.csv` | Una línea por producto de cada pedido | 2.215 | 5 |

Las tablas se relacionan por `order_id` (un pedido tiene una o varias líneas).

**Licencia:** la licencia de redistribución de los datos no está especificada en este proyecto. Se deben consultar las condiciones de uso del dataset original en Kaggle.

## 3. Estructura del repositorio

```
ProyectoFinalFundamentosIntegracion/
├── data/
│   ├── raw/                 CSV originales (no se modifican)
│   └── processed/           resultados: northwind_consolidado.csv y northwind_huerfanas.csv
├── src/
│   ├── config.py            rutas, constantes y reglas del proyecto
│   ├── utils.py             funciones compartidas
│   ├── extraccion.py        lectura de las fuentes como texto
│   ├── diagnostico.py       diagnóstico de calidad (antes de transformar)
│   ├── limpieza.py          unicidad de clave, espacios, ids, encoding, duplicados, huérfanas
│   ├── transformaciones.py  conversión numérica y rangos, fechas, categorías
│   ├── nulos.py             imputaciones con reglas probadas
│   ├── integracion.py       unión de order_details con orders
│   ├── validaciones.py      controles de calidad automáticos
│   └── pipeline.py          orquesta todo el proceso
├── tests/                   pruebas automáticas
├── notebooks/               avance 1 y avance 2 (origen del código de src/)
├── outputs/                 reportes generados en cada corrida
├── docs/                    registro de decisiones
├── main.py                  punto de entrada
├── requirements.txt         dependencias
└── .gitignore
```

## 4. Requisitos

- Python 3.9 o superior (probado con Python 3.12).
- Librería `pandas` (se instala con `requirements.txt`; probado con pandas 3.0.6).

No se necesita conexión a internet para ejecutar el proyecto.

## 5. Ejecución local

Desde la carpeta del proyecto:

```bash
# 1. Crear y activar un entorno virtual
python -m venv .venv
source .venv/bin/activate          # Mac o Linux
.venv\Scripts\activate             # Windows

# 2. Instalar las dependencias
pip install -r requirements.txt

# 3. Ejecutar el pipeline completo
python main.py

# 4. Ejecutar las pruebas (opcional)
python -m unittest discover -s tests -v
```

En algunos equipos el comando es `python3` en lugar de `python`.

`python main.py` termina con una línea como `Listo: northwind_consolidado.csv (2149 filas, 19 columnas)...`. Si algún control de calidad falla, el proceso se detiene y termina con código de error.

## 6. Qué hace el pipeline

1. **Extracción:** lee los CSV como texto para que los errores queden visibles.
2. **Diagnóstico:** mide faltantes, duplicados, tipos, formatos, rangos, integridad entre tablas y encoding (`outputs/reporte_diagnostico.txt`).
3. **Transformaciones:** unicidad de clave, limpieza de texto e identificadores, conversión numérica y de rangos, estandarización de fechas y de categorías.
4. **Nulos:** completa valores con reglas probadas y deja como `NaN` lo que no tiene una fuente confiable.
5. **Integración:** une `order_details` con `orders` por `order_id`, sin perder ni duplicar líneas.
6. **Validaciones y guardado:** ejecuta 23 controles automáticos (`outputs/reporte_validaciones.txt`) y guarda los resultados en `data/processed/`.

Cada decisión (qué se hizo, por qué, qué alternativas se descartaron y con qué evidencia) está en [`docs/registro_decisiones.md`](docs/registro_decisiones.md).

## 7. Resultados

| Archivo | Contenido |
|---|---|
| `data/processed/northwind_consolidado.csv` | Dataset integrado: 2.149 filas y 19 columnas, con 830 pedidos |
| `data/processed/northwind_huerfanas.csv` | 6 líneas de pedido sin pedido en `orders`, conservadas aparte |

Verificaciones finales (todas automáticas):

- Las 2.215 líneas originales se explican por completo: 60 duplicadas + 2.149 con pedido + 6 huérfanas.
- Los 830 pedidos de `orders` aparecen en el consolidado.
- No hay claves `order_id` + `product_id` repetidas.
- El importe total se conserva al unir las tablas: 1.249.945,73.

## 8. Controles de calidad

`src/validaciones.py` ejecuta 23 controles en cada corrida: unicidad de claves, reconciliación de líneas e importes, conservación de registros, integridad entre tablas, tipos, rangos, coherencia de fechas, categorías estándar, texto limpio, integración y archivos guardados. Las pruebas de `tests/` además comprueban que los controles **detecten** datos dañados.

## 9. Reproducibilidad

- Los datos originales están en el repositorio (`data/raw/`), por lo que no hay descargas externas.
- Las dependencias están en `requirements.txt`.
- El proceso completo se ejecuta con un solo comando (`python main.py`) y da el mismo resultado en cada corrida, lo que verifica una de las pruebas.
- Se verificó que el pipeline reproduce el consolidado del notebook del avance 2 (`notebooks/`).

## 10. Limitaciones

- Algunos valores faltantes no se pueden recuperar con información confiable y quedan como `NaN`.
- Las imputaciones de precio (97,7 % de acierto en la prueba) y de descuento (87,9 %) son estimaciones.
- La regla de fechas (barra = día primero, guion = mes primero) es una inferencia basada en las fechas no ambiguas.
- Las 6 líneas huérfanas no se pueden asignar a un pedido con los datos disponibles.

## 11. Integrantes y participación

| Integrante | Usuario de GitHub | Parte del proyecto |
|---|---|---|
| Ana Camila Sanchez | [camilasanchezg1](https://github.com/camilasanchezg1) | Estructura base del repositorio, extracción, integración, pipeline, `main.py` y pruebas |
| Juan Sebastian Gomez Rojas | [Elsebas1](https://github.com/Elsebas1) | Limpieza y transformaciones (`limpieza.py` y `transformaciones.py`) |
| Cristian Cuellar | [pavilion1322](https://github.com/pavilion1322) | Manejo de nulos y controles de calidad (`nulos.py` y `validaciones.py`) |
| Juan David Romero | juandaro2203 | Diagnóstico, registro de decisiones, README y notebooks |

**Repositorio:** ProyectoFinalFundamentosIntegracion · **Tecnologías:** Python y pandas.
