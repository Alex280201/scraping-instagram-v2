import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
for ruta in (ROOT_DIR, CURRENT_DIR):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

import json
import re
from collections import Counter
from statistics import mean

from config import INSTAGRAM_TARGET, DATOS_DIR, crear_carpetas


def _numero(valor):
    """'1,2K' -> 1200 | '14' -> 14 | None -> None"""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    m = re.match(r"^\s*([\d.,]+)\s*([KkMm]?)\s*$", str(valor))
    if not m:
        return None
    num, suf = m.groups()
    num = num.replace(",", ".") if suf else num.replace(",", "").replace(".", "")
    try:
        n = float(num)
    except ValueError:
        return None
    return n * {"k": 1e3, "m": 1e6}.get(suf.lower(), 1)


def _json_dir(nombre):
    ruta = os.path.join(DATOS_DIR, nombre)
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    return None


def _metricas(perfil, pubs, conexiones):
    """Señales de comportamiento que no son texto (se envían a Gemini como contexto)."""
    anios = Counter((p.get("fecha") or "")[:4] for p in pubs if p.get("fecha"))
    likes = [n for n in (_numero(p.get("likes")) for p in pubs) if n is not None]
    coms = [n for n in (_numero(p.get("comentarios")) for p in pubs) if n is not None]
    con_texto = sum(1 for p in pubs if (p.get("descripcion") or "").strip())
    seguidores, seguidos = perfil.get("seguidores"), perfil.get("seguidos")
    res = (conexiones or {}).get("resumen", {})
    m = {
        "publicaciones_analizadas": len(pubs),
        "publicaciones_con_texto": con_texto,
        "publicaciones_por_anio": dict(sorted(anios.items())),
        "porcentaje_reels": round(100 * sum(1 for p in pubs if p.get("tipo") == "reel") / len(pubs), 1) if pubs else 0,
        "likes_promedio": round(mean(likes), 1) if likes else None,
        "comentarios_promedio": round(mean(coms), 1) if coms else None,
        "seguidores": seguidores,
        "seguidos": seguidos,
        "ratio_seguidores_seguidos": round(seguidores / seguidos, 2) if isinstance(seguidores, (int, float)) and seguidos else None,
    }
    if res:
        m["cuentas_mutuas"] = res.get("mutuos")
        m["solo_me_siguen"] = res.get("solo_me_siguen")
        m["solo_los_sigo"] = res.get("solo_los_sigo")
    return m


def cargar_datos_usuario():
    """Consolida perfil, publicaciones y métricas del scraping elegido (datos/<usuario>/<fecha>/)."""
    crear_carpetas()
    nuevo = _json_dir("instagram_datos.json")
    if not nuevo:
        raise SystemExit(f"No hay datos en {DATOS_DIR}. Ejecuta primero:  python scraper.py {INSTAGRAM_TARGET}")
    perfil, pubs = nuevo.get("perfil", {}), nuevo.get("publicaciones", [])
    conexiones = _json_dir("instagram_conexiones.json")

    # Seguro anti-mezcla: los datos deben pertenecer al perfil configurado
    de_quien = (perfil.get("usuario") or "").strip().lstrip("@").lower()
    if de_quien and de_quien != INSTAGRAM_TARGET:
        raise SystemExit(f"Los datos de {DATOS_DIR} son de '{de_quien}' pero se pidió '{INSTAGRAM_TARGET}'.")

    publicaciones = [
        {
            "url": p.get("url", ""),
            "tipo": p.get("tipo", ""),
            "fecha": p.get("fecha") or "",
            "likes": _numero(p.get("likes")),
            "comentarios": _numero(p.get("comentarios")),
            "descripcion": (p.get("descripcion") or "").strip(),
        }
        for p in pubs
    ]
    print(f"[Cargador] @{INSTAGRAM_TARGET} | scraping {os.path.basename(DATOS_DIR)} | "
          f"publicaciones: {len(publicaciones)} (con texto: {sum(1 for p in publicaciones if p['descripcion'])})")
    return {
        "usuario": INSTAGRAM_TARGET,
        "perfil": perfil,
        "publicaciones": publicaciones,
        "metricas": _metricas(perfil, publicaciones, conexiones),
    }


if __name__ == "__main__":
    d = cargar_datos_usuario()
    print(json.dumps(d["metricas"], ensure_ascii=False, indent=2))
