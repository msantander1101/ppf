import streamlit.web.cli as stcli
import sys
from utils.logger import logger
from core.database import init_db

if __name__ == "__main__":
    try:
        init_db()
        logger.info("Arrancando OSINT Suite desde main.py")
        sys.argv = ["streamlit", "run", "ui/login.py"]
        sys.exit(stcli.main())
    except Exception as e:
        logger.exception(f"Error al arrancar la aplicación principal: {e}")
