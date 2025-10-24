import os
import re
import io
from urllib.parse import urlparse
from typing import Dict, Optional
from sqlmodel import select
from pyvis.network import Network
# Importar únicamente la función get_session desde core.database. Las entidades
# se importan desde core.entities para evitar dependencias circulares y errores
# de importación. core.database expone un engine y un context manager, pero no
# define los modelos.
from core.database import get_session
from core.entities import Person, Email, Profile, Relation, SearchLog, User
from utils.logger import logger

GRAPH_OUTPUT = "data/graph.html"
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def _safe_id(prefix: str, label: str) -> str:
    s = str(label or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^0-9A-Za-z_\-\.@:/]", "", s)
    return f"{prefix}_{s}"


class GraphBuilder:
    COLOR_MAP = {
        "user": "#00E5FF",
        "email": "#FFD700",
        "social": "#FF69B4",
        "domain": "#32CD32",
        "leak": "#FF4500",
        "url": "#66B3FF",
        "dork": "#8A2BE2",
        "log": "#FFEB3B",
        "custom": "#FFFFFF",
    }

    def __init__(self, bgcolor: str = "#0e1117", font_color: str = "#FFFFFF"):
        self.net = Network(height="700px", width="100%", bgcolor=bgcolor, font_color=font_color, directed=True)
        self._nodes = set()
        self._type_cache = {}
        try:
            self.net.force_atlas_2based(gravity=-50)
        except Exception:
            pass
        logger.debug("GraphBuilder inicializado correctamente.")

    def add_entity(self, entity: Dict[str, str]):
        if not entity or "id" not in entity:
            return
        node_id = entity["id"]
        if node_id in self._nodes:
            return
        label = entity.get("label", node_id)
        ntype = entity.get("type", "custom")
        color = self.COLOR_MAP.get(ntype, "#FFFFFF")
        self.net.add_node(node_id, label=label, color=color, title=f"{ntype}: {label}")
        self._nodes.add(node_id)

    def add_relation(self, source_id: str, target_id: str, relation: str):
        if not source_id or not target_id:
            return
        for node in (source_id, target_id):
            if node not in self._nodes:
                self.add_entity({"id": node, "label": node, "type": "custom"})
        self.net.add_edge(source_id, target_id, label=relation, title=relation)

    def _infer_type_from_id(self, id_str: str) -> str:
        if id_str in self._type_cache:
            return self._type_cache[id_str]
        if isinstance(id_str, str):
            prefix = id_str.split(":", 1)[0].lower()
            if prefix in self.COLOR_MAP:
                self._type_cache[id_str] = prefix
                return prefix
            if "@" in id_str:
                t = "email"
            elif "." in id_str:
                t = "domain"
            else:
                t = "custom"
        else:
            t = "custom"
        self._type_cache[id_str] = t
        return t

    # ----------------------------------------------------------------------
    # Construcción principal del grafo
    # ----------------------------------------------------------------------
    def build_from_user(self, username: str, return_html: bool = False) -> Optional[str]:
        """
        Construye el grafo a partir del usuario indicado.
        Si return_html=True, devuelve el HTML como string (sin guardar archivo).
        """
        if not username:
            logger.warning("build_from_user: username vacío")
            return None

        with get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()
            if not user:
                logger.warning(f"Usuario '{username}' no encontrado.")
                return None

            user_node = _safe_id("user", username)
            self.add_entity({"id": user_node, "label": username, "type": "user"})

            # Relaciones persistidas
            relations = session.exec(select(Relation).where(Relation.user_id == user.id)).all()
            for rel in relations:
                src, tgt = rel.source_id, rel.target_id
                rel_label = rel.relation or "relacion"
                src_type = self._infer_type_from_id(src)
                tgt_type = self._infer_type_from_id(tgt)
                self.add_entity({"id": src, "label": src, "type": src_type})
                self.add_entity({"id": tgt, "label": tgt, "type": tgt_type})
                self.add_relation(src, tgt, rel_label)

            # Logs de búsqueda
            logs = session.exec(select(SearchLog).where(SearchLog.user_id == user.id)).all()
            for log in logs:
                try:
                    label = (log.query or "Búsqueda")[:120]
                    log_node = f"log_{log.id}"
                    self.add_entity({"id": log_node, "label": label, "type": "log"})
                    self.add_relation(user_node, log_node, "realizó búsqueda")

                    text_blob = f"{log.query or ''} {log.result or ''}"

                    # Emails
                    for em in set(EMAIL_RE.findall(text_blob)):
                        em_id = f"email:{em}"
                        self.add_entity({"id": em_id, "label": em, "type": "email"})
                        self.add_relation(log_node, em_id, "mencionado")
                        self.add_relation(user_node, em_id, "vinculado a")

                    # URLs y dominios
                    for u in set(re.findall(r"https?://[^\s'\"<>]+", text_blob)):
                        parsed = urlparse(u)
                        url_label = parsed.netloc or u
                        url_id = f"url:{u}"
                        domain_id = f"domain:{url_label}"
                        self.add_entity({"id": url_id, "label": url_label, "type": "url"})
                        self.add_relation(log_node, url_id, "mencionado")
                        self.add_relation(user_node, url_id, "vinculado a")
                        self.add_entity({"id": domain_id, "label": url_label, "type": "domain"})
                        self.add_relation(url_id, domain_id, "pertenece a")

                except Exception as e:
                    logger.debug(f"Error procesando log {getattr(log, 'id', 'unknown')}: {e}")

            logger.info(f"Grafo finalizado para '{username}' con {len(self._nodes)} nodos.")

            # Devolver HTML inline
            if return_html:
                return self._export_inline()
            else:
                return self.save(GRAPH_OUTPUT)

    # ----------------------------------------------------------------------
    # Exportación
    # ----------------------------------------------------------------------
    def _export_inline(self) -> str:
        """
        Exporta el grafo en memoria como HTML (string).
        Ideal para API o Streamlit.
        """
        try:
            buffer = io.StringIO()
            self.net.write_html(buffer)
            html_content = buffer.getvalue()
            buffer.close()
            return html_content
        except Exception as e:
            logger.exception(f"Error exportando grafo inline: {e}")
            return "<p>Error generando grafo.</p>"

    def save(self, path: str = GRAPH_OUTPUT) -> str:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.net.write_html(path, notebook=False)
            logger.info(f"Grafo exportado correctamente a {path}")
            return path
        except Exception as e:
            logger.exception(f"Error guardando grafo: {e}")
            raise


