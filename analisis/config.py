import sys
import os
from dotenv import load_dotenv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
for ruta in (ROOT_DIR, CURRENT_DIR):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
INSTAGRAM_TARGET = os.getenv("INSTAGRAM_TARGET", "usuario_objetivo")

# Modelos: ahora se leen del .env (con valores por defecto vigentes).
# text-embedding-004 fue dado de baja el 14/01/2026 -> usar gemini-embedding-001.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_MODEL_RESPALDO = os.getenv("GEMINI_MODEL_RESPALDO", "")  # opcional, se usa si el principal sigue saturado
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
if GEMINI_EMBEDDING_MODEL in ("text-embedding-004", "embedding-001", "models/text-embedding-004"):
    print(f"[Config] AVISO: '{GEMINI_EMBEDDING_MODEL}' está dado de baja; se usa gemini-embedding-001. "
          "Actualiza GEMINI_EMBEDDING_MODEL en tu .env.")
    GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

DATOS_DIR = os.path.join(ROOT_DIR, "datos", INSTAGRAM_TARGET)


def crear_carpetas():
    os.makedirs(DATOS_DIR, exist_ok=True)


if __name__ == "__main__":
    crear_carpetas()
    print(f"[Config] Directorio: {DATOS_DIR}")
    print(f"[Config] Embeddings: {GEMINI_EMBEDDING_MODEL} ({EMBEDDING_DIM} dim) | Generación: {GEMINI_MODEL}")