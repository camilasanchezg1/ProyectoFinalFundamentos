"""Diagnóstico de calidad sobre las fuentes originales (antes de transformar).

Trabaja sobre los datos como texto. No modifica nada: solo mide y devuelve un
reporte de texto con las mismas categorías del avance 1.
"""
import logging
import re

import pandas as pd

from . import config
from .utils import a_numero

log = logging.getLogger(__name__)

_NOMBRES_FORMATO = {
    "9999-99-99": "AAAA-MM-DD (correcto)",
    "99/99/9999": "DD/MM/AAAA o MM/DD/AAAA",
    "99-99-9999": "DD-MM-AAAA o MM-DD-AAAA",
    "99.99.99": "DD.MM.AA",
    "99999999": "AAAAMMDD",
    "9999/99/99": "AAAA/MM/DD",
    "9 A A A 9999": "D de mes de AAAA",
    "99 A A A 9999": "D de mes de AAAA",
    "A 99, 9999": "Mes DD, AAAA",
}


def conteo_faltantes(df):
    """Celdas vacías (o solo espacios) por columna."""
    return df.apply(lambda c: c.str.strip().eq("").sum())


def revisar_numerica(df, columna, entero=False):
    serie = df[columna].str.strip()
    convertido = pd.to_numeric(serie, errors="coerce")
    no_num = serie[convertido.isna() & (serie != "")]
    res = {"no_numericos": len(no_num), "valores": no_num.value_counts().to_dict()}
    if entero:
        res["con_decimales"] = int((convertido.notna() & (convertido % 1 != 0)).sum())
    return res


def formato_fecha(valor):
    x = valor.strip()
    if x == "":
        return "vacío"
    patron = re.sub(r"[A-Za-zÁ-ú]+", "A", re.sub(r"\d", "9", x))
    return _NOMBRES_FORMATO.get(patron, "otro")


