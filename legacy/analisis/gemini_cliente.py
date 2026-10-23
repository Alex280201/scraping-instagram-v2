import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
for ruta in (ROOT_DIR, CURRENT_DIR):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

from google import genai
from config import GEMINI_API_KEY


def obtener_cliente():
    """Inicializa y retorna el cliente oficial de Gemini API."""
    if not GEMINI_API_KEY:
        raise ValueError("[Gemini] No se encontró GEMINI_API_KEY en el archivo .env")
    return genai.Client(api_key=GEMINI_API_KEY)


if __name__ == "__main__":
    try:
        obtener_cliente()
        print("[Gemini Cliente] Inicialización correcta.")
    except Exception as e:
        print(f"[Gemini Cliente] Error: {e}")
