"""Fase 1: lista de SEGUIDORES de un perfil (usuario, nombre, foto) con guardado parcial y reanudación.

Se usa desde main.py:   python main.py seguidores <usuario> [--limite N] [--sin-fotos] [--reiniciar]

Salida (datos/<usuario>/raw/):
    seguidores_lista.json   perfil + estado (completo / parcial / limite) + lista de seguidores
    fotos/<usuario>.jpg     foto de perfil de cada seguidor

Si Instagram corta o bloquea a mitad de camino, lo capturado hasta ese momento queda guardado y
al volver a ejecutar el comando se continúa desde ahí (no se repite lo ya descargado).
"""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

from src.config import rutas_usuario
from src.scraping.conexiones import extraer_lista
from src.scraping.scraper import parsear_cabecera
from src.scraping.sesion_util import abrir_con_sesion

ZONA = ZoneInfo("America/Guayaquil")  # Ecuador (UTC-5)


def _guardar_json(ruta, contenido):
    """Escritura atómica: si el proceso se corta a mitad, el archivo anterior no queda corrupto."""
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)


def _cargar_checkpoint(ruta, usuario):
    """Seguidores ya capturados en una corrida anterior (lista vacía si no hay o es de otro perfil)."""
    if not os.path.exists(ruta):
        return []
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, json.JSONDecodeError):
        print("[Seguidores] El checkpoint anterior está dañado; se empieza de cero.")
        return []
    if (datos.get("usuario") or "").lower() != usuario:
        return []
    return datos.get("seguidores", [])


def scrapear_seguidores(usuario, limite=None, con_fotos=True, confirmar=True, reiniciar=False):
    rutas = rutas_usuario(usuario)
    print(f"\nPerfil: @{usuario}  |  Salida: {rutas.raw}")
    if confirmar:
        input("ENTER para continuar o Ctrl+C para cancelar... ")
    rutas.crear()

    previos = [] if reiniciar else _cargar_checkpoint(rutas.seguidores_json, usuario)
    if previos:
        print(f"[Seguidores] Checkpoint encontrado: {len(previos)} ya capturados; se continúa desde ahí "
              f"(usa --reiniciar para empezar de cero).")

    estado = {"perfil": {}, "esperado": None}

    def guardar(lista, estatus="parcial"):
        _guardar_json(rutas.seguidores_json, {
            "usuario": usuario,
            "estado": estatus,
            "fecha": datetime.now(ZONA).strftime("%Y-%m-%d %H:%M"),
            "perfil": estado["perfil"],
            "seguidores_declarados": estado["esperado"],
            "seguidores_extraidos": len(lista),
            "seguidores": lista,
        })

    error = None
    lista = previos
    with sync_playwright() as p:
        navegador, contexto, pagina = abrir_con_sesion(p)
        try:
            pagina.goto(f"https://www.instagram.com/{usuario}/")
            pagina.wait_for_selector("header", timeout=20000)
            pagina.wait_for_timeout(3000)
            estado["perfil"] = parsear_cabecera(pagina.locator("header").inner_text(), usuario)
            estado["esperado"] = estado["perfil"].get("seguidores")
            print(f"Perfil: {estado['perfil'].get('nombre')} | {estado['esperado']} seguidores declarados")

            lista = extraer_lista(
                pagina, usuario, "followers", estado["esperado"], limite=limite,
                carpeta_fotos=rutas.fotos if con_fotos else None,
                previos=previos, al_guardar=guardar,
            )
        except KeyboardInterrupt:
            error = "interrumpido por el usuario"
        except Exception as e:
            error = str(e).splitlines()[0] if str(e) else type(e).__name__
        finally:
            try:
                navegador.close()
            except Exception:
                pass

    esperado = estado["esperado"]
    if error:
        estatus = "parcial"
    elif limite and len(lista) >= limite:
        estatus = "limite"
    elif esperado and len(lista) < esperado:
        estatus = "parcial"
    else:
        estatus = "completo"
    guardar(lista, estatus)

    con_foto = sum(1 for r in lista if r.get("foto_archivo"))
    print("\n--- SEGUIDORES ---")
    print(f"estado: {estatus}" + (f"  (motivo: {error})" if error else ""))
    print(f"extraídos: {len(lista)}" + (f" de {esperado} declarados" if esperado else ""))
    print(f"con foto guardada: {con_foto}")
    print(f"archivo: {rutas.seguidores_json}")
    if estatus == "parcial":
        print("Para continuar donde quedó, vuelve a ejecutar el mismo comando.")
    return {"estado": estatus, "extraidos": len(lista), "declarados": esperado, "con_foto": con_foto,
            "error": error}
