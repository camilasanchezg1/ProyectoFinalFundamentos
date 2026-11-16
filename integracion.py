"""Integración de order_details con orders mediante order_id."""
import logging

log = logging.getLogger(__name__)


def integrar(details, orders):
    """Une details con orders (relación muchos a uno).

    validate="many_to_one" hace que pandas falle si hubiera un order_id repetido en
    orders, en vez de duplicar líneas en silencio. how="left" desde details no pierde líneas.
    """
    consolidado = details.merge(orders, on="order_id", how="left",
                                validate="many_to_one", indicator=True)
    estados = consolidado["_merge"].value_counts().to_dict()
    if len(consolidado) != len(details):
        raise ValueError(f"La unión cambió el número de líneas: {len(details)} -> {len(consolidado)}")
    if estados.get("left_only", 0):
        raise ValueError(f"Hay {estados['left_only']} líneas sin pedido después de la unión")
    log.info("Integración: %d líneas, %d columnas, merge=%s",
             len(consolidado), consolidado.shape[1] - 1, {str(k): int(v) for k, v in estados.items()})
    return consolidado.drop(columns="_merge")
