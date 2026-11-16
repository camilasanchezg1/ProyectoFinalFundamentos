"""Controles de calidad automáticos.

Cada control devuelve un Resultado (OK / FALLA). El pipeline los ejecuta todos, escribe
el reporte en outputs/reporte_validaciones.txt y, si alguno falla, detiene el proceso
con ValidacionError. Así una corrida con datos dañados no pasa en silencio.
"""
import logging
from dataclasses import dataclass

import pandas as pd

from . import config

log = logging.getLogger(__name__)


class ValidacionError(Exception):
    """Se lanza cuando al menos un control de calidad falla."""


@dataclass
class Resultado:
    control: str
    ok: bool
    detalle: str


def _r(control, condicion, detalle):
    return Resultado(control, bool(condicion), detalle)


def validar_pipeline(df_orders_raw, df_details_raw, orders, details, huerfanas,
                     consolidado, info_dup_details, reconciliacion):
    """Controles sobre el resultado del pipeline. Devuelve una lista de Resultado."""
    R = []

    # Control 1: unicidad de clave --------------------------------------------
    R.append(_r("C1 unicidad de order_id en orders", orders["order_id"].is_unique,
                f"{len(orders)} filas, {orders['order_id'].nunique()} order_id únicos"))
    claves = details.dropna(subset=["product_id"])
    rep = int(claves.duplicated(subset=["order_id", "product_id"]).sum())
    R.append(_r("C1 unicidad de order_id + product_id en order_details", rep == 0,
                f"{rep} claves repetidas"))

    # Control 2: reconciliación de totales ------------------------------------
    rc = reconciliacion
    R.append(_r("C2 reconciliación inicial de líneas",
                rc["lineas_total"] == rc["lineas_con_orden"] + rc["lineas_sin_orden"],
                f"{rc['lineas_total']} = {rc['lineas_con_orden']} + {rc['lineas_sin_orden']}"))
    R.append(_r("C2 reconciliación inicial de importes",
                abs(rc["importe_total"] - rc["importe_con_orden"] - rc["importe_sin_orden"]) < 0.01,
                f"{rc['importe_total']:.2f} = {rc['importe_con_orden']:.2f} + {rc['importe_sin_orden']:.2f}"))

    # Conservación de registros -----------------------------------------------
    esperadas = len(df_details_raw)
    obtenidas = info_dup_details["duplicados_eliminados"] + len(details) + len(huerfanas)
    R.append(_r("C3 conservación de líneas de order_details", esperadas == obtenidas,
                f"{esperadas} = {info_dup_details['duplicados_eliminados']} duplicadas + {len(details)} con pedido + {len(huerfanas)} huérfanas"))
    pedidos_orig = df_orders_raw["order_id"].str.strip().nunique()
    R.append(_r("C3 conservación de pedidos", len(orders) == pedidos_orig,
                f"{pedidos_orig} order_id distintos en origen, {len(orders)} en orders limpio"))

    # Integridad entre tablas -------------------------------------------------
    sin_pedido = int((~details["order_id"].isin(orders["order_id"])).sum())
    R.append(_r("C4 toda línea tiene pedido", sin_pedido == 0, f"{sin_pedido} líneas sin pedido"))
    sin_lineas = int((~orders["order_id"].isin(details["order_id"])).sum())
    R.append(_r("C4 todo pedido tiene al menos una línea", sin_lineas == 0, f"{sin_lineas} pedidos sin líneas"))

    # Tipos -------------------------------------------------------------------
    tipos_ok = (
        pd.api.types.is_float_dtype(details["unit_price"])
        and pd.api.types.is_float_dtype(details["discount"])
        and pd.api.types.is_integer_dtype(details["quantity"])
        and pd.api.types.is_integer_dtype(details["product_id"])
        and pd.api.types.is_float_dtype(orders["freight"])
        and all(pd.api.types.is_datetime64_any_dtype(orders[c]) for c in config.COLUMNAS_FECHA)
    )
    R.append(_r("C5 tipos de dato correctos", tipos_ok, "numéricos, enteros Int64 y fechas datetime"))

    # Rangos ------------------------------------------------------------------
    q = details["quantity"].dropna()
    d = details["discount"].dropna()
    f = orders["freight"].dropna()
    p = details["unit_price"].dropna()
    R.append(_r("C6 quantity entre 1 y %d" % config.CANTIDAD_MAX, ((q >= 1) & (q <= config.CANTIDAD_MAX)).all(),
                f"mín {q.min()}, máx {q.max()}"))
    R.append(_r("C6 discount entre 0 y %s" % config.DESCUENTO_MAX,
                ((d >= config.DESCUENTO_MIN) & (d <= config.DESCUENTO_MAX)).all(), f"mín {d.min()}, máx {d.max()}"))
    R.append(_r("C6 freight >= 0", (f >= 0).all(), f"mín {f.min()}"))
    R.append(_r("C6 unit_price > 0", (p > 0).all(), f"mín {p.min()}"))

    # Fechas ------------------------------------------------------------------
    o, rq, sh = orders["order_date"], orders["required_date"], orders["shipped_date"]
    n_env = int((sh < o).sum())
    n_req = int((rq < o).sum())
    R.append(_r("C7 ningún envío antes del pedido", n_env == 0, f"{n_env} casos"))
    R.append(_r("C7 ninguna fecha requerida antes del pedido", n_req == 0, f"{n_req} casos"))

    # Categorías y texto ------------------------------------------------------
    pais = orders["ship_country"]
    fuera = int(((pais != "") & ~pais.isin(config.PAISES_VALIDOS)).sum())
    R.append(_r("C8 países estándar", fuera == 0, f"{fuera} filas con país no estándar"))
    cols_texto = [c for c in orders.columns
                  if not pd.api.types.is_datetime64_any_dtype(orders[c])
                  and not pd.api.types.is_numeric_dtype(orders[c])]
    extranos = int(orders[cols_texto].apply(lambda c: c.str.contains(config.PATRON_CARACTERES_EXTRANOS, regex=True)).sum().sum())
    R.append(_r("C8 sin caracteres mal codificados", extranos == 0, f"{extranos} celdas"))
    espacios = int((orders[cols_texto] != orders[cols_texto].apply(lambda c: c.str.strip())).sum().sum())
    R.append(_r("C8 sin espacios al inicio o al final", espacios == 0, f"{espacios} celdas"))

    # Integración -------------------------------------------------------------
    R.append(_r("C9 la unión conserva las líneas", len(consolidado) == len(details),
                f"{len(details)} antes, {len(consolidado)} después"))
    R.append(_r("C9 la unión conserva los pedidos", consolidado["order_id"].nunique() == len(orders),
                f"{consolidado['order_id'].nunique()} de {len(orders)} pedidos"))
    antes, despues = round(details["importe"].sum(), 2), round(consolidado["importe"].sum(), 2)
    R.append(_r("C9 el importe total se conserva al unir", antes == despues, f"{antes:,.2f} antes, {despues:,.2f} después"))

    for r in R:
        log.info("%s | %s | %s", "OK   " if r.ok else "FALLA", r.control, r.detalle)
    return R


