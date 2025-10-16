import streamlit as st

def run(username: str):
    """
    Módulo de enriquecimiento de datos.

    Actualmente no utiliza el parámetro `username`, pero se acepta para mantener
    compatibilidad con la llamada en el dashboard. En el futuro podría
    personalizarse según el usuario.
    """
    st.header("💡 Enriquecimiento de Datos")
    st.info("Aquí podrás ampliar información sobre correos, usuarios y dominios.")
