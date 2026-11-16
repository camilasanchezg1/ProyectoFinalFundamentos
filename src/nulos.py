"""Manejo de valores nulos con reglas explícitas y probadas.

Cada regla de imputación se prueba primero con los valores que sí se conocen
(como si no estuvieran) y se reporta el porcentaje de acierto. Lo que no tiene una
fuente confiable dentro de los datos se deja como NaN.
"""
import logging

import numpy as np
import pandas as pd

from .utils import calcular_importe

log = logging.getLogger(__name__)


def resumen_nulos(df):
    n = df.replace("", pd.NA).isna().sum()
    return {col: int(v) for col, v in n.items() if v > 0}


# --- Cliente y datos de envío -------------------------------------------------
def completar_cliente_y_envio(orders):
    """customer_id vacío -> se toma de ship_name; campos de envío vacíos -> del cliente."""
    orders = orders.copy()
    info = {}

    datos = orders[(orders["customer_id"] != "") & (orders["ship_name"] != "")]
    info["ship_name_con_mas_de_un_cliente"] = int((datos.groupby("ship_name")["customer_id"].nunique() > 1).sum())
    cliente_por_nombre = datos.groupby("ship_name")["customer_id"].first()
    vacio = orders["customer_id"] == ""
    orders.loc[vacio, "customer_id"] = orders.loc[vacio, "ship_name"].map(cliente_por_nombre).fillna("")
    info["customer_id_vacios_antes"] = int(vacio.sum())
    info["customer_id_vacios_despues"] = int((orders["customer_id"] == "").sum())

    for col in ["ship_name", "ship_address", "ship_city", "ship_region", "ship_postal_code", "ship_country"]:
        datos = orders[(orders["customer_id"] != "") & (orders[col] != "")]
        valor_cliente = datos.groupby("customer_id")[col].agg(lambda s: s.mode()[0])
        vacio = (orders[col] == "") & (orders["customer_id"] != "")
        nuevo = orders.loc[vacio, "customer_id"].map(valor_cliente)
        orders.loc[vacio, col] = nuevo.fillna("")
        info[col] = {"vacios_con_cliente": int(vacio.sum()), "completados": int(nuevo.notna().sum())}
    log.info("Nulos cliente/envío: %s", info)
    return orders, info


# --- Precio unitario ----------------------------------------------------------
def _indice_precios(conocidos):
    grupos = {}
    for producto, g in conocidos.groupby("product_id", sort=False):
        grupos[int(producto)] = (
            g.index.to_numpy(),
            g["order_id"].to_numpy(dtype="int64"),
            g["unit_price"].to_numpy(dtype="float64"),
        )
    return grupos


def _precio_cercano(grupos, producto, pedido, excluir=None):
    """Precio del mismo producto en el pedido con order_id más cercano."""
    g = grupos.get(int(producto))
    if g is None:
        return float("nan")
    indices, pedidos, precios = g
    if excluir is not None:
        m = indices != excluir
        pedidos, precios = pedidos[m], precios[m]
    if len(pedidos) == 0:
        return float("nan")
    return float(precios[np.abs(pedidos - int(pedido)).argmin()])


def completar_precios(details):
    details = details.copy()
    conocidos = details.dropna(subset=["product_id", "unit_price"])
    grupos = _indice_precios(conocidos)

    aciertos = sum(
        _precio_cercano(grupos, p, o, i) == real
        for i, p, o, real in zip(conocidos.index, conocidos["product_id"],
                                  conocidos["order_id"], conocidos["unit_price"])
    )
    falta = details["unit_price"].isna() & details["product_id"].notna()
    details.loc[falta, "unit_price"] = [
        _precio_cercano(grupos, f.product_id, f.order_id) for f in details[falta].itertuples()
    ]
    info = {
        "aciertos": int(aciertos), "probados": len(conocidos),
        "porcentaje_acierto": round(aciertos / len(conocidos) * 100, 1),
        "completados": int(falta.sum()),
        "siguen_vacios": int(details["unit_price"].isna().sum()),
    }
    log.info("Nulos precio unitario: %s", info)
    return details, info


# --- Descuento ----------------------------------------------------------------
def completar_descuentos(details):
    """Si las otras líneas del mismo pedido tienen un solo descuento se usa ese; si no, 0."""
    details = details.copy()
    con_desc = details.dropna(subset=["discount"])
    por_pedido = {
        int(pedido): (g.index.to_numpy(), g["discount"].to_numpy(dtype="float64"))
        for pedido, g in con_desc.groupby("order_id", sort=False)
    }

    def descuento_pedido(pedido, excluir=None):
        g = por_pedido.get(int(pedido))
        if g is None:
            return None
        indices, valores = g
        if excluir is not None:
            valores = valores[indices != excluir]
        return float(valores[0]) if len(np.unique(valores)) == 1 else None

    prueba = [(descuento_pedido(o, i), real)
              for i, o, real in zip(con_desc.index, con_desc["order_id"], con_desc["discount"])]
    prueba = [(p, real) for p, real in prueba if p is not None]
    aciertos = sum(p == real for p, real in prueba)
    acierto_cero = float((con_desc["discount"] == 0).mean() * 100)

    falta = details["discount"].isna()
    valores = [descuento_pedido(f.order_id) for f in details[falta].itertuples()]
    n_pedido = sum(v is not None for v in valores)
    details.loc[falta, "discount"] = [0.0 if v is None else v for v in valores]
    info = {
        "aciertos": int(aciertos), "probados": len(prueba),
        "porcentaje_acierto": round(aciertos / len(prueba) * 100, 1),
        "porcentaje_acierto_si_siempre_cero": round(acierto_cero, 1),
        "vacios": int(falta.sum()), "con_descuento_del_pedido": int(n_pedido),
        "con_cero": int(len(valores) - n_pedido),
    }
    log.info("Nulos descuento: %s", info)
    return details, info


def recalcular_importe(details):
    details = details.copy()
    details["importe"] = calcular_importe(details)
    log.info("Importe tras imputaciones: total %.2f, líneas sin importe %d",
             details["importe"].sum(), details["importe"].isna().sum())
    return details
