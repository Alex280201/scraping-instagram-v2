"""Pipeline de análisis: embeddings (Gemini) -> perfil Big Five -> documento Word + gráfico.

Antes, el scraping debe haber generado datos:  python scraper.py <usuario>

Uso:
    python analisis/main.py                       (perfil de INSTAGRAM_TARGET, scraping más reciente)
    python analisis/main.py otro_usuario
    python analisis/main.py usuario --corrida 2026-10-22_1530    (elegir un scraping concreto)
    python analisis/main.py --forzar              (regenera embeddings)
"""
import argparse
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
for ruta in (os.path.dirname(CURRENT_DIR), CURRENT_DIR):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("usuario", nargs="?")
    ap.add_argument("--corrida")
    ap.add_argument("--forzar", action="store_true")
    args = ap.parse_args(argv)

    # Deben definirse ANTES de importar config (que los lee al cargarse)
    if args.usuario:
        os.environ["INSTAGRAM_TARGET"] = args.usuario
    if args.corrida:
        os.environ["CORRIDA"] = args.corrida

    from config import DATOS_DIR, INSTAGRAM_TARGET, crear_carpetas
    from embeddings import procesar_y_guardar_embeddings
    from bigfive import generar_perfil_bigfive
    from reporte import generar_reporte

    crear_carpetas()
    print(f"[Análisis] Perfil @{INSTAGRAM_TARGET} | scraping: {os.path.basename(DATOS_DIR)}")
    procesar_y_guardar_embeddings(forzar=args.forzar)
    perfil = generar_perfil_bigfive()
    generar_reporte(perfil)


if __name__ == "__main__":
    main()