def diagnosticar(df_orders, df_details):
    """Devuelve (reporte_texto, resumen_dict)."""
    L = []
    resumen = {}

    def titulo(t):
        L.append("")
        L.append(t)
        L.append("-" * len(t))

    L.append("DIAGNÓSTICO DE CALIDAD (datos originales, antes de transformar)")
    L.append(f"orders: {df_orders.shape} | order_details: {df_details.shape}")

    # 1. Faltantes ------------------------------------------------------------
    titulo("1. Valores faltantes (vacíos)")
    for nombre, df in [("orders", df_orders), ("order_details", df_details)]:
        v = conteo_faltantes(df)
        L.append(f"{nombre}:")
        for col, n in v[v > 0].sort_values(ascending=False).items():
            L.append(f"  {col}: {n} ({n / len(df) * 100:.2f} %)")
    na = (df_details["unit_price"] == "N/A").sum()
    free = (df_details["unit_price"] == "free").sum()
    L.append(f"unit_price escrito como texto: N/A = {na}, free = {free}")

    # 2. Duplicados -----------------------------------------------------------
    titulo("2. Registros duplicados")
    exactos = int(df_orders.duplicated().sum())
    por_id = int(df_orders.duplicated(subset="order_id").sum())
    resumen["orders_duplicados_exactos"] = exactos
    resumen["orders_conflicto"] = por_id - exactos
    L.append(f"orders: filas idénticas repetidas = {exactos}; mismo order_id con contenido distinto = {por_id - exactos}")
    sin_exactos = df_orders.drop_duplicates()
    conflicto = sin_exactos[sin_exactos.duplicated(subset="order_id", keep=False)]
    if len(conflicto):
        difieren = conflicto.groupby("order_id").agg(lambda s: s.nunique() > 1).any()
        L.append(f"  columnas que difieren entre las copias: {difieren[difieren].index.tolist()}")
    exactos_d = int(df_details.duplicated().sum())
    por_clave_tras = int(df_details.drop_duplicates().duplicated(subset=["order_id", "product_id"]).sum())
    resumen["details_duplicados_exactos"] = exactos_d
    L.append(f"order_details: filas idénticas repetidas = {exactos_d}; repetidas por order_id + product_id tras quitar idénticas = {por_clave_tras}")

    # 3. Tipos ----------------------------------------------------------------
    titulo("3. Tipos de dato incorrectos (valores no convertibles)")
    for col, entero in [("order_id", True), ("product_id", True), ("unit_price", False),
                        ("quantity", True), ("discount", False)]:
        r = revisar_numerica(df_details, col, entero)
        extra = f", con decimales = {r['con_decimales']}" if entero else ""
        L.append(f"order_details.{col}: no numéricos = {r['no_numericos']}{extra}")
    for col, entero in [("order_id", True), ("employee_id", True), ("ship_via", True), ("freight", False)]:
        r = revisar_numerica(df_orders, col, entero)
        L.append(f"orders.{col}: no numéricos = {r['no_numericos']}")
    for col in config.COLUMNAS_FECHA:
        s = df_orders[col].str.strip()
        iso = s.str.fullmatch(r"\d{4}-\d{2}-\d{2}")
        L.append(f"orders.{col}: fuera de AAAA-MM-DD = {int((~iso & (s != '')).sum())}")

    # 4. Formatos -------------------------------------------------------------
    titulo("4. Formatos inconsistentes")
    for nombre, df in [("orders", df_orders), ("order_details", df_details)]:
        for col in df.columns:
            n = int((df[col] != df[col].str.strip()).sum())
            if n:
                L.append(f"{nombre}.{col}: {n} valores con espacios al inicio o al final")
    L.append(f"order_details.order_id con '.0' al final: {int(df_details['order_id'].str.strip().str.endswith('.0').sum())}")
    pais = df_orders["ship_country"].str.strip()
    no_estandar = pais[(pais != "") & ~pais.isin(config.PAISES_VALIDOS)]
    resumen["paises_no_estandar_filas"] = len(no_estandar)
    L.append(f"ship_country: {len(no_estandar)} filas con país no estándar ({no_estandar.nunique()} variantes)")
    tabla = pd.DataFrame({c: df_orders[c].map(formato_fecha).value_counts() for c in config.COLUMNAS_FECHA})
    L.append("Formatos de fecha en orders:")
    L.append(tabla.fillna(0).astype(int).to_string())

    # 5. Fuera de rango -------------------------------------------------------
    titulo("5. Valores fuera de rango")
    q = a_numero(df_details["quantity"])
    desc = a_numero(df_details["discount"])
    f = a_numero(df_orders["freight"])
    L.append(f"quantity <= 0: {int((q <= 0).sum())} | quantity > {config.CANTIDAD_MAX}: {int((q > config.CANTIDAD_MAX).sum())}")
    L.append(f"discount fuera de los valores típicos: {int((desc.notna() & ~desc.isin(config.DESCUENTOS_TIPICOS)).sum())}")
    L.append(f"freight < 0: {int((f < 0).sum())}")

    # 6. Integridad entre tablas ---------------------------------------------
    titulo("6. Integridad entre tablas")
    ids_orders = set(df_orders["order_id"].str.strip())
    ids_details = set(df_details["order_id"])
    L.append(f"order_id de order_details sin pedido en orders (tal como vienen): {len(ids_details - ids_orders)}")
    ids_norm = df_details["order_id"].str.strip().str.replace(r"\.0$", "", regex=True)
    huerfanos = ids_norm[~ids_norm.isin(ids_orders)]
    resumen["lineas_huerfanas_normalizadas"] = len(huerfanos)
    L.append(f"tras normalizar espacios y '.0': {len(huerfanos)} líneas sin pedido {sorted(huerfanos.unique())}")

    # 7. Encoding -------------------------------------------------------------
    titulo("7. Caracteres mal codificados")
    for nombre, df in [("orders", df_orders), ("order_details", df_details)]:
        total = 0
        for col in df.columns:
            n = int(df[col].str.contains(config.PATRON_CARACTERES_EXTRANOS, regex=True).sum())
            if n:
                total += n
                L.append(f"{nombre}.{col}: {n} valores con caracteres extraños")
        L.append(f"{nombre}: {total} celdas afectadas")
        resumen[f"{nombre}_celdas_encoding"] = total

    log.info("Diagnóstico completado")
    return "\n".join(L) + "\n", resumen
