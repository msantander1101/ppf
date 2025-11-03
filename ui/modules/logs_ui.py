"""
Módulo visual de logs — OSINT Suite v2
Permite ver logs del sistema en tiempo real, filtrados por módulo o nivel.
"""

import os
import time
import streamlit as st
from utils.logger import logger
from datetime import datetime

LOG_DIR = os.path.join(os.getcwd(), "logs")


def run():
    """
    Interfaz de visualización de logs con filtro de módulos y actualización dinámica.
    """
    st.title("🪵 Monitor de Logs del Sistema")

    # Archivo de log actual
    today_log = os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.log")

    if not os.path.exists(today_log):
        st.warning("⚠️ Aún no hay logs generados hoy.")
        return

    # Filtros
    st.sidebar.header("🔍 Filtros de visualización")

    module_filter = st.sidebar.multiselect(
        "Filtrar por módulo:",
        ["AI", "HIBP", "SEARCH", "CONFIG", "UI", "CORE", "GENERAL"],
        default=["AI", "HIBP", "SEARCH", "CONFIG", "UI"],
    )

    level_filter = st.sidebar.multiselect(
        "Filtrar por nivel:",
        ["INFO", "WARNING", "ERROR", "DEBUG"],
        default=["INFO", "WARNING", "ERROR"],
    )

    auto_refresh = st.sidebar.checkbox("🔄 Actualizar automáticamente", value=True)
    refresh_interval = st.sidebar.slider("Intervalo de actualización (s)", 2, 10, 5)

    st.markdown("---")
    st.markdown("### 📜 Últimos registros:")

    # Contenedor de logs
    log_container = st.empty()

    def read_logs():
        try:
            with open(today_log, "r", encoding="utf-8") as f:
                return f.readlines()[-400:]  # solo últimas 400 líneas
        except Exception as e:
            logger.error(f"[logs_ui] Error leyendo archivo de logs: {e}")
            return []

    def render_logs(lines):
        visible_logs = []
        for line in lines:
            line_upper = line.upper()
            if not any(lvl in line_upper for lvl in level_filter):
                continue
            if not any(mod in line_upper for mod in module_filter):
                continue

            # Color según nivel
            if "ERROR" in line_upper:
                color = "#FF4B4B"
            elif "WARNING" in line_upper:
                color = "#FFB200"
            elif "DEBUG" in line_upper:
                color = "#8A8A8A"
            else:
                color = "#4CAF50"

            visible_logs.append(f"<span style='color:{color}; font-family: monospace;'>{line.strip()}</span>")

        if not visible_logs:
            return "<i>Sin logs coincidentes con los filtros actuales.</i>"

        return "<br>".join(visible_logs[-200:])  # limitar salida

    # Loop de actualización en tiempo real
    while True:
        lines = read_logs()
        rendered = render_logs(lines)
        log_container.markdown(rendered, unsafe_allow_html=True)

        if not auto_refresh:
            break
        time.sleep(refresh_interval)
        st.experimental_rerun()