def validar_archivos_guardados(consolidado, huerfanas, ruta_consolidado, ruta_huerfanas):
    """Relee los CSV guardados y comprueba que tengan el tamaño esperado."""
    R = []
    for nombre, df, ruta in [("consolidado", consolidado, ruta_consolidado),
                             ("huérfanas", huerfanas, ruta_huerfanas)]:
        leido = pd.read_csv(ruta)
        R.append(_r(f"C10 archivo {nombre} guardado completo", leido.shape == df.shape,
                    f"esperado {df.shape}, leído {leido.shape}"))
    for r in R:
        log.info("%s | %s | %s", "OK   " if r.ok else "FALLA", r.control, r.detalle)
    return R


def escribir_reporte(resultados, ruta):
    fallas = [r for r in resultados if not r.ok]
    lineas = ["REPORTE DE VALIDACIONES", "=" * 23, ""]
    for r in resultados:
        lineas.append(f"[{'OK' if r.ok else 'FALLA'}] {r.control}: {r.detalle}")
    lineas += ["", f"Total: {len(resultados)} controles, {len(resultados) - len(fallas)} OK, {len(fallas)} con falla"]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return fallas


def exigir_todos_ok(resultados):
    fallas = [r for r in resultados if not r.ok]
    if fallas:
        raise ValidacionError("Fallaron %d controles: %s" % (len(fallas), "; ".join(r.control for r in fallas)))
