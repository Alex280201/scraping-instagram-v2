"""Flujo completo (prueba global):  python main.py completo <usuario>

Pasos:  1 publicaciones+perfil  ->  2 lista de seguidores  ->  3 contadores de cada seguidor  ->  4 Benford (+gráfica)
        ->  5 Excel  ->  6 Big Five  ->  7 informe final

Cada paso es reanudable (checkpoints), así que si Instagram corta, se repite el mismo comando y continúa.
Un paso opcional que falla (Big Five sin API key, por ejemplo) no detiene el resto; si falla un paso del que dependen
los demás (lista de seguidores o contadores) se detiene y lo dice.
"""
import os
import time

from src.config import GEMINI_API_KEY, rutas_usuario

OK, OMITIDO, FALLO = "ok", "omitido", "FALLÓ"


def _paso(estado, n, total, titulo):
    print(f"\n{'=' * 70}\n[Paso {n}/{total}] {titulo}\n{'=' * 70}")


def _resumen_error(e):
    return (str(e).splitlines() or [type(e).__name__])[0] or type(e).__name__


def ejecutar_completo(usuario, workers=3, limite=None, limite_pub=None, con_publicaciones=True, con_bigfive=True,
                      radar=True, minimo=None, abrir=False, confirmar=True):
    from src.scraping import contadores as m_cont
    from src.scraping import scraper as m_scraper
    from src.scraping import seguidores as m_seg
    from src.benford import benford as m_bf
    from src.exportar import excel_seguidores as m_xl
    from src.exportar import informe as m_inf

    rutas = rutas_usuario(usuario)
    pasos, total = {}, 7
    print(f"\nPRUEBA GLOBAL sobre @{usuario}")
    print("Se ejecutará: publicaciones" + ("" if con_publicaciones else " (omitido)") + " → lista de seguidores → "
          "contadores → Benford → Excel → Big Five" + ("" if con_bigfive else " (omitido)") + " → informe.")
    print("Usa SOLO perfiles cuya titular haya dado su autorización. Tarda: unos 10-20 min por cada 200 seguidores.")
    if confirmar:
        input("ENTER para continuar o Ctrl+C para cancelar... ")
    inicio = time.time()

    def correr(clave, n, titulo, fn, critico=False, omitir=False, motivo_omision=""):
        _paso(pasos, n, total, titulo)
        if omitir:
            print(f"(omitido: {motivo_omision})")
            pasos[clave] = (OMITIDO, motivo_omision)
            return True
        try:
            fn()
            pasos[clave] = (OK, "")
            return True
        except SystemExit as e:                      # los módulos usan SystemExit para errores "esperados"
            detalle = _resumen_error(e) if e.code not in (None, 0) else "terminó sin datos"
        except KeyboardInterrupt:
            raise
        except Exception as e:
            detalle = _resumen_error(e)
        print(f"[!] {titulo}: {detalle}")
        pasos[clave] = (FALLO, detalle)
        return not critico

    # 1) publicaciones y datos del perfil (para el Big Five y la ficha del informe)
    correr("publicaciones", 1, "Publicaciones y datos del perfil",
           lambda: m_scraper.scrapear(usuario, guardar_imagenes=False, con_conexiones=False, confirmar=False,
                                      limite=limite_pub),
           omitir=not con_publicaciones, motivo_omision="--sin-publicaciones")

    # 2) lista de seguidores
    if not correr("seguidores", 2, "Lista de seguidores (nombre y foto)",
                  lambda: m_seg.scrapear_seguidores(usuario, limite=limite, con_fotos=True, confirmar=False),
                  critico=True) or not os.path.exists(rutas.seguidores_json):
        return _cierre(usuario, pasos, inicio, abortado="no se pudo obtener la lista de seguidores")

    # 3) contadores
    if not correr("contadores", 3, "Seguidos y seguidores de cada seguidor",
                  lambda: m_cont.extraer_contadores(usuario, workers=workers, confirmar=False), critico=True) \
            or not os.path.exists(rutas.contadores_json):
        return _cierre(usuario, pasos, inicio, abortado="no se pudieron obtener los contadores")

    # 4) Benford
    kw = {} if minimo is None else {"minimo": minimo}
    correr("benford", 4, "Ley de Benford (chi-cuadrada, MAD y gráfica)",
           lambda: m_bf.analizar_usuario(usuario, grafica=True, abrir=abrir, **kw))

    # 5) Excel
    correr("excel", 5, "Excel de seguidores (foto, contadores, primer dígito, hoja Benford)",
           lambda: m_xl.generar_excel_seguidores(usuario))

    # 6) Big Five
    sin_texto = not os.path.exists(rutas.datos_json)
    omitir = (not con_bigfive) or (not GEMINI_API_KEY) or sin_texto
    motivo = ("--sin-bigfive" if not con_bigfive else "falta GEMINI_API_KEY en el .env" if not GEMINI_API_KEY
              else "no hay publicaciones extraídas")

    def bigfive():
        from src.analisis import bigfive as m_big
        m_big.generar_perfil_bigfive(usuario)
    correr("bigfive", 6, "Perfil Big Five (embeddings + Gemini)", bigfive, omitir=omitir, motivo_omision=motivo)

    # 7) informe
    correr("informe", 7, "Informe final y mini-sitio enlazado", lambda: m_inf.generar_informe(usuario, radar=radar))
    return _cierre(usuario, pasos, inicio, abrir=abrir)


def _cierre(usuario, pasos, inicio, abortado=None, abrir=False):
    rutas = rutas_usuario(usuario)
    print(f"\n{'=' * 70}\nRESUMEN DE LA PRUEBA GLOBAL — @{usuario}  ({(time.time() - inicio) / 60:.1f} min)\n{'=' * 70}")
    nombres = {"publicaciones": "Publicaciones", "seguidores": "Lista de seguidores", "contadores": "Contadores",
               "benford": "Benford", "excel": "Excel", "bigfive": "Big Five", "informe": "Informe"}
    for clave, nombre in nombres.items():
        if clave in pasos:
            estado, detalle = pasos[clave]
            print(f"  {nombre:<22} {estado}" + (f"  — {detalle}" if detalle else ""))
    if abortado:
        print(f"\nSe detuvo: {abortado}. Corrige el motivo y repite el mismo comando: continúa donde quedó.")
    informe = os.path.join(rutas.resultados, "informe.html")
    if os.path.exists(informe):
        print(f"\nInforme (Mini-sitio): {informe}\nExcel:                {rutas.seguidores_xlsx}")
        if abrir:
            import webbrowser
            webbrowser.open("file:///" + informe.replace(os.sep, "/").lstrip("/"))
    return pasos