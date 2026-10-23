
"""Utilidades compartidas para abrir Instagram con la sesión guardada."""

import os
import sys
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

ARCHIVO_SESION = "sesion.json"
URL_INSTAGRAM = "https://www.instagram.com/"


def lanzar_navegador(p):
    """Abre Chrome si está instalado; si no, usa Chromium de Playwright."""
    opciones = {
        "headless": False,
        "args": ["--disable-blink-features=AutomationControlled"],
    }

    try:
        return p.chromium.launch(channel="chrome", **opciones)
    except Exception:
        return p.chromium.launch(**opciones)


def sesion_activa(contexto):
    """Comprueba si existe una cookie de sesión de Instagram."""
    try:
        return any(
            cookie.get("name") == "sessionid"
            and cookie.get("value")
            for cookie in contexto.cookies()
        )
    except Exception:
        return False


def abrir_con_sesion(p):
    """
    Devuelve (navegador, contexto, pagina) usando la sesión guardada.

    Si no existe la sesión, está caducada o no se puede abrir Instagram,
    muestra un mensaje claro.
    """
    if not os.path.isfile(ARCHIVO_SESION):
        sys.exit(
            "No existe sesion.json. Ejecuta primero: "
            "python guardar_sesion.py"
        )

    navegador = None

    try:
        navegador = lanzar_navegador(p)
        contexto = navegador.new_context(
            storage_state=ARCHIVO_SESION
        )
        pagina = contexto.new_page()

        try:
            pagina.goto(
                URL_INSTAGRAM,
                wait_until="domcontentloaded",
                timeout=30000,
            )
        except PlaywrightTimeoutError:
            # Si la página sigue cargando, comprobamos su estado actual.
            if "instagram.com" not in pagina.url:
                raise

        pagina.wait_for_timeout(3000)

        if "/accounts/login" in pagina.url or not sesion_activa(contexto):
            navegador.close()
            sys.exit(
                "La sesión de Instagram no está activa o ha caducado.\n"
                "Inicia sesión de nuevo con: python guardar_sesion.py"
            )

        return navegador, contexto, pagina

    except Exception as error:
        if navegador is not None:
            try:
                navegador.close()
            except Exception:
                pass

        sys.exit(
            "No se pudo abrir Instagram con la sesión guardada.\n"
            "Comprueba tu conexión a Internet y la URL.\n"
            f"Detalle: {error}"
        )
