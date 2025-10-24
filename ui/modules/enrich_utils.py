# ui/modules/enrich_utils.py
import re
from urllib.parse import urlparse
from core import enrichment as core_enrichment

SOCIAL_HOSTS = ("twitter.com", "x.com", "linkedin.com", "instagram.com", "facebook.com", "github.com", "gitlab.com")

def smart_enrich(username: str, link_or_text: str):
    # 1) ¿Email?
    m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", link_or_text or "")
    if m:
        return core_enrichment.enrich_email(username, m.group(0))

    # 2) ¿URL?
    if isinstance(link_or_text, str) and link_or_text.startswith("http"):
        host = urlparse(link_or_text).netloc.lower()
        if any(h in host for h in SOCIAL_HOSTS):
            # enriquecer persona por username (último segmento)
            handle = link_or_text.rstrip("/").split("/")[-1]
            return core_enrichment.enrich_person(username, {"username": handle})
        # dominio genérico
        return core_enrichment.enrich_domain(username, host)

    # 3) fallback: persona por nombre
    return core_enrichment.enrich_person(username, {"name": link_or_text})
