"""Convierte biografía y descripciones en vectores (embeddings) con Gemini."""
import json
import os
import time

import numpy as np
from google.genai import types

from src.analisis.cargador import cargar_datos_usuario
from src.analisis.privacidad import anonimizar_texto
from src.config import EMBEDDING_DIM, GEMINI_EMBEDDING_MODEL, rutas_usuario
from src.gemini.cliente import obtener_cliente


def _normalizar(m: np.ndarray) -> np.ndarray:
    # Con output_dimensionality < 3072 los vectores deben normalizarse manualmente.
    n = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.where(n == 0, 1, n)


def embeber(cliente, textos, tarea="RETRIEVAL_DOCUMENT", lote=50, reintentos=4):
    """Devuelve una matriz (n, EMBEDDING_DIM) normalizada. Usa lotes y reintenta ante límites de cuota."""
    vectores = []
    for i in range(0, len(textos), lote):
        parte = textos[i:i + lote]
        for intento in range(reintentos):
            try:
                resp = cliente.models.embed_content(
                    model=GEMINI_EMBEDDING_MODEL,
                    contents=parte,
                    config=types.EmbedContentConfig(task_type=tarea, output_dimensionality=EMBEDDING_DIM),
                )
                vectores.extend(e.values for e in resp.embeddings)
                break
            except Exception as e:
                if intento == reintentos - 1:
                    raise
                espera = 2 ** (intento + 1)
                print(f"[Embeddings] Error ({e}). Reintentando en {espera}s...")
                time.sleep(espera)
    return _normalizar(np.array(vectores, dtype=np.float32))


def construir_documentos(datos):
    """Textos que sí aportan señal: biografía y descripciones de publicaciones."""
    docs = []
    bio = (datos.get("perfil") or {}).get("biografia", "")
    if bio and len(bio.strip()) > 3:
        docs.append({"id": "biografia", "tipo": "perfil", "texto": anonimizar_texto(bio), "fecha": "", "url": ""})
    for i, p in enumerate(datos.get("publicaciones", [])):
        if len(p["descripcion"]) > 3:
            docs.append({
                "id": f"pub_{i}", "tipo": p["tipo"] or "publicacion",
                "texto": anonimizar_texto(p["descripcion"]),
                "fecha": p["fecha"], "url": p["url"],
            })
    return docs


def procesar_y_guardar_embeddings(usuario, forzar=False):
    rutas = rutas_usuario(usuario).crear()
    desactualizado = (os.path.exists(rutas.datos_json) and os.path.exists(rutas.emb_npy)
                      and os.path.getmtime(rutas.datos_json) > os.path.getmtime(rutas.emb_npy))
    if desactualizado:
        print("[Embeddings] Hay datos más nuevos que los embeddings; se regeneran.")
    if not forzar and not desactualizado and os.path.exists(rutas.emb_npy) and os.path.exists(rutas.emb_meta):
        with open(rutas.emb_meta, encoding="utf-8") as f:
            meta = json.load(f)
        matriz = np.load(rutas.emb_npy)
        if meta and len(meta) == matriz.shape[0]:
            print("[Embeddings] Ya existen; se reutilizan (usa --forzar para regenerar).")
            return matriz, meta
        print("[Embeddings] La caché está vacía o no coincide; se regeneran.")

    datos = cargar_datos_usuario(usuario)
    docs = construir_documentos(datos)
    if not docs:
        print("[Embeddings] No hay texto para vectorizar.")
        return None, []

    print(f"[Embeddings] Vectorizando {len(docs)} textos con {GEMINI_EMBEDDING_MODEL}...")
    matriz = embeber(obtener_cliente(), [d["texto"] for d in docs])
    np.save(rutas.emb_npy, matriz)
    with open(rutas.emb_meta, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    print(f"[Embeddings] Guardado en {rutas.embeddings} {matriz.shape}")
    return matriz, docs
