"""
Logger avanzado para Quasar OSINT Suite v2.
Centraliza el logging de todos los módulos con formato visual, colores y registro en archivo.
"""

import logging
import os
import sys
from datetime import datetime

# ==============================================
# 🎨 COLORES TERMINAL
# ==============================================
class LogColors:
    RESET = "\033[0m"
    GREY = "\033[90m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"


# ==============================================
# 🧩 FORMATO PERSONALIZADO
# ==============================================
class CustomFormatter(logging.Formatter):
    LEVEL_ICONS = {
        "DEBUG": "🐛",
        "INFO": "ℹ️ ",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "💥"
    }

    LEVEL_COLORS = {
        "DEBUG": LogColors.GREY,
        "INFO": LogColors.GREEN,
        "WARNING": LogColors.YELLOW,
        "ERROR": LogColors.RED,
        "CRITICAL": LogColors.MAGENTA
    }

    def format(self, record):
        timestamp = datetime.now().strftime("%H:%M:%S")
        icon = self.LEVEL_ICONS.get(record.levelname, "")
        color = self.LEVEL_COLORS.get(record.levelname, LogColors.WHITE)

        # Detección automática del módulo
        module_name = record.name.upper()
        if "AI" in module_name:
            module_color = LogColors.CYAN
        elif "HIBP" in module_name:
            module_color = LogColors.RED
        elif "SEARCH" in module_name:
            module_color = LogColors.BLUE
        elif "CONFIG" in module_name:
            module_color = LogColors.MAGENTA
        elif "UI" in module_name:
            module_color = LogColors.YELLOW
        else:
            module_color = LogColors.WHITE

        message = record.getMessage().replace("\n", " ").strip()

        return (
            f"{LogColors.GREY}[{timestamp}]{LogColors.RESET} "
            f"{color}{icon}{LogColors.RESET} "
            f"{module_color}[{module_name}]{LogColors.RESET} "
            f"{message}"
        )


# ==============================================
# 🪵 CONFIGURACIÓN GLOBAL
# ==============================================
def get_logger(name: str = "osint_suite"):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Consola
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(CustomFormatter())
    console.setLevel(logging.DEBUG)

    # Archivo
    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    file_handler.setLevel(logging.DEBUG)

    logger.addHandler(console)
    logger.addHandler(file_handler)
    logger.propagate = False

    return logger


# ==============================================
# 🌍 INICIALIZADOR GLOBAL
# ==============================================
def init_logger():
    """
    Inicializa el logger global y lo aplica a todos los módulos relevantes.
    """
    base_logger = get_logger("osint_suite")

    submodules = [
        "core",
        "core.config",
        "core.database",
        "modules.ai",
        "modules.search",
        "modules.hibp",
        "modules.ui",
        "ui",
    ]

    for mod in submodules:
        child_logger = logging.getLogger(mod)
        child_logger.setLevel(logging.DEBUG)
        child_logger.handlers = base_logger.handlers
        child_logger.propagate = False

    base_logger.info("✅ Logger global inicializado para todos los módulos.")
    return base_logger


# Instancia base (por compatibilidad retro)
logger = get_logger("osint_suite")
