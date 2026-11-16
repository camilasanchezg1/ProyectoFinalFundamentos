"""Transformaciones 3, 4 y 5: conversión numérica y rangos, fechas y categorías."""
import logging
import re

import numpy as np
import pandas as pd

from . import config
from .utils import calcular_importe

log = logging.getLogger(__name__)


# --- Transformación 3: conversión numérica y rangos ---------------------------
def limpiar_numero(serie):
    """Quita $ y USD, cambia la coma por punto, divide entre 100 los valores con %
    y traduce las palabras 'diez' y 'cinco'. Lo que no se puede convertir queda NaN."""
    s = serie.str.strip().str.lower().replace(config.PALABRAS_NUMERICAS)
    s = s.str.replace("$", "", regex=False).str.replace("usd", "", regex=False)
    s = s.str.replace(",", ".", regex=False).str.strip()
    porcentaje = s.str.endswith("%")
    numero = pd.to_numeric(s.str.replace("%", "", regex=False), errors="coerce")
    numero.loc[porcentaje] = numero.loc[porcentaje] / 100
    return numero


def convertir_numericas(details, orders):
    details, orders = details.copy(), orders.copy()
    info = {}
    for df, nombre, columna in [(details, "order_details", "unit_price"),
                                (details, "order_details", "quantity"),
                                (details, "order_details", "discount"),
                                (orders, "orders", "freight")]:
        original = df[columna]
        df[columna] = limpiar_numero(original)
        sin_convertir = original[(original != "") & df[columna].isna()]
        info[f"{nombre}.{columna}"] = {"convertidos": int(df[columna].notna().sum()),
                                      "quedan_nan": sorted(sin_convertir.unique().tolist())}
    log.info("T3 conversión numérica: %s", info)
    return details, orders, info


def aplicar_rangos(details, orders):
    """Lo que está fuera de rango queda como NaN (así no se pierde el resto de la línea).

    Reglas: quantity entera, > 0 y <= CANTIDAD_MAX; discount entre 0 y 0.25;
    freight >= 0. Los descuentos de 0.01 a 0.06 del pedido 11077 quedan dentro del rango.
    """
    details, orders = details.copy(), orders.copy()
    q, desc, f = details["quantity"], details["discount"], orders["freight"]
    mala_q = q.notna() & ((q <= 0) | (q > config.CANTIDAD_MAX) | (q % 1 != 0))
    malo_desc = (desc < config.DESCUENTO_MIN) | (desc > config.DESCUENTO_MAX)
    malo_f = f < 0
    info = {
        "quantity_invalidas": sorted(q[mala_q].tolist()),
        "discount_invalidos": sorted(desc[malo_desc].tolist()),
        "freight_negativos": sorted(f[malo_f].tolist()),
        "unit_price_no_positivos": int((details["unit_price"] <= 0).sum()),
    }
    details.loc[mala_q, "quantity"] = np.nan
    details.loc[malo_desc, "discount"] = np.nan
    orders.loc[malo_f, "freight"] = np.nan
    log.info("T3 rangos: %s", info)
    return details, orders, info


def _a_int64(serie):
    return pd.to_numeric(serie.replace("", np.nan)).astype("Int64")


def convertir_enteros(details, orders):
    """Int64 (con mayúscula) porque este tipo sí admite valores vacíos."""
    details, orders = details.copy(), orders.copy()
    for col in ["order_id", "product_id", "quantity"]:
        details[col] = _a_int64(details[col])
    for col in ["order_id", "employee_id", "ship_via"]:
        orders[col] = _a_int64(orders[col])
    return details, orders


def agregar_importe(details):
    details = details.copy()
    details["importe"] = calcular_importe(details)
    log.info("Importe recalculado: total %.2f, líneas sin importe %d",
             details["importe"].sum(), details["importe"].isna().sum())
    return details


# --- Transformación 4: fechas -------------------------------------------------
def convertir_fecha(x):
    """Convierte un texto de fecha en Timestamp; si no se reconoce devuelve NaT."""
    if x == "":
        return pd.NaT
    for patron, formato in config.FORMATOS_FECHA:
        if re.fullmatch(patron, x):
            return pd.to_datetime(x, format=formato)
    m = re.fullmatch(r"(\d{1,2}) de ([a-z]+) de (\d{4})", x.lower())
    if m and m.group(2) in config.MESES_ES:
        return pd.Timestamp(int(m.group(3)), config.MESES_ES[m.group(2)], int(m.group(1)))
    m = re.fullmatch(r"([A-Za-z]{3}) (\d{2}), (\d{4})", x)
    if m and m.group(1).lower() in config.MESES_EN_ABREV:
        return pd.Timestamp(int(m.group(3)), config.MESES_EN_ABREV[m.group(1).lower()], int(m.group(2)))
    return pd.NaT


