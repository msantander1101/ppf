# core/auth.py
"""
Módulo de autenticación y gestión de usuarios.
Incluye registro, login, hashing de contraseñas y persistencia de sesión segura.
"""

from core.database import get_session
from core.entities import User
from utils.logger import logger
from sqlmodel import select
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import streamlit as st


# ======================================================
# 🔐 REGISTRO DE USUARIO
# ======================================================
def register_user(username: str, password: str) -> bool:
    """Registra un nuevo usuario en la base de datos."""
    try:
        with get_session() as session:
            # Verificar si ya existe
            existing = session.exec(select(User).where(User.username == username)).first()
            if existing:
                logger.warning(f"Intento de registrar usuario existente: {username}")
                return False

            # Crear nuevo usuario
            new_user = User(
                username=username,
                password_hash=generate_password_hash(password),
                created_at=datetime.utcnow(),
            )
            session.add(new_user)
            session.commit()

            logger.info(f"Usuario registrado correctamente: {username}")
            return True

    except Exception as e:
        logger.exception(f"Error registrando usuario '{username}': {e}")
        return False


# ======================================================
# 🔑 LOGIN DE USUARIO
# ======================================================
def login_user(username: str, password: str) -> bool:
    """Valida las credenciales del usuario y guarda los datos en sesión Streamlit."""
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()

            if not user:
                logger.warning(f"Intento de login con usuario inexistente: {username}")
                return False

            if not check_password_hash(user.password_hash, password):
                logger.warning(f"Contraseña incorrecta para usuario: {username}")
                return False

            # 💾 Guardar datos del usuario en la sesión (solo valores primitivos)
            st.session_state["user"] = {
                "id": user.id,
                "username": user.username,
                "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }

            logger.info(f"Login exitoso: {username}")
            return True

    except Exception as e:
        logger.exception(f"Error en login de usuario '{username}': {e}")
        return False


# ======================================================
# 🚪 LOGOUT DE USUARIO
# ======================================================
def logout_user():
    """Cierra la sesión actual del usuario."""
    if "user" in st.session_state:
        username = st.session_state["user"]["username"]
        del st.session_state["user"]
        logger.info(f"Usuario '{username}' cerró sesión correctamente.")
    else:
        logger.warning("Intento de logout sin usuario activo.")


# ======================================================
# 👤 OBTENER USUARIO ACTUAL
# ======================================================
def get_current_user():
    """Devuelve el usuario actual desde la sesión Streamlit."""
    return st.session_state.get("user", None)
