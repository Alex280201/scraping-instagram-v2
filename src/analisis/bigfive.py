"""Perfil Big Five (OCEAN): evidencia por similitud de embeddings + generación con Gemini."""
import json
import time
import numpy as np
from pydantic import BaseModel, Field
from google.genai import types, errors

from src.analisis.cargador import cargar_datos_usuario
from src.config import GEMINI_MODEL, GEMINI_MODEL_RESPALDO, rutas_usuario
from src.embeddings.embeddings import embeber, procesar_y_guardar_embeddings
from src.gemini.cliente import obtener_cliente

MAX_TEXTOS_COMPLETOS = 80   # hasta este número se envían TODOS los textos a Gemini; si hay más, se filtra por similitud
RASGOS = ["apertura", "responsabilidad", "extraversion", "amabilidad", "neuroticismo"]

# Frases ancla: se vectorizan y se comparan con tus textos para recuperar la evidencia más relevante por rasgo.
ANCLAS = {
    "apertura": ["curiosidad, creatividad, arte, música, ideas nuevas, viajar y probar cosas distintas",
                 "preferencia por la rutina y lo conocido, poco interés en lo abstracto o artístico"],
    "responsabilidad": ["organización, metas, disciplina, constancia, planificación y cumplir compromisos",
                        "impulsividad, desorden, dejar las cosas para después"],
    "extraversion": ["salir con amigos, fiestas, eventos, hablar mucho, energía social y compartir con otros",
                     "preferencia por la soledad, el silencio, la reserva y pocas interacciones sociales"],
    "amabilidad": ["empatía, gratitud, apoyo a otros, cariño por familia y amigos, cooperación",
                   "competitividad, crítica dura, sarcasmo, conflicto con otros"],
    "neuroticismo": ["ansiedad, tristeza, estrés, preocupación, cambios de ánimo e inseguridad",
                     "calma, estabilidad emocional, tranquilidad ante los problemas"],
}


class Rasgo(BaseModel):
    rasgo: str = Field(description="apertura, responsabilidad, extraversion, amabilidad o neuroticismo")
    puntaje: int = Field(description="0-100; 50 = sin evidencia suficiente")
    confianza: float = Field(description="0.0-1.0, qué tan respaldado está el puntaje por la evidencia")
    evidencia: list[str] = Field(description="ids de los textos usados (p. ej. pub_3, biografia) o nombres de métricas")
    justificacion: str


class PerfilBigFive(BaseModel):
    rasgos: list[Rasgo]
    resumen: str
    limitaciones: str


def _techo_confianza(n_textos: int) -> float:
    """Límite duro: con poco texto el modelo no puede declarar confianza alta."""
    if n_textos < 5:
        return 0.25
    if n_textos < 15:
        return 0.45
    if n_textos < 40:
        return 0.65
    return 0.8


def seleccionar_evidencia(cliente, matriz, docs, k=4):
    """RAG por rasgo: los k textos más cercanos a las anclas de cada rasgo."""
    if len(docs) <= MAX_TEXTOS_COMPLETOS:
        return docs
    elegidos = {}
    anclas = [(r, a) for r in RASGOS for a in ANCLAS[r]]
    vec_anclas = embeber(cliente, [a for _, a in anclas], tarea="RETRIEVAL_QUERY")
    sims = matriz @ vec_anclas.T  # coseno (todo normalizado)
    for r in RASGOS:
        cols = [j for j, (rr, _) in enumerate(anclas) if rr == r]
        puntaje = sims[:, cols].max(axis=1)
        for idx in np.argsort(-puntaje)[:k]:
            elegidos[docs[idx]["id"]] = docs[idx]
    return list(elegidos.values())


def _generar_con_reintentos(cliente, prompt, intentos=6):
    """Reintenta ante 429/5xx (picos de demanda) con espera creciente; usa modelo de respaldo si está definido."""
    modelos = [m for m in (GEMINI_MODEL, GEMINI_MODEL_RESPALDO) if m]
    cfg = types.GenerateContentConfig(response_mime_type="application/json",
                                      response_schema=PerfilBigFive, temperature=0.2)
    for n_modelo, modelo in enumerate(modelos):
        es_ultimo = n_modelo == len(modelos) - 1
        for i in range(intentos):
            try:
                resp = cliente.models.generate_content(model=modelo, contents=prompt, config=cfg)
                return resp, modelo
            except (errors.ServerError, errors.ClientError) as e:
                codigo = getattr(e, "code", None) or getattr(e, "status_code", None)
                if codigo == 404:
                    raise RuntimeError(f"El modelo '{modelo}' no existe o no está disponible para tu cuenta. "
                                       "Cambia GEMINI_MODEL en el .env.") from e
                reintentable = codigo in (429, 500, 502, 503, 504)
                if not reintentable or i == intentos - 1:
                    if es_ultimo or not reintentable:
                        raise
                    print(f"[Gemini] {modelo} sigue saturado; probando modelo de respaldo...")
                    break
                espera = min(5 * 2 ** i, 60)
                print(f"[Gemini] {codigo} en {modelo}. Reintento {i + 1}/{intentos - 1} en {espera}s...")
                time.sleep(espera)
    raise RuntimeError("No se pudo generar el perfil con ningún modelo.")


def generar_perfil_bigfive(usuario, forzar=False):
    rutas = rutas_usuario(usuario).crear()
    cliente = obtener_cliente()
    matriz, docs = procesar_y_guardar_embeddings(usuario, forzar=forzar)
    datos = cargar_datos_usuario(usuario)
    metricas = datos["metricas"]

    docs = docs or []
    evidencia = seleccionar_evidencia(cliente, matriz, docs) if docs else []
    texto_ev = "\n".join(f"[{d['id']}] ({d.get('fecha','')[:10]}) {d['texto']}" for d in evidencia) or "(sin textos)"

    prompt = f"""Eres un analista de psicología de la personalidad. Estima un perfil Big Five (OCEAN) a partir
SOLO de la evidencia dada. Reglas:
- Puntaje 0-100 por rasgo. Si la evidencia es insuficiente para un rasgo, usa 50 y confianza baja.
- Cita en "evidencia" los ids o nombres de métricas en que te basas. No inventes hechos.
- Las métricas de comportamiento (frecuencia de publicación, likes, red de contactos) son señales débiles; no las sobreinterpretes.
- Esto es una estimación exploratoria, no un diagnóstico. Responde en español.

MÉTRICAS:
{json.dumps(metricas, ensure_ascii=False, indent=2)}

TEXTOS ({len(evidencia)} de {len(docs)} disponibles):
{texto_ev}
"""
    resp, modelo_usado = _generar_con_reintentos(cliente, prompt)
    perfil = PerfilBigFive.model_validate_json(resp.text)

    techo = _techo_confianza(len(docs))
    for r in perfil.rasgos:
        r.puntaje = max(0, min(100, r.puntaje))
        r.confianza = round(min(max(r.confianza, 0.0), techo), 2)

    salida = perfil.model_dump()
    salida["meta"] = {"usuario": usuario, "textos_disponibles": len(docs), "techo_confianza": techo,
                      "modelo": modelo_usado}
    ruta = rutas.bigfive_json
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    print(f"\n=== Big Five (textos usados: {len(docs)}; confianza máxima permitida: {techo}) ===")
    for r in perfil.rasgos:
        print(f"{r.rasgo:<16} {r.puntaje:>3}/100  confianza {r.confianza}")
    print(f"\n{perfil.resumen}\n\nLimitaciones: {perfil.limitaciones}\n[Guardado en {ruta}]")
    return salida

