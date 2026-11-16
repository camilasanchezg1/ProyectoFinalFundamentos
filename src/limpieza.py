"""Transformaciones 1 y 2: unicidad de clave, texto, identificadores, encoding y duplicados.

Cada función recibe DataFrames y devuelve DataFrames nuevos (no modifica los de entrada)
junto con un diccionario con los conteos que sirven como evidencia en el log.
"""
import logging

import pandas as pd

from . import config
from .utils import calcular_importe

log = logging.getLogger(__name__)


# --- Transformación 1: unicidad de clave (Control 1) --------------------------
def deduplicar_orders(df_orders):
    """Quita duplicados exactos y, si un order_id sigue repetido con contenido
    distinto, deja la fila con más campos llenos."""
    sin_exactos = df_orders.drop_duplicates().copy()
    sin_exactos["_llenos"] = sin_exactos.apply(lambda c: c.str.strip().ne("")).sum(axis=1)
    orders_dep = (
        sin_exactos.sort_values("_llenos", ascending=False, kind="stable")
        .drop_duplicates(subset="order_id", keep="first")
        .drop(columns="_llenos")
        .sort_values("order_id")
    )
    info = {
        "filas_antes": len(df_orders),
        "duplicados_exactos": len(df_orders) - len(sin_exactos),
        "conflictos_resueltos": len(sin_exactos) - len(orders_dep),
        "filas_despues": len(orders_dep),
    }
    log.info("T1 unicidad orders: %s", info)
    return orders_dep, info


# --- Control 2: reconciliación de totales (antes de normalizar ids) -----------
def reconciliar_totales(df_details, orders_dep):
    """Separa las líneas sin pedido en orders_dep y comprueba que nada se pierda."""
    importe = calcular_importe(df_details)
    con_orden = df_details["order_id"].isin(orders_dep["order_id"])
    info = {
        "lineas_total": len(df_details),
        "lineas_con_orden": int(con_orden.sum()),
        "lineas_sin_orden": int((~con_orden).sum()),
        "importe_total": float(importe.sum()),
        "importe_con_orden": float(importe[con_orden].sum()),
        "importe_sin_orden": float(importe[~con_orden].sum()),
        "lineas_sin_importe": int(importe.isna().sum()),
    }
    log.info("Control 2 reconciliación inicial: %s", info)
    return info


# --- Transformación 2: texto, identificadores, encoding, duplicados ----------
def limpiar_texto_e_ids(orders_dep, df_details):
    """strip() en todas las columnas y quita el '.0' final de los order_id de order_details."""
    orders_limpio = orders_dep.apply(lambda c: c.str.strip())
    details_limpio = df_details.apply(lambda c: c.str.strip())
    details_limpio["order_id"] = details_limpio["order_id"].str.replace(r"\.0$", "", regex=True)
    info = {
        "celdas_con_espacios_orders": int((orders_dep != orders_limpio).sum().sum()),
        "order_id_corregidos_details": int((df_details["order_id"] != details_limpio["order_id"]).sum()),
    }
    log.info("T2 texto e ids: %s", info)
    return orders_limpio, details_limpio, info


def quitar_encoding(orders_limpio):
    """Elimina las secuencias mal codificadas (la reparación de mojibake no recupera el original)."""
    antes = int(orders_limpio.apply(lambda c: c.str.contains(config.PATRON_ENCODING_RARO, regex=True)).sum().sum())
    limpio = orders_limpio.apply(
        lambda c: c.str.replace(config.PATRON_ENCODING_RARO, "", regex=True).str.strip()
    )
    despues = int(limpio.apply(lambda c: c.str.contains(config.PATRON_CARACTERES_EXTRANOS, regex=True)).sum().sum())
    info = {"celdas_antes": antes, "celdas_despues": despues}
    log.info("T2 encoding: %s", info)
    return limpio, info


def deduplicar_details(details_limpio):
    n_dup = int(details_limpio.duplicated().sum())
    sin_dup = details_limpio.drop_duplicates()
    con_producto = sin_dup[sin_dup["product_id"] != ""]
    info = {
        "duplicados_eliminados": n_dup,
        "filas_restantes": len(sin_dup),
        "repetidas_order_product": int(con_producto.duplicated(subset=["order_id", "product_id"]).sum()),
    }
    log.info("T2 duplicados order_details: %s", info)
    return sin_dup, info


def separar_huerfanas(details_limpio, orders_limpio):
    """Las líneas sin pedido en orders no se borran: se guardan aparte."""
    con_orden = details_limpio["order_id"].isin(orders_limpio["order_id"])
    huerfanas = details_limpio.loc[~con_orden].copy()
    con_pedido = details_limpio.loc[con_orden].copy()
    info = {
        "lineas_con_pedido": len(con_pedido),
        "lineas_huerfanas": len(huerfanas),
        "ids_huerfanos": sorted(huerfanas["order_id"].tolist()),
        "pedidos_sin_lineas": int((~orders_limpio["order_id"].isin(con_pedido["order_id"])).sum()),
    }
    log.info("T2 integridad: %s", info)
    return con_pedido, huerfanas, info
