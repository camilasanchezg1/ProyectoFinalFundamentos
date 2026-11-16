"""Orquesta el proceso completo, en el mismo orden del avance 2."""
import logging
from pathlib import Path

from . import (config, diagnostico, extraccion, integracion, limpieza, nulos,
               transformaciones, validaciones)

log = logging.getLogger(__name__)


def ejecutar(dir_raw=None, dir_processed=None, dir_outputs=None):
    """Corre todo el pipeline y devuelve un diccionario con los resultados."""
    dir_raw = Path(dir_raw or config.DIR_RAW)
    dir_processed = Path(dir_processed or config.DIR_PROCESSED)
    dir_outputs = Path(dir_outputs or config.DIR_OUTPUTS)
    dir_processed.mkdir(parents=True, exist_ok=True)
    dir_outputs.mkdir(parents=True, exist_ok=True)

    # 1. Extracción y diagnóstico ---------------------------------------------
    df_orders, df_details = extraccion.extraer_fuentes(dir_raw)
    reporte, resumen_diag = diagnostico.diagnosticar(df_orders, df_details)
    (dir_outputs / "reporte_diagnostico.txt").write_text(reporte, encoding="utf-8")

    # 2. Transformación 1 y Control 2 -----------------------------------------
    orders, _ = limpieza.deduplicar_orders(df_orders)
    reconciliacion = limpieza.reconciliar_totales(df_details, orders)

    # 3. Transformación 2 -----------------------------------------------------
    orders, details, _ = limpieza.limpiar_texto_e_ids(orders, df_details)
    orders, _ = limpieza.quitar_encoding(orders)
    details, info_dup_details = limpieza.deduplicar_details(details)
    details, huerfanas, _ = limpieza.separar_huerfanas(details, orders)

    # 4. Transformación 3 -----------------------------------------------------
    details, orders, _ = transformaciones.convertir_numericas(details, orders)
    details, orders, _ = transformaciones.aplicar_rangos(details, orders)
    details, orders = transformaciones.convertir_enteros(details, orders)
    details = transformaciones.agregar_importe(details)

    # 5. Transformación 4 -----------------------------------------------------
    orders, _ = transformaciones.convertir_fechas(orders)

    # 6. Transformación 5 -----------------------------------------------------
    orders, _ = transformaciones.estandarizar_paises(orders)
    orders, _ = transformaciones.unificar_mayusculas(orders)
    orders, _ = transformaciones.corregir_por_cliente(orders)

    # 7. Manejo de nulos ------------------------------------------------------
    orders, _ = nulos.completar_cliente_y_envio(orders)
    details, _ = nulos.completar_precios(details)
    details, _ = nulos.completar_descuentos(details)
    details = nulos.recalcular_importe(details)

    # 8. Integración ----------------------------------------------------------
    consolidado = integracion.integrar(details, orders)

    # 9. Validaciones y guardado ----------------------------------------------
    resultados = validaciones.validar_pipeline(
        df_orders, df_details, orders, details, huerfanas, consolidado,
        info_dup_details, reconciliacion)

    ruta_consolidado = dir_processed / config.ARCHIVO_CONSOLIDADO
    ruta_huerfanas = dir_processed / config.ARCHIVO_HUERFANAS
    consolidado.to_csv(ruta_consolidado, index=False)
    huerfanas.to_csv(ruta_huerfanas, index=False)
    resultados += validaciones.validar_archivos_guardados(
        consolidado, huerfanas, ruta_consolidado, ruta_huerfanas)

    validaciones.escribir_reporte(resultados, dir_outputs / "reporte_validaciones.txt")
    validaciones.exigir_todos_ok(resultados)

    log.info("Listo: %s (%d filas, %d columnas) y %s (%d filas)",
             ruta_consolidado.name, len(consolidado), consolidado.shape[1],
             ruta_huerfanas.name, len(huerfanas))
    return {"consolidado": consolidado, "huerfanas": huerfanas, "orders": orders,
            "details": details, "resultados": resultados, "diagnostico": resumen_diag,
            "df_orders_raw": df_orders, "df_details_raw": df_details,
            "info_dup_details": info_dup_details, "reconciliacion": reconciliacion}
