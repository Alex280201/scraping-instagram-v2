"""Carpetas por scraping: datos/<usuario>/<AAAA-MM-DD_HHMM>/  (cada scraping queda separado)."""
import os
import re
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(BASE, "datos")
_PATRON = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}$")


def carpeta_usuario(usuario):
    return os.path.join(DATOS, usuario)


def listar_corridas(usuario):
    base = carpeta_usuario(usuario)
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base)
                  if _PATRON.match(d) and os.path.isdir(os.path.join(base, d)))


def nueva_corrida(usuario):
    """Crea y devuelve la carpeta del scraping de ahora mismo."""
    ruta = os.path.join(carpeta_usuario(usuario), datetime.now().strftime("%Y-%m-%d_%H%M"))
    os.makedirs(ruta, exist_ok=True)
    return ruta


def buscar_corrida(usuario, nombre=None):
    """Carpeta de un scraping: la indicada, o la más reciente. None si no hay ninguno."""
    base = carpeta_usuario(usuario)
    if nombre:
        ruta = os.path.join(base, nombre)
        return ruta if os.path.isdir(ruta) else None
    corridas = listar_corridas(usuario)
    if corridas:
        return os.path.join(base, corridas[-1])
    if os.path.exists(os.path.join(base, "instagram_datos.json")):  # carpeta antigua, sin fecha
        return base
    return None
