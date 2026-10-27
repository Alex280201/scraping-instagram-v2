import sys
import os
from dotenv import load_dotenv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
for ruta in (ROOT_DIR, CURRENT_DIR):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

from corridas import buscar_corrida  # noqa: E402

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
INSTAGRAM_TARGET = os.getenv("INSTAGRAM_TARGET", "usuario_objetivo").strip().lstrip("@").lower()
CORRIDA = (os.getenv("CORRIDA") or "").strip() or None   # None = el scraping más reciente del perfil

# Modelos: se leen del .env (con valores por defecto vigentes).
# text-embedding-004 fue dado de baja el 14/01/2026 -> usar gemini-embedding-001.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_MODEL_RESPALDO = os.getenv("GEMINI_MODEL_RESPALDO", "")  # opcional, se usa si el principal sigue saturado
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
if GEMINI_EMBEDDING_MODEL in ("text-embedding-004", "embedding-001", "models/text-embedding-004"):
    print(f"[Config] AVISO: '{GEMINI_EMBEDDING_MODEL}' está dado de baja; se usa gemini-embedding-001. "
          "Actualiza GEMINI_EMBEDDING_MODEL en tu .env.")
    GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"

# Carpeta del scraping que se analiza: datos/<usuario>/<fecha>/
_carpeta = buscar_corrida(INSTAGRAM_TARGET, CORRIDA)
HAY_CORRIDA = _carpeta is not None
DATOS_DIR = _carpeta or os.path.join(ROOT_DIR, "datos", INSTAGRAM_TARGET, "(sin_scraping)")


def crear_carpetas():
    if not HAY_CORRIDA:
        raise SystemExit(f"No hay ningún scraping de '{INSTAGRAM_TARGET}'. "
                         f"Ejecuta primero:  python scraper.py {INSTAGRAM_TARGET}")
    os.makedirs(DATOS_DIR, exist_ok=True)
