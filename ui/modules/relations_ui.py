# ui/modules/relations_ui.py
"""
Interfaz para visualizar, filtrar y gestionar relaciones entre entidades OSINT,
con vista en tabla y grafo global interactivo.
"""

import streamlit as st
from sqlmodel import select
from core.database import get_session
from core.entities import Relation, Person, Email, Domain
from utils.logger import logger
from pyvis.network import Network
import pandas as pd
import os
from datetime import datetime


def run(username: str):
    st.header("🕸️ Relaciones — Grafo Global de Entidades")
    st.info("Visualiza todas las relaciones detectadas entre personas, correos, dominios, URLs y más.")

    tab1, tab2 = st.tabs(["📋 Tabla de relaciones", "🌐 Grafo global"])

    with tab1:
        _show_table_view()

    with tab2:
        _show_global_graph()


# ==========================================================
# TABLA DE RELACIONES
# ==========================================================
def _show_table_view():
    col1, col2, col3 = st.columns(3)
    with col1:
        type_filter = st.selectbox("Filtrar por tipo", ["Todas", "referencia", "auto_enriched", "pwned_in", "related_domain", "found_by"])
    with col2:
        source_filter = st.text_input("Buscar en source_id", "")
    with col3:
        target_filter = st.text_input("Buscar en target_id", "")

    with get_session() as session:
        query = select(Relation)
        if type_filter != "Todas":
            query = query.where(Relation.relation == type_filter)
        relations = session.exec(query).all()

    if not relations:
        st.warning("No hay relaciones registradas todavía.")
        return

    data = [
        {
            "ID": r.id,
            "Origen (source_id)": r.source_id,
            "Destino (target_id)": r.target_id,
            "Tipo de relación": r.relation,
            "Fecha": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "—",
        }
        for r in relations
        if (not source_filter or source_filter.lower() in r.source_id.lower())
        and (not target_filter or target_filter.lower() in r.target_id.lower())
    ]

    if not data:
        st.warning("No se encontraron resultados que coincidan con los filtros.")
        return

    df = pd.DataFrame(data)
    st.dataframe(df, hide_index=True, width='stretch')

    st.markdown("---")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        delete_id = st.text_input("ID de relación a eliminar")
        if st.button("🗑️ Eliminar relación"):
            _delete_relation(delete_id)
    with col_b:
        if st.button("🔄 Refrescar"):
            st.rerun()
    with col_c:
        if st.button("💾 Exportar CSV"):
            _export_relations(df)


# ==========================================================
# GRAFO GLOBAL
# ==========================================================
def _show_global_graph():
    st.subheader("🌐 Grafo global de entidades")
    st.caption("Representa visualmente todas las relaciones almacenadas en la base de datos.")

    with get_session() as session:
        relations = session.exec(select(Relation)).all()
        persons = session.exec(select(Person)).all()
        emails = session.exec(select(Email)).all()
        try:
            domains = session.exec(select(Domain)).all()
        except Exception:
            domains = []

    if not relations:
        st.info("No hay relaciones registradas todavía.")
        return

    net = Network(height="750px", width="100%", bgcolor="#0e1117", font_color="white")
    net.barnes_hut()

    # === Añadimos los nodos ===
    for p in persons:
        net.add_node(f"person:{p.id}", label=p.name, color="#00aaff", shape="ellipse", title=f"Persona: {p.name}")
    for e in emails:
        net.add_node(f"email:{e.id}", label=e.address, color="#ffcc00", shape="dot", title=f"Email: {e.address}")
    for d in domains:
        net.add_node(f"domain:{d.id}", label=d.name, color="#00cc99", shape="box", title=f"Dominio: {d.name}")

    # === Nodos adicionales de relaciones ===
    for r in relations:
        src = r.source_id
        tgt = r.target_id
        if not net.get_node(src):
            _add_dynamic_node(net, src)
        if not net.get_node(tgt):
            _add_dynamic_node(net, tgt)
        net.add_edge(src, tgt, title=r.relation, color="#cccccc")

    # Exportar y mostrar grafo
    os.makedirs("data", exist_ok=True)
    out_path = "data/global_graph.html"
    net.show(out_path)

    with open(out_path, "r", encoding="utf-8") as f:
        st.components.v1.html(f.read(), height=750, scrolling=True)

    st.markdown("---")
    st.caption("Colores: 🟦 Personas | 🟨 Emails | 🟩 Dominios | 🟧 Otros nodos detectados")


def _add_dynamic_node(net, node_id: str):
    """Añade un nodo detectando su tipo por prefijo."""
    if node_id.startswith("url:"):
        net.add_node(node_id, label=node_id[4:], color="#ffa500", shape="diamond", title=node_id)
    elif node_id.startswith("breach:"):
        net.add_node(node_id, label=node_id[7:], color="#ff6666", shape="triangle", title="Data Breach")
    elif node_id.startswith("domain:"):
        net.add_node(node_id, label=node_id[7:], color="#00cc99", shape="box", title=node_id)
    elif node_id.startswith("email:"):
        net.add_node(node_id, label=node_id[6:], color="#ffcc00", shape="dot", title=node_id)
    elif node_id.startswith("person:"):
        net.add_node(node_id, label=node_id[7:], color="#00aaff", shape="ellipse", title=node_id)
    else:
        net.add_node(node_id, label=node_id, color="#aaaaaa", shape="star", title=node_id)


# ==========================================================
# FUNCIONES DE APOYO
# ==========================================================
def _delete_relation(relation_id: str):
    """Elimina una relación específica."""
    try:
        # Convertir el ID a entero si es posible
        rel_id = None
        if relation_id and str(relation_id).isdigit():
            rel_id = int(relation_id)
        with get_session() as session:
            relation = session.get(Relation, rel_id) if rel_id is not None else None
            if not relation:
                st.warning("Relación no encontrada.")
                return
            session.delete(relation)
            session.commit()
            st.success(f"✅ Relación {relation_id} eliminada correctamente.")
    except Exception as e:
        logger.exception(f"Error eliminando relación {relation_id}: {e}")
        st.error(f"Error al eliminar relación: {e}")


def _export_relations(df):
    """Exporta el dataframe a CSV."""
    try:
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Descargar CSV",
            data=csv.encode("utf-8"),
            file_name="relaciones_osint.csv",
            mime="text/csv",
        )
        st.success("Archivo CSV generado correctamente.")
    except Exception as e:
        logger.exception("Error exportando relaciones:", e)
        st.error("Error al generar el archivo CSV.")
