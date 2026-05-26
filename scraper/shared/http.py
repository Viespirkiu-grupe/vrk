import requests


def fetch_text(url: str, timeout_seconds: int = 45) -> str:
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    return response.text
