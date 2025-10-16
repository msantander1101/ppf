import requests

def run(email: str, api_key: str = None):
    """
    Consulta básica a HaveIBeenPwned API (requiere API key)
    """
    if not api_key:
        return {"error": "Falta la API key"}
    headers = {"hibp-api-key": api_key, "user-agent": "osint-suite"}
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return {"email": email, "breaches": r.json()}
    elif r.status_code == 404:
        return {"email": email, "breaches": []}
    else:
        return {"error": f"Error {r.status_code}: {r.text}"}
