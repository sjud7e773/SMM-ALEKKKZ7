"""
Logger do sistema.
==================
Configuração centralizada de logging.
"""

import logging
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data", "logs")


def configurar_logger():
    """Configura o logger do sistema."""
    os.makedirs(LOG_DIR, exist_ok=True)

    log_file = os.path.join(LOG_DIR, f"bot_{datetime.now().strftime('%Y%m%d')}.log")

    # Formato
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Handler arquivo
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # Handler console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Logger principal
    log = logging.getLogger("smm_bot")
    log.setLevel(logging.DEBUG)

    # Evita handlers duplicados
    if not log.handlers:
        log.addHandler(file_handler)
        log.addHandler(console_handler)

    return log


logger = configurar_logger()
