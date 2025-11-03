# modules/graph/visualize.py
from pyvis.network import Network
from core.database import get_session
from core.entities import Relation, Person, OsintResult
from sqlmodel import select
from utils.logger import logger
from typing import Optional

def build_person_graph_html(person_id: int, output_path: str = None) -> Optional[str]:
    """
    Construye un grafo con pyvis para una persona (nodos: persona, emails, perfiles, urls, breaches).
    Devuelve la ruta del archivo HTML generado (temporal) o None en error.
    """
    try:
        net = Network(height="700px", width="100%", directed=True)
        with get_session() as session:
            # nodo persona
            person = session.get(Person, int(person_id))
            if not person:
                logger.warning(f"[graph] Persona {person_id} no encontrada")
                return None

            person_node = f"person:{person.id}"
            net.add_node(person_node, label=person.name, title=f"Persona: {person.name}", shape="ellipse", color="#1f77b4")

            # relaciones guardadas (desde Relation)
            rels = session.exec(select(Relation).where(Relation.source_id == person_node)).all()
            for r in rels:
                target = r.target_id
                # si target es person:something, o url:xxx o hibp:breach
                label = r.relation or ""
                # Añadir nodo destino si no existe
                net.add_node(target, label=target, title=f"{label}\n{target}", shape="dot")
                net.add_edge(person_node, target, title=label)

            # También añadir resultados guardados en OsintResult (si existe)
            try:
                ors = session.exec(select(OsintResult).where(OsintResult.person_id == person.id)).all()
                for orr in ors:
                    node_id = f"osint:{orr.id}"
                    title = f"{orr.source} - {orr.mode}"
                    net.add_node(node_id, label=(orr.title[:40] or orr.query), title=f"{title}\n{orr.snippet}", shape="triangle")
                    net.add_edge(person_node, node_id, title=orr.mode)
            except Exception:
                # si no existe OsintResult, lo ignoramos (compatibilidad)
                pass

        # config
        net.set_options("""
        var options = {
          "nodes": { "font": { "size": 14 }},
          "edges": { "arrows": { "to": { "enabled": true }}},
          "physics": { "stabilization": false, "barnesHut": { "gravitationalConstant": -8000 } }
        }
        """)

        out = output_path or f"/tmp/osint_graph_person_{person_id}.html"
        net.save_graph(out)
        logger.info(f"[graph] Grafo guardado en {out}")
        return out
    except Exception as e:
        logger.exception(f"[graph] Error build_person_graph_html: {e}")
        return None
