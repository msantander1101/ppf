import streamlit as st
from core.config import get_user_setting, store_user_setting
from utils.logger import logger
import os

def run(username: str):
    """
    Interfaz de configuración del usuario:
    permite gestionar las claves API y otros ajustes personales.
    """

    st.header("⚙️ Configuración del Usuario")
    st.write(f"Usuario activo: **{username}**")

    st.markdown("---")

    # Aviso de seguridad si no hay clave de cifrado
    if not os.environ.get("APP_ENCRYPTION_KEY"):
        st.warning("⚠️ Las claves se almacenarán en texto plano. "
                   "Configura la variable de entorno `APP_ENCRYPTION_KEY` para habilitar cifrado AES.")

    # Diccionario de claves admitidas
    api_keys = {
        "serpapi": "🔍 SerpAPI",
        "hunter": "📧 Hunter.io",
        "hibp": "💀 Have I Been Pwned",
        "whoisxml": "🌐 WhoisXML API",
        "shodan": "🕸️ Shodan",
        "virustotal": "🧬 VirusTotal"
    }

    st.markdown("### 🔑 Claves API")
    st.info("Introduce tus claves API personales. Se guardarán vinculadas a tu usuario y se usarán automáticamente por los módulos correspondientes.")

    # Mostrar un formulario por clave
    for key_id, label in api_keys.items():
        with st.expander(label, expanded=False):
            try:
                current_value = get_user_setting(username, key_id)
            except Exception as e:
                logger.warning(f"No se pudo obtener la clave {key_id}: {e}")
                current_value = ""

            new_value = st.text_input(f"{label} Key", current_value or "", type="password", key=f"input_{key_id}")
            col1, col2 = st.columns([1, 1])
            if col1.button(f"Guardar {label}", key=f"save_{key_id}"):
                if new_value.strip():
                    store_user_setting(username, key_id, new_value.strip())
                    st.success(f"✅ Clave {label} guardada correctamente.")
                else:
                    st.warning(f"Introduce una clave válida para {label}.")
            if col2.button(f"Eliminar {label}", key=f"delete_{key_id}"):
                store_user_setting(username, key_id, "")
                st.info(f"🔒 Clave {label} eliminada.")

    st.markdown("---")

    # Otros ajustes personales
    st.markdown("### ⚙️ Preferencias adicionales")
    st.text_input("🌐 Proxy (opcional)", placeholder="http://usuario:contraseña@host:puerto")
    st.checkbox("Activar modo debug", value=False, help="Muestra mensajes de depuración adicionales en la interfaz.")

    st.markdown("---")
    st.caption("🧩 OSINT Suite — Configuración del usuario")


# Permite ejecutar el módulo directamente para pruebas
if __name__ == "__main__":
    st.session_state["username"] = "demo"
    run("demo")
