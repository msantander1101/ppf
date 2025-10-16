import streamlit as st
import streamlit.components.v1 as components
from utils.logger import logger
from modules.graph.builder import GraphBuilder
import os

def run(username: str):
    """
    Interfaz para renderizar el grafo dinámico del usuario.
    """
    st.header("🕸️ Grafo Relacional (dinámico)")
    st.write("Visualiza las relaciones automáticas extraídas de tu historial de búsquedas.")

    if not username:
        st.warning("No hay usuario activo.")
        return

    # Botón para (re)construir grafo
    if st.button("🔄 Generar/Actualizar grafo"):
        try:
            builder = GraphBuilder()
            builder.build_from_user(username)
            path = builder.save()
            st.success("Grafo generado correctamente.")
            # Renderizar HTML
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    html = f.read()
                components.html(html, height=720, scrolling=True)
            else:
                st.error("No se encontró el archivo del grafo.")
        except Exception as e:
            st.error("Error generando el grafo. Revisa los logs.")
            logger.exception(f"Error en graph_ui.run para {username}: {e}")
    else:
        st.info("Pulsa 'Generar/Actualizar grafo' para construirlo a partir de tu historial.")

    # Opción: mostrar número de entradas (simple)
    st.markdown("---")
    st.caption("El grafo se genera a partir de las entradas almacenadas en tu historial (SearchLog).")
