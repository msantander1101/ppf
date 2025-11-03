import streamlit.web.cli as stcli
import sys
from utils.logger import init_logger
from core.database import init_db

if __name__ == "__main__":
    try:
        init_db()
        logger = init_logger()
        logger.info(f" Osint Souite iniciando.")
        sys.argv = ["streamlit", "run", "ui/login.py"]
        sys.exit(stcli.main())
    except Exception as e:
        logger.exception(f"Error al arrancar la aplicación principal: {e}")
