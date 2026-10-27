import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
for ruta in (ROOT_DIR, CURRENT_DIR):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

import json
import time
import numpy as np
from google.genai import types

from config import GEMINI_EMBEDDING_MODEL, EMBEDDING_DIM, DATOS_DIR, crear_carpetas
from gemini_cliente import obtener_cliente
from cargador import cargar_datos_usuario
from privacidad import anonimizar_texto

RUTA_NPY = os.path.join(DATOS_DIR, "embeddings.npy")
RUTA_META = os.path.join(DATOS_DIR, "metadatos.json")


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
                vectores.extend(e.values for e in resp.embeddings)  # <- .embeddings (lista), no .embedding
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
        docs.append({"id": "biografia", "tipo": "perfil", "texto": anonimizar_texto(bio)})
    for i, p in enumerate(datos.get("publicaciones", [])):
        if len(p["descripcion"]) > 3:
            docs.append({
                "id": f"pub_{i}", "tipo": p["tipo"] or "publicacion",
                "texto": anonimizar_texto(p["descripcion"]),
                "fecha": p["fecha"], "url": p["url"],
            })
    return docs


def procesar_y_guardar_embeddings(forzar=False):
    crear_carpetas()
    ruta_datos = os.path.join(DATOS_DIR, "instagram_datos.json")
    desactualizado = os.path.exists(ruta_datos) and os.path.exists(RUTA_NPY) \
        and os.path.getmtime(ruta_datos) > os.path.getmtime(RUTA_NPY)
    if desactualizado:
        print("[Embeddings] Hay datos más nuevos que los embeddings; se regeneran.")
    if not forzar and not desactualizado and os.path.exists(RUTA_NPY) and os.path.exists(RUTA_META):
        print("[Embeddings] Ya existen; se reutilizan (usa --forzar para regenerar).")
        with open(RUTA_META, encoding="utf-8") as f:
            return np.load(RUTA_NPY), json.load(f)

    datos = cargar_datos_usuario()
    docs = construir_documentos(datos)
    if not docs:
        print("[Embeddings] No hay texto para vectorizar.")
        return None, []

    print(f"[Embeddings] Vectorizando {len(docs)} textos con {GEMINI_EMBEDDING_MODEL}...")
    matriz = embeber(obtener_cliente(), [d["texto"] for d in docs])
    np.save(RUTA_NPY, matriz)
    with open(RUTA_META, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    print(f"[Embeddings] Guardado {RUTA_NPY} {matriz.shape}")
    return matriz, docs


if __name__ == "__main__":
    procesar_y_guardar_embeddings(forzar="--forzar" in sys.argv)