def revisar_orden_dia_mes(orders):
    """Evidencia de la regla barra = DD/MM y guion = MM-DD: cuántas fechas no ambiguas
    muestran el día primero y cuántas el mes primero, por separador."""
    resultado = {}
    for sep in ["/", "-"]:
        total = dia_primero = mes_primero = 0
        for col in config.COLUMNAS_FECHA:
            s = orders[col]
            m = s[s.str.fullmatch(r"\d{2}" + re.escape(sep) + r"\d{2}" + re.escape(sep) + r"\d{4}")]
            total += len(m)
            dia_primero += int((m.str[:2].astype(int) > 12).sum())
            mes_primero += int((m.str[3:5].astype(int) > 12).sum())
        resultado[sep] = {"total": total, "dia_primero": dia_primero, "mes_primero": mes_primero}
    return resultado


def convertir_fechas(orders):
    orders = orders.copy()
    info = {"orden_dia_mes": revisar_orden_dia_mes(orders)}
    for col in config.COLUMNAS_FECHA:
        original = orders[col]
        orders[col] = pd.to_datetime(original.map(convertir_fecha))
        info[col] = {
            "convertidas": int(orders[col].notna().sum()),
            "vacias": int((original == "").sum()),
            "sin_convertir": int(((original != "") & orders[col].isna()).sum()),
        }
    log.info("T4 fechas: %s", info)
    return orders, info


# --- Transformación 5: categorías --------------------------------------------
def estandarizar_paises(orders):
    orders = orders.copy()
    validos_minus = {p.lower(): p for p in config.PAISES_VALIDOS}

    def estandarizar(x):
        clave = x.lower()
        if clave in validos_minus:
            return validos_minus[clave]
        return config.EQUIVALENCIAS_PAIS.get(clave, x)

    antes = orders["ship_country"]
    orders["ship_country"] = antes.map(estandarizar)
    info = {
        "distintos_antes": int(antes.nunique()),
        "distintos_despues": int(orders["ship_country"].nunique()),
        "filas_cambiadas": int((antes != orders["ship_country"]).sum()),
    }
    log.info("T5 países: %s", info)
    return orders, info


def _forma_comun(serie):
    """Para valores que solo cambian en mayúsculas deja la forma mixta más frecuente."""
    s = serie[serie != ""]
    mixtas = s[~s.str.isupper() & ~s.str.islower()]
    forma = mixtas.groupby(mixtas.str.lower()).agg(lambda x: x.value_counts().index[0])
    return serie.map(lambda x: forma.get(x.lower(), x))


def unificar_mayusculas(orders, columnas=("ship_name", "ship_city", "ship_address")):
    orders = orders.copy()
    info = {}
    for col in columnas:
        antes = orders[col]
        orders[col] = _forma_comun(antes)
        info[col] = int((antes != orders[col]).sum())
    log.info("T5 mayúsculas (filas cambiadas): %s", info)
    return orders, info


def _variantes_por_cliente(df, col):
    datos = df[(df["customer_id"] != "") & (df[col] != "")]
    return int((datos.groupby("customer_id")[col].nunique() > 1).sum())


def _corregir_columna_por_cliente(df, col):
    """Cada cliente tiene una sola dirección de envío: se usa la forma más repetida.
    Si hay empate no se cambia nada. Las filas sin customer_id quedan igual."""
    datos = df[(df["customer_id"] != "") & (df[col] != "")]
    moda = datos.groupby("customer_id")[col].agg(lambda s: s.mode()[0] if len(s.mode()) == 1 else None)
    correcto = df["customer_id"].map(moda)
    cambiar = correcto.notna() & (df[col] != "") & (df[col] != correcto)
    return df[col].where(~cambiar, correcto), int(cambiar.sum())


def corregir_por_cliente(orders, columnas=("ship_name", "ship_address", "ship_city", "ship_postal_code")):
    orders = orders.copy()
    info = {}
    for col in columnas:
        antes = _variantes_por_cliente(orders, col)
        orders[col], cambios = _corregir_columna_por_cliente(orders, col)
        info[col] = {"filas_corregidas": cambios, "clientes_con_variantes_antes": antes,
                     "clientes_con_variantes_despues": _variantes_por_cliente(orders, col)}
    log.info("T5 corrección por cliente: %s", info)
    return orders, info
