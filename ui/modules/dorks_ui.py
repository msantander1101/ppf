import streamlit as st
import json
from datetime import datetime
from typing import Optional
from utils.logger import logger
from core.database import get_session, SearchLog, User
# Se evita importar add_relation en el ámbito global para que el módulo
# funcione incluso si las dependencias de relaciones no están disponibles.
from modules.search.google_dork import search_dork
from core.config import get_user_setting


def run(username: str, previous_query: Optional[str] = None):
    try:
        from modules.relations.utils import add_relation
    except Exception as e:
        add_relation = None
        import traceback, sys
        logger.warning(f"add_relation no disponible temporalmente: {e}\\n{traceback.format_exc()}")
    st.title("🔎 Dorks — Búsqueda OSINT")
    # Descripción del módulo. Markdown requiere un cuerpo obligatorio a partir de Streamlit 1.30+.
    st.markdown(
        "Este módulo permite ejecutar consultas dork de Google/Bing para descubrir "
        "información sensible o expuesta en la web pública. Introduce tu consulta "
        "y selecciona el motor de búsqueda deseado."
    )

    # Entrada
    dork_query = st.text_input(
        "Dork / consulta:",
        value=previous_query or "",
        placeholder='Ej: site:pastebin.com "contraseña" "gmail.com"',
    )

    # Parámetros
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        engine = st.selectbox(
            "Engine", ["auto", "serpapi", "bing"], index=0,
            help="auto = usa SerpApi si hay clave, si no recurre a Bing"
        )
    with col2:
        max_results = st.number_input("Resultados", min_value=1, max_value=50, value=10)
    with col3:
        use_proxy = st.checkbox("Usar proxy (manual)", value=False)

    proxies = None
    if use_proxy:
        proxy_string = st.text_input("Proxy (http://user:pass@ip:port)", placeholder="http://127.0.0.1:3128")
        if proxy_string:
            proxies = {"http": proxy_string, "https": proxy_string}

    # Ejecutar búsqueda
    if st.button("🚀 Ejecutar búsqueda real"):
        if not dork_query.strip():
            st.warning("Introduce una dork o consulta válida.")
            return

        st.info(f"Ejecutando '{dork_query}' (engine={engine}, max={max_results})")
        with st.spinner("Ejecutando búsqueda..."):
            try:
                # Obtiene la API key de SerpApi para este usuario (si existe) y la pasa a search_dork
                api_key = get_user_setting(username, "serpapi")
                results = search_dork(dork_query, max_results, engine=engine, api_key=api_key, use_proxies=proxies)

                # Guardar resultados
                with get_session() as session:
                    user = session.query(User).filter(User.username == username).first()
                    if not user:
                        st.error("Usuario no encontrado en la base de datos.")
                        return

                    log_entry = SearchLog(
                        query=dork_query,
                        result=json.dumps(results, ensure_ascii=False),
                        user_id=user.id,
                        type="dork",
                        created_at=datetime.utcnow(),
                    )
                    session.add(log_entry)
                    session.commit()
                    logger.info(f"Búsqueda guardada para {username}: {dork_query}")

                # Crear relaciones
                if add_relation:
                    add_relation(username, f"user:{username}", f"dork:{dork_query}", "realizó búsqueda")

                    for r in results:
                        link = r.get("link", "")
                        domain = r.get("domain", "")
                        title = r.get("title", "")
                        emails = r.get("emails", [])

                        if link:
                            add_relation(username, f"dork:{dork_query}", f"url:{link}", "devuelve")
                        if domain:
                            add_relation(username, f"url:{link}", f"domain:{domain}", "pertenece a")
                        if link and title:
                            add_relation(username, f"url:{link}", f"meta:title:{title[:80]}", "título")
                        for em in emails:
                            add_relation(username, f"url:{link}", f"email:{em}", "menciona correo")
                            add_relation(username, f"email:{em}", f"domain:{domain}", "pertenece a")

                # Mostrar resultados
                st.success(f"✅ Búsqueda completada — {len(results)} resultados.")
                st.markdown("### Resultados (primeros items)")
                if not results:
                    st.info("No se encontraron resultados.")
                else:
                    for idx, item in enumerate(results[:max_results]):
                        st.markdown(f"**{idx+1}. {item.get('title','(sin título)')}**")
                        st.write(f"- URL: {item.get('link','')}")
                        st.write(f"- Dominio: {item.get('domain','')}")
                        snippet = item.get("snippet", "")
                        if snippet:
                            st.write(f"- Snippet: {snippet}")
                        emails = item.get("emails", [])
                        if emails:
                            st.write(f"- Correos detectados: {', '.join(emails)}")
                        st.markdown("---")

                    st.info("Ve al módulo **Grafo** y pulsa 'Construir grafo' para visualizar las relaciones.")
            except Exception as e:
                logger.exception(f"Error ejecutando búsqueda dork '{dork_query}': {e}")
                st.error(f"Ocurrió un error al ejecutar la búsqueda: {e}")
