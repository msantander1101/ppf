import os
import re
from urllib.parse import urlparse
from typing import Dict, Any
from sqlmodel import select
from pyvis.network import Network
import json
from core.database import get_session, Person, Email, Profile, Relation, SearchLog, Relation, User
from utils.logger import logger

GRAPH_OUTPUT = "data/graph.html"
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def _safe_id(prefix: str, label: str) -> str:
    """
    Construye un, id seguro para nodos a partir de un prefijo y etiqueta.
    Reemplaza espacios y caracteres problemáticos.
    """
    s = str(label or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^0-9A-Za-z_\-\.@:/]", "", s)  # permitimos ':' '/' para preservar prefijos y URLs mínimamente
    return f"{prefix}_{s}"


class GraphBuilder:
    def __init__(self, bgcolor: str = "#0e1117", font_color: str = "white"):
        self.net = Network(height="700px", width="100%", bgcolor=bgcolor, font_color=font_color, directed=True)
        # intentar ajustar física si está disponible
        try:
            self.net.force_atlas_2based(gravity=-50)
        except Exception:
            pass
        self._nodes = set()
        logger.debug("GraphBuilder inicializado")

    def add_entity(self, entity: Dict[str, str]):
        """
        Añade un nodo si no existe.
        entity: {"id": ..., "label": ..., "type": ...}
        """
        if entity["id"] in self._nodes:
            return
        color_map = {
            "user": "#00FFFF",
            "email": "#FFD700",
            "social": "#FF69B4",
            "domain": "#32CD32",
            "leak": "#FF4500",
            "url": "#66b3ff",
            "dork": "#8A2BE2",
            "log": "#FFD54F",
            "custom": "#FFFFFF"
        }
        color = color_map.get(entity.get("type"), "#FFFFFF")
        label = entity.get("label") or entity["id"]
        self.net.add_node(entity["id"], label=label, color=color, title=label)
        self._nodes.add(entity["id"])
        logger.debug(f"Añadido nodo: {entity}")

    def add_relation(self, source_id: str, target_id: str, relation: str):
        """
        Añade una arista (edge) al grafo.
        """
        # Aseguramos que los nodos existan (si no, se crean con label = id)
        if source_id not in self._nodes:
            self.add_entity({"id": source_id, "label": source_id, "type": "custom"})
        if target_id not in self._nodes:
            self.add_entity({"id": target_id, "label": target_id, "type": "custom"})
        self.net.add_edge(source_id, target_id, label=relation, title=relation)
        logger.debug(f"Añadida relación {source_id} -> {target_id}: {relation}")

    def save(self, path: str = GRAPH_OUTPUT):
        """
        Guarda el grafo como HTML usando write_html (no intenta abrir navegador).
        """
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.net.write_html(path, notebook=False)
            logger.info(f"Grafo exportado correctamente a {path}")
            return path
        except Exception as e:
            logger.exception(f"Error guardando grafo: {e}")
            raise

    # ---------------------------
    # Construcción dinámica desde DB
    # ---------------------------
    def build_from_user(self, username: str):
        """
        Construye el grafo usando:
         - Relaciones persistidas (Relation)
         - Logs de búsqueda (SearchLog) (se añaden como nodos conectados al usuario)
         - Heurísticas simples: extracción de emails/urls desde logs/resultados guardados
        """
        if not username:
            logger.warning("build_from_user: username vacío")
            return None

        try:
            with get_session() as session:
                user = session.exec(select(User).where(User.username == username)).first()
                if not user:
                    logger.warning(f"build_from_user: usuario '{username}' no encontrado")
                    return None

                # Nodo principal del usuario
                user_node = _safe_id("user", username)
                self.add_entity({"id": user_node, "label": username, "type": "user"})

                # 1) Relaciones persistidas
                relations = session.exec(select(Relation).where(Relation.user_id == user.id)).all()
                for rel in relations:
                    src = rel.source_id
                    tgt = rel.target_id
                    rel_label = rel.relation or "relacion"
                    # añadimos nodos y aristas tal cual están almacenadas
                    # si prefieres normalizar ids, aplicar transformaciones aquí
                    self.add_entity({"id": src, "label": src, "type": self._infer_type_from_id(src)})
                    self.add_entity({"id": tgt, "label": tgt, "type": self._infer_type_from_id(tgt)})
                    self.add_relation(src, tgt, rel_label)

                # 2) Logs de búsqueda — los representamos como nodos conectados al usuario
                logs = session.exec(select(SearchLog).where(SearchLog.user_id == user.id)).all()
                for log in logs:
                    try:
                        label = (log.query or "")[:120]  # etiqueta corta de la búsqueda
                        log_node = f"log_{log.id}"
                        self.add_entity({"id": log_node, "label": label, "type": "log"})
                        self.add_relation(user_node, log_node, "realizó búsqueda")

                        # Intentar extraer emails y urls desde el campo result o query
                        text_blob = f"{log.query or ''} {log.result or ''}"
                        # emails
                        for em in set(EMAIL_RE.findall(text_blob)):
                            em_id = f"email:{em}"
                            self.add_entity({"id": em_id, "label": em, "type": "email"})
                            self.add_relation(log_node, em_id, "mencionado")
                            self.add_relation(user_node, em_id, "vinculado a")
                        # urls
                        for u in set(re.findall(r"https?://[^\s'\"<>]+", text_blob)):
                            parsed = urlparse(u)
                            url_label = parsed.netloc or u
                            url_id = f"url:{u}"
                            domain_id = f"domain:{url_label}"
                            self.add_entity({"id": url_id, "label": url_label, "type": "url"})
                            self.add_relation(log_node, url_id, "mencionado")
                            self.add_relation(user_node, url_id, "vinculado a")
                            # dominio
                            self.add_entity({"id": domain_id, "label": url_label, "type": "domain"})
                            self.add_relation(url_id, domain_id, "pertenece a")

                    except Exception as e:
                        logger.debug(f"No se pudo procesar log {getattr(log, 'id', 'unknown')}: {e}")

                logger.info(f"Grafo construido para usuario '{username}' con {len(self._nodes)} nodos.")
                return True

        except Exception as e:
            logger.exception(f"Error construyendo grafo para {username}: {e}")
            return None

    def _infer_type_from_id(self, id_str: str) -> str:
        """
        Heurística simple para inferir el tipo de entidad a partir del id.
        Por ejemplo: 'email:foo@x' -> 'email', 'domain:example.com' -> 'domain'
        """
        if isinstance(id_str, str) and ":" in id_str:
            t = id_str.split(":", 1)[0].lower()
            mapping = {
                "user": "user",
                "email": "email",
                "domain": "domain",
                "leak": "leak",
                "url": "url",
                "dork": "dork",
                "social": "social",
            }
            return mapping.get(t, "custom")
        # fallback por extensión del string
        if "@" in str(id_str):
            return "email"
        if "." in str(id_str):
            return "domain"
        return "custom"


def build_graph_html_for_person(person_id: int, outpath: str = "data/graph_person.html"):
    net = Network(height="800px", width="100%", bgcolor="#222222", font_color="white", notebook=False)
    with get_session() as session:
        p = session.get(Person, person_id)
        if not p:
            raise ValueError("Person not found")
        # Add person node
        net.add_node(f"person:{p.id}", label=p.name, title=p.notes or "", color="#00aaff", shape="ellipse", size=30)
        # Emails
        for e in p.emails:
            net.add_node(f"email:{e.id}", label=e.address, title=e.leaks_summary or "", color="#ffcc00",
                             shape="dot")
            net.add_edge(f"person:{p.id}", f"email:{e.id}", title="has email")
        # Profiles
        for pr in p.profiles:
            net.add_node(f"profile:{pr.id}", label=f"{pr.platform}:{pr.handle}", title=pr.url, color="#66cc66",
                             shape="box")
            net.add_edge(f"person:{p.id}", f"profile:{pr.id}", title="profile")
        # Optionally, add relations table entries
        rels = session.exec(select(Relation).where(Relation.user_id == p.id)).all() if False else []
        # Save
        net.show(outpath)
    return outpath