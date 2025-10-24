import os
from pyvis.network import Network
from core.database import get_session
from core.entities import Relation, User
from utils.logger import logger


class RelationExplorer:
    """Crea y visualiza un grafo basado en las relaciones almacenadas."""

    def __init__(self, username: str):
        self.username = username
        self.net = Network(
            height="600px",
            width="100%",
            bgcolor="#0e1117",
            font_color="white",
            notebook=False,
            directed=True
        )
        logger.debug(f"Inicializando RelationExplorer para usuario {username}")

    def build_graph(self):
        """Construye el grafo a partir de las relaciones del usuario."""
        try:
            with get_session() as session:
                user = session.query(User).filter(User.username == self.username).first()
                if not user:
                    logger.warning(f"No se encontró el usuario '{self.username}' para grafo.")
                    return None

                relations = session.query(Relation).filter(Relation.user_id == user.id).all()
                if not relations:
                    logger.info(f"No hay relaciones registradas para {self.username}.")
                    return None

                added_nodes = set()
                for rel in relations:
                    if rel.source_id not in added_nodes:
                        self.net.add_node(rel.source_id, label=rel.source_id, color="#4FC3F7")
                        added_nodes.add(rel.source_id)
                    if rel.target_id not in added_nodes:
                        self.net.add_node(rel.target_id, label=rel.target_id, color="#81C784")
                        added_nodes.add(rel.target_id)
                    self.net.add_edge(rel.source_id, rel.target_id, label=rel.relation)

                logger.debug(f"Grafo construido con {len(added_nodes)} nodos y {len(relations)} relaciones.")
                return True

        except Exception as e:
            logger.exception(f"Error construyendo grafo para usuario {self.username}: {e}")
            return None

    def save_graph(self):
        """Guarda el grafo como HTML seguro para Streamlit."""
        try:
            os.makedirs("data/graphs", exist_ok=True)
            path = f"data/graphs/relations_{self.username}.html"
            self.net.write_html(path, notebook=False)
            logger.info(f"Grafo de relaciones guardado en {path}")
            return path
        except Exception as e:
            logger.exception(f"Error guardando grafo de {self.username}: {e}")
            return None
