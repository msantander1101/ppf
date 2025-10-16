import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from core.auth import register_user, login_user
from core.database import init_db
from utils.logger import logger

st.set_page_config(page_title="Login - OSINT Suite", page_icon="🔐")

# --- Inicialización ---
try:
    init_db()
except Exception as e:
    st.error(f"Error inicializando base de datos: {e}")
    logger.exception("Error inicializando DB al arrancar login.py")

# --- Redirección si ya hay sesión ---
if st.session_state.get("logged_in"):
    logger.debug(f"Usuario ya logueado: {st.session_state.username}, redirigiendo al dashboard.")
    st.switch_page("ui/dashboard.py")  # 👈 redirige al dashboard directamente

# --- Estado de sesión ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None

st.title("🔐 OSINT Suite - Login / Registro")

tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrar Usuario"])

# --- LOGIN ---
with tab1:
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if not username.strip() or not password.strip():
            st.warning("Por favor, completa los campos.")
            logger.warning("Campos de login vacíos.")
        else:
            try:
                if login_user(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.success(f"Bienvenido, {username}")
                    logger.info(f"Usuario '{username}' inició sesión correctamente.")
                    st.switch_page("pages/1_Dashboard.py")  # 👈 redirige al dashboard tras login
                else:
                    st.error("Usuario o contraseña incorrectos.")
                    logger.warning(f"Intento de login fallido: {username}")
            except Exception as e:
                st.error("Error durante el login. Revisa los logs.")
                logger.exception(f"Excepción durante login: {e}")

# --- REGISTRO ---
with tab2:
    new_user = st.text_input("Nuevo usuario")
    new_pass = st.text_input("Nueva contraseña", type="password")
    if st.button("Registrar"):
        if not new_user.strip() or not new_pass.strip():
            st.warning("Por favor, completa ambos campos.")
        else:
            try:
                if register_user(new_user, new_pass):
                    st.success("Usuario registrado correctamente.")
                else:
                    st.warning("Ese usuario ya existe.")
            except Exception as e:
                st.error("Error durante el registro.")
                logger.exception(f"Error registrando usuario: {e}")
