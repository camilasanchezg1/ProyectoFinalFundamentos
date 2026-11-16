"""Lectura de las fuentes originales.

Los CSV se leen como texto (dtype=str) para que pandas no adivine tipos y los
errores del archivo queden visibles para el diagnóstico.
"""
import logging
from pathlib import Path

import pandas as pd

from . import config

log = logging.getLogger(__name__)


def leer_csv_como_texto(ruta, columnas_esperadas):
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró {ruta}. Los archivos originales deben estar en data/raw/ "
            f"({config.ARCHIVO_ORDERS} y {config.ARCHIVO_DETAILS})."
        )
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    faltan = [c for c in columnas_esperadas if c not in df.columns]
    if faltan:
        raise ValueError(f"{ruta.name} no tiene las columnas esperadas: {faltan}")
    return df


def extraer_fuentes(dir_raw=None):
    """Devuelve (df_orders, df_details), ambos con todas las columnas como texto."""
    dir_raw = Path(dir_raw or config.DIR_RAW)
    df_orders = leer_csv_como_texto(dir_raw / config.ARCHIVO_ORDERS, config.COLUMNAS_ORDERS)
    df_details = leer_csv_como_texto(dir_raw / config.ARCHIVO_DETAILS, config.COLUMNAS_DETAILS)
    log.info("Extracción: orders %s, order_details %s", df_orders.shape, df_details.shape)
    return df_orders, df_details
