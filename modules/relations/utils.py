# modules/relations/utils.py
from core.database import get_session
from core.entities import Relation
from utils.logger import logger
from sqlmodel import select

def add_relation(username: str, source_id: str, target_id: str, relation_label: str):
    try:
        with get_session() as session:
            r = Relation(source_id=source_id, target_id=target_id, relation=relation_label)
            session.add(r)
            session.commit()
            logger.info(f"[relations] add_relation by {username}: {source_id} -> {target_id} ({relation_label})")
            return r
    except Exception as e:
        logger.exception(f"[relations] add_relation error: {e}")
        return None

def delete_relation(username: str, relation_id: int):
    try:
        with get_session() as session:
            r = session.get(Relation, int(relation_id))
            if not r:
                logger.warning(f"[relations] delete_relation: id {relation_id} not found")
                return False
            session.delete(r)
            session.commit()
            logger.info(f"[relations] delete_relation by {username}: id {relation_id}")
            return True
    except Exception as e:
        logger.exception(f"[relations] delete_relation error: {e}")
        return False

def update_relation(username: str, relation_id: int, new_label: str, new_target: str = None):
    try:
        with get_session() as session:
            r = session.get(Relation, int(relation_id))
            if not r:
                logger.warning(f"[relations] update_relation: id {relation_id} not found")
                return False
            r.relation = new_label
            if new_target:
                r.target_id = new_target
            session.add(r)
            session.commit()
            logger.info(f"[relations] update_relation by {username}: id {relation_id} -> {new_label}, target={new_target}")
            return True
    except Exception as e:
        logger.exception(f"[relations] update_relation error: {e}")
        return False

def list_relations_by_source(source_id: str):
    try:
        with get_session() as session:
            q = session.exec(select(Relation).where(Relation.source_id == source_id)).all()
            return q
    except Exception as e:
        logger.exception(f"[relations] list_relations_by_source error: {e}")
        return []
