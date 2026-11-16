"""Funciones pequeñas que usan varios módulos."""
import pandas as pd


def a_numero(serie):
    """Convierte una serie de texto a número; lo que no se puede convertir queda NaN."""
    return pd.to_numeric(serie.str.strip(), errors="coerce")


def calcular_importe(df):
    """importe = unit_price * quantity * (1 - discount). Un descuento vacío cuenta como 0."""
    p = pd.to_numeric(df["unit_price"], errors="coerce")
    q = pd.to_numeric(df["quantity"], errors="coerce")
    d = pd.to_numeric(df["discount"], errors="coerce").fillna(0)
    return (p * q * (1 - d)).astype("float64")
