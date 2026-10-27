"""Punto de entrada del proyecto.

  python main.py sesion                      Guardar la sesión de Instagram (solo la primera vez o si caduca)
  python main.py scrape   [usuario]          Scraping -> datos/<usuario>/raw/
  python main.py seguidores [usuario]        Lista de seguidores (usuario, nombre, foto) -> datos/<usuario>/raw/
  python main.py contadores [usuario]        Seguidos/seguidores de cada seguidor de la lista -> raw/seguidores_contadores.json
  python main.py excel [usuario]             Excel de seguidores (foto, nombre, seguidos, seguidores, 1er dígito)
  python main.py benford [usuario]           Ley de Benford + chi-cuadrada + MAD sobre los seguidores de los seguidores
  python main.py informe [usuario]           Informe final (datos del perfil + Benford + Big Five interactivo) -> resultados/informe.html
  python main.py completo [usuario]          PRUEBA GLOBAL: publicaciones → seguidores → contadores → Benford → Excel → Big Five → informe
  python main.py analizar [usuario]          Embeddings (Gemini) + perfil Big Five -> datos/<usuario>/
  python main.py todo     [usuario]          scrape + analizar

Si no indicas usuario se usa INSTAGRAM_TARGET del .env.
Opciones:  --si (sin pedir confirmación)  --sin-imagenes  --conexiones  --limite N  --forzar
           seguidores: --si  --sin-fotos  --limite N  --reiniciar (ignora el checkpoint)
"""
import argparse

from src.config import resolver_usuario


def crear_parser():
    ap = argparse.ArgumentParser(description="Scraping de Instagram -> embeddings -> perfil Big Five")
    sub = ap.add_subparsers(dest="comando", required=True)

    sub.add_parser("sesion", help="guardar la sesión de Instagram")

    seg = sub.add_parser("seguidores", help="extraer la lista de seguidores (usuario, nombre, foto)")
    seg.add_argument("usuario", nargs="?", help="perfil (por defecto INSTAGRAM_TARGET del .env)")
    seg.add_argument("--si", action="store_true", help="no pedir confirmación")
    seg.add_argument("--sin-fotos", action="store_true", help="no descargar las fotos de perfil")
    seg.add_argument("--limite", type=int, help="capturar solo N seguidores (pruebas)")
    seg.add_argument("--reiniciar", action="store_true", help="ignorar el checkpoint y empezar de cero")
    con = sub.add_parser("contadores", help="seguidos y seguidores de cada seguidor de la lista")
    con.add_argument("usuario", nargs="?", help="perfil (por defecto INSTAGRAM_TARGET del .env)")
    con.add_argument("--si", action="store_true", help="no pedir confirmación")
    con.add_argument("--workers", type=int, default=3, help="perfiles en paralelo (por defecto 3, máximo 6)")
    con.add_argument("--limite", type=int, help="procesar solo N perfiles pendientes (pruebas)")
    con.add_argument("--ver", action="store_true", help="mostrar el navegador (por defecto va oculto)")
    con.add_argument("--reiniciar", action="store_true", help="ignorar lo ya guardado y empezar de cero")

    bf = sub.add_parser("benford", help="Ley de Benford (chi-cuadrada y MAD) con veredicto humano/posible bot/bot")
    bf.add_argument("usuario", nargs="?", help="perfil (por defecto INSTAGRAM_TARGET del .env)")
    bf.add_argument("--minimo", type=int, default=30,
                    help="datos válidos mínimos para dar veredicto (por defecto 30; con menos de 110 el valor p se "
                         "calcula por simulación)")

    bf.add_argument("--sin-grafica", action="store_true", help="no generar benford.png / benford.html")
    bf.add_argument("--abrir", action="store_true", help="abrir la gráfica interactiva en el navegador")

    inf = sub.add_parser("informe", help="informe final en HTML (perfil + Benford + Big Five interactivo)")
    inf.add_argument("usuario", nargs="?", help="perfil (por defecto INSTAGRAM_TARGET del .env)")
    inf.add_argument("--sin-radar", dest="radar", action="store_false", help="omitir la generación del gráfico radar interactivo Big Five")
    inf.set_defaults(radar=True)
    inf.add_argument("--abrir", action="store_true", help="abrir el informe en el navegador")

    comp = sub.add_parser("completo", help="prueba global: todo el flujo sobre un perfil")
    comp.add_argument("usuario", nargs="?", help="perfil (por defecto INSTAGRAM_TARGET del .env)")
    comp.add_argument("--si", action="store_true", help="no pedir confirmación")
    comp.add_argument("--workers", type=int, default=3, help="perfiles en paralelo para los contadores (3, máx. 6)")
    comp.add_argument("--limite", type=int, help="capturar solo N seguidores (por defecto, todos los que cargue Instagram)")
    comp.add_argument("--limite-pub", type=int, help="procesar solo N publicaciones (pruebas)")
    comp.add_argument("--sin-publicaciones", action="store_true", help="omitir el scraping de publicaciones (y el Big Five)")
    comp.add_argument("--sin-bigfive", action="store_true", help="omitir el Big Five")
    comp.add_argument("--sin-radar", dest="radar", action="store_false", help="omitir la generación del gráfico radar interactivo Big Five")
    comp.set_defaults(radar=True)
    comp.add_argument("--minimo", type=int, help="datos válidos mínimos para el veredicto de Benford (por defecto 30)")
    comp.add_argument("--abrir", action="store_true", help="abrir el informe al terminar")

    xl = sub.add_parser("excel", help="generar el Excel de seguidores con foto y primer dígito")
    xl.add_argument("usuario", nargs="?", help="perfil (por defecto INSTAGRAM_TARGET del .env)")

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
    return ap


