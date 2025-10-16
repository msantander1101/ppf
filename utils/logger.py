import logging
import os

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

os.makedirs(LOG_DIR, exist_ok=True)

# Configuración global de logging
logging.basicConfig(
    level=logging.DEBUG,  # Cambia a INFO o WARNING si quieres menos detalle
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()  # también muestra en consola
    ]
)

# Logger principal del proyecto
logger = logging.getLogger("osint_suite")
