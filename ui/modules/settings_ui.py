import streamlit as st
from core.config import store_user_setting, get_user_setting, delete_user_setting
from utils.logger import logger

def run(username: str):
    st.title("⚙️ Configuración — API Keys")
    st.markdown("Gestiona tus claves API. Se almacenan cifradas si APP_ENCRYPTION_KEY está configurada.")

    services = ["serpapi", "shodan", "hibp", "whoisxmlapi", "other"]

    st.subheader("➕ Añadir / actualizar clave")
    with st.form("add_api_form", clear_on_submit=False):
        svc = st.selectbox("Servicio", services, index=0)
        label = st.text_input("Etiqueta (solo si escoges 'other')", value="")
        key_val = st.text_input("Clave API / Token", value="", type="password")
        save = st.form_submit_button("💾 Guardar clave")
        if save:
            if not key_val.strip():
                st.warning("Introduce una clave válida.")
            else:
                k = svc if svc != "other" else (label.strip() or "other")
                ok = store_user_setting(username, k, key_val.strip())
                if ok:
                    st.success(f"Clave guardada para '{k}'.")
                else:
                    st.error("No se pudo guardar la clave. Revisa los logs.")

    st.divider()

    # Google CSE específico
    st.markdown("### Integración Google CSE (Custom Search)")
    st.info("Si vas a usar Google Custom Search, añade tu `google_api_key` y `google_cx` aquí.")
    with st.form("google_cse_form", clear_on_submit=False):
        g_api = st.text_input("Google API Key (google_api_key)", type="password", placeholder="AIza...")
        g_cx = st.text_input("Google CX (google_cx)", placeholder="0123456789:abcdefg")
        save_google = st.form_submit_button("💾 Guardar credenciales Google")
        if save_google:
            if not g_api.strip() or not g_cx.strip():
                st.warning("Introduce tanto API Key como CX.")
            else:
                ok1 = store_user_setting(username, "google_api_key", g_api.strip())
                ok2 = store_user_setting(username, "google_cx", g_cx.strip())
                if ok1 and ok2:
                    st.success("Credenciales Google guardadas correctamente.")
                else:
                    st.error("No se pudieron guardar las credenciales. Revisa logs.")

    if st.button("🔎 Probar Google CSE"):
        api_key = get_user_setting(username, "google_api_key")
        cx = get_user_setting(username, "google_cx")
        if not api_key or not cx:
            st.error("Faltan google_api_key o google_cx en tu configuración.")
        else:
            try:
                from modules.search.google_cse import search_google_cse
                test_results = search_google_cse("site:github.com python", api_key=api_key, cx=cx, num=1)
                if test_results:
                    st.success("✅ Google CSE responde correctamente. Ejemplo:")
                    st.write(test_results[0])
                else:
                    st.warning("La consulta devolvió 0 resultados (pero la API respondió).")
            except Exception as e:
                st.error(f"Error al probar Google CSE: {e}")
                logger.exception("Error probando Google CSE", exc_info=True)

    st.divider()
    st.subheader("🔒 Claves guardadas")

    known = services + ["google_api_key", "google_cx", "custom"]
    any_shown = False
    for svc in known:
        val = get_user_setting(username, svc)
        if val:
            any_shown = True
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{svc}** — `{val[:6]}...`")
            with col2:
                if st.button(f"🔑 Mostrar {svc}", key=f"show_{svc}"):
                    st.info(f"Valor (parcial): {val[:400]}")
            with col3:
                if st.button(f"🗑️ Eliminar {svc}", key=f"del_{svc}"):
                    if delete_user_setting(username, svc):
                        st.success(f"Clave '{svc}' eliminada.")
                        st.rerun()
                    else:
                        st.error("No se pudo eliminar la clave.")

    if not any_shown:
        st.info("No se han guardado claves aún. Usa el formulario anterior para añadirlas.")
