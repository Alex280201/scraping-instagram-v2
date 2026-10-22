"""Pipeline de análisis: embeddings (Gemini) -> perfil Big Five.
Antes, el scraping debe haber generado datos_completos.json (python scraper.py).
Uso:  python analisis/main.py            (reutiliza embeddings si existen)
      python analisis/main.py --forzar   (regenera embeddings)
"""
import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
for ruta in (os.path.dirname(CURRENT_DIR), CURRENT_DIR):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

from embeddings import procesar_y_guardar_embeddings
from bigfive import generar_perfil_bigfive

if __name__ == "__main__":
    procesar_y_guardar_embeddings(forzar="--forzar" in sys.argv)
    generar_perfil_bigfive()
