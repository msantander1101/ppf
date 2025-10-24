import streamlit as st
from core.auth import login_user, register_user, get_current_user
from utils.logger import logger


def run():
    st.set_page_config(page_title="OSINT Suite — Login", page_icon="🔐", layout="centered")
    st.title("🔐 OSINT Suite — Inicio de sesión")

    # Si ya hay sesión, redirigimos directamente
    user = get_current_user()
    if user:
        st.info(f"✅ Sesión activa como **{user['username']}**")
        st.switch_page("pages/1_Dashboard.py")
        st.stop()

    tab_login, tab_register = st.tabs(["🔑 Iniciar sesión", "🧾 Registrarse"])

    # ------------------------------
    # TAB: LOGIN
    # ------------------------------
    with tab_login:
        st.subheader("Accede a tu cuenta")
        username = st.text_input("👤 Usuario", key="login_username")
        password = st.text_input("🔒 Contraseña", type="password", key="login_password")

        if st.button("🚀 Iniciar sesión", key="btn_login"):
            if not username or not password:
                st.warning("Por favor, completa todos los campos.")
            else:
                if login_user(username, password):
                    st.success(f"✅ Bienvenido, {username}")
                    st.switch_page("pages/1_Dashboard.py")
                    st.stop()
                else:
                    st.error("❌ Credenciales incorrectas o usuario inexistente.")

    # ------------------------------
    # TAB: REGISTRO
    # ------------------------------
    with tab_register:
        st.subheader("Crear nueva cuenta")
        new_user = st.text_input("👤 Nuevo usuario", key="register_username")
        new_pass = st.text_input("🔒 Contraseña", type="password", key="register_password")
        confirm_pass = st.text_input("🔒 Confirmar contraseña", type="password", key="register_confirm")

        if st.button("🧾 Registrarme", key="btn_register"):
            if not new_user or not new_pass:
                st.warning("Debes completar todos los campos.")
            elif new_pass != confirm_pass:
                st.error("Las contraseñas no coinciden.")
            else:
                if register_user(new_user, new_pass):
                    st.success("✅ Registro exitoso. Ahora puedes iniciar sesión.")
                else:
                    st.error("⚠️ El usuario ya existe o ocurrió un error durante el registro.")


if __name__ == "__main__":
    run()
