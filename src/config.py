"""Rutas, constantes y reglas del proyecto.

Todo lo que es una decisión de negocio (países válidos, rango de descuentos,
equivalencias de nombres, etc.) vive aquí para que se pueda revisar en un solo lugar.
"""
from pathlib import Path

# --- Rutas -------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw"
DIR_PROCESSED = RAIZ / "data" / "processed"
DIR_OUTPUTS = RAIZ / "outputs"

ARCHIVO_ORDERS = "orders.csv"
ARCHIVO_DETAILS = "order_details.csv"
ARCHIVO_CONSOLIDADO = "northwind_consolidado.csv"
ARCHIVO_HUERFANAS = "northwind_huerfanas.csv"

COLUMNAS_ORDERS = [
    "order_id", "customer_id", "employee_id", "order_date", "required_date",
    "shipped_date", "ship_via", "freight", "ship_name", "ship_address",
    "ship_city", "ship_region", "ship_postal_code", "ship_country",
]
COLUMNAS_DETAILS = ["order_id", "product_id", "unit_price", "quantity", "discount"]
COLUMNAS_FECHA = ["order_date", "required_date", "shipped_date"]

# --- Encoding ----------------------------------------------------------------
# Secuencias que aparecen cuando una letra con acento se lee con la codificación
# equivocada ("Ã¼", "Ã±", "Ã©") y el carácter de reemplazo U+FFFD.
PATRON_ENCODING_RARO = "Ã[¼±©]|\ufffd"
PATRON_CARACTERES_EXTRANOS = "[ÃÂ\ufffd]"

# --- Reglas del diccionario de datos -----------------------------------------
CANTIDAD_MAX = 130
DESCUENTO_MIN = 0.0
DESCUENTO_MAX = 0.25
DESCUENTOS_TIPICOS = [0, 0.05, 0.10, 0.15, 0.20, 0.25]  # solo para el diagnóstico

PALABRAS_NUMERICAS = {"diez": "10", "cinco": "5%"}

# --- Países ------------------------------------------------------------------
PAISES_VALIDOS = [
    "USA", "Germany", "Brazil", "France", "UK", "Venezuela", "Austria",
    "Sweden", "Italy", "Canada", "Mexico", "Finland", "Ireland", "Spain",
    "Denmark", "Switzerland", "Belgium", "Argentina", "Portugal", "Poland", "Norway",
]
EQUIVALENCIAS_PAIS = {
    "germnay": "Germany", "germay": "Germany", "frnace": "France", "francia": "France",
    "méxico": "Mexico", "méxco": "Mexico", "finalnd": "Finland", "venezuala": "Venezuela",
    "itally": "Italy", "italia": "Italy", "canda": "Canada", "austira": "Austria",
    "brasil": "Brazil", "united states": "USA", "eeuu": "USA",
    "u.k.": "UK", "united kingdom": "UK",
}

# --- Fechas ------------------------------------------------------------------
# Decisión (avance 2): con barra el día va primero y con guion el mes va primero,
# porque así lo muestran los datos no ambiguos (20 y 17 casos, ninguno al revés).
FORMATOS_FECHA = [
    (r"\d{4}-\d{2}-\d{2}", "%Y-%m-%d"),
    (r"\d{2}/\d{2}/\d{4}", "%d/%m/%Y"),
    (r"\d{2}-\d{2}-\d{4}", "%m-%d-%Y"),
    (r"\d{2}\.\d{2}\.\d{2}", "%d.%m.%y"),
    (r"\d{8}", "%Y%m%d"),
    (r"\d{4}/\d{2}/\d{2}", "%Y/%m/%d"),
]
MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
MESES_EN_ABREV = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
