
import os
import random
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

from sesion_util import abrir_con_sesion

USUARIO = os.getenv("INSTAGRAM_TARGET")

with sync_playwright() as p:
    navegador, contexto, pagina = abrir_con_sesion(p)
    pagina.goto(f"https://www.instagram.com/{USUARIO}/")
    pagina.wait_for_selector("header", timeout=20000)
    pagina.wait_for_timeout(random.randint(2000, 4000))
    html = pagina.content()
    input("Presiona ENTER para cerrar el navegador...")
    navegador.close()

with open("perfil.html", "w", encoding="utf-8") as f:
    f.write(html)

soup = BeautifulSoup(html, "lxml")
print("Título:", soup.title.string if soup.title else None)
meta = soup.find("meta", property="og:description")
print("Descripción:", meta["content"] if meta else "No encontrada")
