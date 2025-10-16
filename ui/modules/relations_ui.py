import streamlit as st
import os
from utils.logger import logger
from modules.relations.explorer import RelationExplorer
from core.database import get_session, Relation, User


def run(username: str):
    """Interfaz del módulo de relaciones — creación y visualización de grafos."""
    st.title("🌐 Grafo de Relaciones")
    st.markdown("Visualiza y gestiona las conexiones entre entidades descubiertas durante tus investigaciones OSINT.")

    st.subheader("➕ Añadir relación manual")
    with st.form("add_relation_form", clear_on_submit=True):
        source = st.text_input("Entidad origen (source_id)", placeholder="p. ej. user_1 o correo@example.com")
        target = st.text_input("Entidad destino (target_id)", placeholder="p. ej. domain_1 o example.com")
        relation = st.text_input("Tipo de relación", placeholder="p. ej. usa, pertenece a, aparece en")
        submitted = st.form_submit_button("💾 Guardar relación")

        if submitted:
            if not source or not target or not relation:
                st.warning("Por favor, completa todos los campos antes de guardar.")
            else:
                try:
                    with get_session() as session:
                        user = session.query(User).filter(User.username == username).first()
                        if not user:
                            st.error("Error interno: usuario no encontrado en la base de datos.")
                            logger.error(f"No se encontró el usuario '{username}' al guardar relación.")
                            return

                        new_rel = Relation(
                            source_id=source,
                            target_id=target,
                            relation=relation,
                            user_id=user.id
                        )
                        session.add(new_rel)
                        session.commit()

                        st.success(f"Relación '{source}' → '{target}' guardada correctamente.")
                        logger.info(f"Relación añadida manualmente por {username}: {source} -> {target} ({relation})")
                except Exception as e:
                    st.error("Ocurrió un error al guardar la relación.")
                    logger.exception(f"Error guardando relación manual: {e}")

    st.divider()

    st.subheader("🕸️ Visualizar grafo de relaciones")
    explorer = RelationExplorer(username)

    if st.button("🔄 Construir grafo"):
        with st.spinner("Generando grafo..."):
            built = explorer.build_graph()
            if not built:
                st.warning("No se encontraron relaciones registradas para este usuario.")
                return

            path = explorer.save_graph()
            if path and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        html_content = f.read()
                    st.components.v1.html(html_content, height=600, scrolling=True)
                    st.success("✅ Grafo generado correctamente.")
                    logger.info(f"Grafo de relaciones mostrado en interfaz para {username}")
                except Exception as e:
                    logger.exception(f"Error mostrando grafo en interfaz: {e}")
                    st.error(f"Ocurrió un error al mostrar el grafo: {e}")
            else:
                st.error("No se pudo generar el grafo.")
