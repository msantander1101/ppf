def run(query: str):
    """
    Genera dorks simples de Google a partir de un nombre.
    """
    dorks = [
        f'"{query}" site:linkedin.com',
        f'"{query}" site:twitter.com',
        f'"{query}" filetype:pdf',
    ]
    urls = [f"https://www.google.com/search?q={d.replace(' ', '+')}" for d in dorks]
    return {"query": query, "dorks": dorks, "urls": urls}