def main(argv=None):
    args = crear_parser().parse_args(argv)

    if args.comando == "sesion":
        from src.scraping.guardar_sesion import guardar_sesion
        return guardar_sesion()

    usuario = resolver_usuario(args.usuario)

    if args.comando == "informe":
        from src.exportar.informe import generar_informe
        ruta = generar_informe(usuario, radar=args.radar)
        if args.abrir:
            import webbrowser
            webbrowser.open("file:///" + ruta.replace("\\", "/").lstrip("/"))
        return

    if args.comando == "completo":
        from src.pipeline import ejecutar_completo
        ejecutar_completo(usuario, workers=args.workers, limite=args.limite, limite_pub=args.limite_pub,
                          con_publicaciones=not (args.sin_publicaciones), con_bigfive=not (args.sin_bigfive or args.sin_publicaciones),
                          radar=args.radar, minimo=args.minimo, abrir=args.abrir, confirmar=not args.si)
        return

    if args.comando == "benford":
        from src.benford.benford import analizar_usuario
        analizar_usuario(usuario, minimo=args.minimo, grafica=not args.sin_grafica, abrir=args.abrir)
        return

    if args.comando == "excel":
        from src.exportar.excel_seguidores import generar_excel_seguidores
        generar_excel_seguidores(usuario)
        return

    if args.comando == "contadores":
        from src.scraping.contadores import extraer_contadores
        extraer_contadores(usuario, workers=args.workers, limite=args.limite, ver=args.ver,
                           confirmar=not args.si, reiniciar=args.reiniciar)
        return

    if args.comando == "seguidores":
        from src.scraping.seguidores import scrapear_seguidores
        scrapear_seguidores(usuario, limite=args.limite, con_fotos=not args.sin_fotos,
                            confirmar=not args.si, reiniciar=args.reiniciar)
        return

    if args.comando in ("scrape", "todo"):
        from src.scraping.scraper import scrapear
        scrapear(usuario, guardar_imagenes=not args.sin_imagenes, con_conexiones=args.conexiones,
                 confirmar=not args.si, limite=args.limite)

    if args.comando in ("analizar", "todo"):
        from src.analisis.bigfive import generar_perfil_bigfive
        generar_perfil_bigfive(usuario, forzar=getattr(args, "forzar", False))


if __name__ == "__main__":
    main()