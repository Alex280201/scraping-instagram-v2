
import json
import os
import random
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

from sesion_util import abrir_con_sesion

USUARIO = os.getenv("INSTAGRAM_TARGET")


def pausa(minimo=2, maximo=4):
    return random.randint(minimo * 1000, maximo * 1000)


with sync_playwright() as p:
    navegador, contexto, pagina = abrir_con_sesion(p)
    pagina.goto(f"https://www.instagram.com/{USUARIO}/")
    pagina.wait_for_selector("header", timeout=20000)
    pagina.wait_for_timeout(pausa())

    # 1. Datos del perfil
    soup = BeautifulSoup(pagina.content(), "lxml")
    meta = soup.find("meta", property="og:description")
    descripcion = meta["content"] if meta else ""

    def buscar(patron):
        m = re.search(patron, descripcion, re.IGNORECASE)
        return m.group(1) if m else None

    perfil = {
        "usuario": USUARIO,
        "seguidores": buscar(r"([\d.,]+\s?[KMkm]?)\s+seguidores"),
        "seguidos": buscar(r"([\d.,]+\s?[KMkm]?)\s+siguiendo"),
        "publicaciones": buscar(r"([\d.,]+\s?[KMkm]?)\s+publicaciones"),
        "descripcion_meta": descripcion,
        "texto_cabecera": pagina.locator("header").inner_text(),
    }

    # 2. Recolectar enlaces de publicaciones visibles
    enlaces = set()
    sin_cambios = 0

    while sin_cambios < 3 and len(enlaces) < 60:
        hrefs = pagina.eval_on_selector_all(
            'a[href*="/p/"], a[href*="/reel/"]',
            "els => els.map(e => e.getAttribute('href'))",
        )
        antes = len(enlaces)
        enlaces.update(href for href in hrefs if href)
        sin_cambios = sin_cambios + 1 if len(enlaces) == antes else 0

        pagina.mouse.wheel(0, 2500)
        pagina.wait_for_timeout(pausa())
        print(f"Publicaciones encontradas: {len(enlaces)}")

    perfil["enlaces_publicaciones"] = sorted(enlaces)
    navegador.close()

with open("datos_perfil.json", "w", encoding="utf-8") as f:
    json.dump(perfil, f, ensure_ascii=False, indent=2)

print("\n--- RESUMEN ---")
print("Seguidores:", perfil["seguidores"])
print("Seguidos:", perfil["seguidos"])
print("Publicaciones:", perfil["publicaciones"])
print("Enlaces recolectados:", len(perfil["enlaces_publicaciones"]))
print("\nTexto de la cabecera:\n", perfil["texto_cabecera"])
