"""Guarda la sesión de Instagram SIN iniciar sesión dentro de un navegador automatizado.

1. Abre tu Google Chrome real, con un perfil propio de este proyecto.
2. Tú inicias sesión normalmente en esa ventana.
3. Playwright se conecta a ese Chrome y copia las cookies a sesion.json.
"""
import os
import shutil
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

from src.config import ARCHIVO_SESION, PERFIL_CHROME
from src.scraping.sesion_util import sesion_activa

PUERTO = 9222
RUTAS_CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    "/usr/bin/google-chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def buscar_chrome():
    for ruta in RUTAS_CHROME:
        if os.path.exists(ruta):
            return ruta
    return shutil.which("chrome") or shutil.which("google-chrome")


def guardar_sesion():
    chrome = buscar_chrome()
    if not chrome:
        sys.exit("No encontré Google Chrome. Instálalo o edita RUTAS_CHROME en este archivo.")

    # Cierra cualquier Chrome que use el mismo perfil antes de continuar.
    proceso = subprocess.Popen([
        chrome,
        f"--remote-debugging-port={PUERTO}",
        f"--user-data-dir={PERFIL_CHROME}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://www.instagram.com/accounts/login/",
    ])
    time.sleep(4)

    print("1) En la ventana de Chrome que se abrió, inicia sesión en Instagram con tu cuenta personal.")
    print("2) Completa cualquier verificación (código, 'fui yo', captcha) manualmente.")
    print("3) Espera a ver el feed de Instagram.")
    input("Presiona ENTER aquí SOLO cuando veas el feed... ")

    with sync_playwright() as p:
        navegador = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PUERTO}")
        contexto = navegador.contexts[0]
        if not sesion_activa(contexto):
            navegador.close()
            proceso.terminate()
            sys.exit("No se detectó sesión iniciada. Vuelve a ejecutar el comando y espera a ver el feed.")
        contexto.storage_state(path=ARCHIVO_SESION)
        navegador.close()

    proceso.terminate()
    print(f"Sesión guardada en {ARCHIVO_SESION}. Ya puedes ejecutar: python main.py scrape <usuario>")
