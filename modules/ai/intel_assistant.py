"""
Análisis de resultados OSINT mediante IA (o resumen lógico).
Compatible con person_ui y búsqueda libre.
"""

from utils.logger import logger


def analyze_results_with_ai(results: list) -> str:
    """
    Recibe una lista de resultados OSINT y devuelve un resumen textual.
    Puede adaptarse para usar OpenAI si hay API configurada.
    """
    if not results:
        return "No hay resultados para analizar."

    try:
        counts = {}
        for r in results:
            src = r.get("source", "Desconocido")
            counts[src] = counts.get(src, 0) + 1

        resumen = ["**Resumen general:**"]
        for s, c in counts.items():
            resumen.append(f"- {s}: {c} hallazgos")

        breaches = []
        for r in results:
            if r.get("breaches"):
                breaches.extend(r["breaches"])

        if breaches:
            resumen.append(f"\n**Brechas encontradas:** {len(breaches)}")
            for b in breaches[:10]:
                resumen.append(f"- {b.get('Name')} ({b.get('BreachDate')})")

        return "\n".join(resumen)

    except Exception as e:
        logger.error(f"[AI] Error analizando resultados: {e}")
        return f"Error analizando resultados con IA: {e}"
