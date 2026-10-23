"""Carga lo recolectado por el scraping (datos/<usuario>/raw/) y calcula métricas de comportamiento."""
import json
import os
import re
from collections import Counter
from statistics import mean

from src.config import rutas_usuario


def _leer_json(ruta):
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    return None


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


def cargar_datos_usuario(usuario):
    """Consolida perfil, publicaciones y métricas en un solo diccionario."""
    rutas = rutas_usuario(usuario)
    datos = _leer_json(rutas.datos_json)
    if not datos:
        raise SystemExit(f"No hay datos en {rutas.raw}. Ejecuta primero:  python main.py scrape {usuario}")
    perfil, pubs = datos.get("perfil", {}), datos.get("publicaciones", [])
    conexiones = _leer_json(rutas.conexiones_json)

    # Seguro anti-mezcla: los datos deben pertenecer al perfil pedido
    de_quien = (perfil.get("usuario") or "").strip().lstrip("@").lower()
    if de_quien and de_quien != usuario:
        raise SystemExit(f"Los datos de {rutas.raw} son de '{de_quien}', no de '{usuario}'.")

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
    print(f"[Cargador] @{usuario}: {len(publicaciones)} publicaciones "
          f"(con texto: {sum(1 for p in publicaciones if p['descripcion'])})")
    return {
        "usuario": usuario,
        "perfil": perfil,
        "publicaciones": publicaciones,
        "metricas": _metricas(perfil, publicaciones, conexiones),
    }
