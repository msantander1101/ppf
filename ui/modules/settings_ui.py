# ui/modules/settings_ui.py
"""
Interfaz para gestionar las claves API y configuraciones de usuario.
Cada usuario puede registrar sus propias claves (SerpAPI, Shodan, etc.)
y preferencias de uso.
"""

import streamlit as st
from core.config import get_user_setting, set_user_setting, delete_user_setting

SETTINGS_KEYS = {
    "serpapi": "🔍 SerpAPI Key",
    "google_api_key": "🌐 Google API Key",
    "google_cse_cx": "🔎 Google CSE CX",
    "shodan_api_key": "🛰️ Shodan API Key",
    "virustotal_api_key": "🧬 VirusTotal API Key",
    "hibp_api_key": "💀 Have I Been Pwned API Key",
}


def run(username: str):
    st.subheader("⚙️ Configuración de Usuario")
    st.caption("Gestiona tus claves API y preferencias personales de búsqueda.")

    for key_id, label in SETTINGS_KEYS.items():
        with st.expander(label):
            current_value = get_user_setting(username, key_id) or ""
            new_value = st.text_input(
                f"{label}",
                value=current_value,
                type="password",
                key=f"input_{key_id}",
            )

            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button(f"💾 Guardar {label}", key=f"save_{key_id}"):
                    if new_value.strip():
                        set_user_setting(username, key_id, new_value.strip())
                        st.success(f"✅ Clave {label} guardada correctamente.")
                    else:
                        st.warning("Introduce un valor válido antes de guardar.")

            with col2:
                if st.button(f"🗑️ Eliminar {label}", key=f"delete_{key_id}"):
                    delete_user_setting(username, key_id)
                    st.info(f"🔒 Clave {label} eliminada.")
