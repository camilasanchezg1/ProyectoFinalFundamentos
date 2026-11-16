"""Punto de entrada: ejecuta el pipeline completo.

Uso:
    python main.py
"""
import logging
import sys

from src import config, pipeline


def configurar_log():
    config.DIR_OUTPUTS.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(config.DIR_OUTPUTS / "log_ejecucion.log", mode="w", encoding="utf-8"),
        ],
    )


def main():
    configurar_log()
    try:
        pipeline.ejecutar()
    except Exception as error:  # el mensaje queda en el log y el código de salida es 1
        logging.getLogger(__name__).error("El pipeline falló: %s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