# ----------------------------------------------------------------------
# Grafo individual de persona
# ----------------------------------------------------------------------
def build_graph_html_for_person(person_id: int, return_html: bool = False, outpath: str = "data/graph_person.html"):
    net = Network(height="800px", width="100%", bgcolor="#1a1a1a", font_color="white", notebook=False)
    with get_session() as session:
        p = session.get(Person, person_id)
        if not p:
            raise ValueError("Persona no encontrada")

        net.add_node(f"person:{p.id}", label=p.name, title=p.notes or "", color="#00AEEF", shape="ellipse", size=30)

        for e in p.emails:
            net.add_node(f"email:{e.id}", label=e.address, title=e.leaks_summary or "", color="#FFCC00", shape="dot")
            net.add_edge(f"person:{p.id}", f"email:{e.id}", title="tiene email")

        for pr in p.profiles:
            net.add_node(f"profile:{pr.id}", label=f"{pr.platform}:{pr.handle}", title=pr.url, color="#66CC66", shape="box")
            net.add_edge(f"person:{p.id}", f"profile:{pr.id}", title="perfil")

        if return_html:
            buf = io.StringIO()
            net.write_html(buf)
            html = buf.getvalue()
            buf.close()
            return html

        os.makedirs(os.path.dirname(outpath), exist_ok=True)
        net.write_html(outpath, notebook=False)
        logger.info(f"Grafo de persona {p.name} guardado en {outpath}")
        return outpath
