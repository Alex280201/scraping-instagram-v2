"""Punto de entrada del proyecto.

  python main.py sesion                      Guardar la sesión de Instagram (solo la primera vez o si caduca)
  python main.py scrape   [usuario]          Scraping -> datos/<usuario>/<fecha>/raw/
  python main.py analizar [usuario]          Embeddings (Gemini) + perfil Big Five -> datos/<usuario>/
  python main.py todo     [usuario]          scrape + analizar

Si no indicas usuario se usa INSTAGRAM_TARGET del .env.
Opciones:  --si (sin pedir confirmación)  --sin-imagenes  --conexiones  --limite N  --forzar  --corrida <nombre>
"""
import argparse

from src.config import resolver_usuario


def crear_parser():
    ap = argparse.ArgumentParser(description="Scraping de Instagram -> embeddings -> perfil Big Five")
    sub = ap.add_subparsers(dest="comando", required=True)

    sub.add_parser("sesion", help="guardar la sesión de Instagram")
    for nombre, ayuda in (("scrape", "extraer publicaciones"), ("analizar", "embeddings + Big Five"),
                          ("todo", "scrape + analizar")):
        p = sub.add_parser(nombre, help=ayuda)
        p.add_argument("usuario", nargs="?", help="perfil (por defecto INSTAGRAM_TARGET del .env)")
        if nombre != "analizar":
            p.add_argument("--si", action="store_true", help="no pedir confirmación")
            p.add_argument("--sin-imagenes", action="store_true", help="no descargar las imágenes")
            p.add_argument("--conexiones", action="store_true", help="extraer también seguidores y seguidos")
            p.add_argument("--limite", type=int, help="procesar solo N publicaciones (pruebas)")
        if nombre != "scrape":
            p.add_argument("--forzar", action="store_true", help="regenerar los embeddings")
        p.add_argument("--corrida", help="carpeta de corrida (fecha_hora) a usar")
    return ap


def main(argv=None):
    args = crear_parser().parse_args(argv)

    if args.comando == "sesion":
        from src.scraping.guardar_sesion import guardar_sesion
        return guardar_sesion()

    usuario = resolver_usuario(args.usuario)

    if args.comando in ("scrape", "todo"):
        from src.scraping.scraper import scrapear
        scrapear(usuario, guardar_imagenes=not args.sin_imagenes, con_conexiones=args.conexiones,
                 confirmar=not args.si, limite=args.limite)

    if args.comando in ("analizar", "todo"):
        from src.analisis.bigfive import generar_perfil_bigfive
        generar_perfil_bigfive(usuario, forzar=getattr(args, "forzar", False), corrida=getattr(args, "corrida", None))


if __name__ == "__main__":
    main()
