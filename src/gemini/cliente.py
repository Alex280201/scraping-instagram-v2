"""Cliente de la API de Gemini (usa GEMINI_API_KEY del .env)."""
from google import genai

from src.config import GEMINI_API_KEY


def obtener_cliente():
    if not GEMINI_API_KEY:
        raise SystemExit("[Gemini] No se encontró GEMINI_API_KEY en el archivo .env")
    return genai.Client(api_key=GEMINI_API_KEY)
