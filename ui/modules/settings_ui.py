# ui/modules/settings_ui.py
"""
Interfaz de configuración del usuario:
Permite gestionar las claves API y otros ajustes personales.
Compatible con core/config.py (get/set/delete_user_setting).
"""

import streamlit as st
import os
from core.config import get_user_setting, set_user_setting, delete_user_setting, list_user_settings
from utils.logger import logger


def run(username: str):
    """
    Interfaz visual para gestionar ajustes personales y claves API del usuario.
    """
    st.header("⚙️ Configuración del Usuario")
    st.write(f"Usuario activo: **{username}**")

    st.markdown("---")

    # ==========================================================
    # 🛡️ Aviso de seguridad
    # ==========================================================
    if not os.environ.get("APP_ENCRYPTION_KEY"):
        st.warning(
            "⚠️ Las claves se almacenarán en texto plano. "
            "Configura la variable de entorno `APP_ENCRYPTION_KEY` para habilitar cifrado AES."
        )

    # ==========================================================
    # 🔑 CLAVES API
    # ==========================================================
    st.markdown("### 🔑 Claves API y Servicios Externos")
    st.info(
        "Introduce tus claves API personales. "
        "Se guardarán vinculadas a tu usuario y se usarán automáticamente "
        "en los módulos de búsqueda, IA y análisis OSINT."
    )

    api_keys = {
        "serpapi": "🔍 SerpAPI (Google Search)",
        "google_api_key": "🌐 Google Custom Search API",
        "google_cse_cx": "🧩 Google CSE CX ID",
        "hibp": "💀 Have I Been Pwned",
        "hunter": "📧 Hunter.io",
        "whoisxml": "🌍 WhoisXML API",
        "shodan": "🕸️ Shodan",
        "virustotal": "🧬 VirusTotal",
        "openai_api_key": "🧠 OpenAI / GPT API Key",
    }

    # Mostrar formulario dinámico
    for key_id, label in api_keys.items():
        with st.expander(label, expanded=False):
            try:
                current_value = get_user_setting(username, key_id)
            except Exception as e:
                logger.warning(f"[settings_ui] No se pudo obtener {key_id}: {e}")
                current_value = ""

            new_value = st.text_input(
                f"{label}", current_value or "", type="password", key=f"input_{key_id}"
            )

            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button(f"💾 Guardar", key=f"save_{key_id}"):
                    if new_value.strip():
                        set_user_setting(username, key_id, new_value.strip())
                        st.success(f"✅ Clave '{label}' guardada correctamente.")
                    else:
                        st.warning("⚠️ Introduce una clave válida antes de guardar.")
            with col2:
                if st.button(f"🗑️ Eliminar", key=f"delete_{key_id}"):
                    delete_user_setting(username, key_id)
                    st.info(f"🔒 Clave '{label}' eliminada correctamente.")
                    st.rerun()

    # ==========================================================
    # ⚙️ PREFERENCIAS ADICIONALES
    # ==========================================================
    st.markdown("---")
    st.markdown("### ⚙️ Preferencias adicionales")

    proxy_value = get_user_setting(username, "proxy") or ""
    proxy = st.text_input("🌐 Proxy (opcional)", proxy_value, placeholder="http://usuario:contraseña@host:puerto")

    debug_mode = st.checkbox(
        "🪲 Activar modo debug",
        value=bool(get_user_setting(username, "debug") == "true"),
        help="Muestra mensajes de depuración adicionales en la interfaz."
    )

    if st.button("💾 Guardar preferencias"):
        set_user_setting(username, "proxy", proxy.strip())
        set_user_setting(username, "debug", "true" if debug_mode else "false")
        st.success("✅ Preferencias guardadas correctamente.")

    # ==========================================================
    # 📜 VISTA DE CONFIGURACIONES GUARDADAS
    # ==========================================================
    st.markdown("---")
    st.markdown("### 📜 Configuraciones almacenadas")

    with st.expander("🔍 Ver todas las claves guardadas"):
        settings = list_user_settings(username)
        if not settings:
            st.info("No hay configuraciones guardadas todavía.")
        else:
            for key, value in settings.items():
                hidden_value = "*" * len(value) if value else ""
                st.write(f"- **{key}** → {hidden_value}")

    st.markdown("---")
    st.caption("🧩 OSINT Suite — Módulo de Configuración del Usuario")


# ==========================================================
# 🔧 MODO DE PRUEBAS LOCAL
# ==========================================================
if __name__ == "__main__":
    st.session_state["username"] = "demo"
    run("demo")
