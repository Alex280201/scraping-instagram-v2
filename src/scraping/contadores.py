"""Fase 2: seguidos y seguidores de CADA seguidor (visita su perfil, con pocos workers en paralelo).

Se usa desde main.py:   python main.py contadores <usuario> [--workers 3] [--limite N] [--ver] [--reiniciar]

Entrada : datos/<usuario>/raw/seguidores_lista.json        (Fase 1)
Salida  : datos/<usuario>/raw/seguidores_contadores.json   (se guarda cada pocos perfiles)

Cuidado con Instagram:
  * pocos workers (3 por defecto), pausas aleatorias largas y un descanso cada cierto número de perfiles;
  * si aparece login/verificación, HTTP 429 o muchos errores seguidos, se DETIENE todo y se conserva lo guardado;
  * al repetir el comando se continúa con los pendientes (no se vuelve a visitar lo ya resuelto).
"""
import asyncio
import json
import os
import random
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright

from src.config import ARCHIVO_SESION, rutas_usuario

ZONA = ZoneInfo("America/Guayaquil")  # Ecuador (UTC-5)

# ---------------- Configuración (ajustable) ----------------
URL_BASE = "https://www.instagram.com"
WORKERS_POR_DEFECTO = 3
PAUSA_MIN, PAUSA_MAX = 4.0, 8.0          # segundos entre perfiles de un mismo worker
DESCANSO_CADA = 25                       # cada N perfiles un worker descansa...
DESCANSO_MIN, DESCANSO_MAX = 20.0, 40.0  # ...entre estos segundos
CHECKPOINT_CADA = 10                     # guardar cada N perfiles resueltos
MAX_ERRORES_SEGUIDOS = 5                 # errores seguidos (global) antes de parar: señal de límite de Instagram
ESPERA_CABECERA_MS = 15000
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

ESTADOS_RESUELTOS = {"ok", "privado", "no_existe"}   # "error" se reintenta en la siguiente corrida


class Bloqueo(Exception):
    """Instagram pidió login/verificación o está limitando: hay que parar todo."""


# ---------------- Parseo de números (español e inglés) ----------------
_SUFIJOS = {"k": 1e3, "mil": 1e3, "m": 1e6, "mill": 1e6, "mm": 1e9}
_NUM = r"\d[\d.,]*(?:\s?(?:mil|mill|mm|[kKmM]))?"


def parsear_contador(texto):
    """'1,234' -> 1234 | '12,5 mil' -> 12500 | '1,2 M' -> 1200000 | '1.234.567' -> 1234567 | None si no es número."""
    if texto is None:
        return None
    t = str(texto).strip().lower()
    m = re.fullmatch(r"(\d[\d.,]*)\s?(mil|mill|mm|k|m)?", t)
    if not m:
        return None
    num, sufijo = m.groups()
    if sufijo:                                   # con sufijo, el separador es DECIMAL ('12,5 mil')
        try:
            return int(round(float(num.replace(",", ".")) * _SUFIJOS[sufijo]))
        except ValueError:
            return None
    digitos = re.sub(r"[.,]", "", num)           # sin sufijo, los separadores son de MILES ('1.234' / '1,234')
    return int(digitos) if digitos.isdigit() else None


def _buscar(patron_etiqueta, texto):
    m = re.search(rf"(?<![\w.,])({_NUM})\s+(?:{patron_etiqueta})\b", texto, re.IGNORECASE)
    return parsear_contador(m.group(1)) if m else None


def parsear_cabecera_contadores(texto_cabecera, titulos=None):
    """Lee publicaciones / seguidores / seguidos del texto visible de la cabecera.

    `titulos` = {'followers': '12,534', ...}: el atributo title de Instagram trae el número EXACTO
    (el texto visible puede venir abreviado, '12,5 mil'); si existe, se prefiere.
    """
    t = re.sub(r"\s+", " ", texto_cabecera or "")
    res = {
        "publicaciones": _buscar(r"publicaci(?:o|ó)nes|publicaci(?:o|ó)n|posts?", t),
        "seguidores": _buscar(r"seguidores|seguidor|followers?", t),
        "seguidos": _buscar(r"seguidos|siguiendo|following", t),
    }
    for clave, tipo in (("seguidores", "followers"), ("seguidos", "following")):
        exacto = parsear_contador((titulos or {}).get(tipo))
        if exacto is not None:
            res[clave] = exacto
    return res


# ---------------- Lectura de un perfil ----------------
JS_PERFIL = r"""
() => {
  const h = document.querySelector('header');
  const cuerpo = document.body ? document.body.innerText : '';
  const titulos = {};
  document.querySelectorAll('header a[href$="/followers/"] [title], header a[href$="/following/"] [title]').forEach(e => {
    const a = e.closest('a');
    const tipo = a.getAttribute('href').endsWith('/followers/') ? 'followers' : 'following';
    titulos[tipo] = e.getAttribute('title');
  });
  return {cabecera: h ? h.innerText : '', cuerpo: cuerpo.slice(0, 4000), titulos};
}
"""
JS_ESPERA = r"""
() => !!document.querySelector('header') ||
      /no está disponible|isn't available|no existe|Sorry, this page/i.test(document.body ? document.body.innerText : '')
"""
RE_NO_EXISTE = re.compile(r"no está disponible|isn't available|Sorry, this page|no existe", re.I)
RE_PRIVADO = re.compile(r"cuenta es privada|account is private", re.I)


def _sesion_perdida(url):
    return "/accounts/login" in url or "/challenge" in url or "/suspended" in url


async def procesar_perfil(pagina, usuario):
    """Visita el perfil y devuelve {usuario, seguidores, seguidos, publicaciones, estado, motivo}."""
    resp = await pagina.goto(f"{URL_BASE}/{usuario}/", wait_until="domcontentloaded", timeout=30000)
    if resp is not None and resp.status == 429:
        raise Bloqueo("Instagram respondió 429 (demasiadas solicitudes)")
    if _sesion_perdida(pagina.url):
        raise Bloqueo("Instagram pidió iniciar sesión o verificación (posible bloqueo temporal)")

    try:
        await pagina.wait_for_function(JS_ESPERA, timeout=ESPERA_CABECERA_MS)
    except Exception:
        if _sesion_perdida(pagina.url):
            raise Bloqueo("Instagram pidió iniciar sesión o verificación (posible bloqueo temporal)")
        raise RuntimeError("la página no cargó la cabecera del perfil")
    await pagina.wait_for_timeout(random.randint(600, 1400))   # deja que se pinten los contadores

    info = await pagina.evaluate(JS_PERFIL)
    base = {"usuario": usuario, "seguidores": None, "seguidos": None, "publicaciones": None, "motivo": ""}

    if not info["cabecera"].strip():
        if RE_NO_EXISTE.search(info["cuerpo"]):
            return {**base, "estado": "no_existe", "motivo": "el perfil no existe o fue eliminado"}
        raise RuntimeError("cabecera vacía")

    cont = parsear_cabecera_contadores(info["cabecera"], info.get("titulos"))
    resumen_cab = re.sub(r"\s+", " ", info["cabecera"]).strip()[:300]
    if cont["seguidores"] is None:
        # Un perfil sin el contador de seguidores NO se da por bueno: queda como error (se reintenta)
        # y el motivo trae el texto crudo de la cabecera para poder ajustar la lectura.
        raise RuntimeError(f"no se encontró el contador de seguidores; cabecera: «{resumen_cab}»")
    estado = "privado" if RE_PRIVADO.search(info["cuerpo"]) else "ok"
    resultado = {**base, **cont, "estado": estado}
    if cont["seguidores"] == 0:
        # 0 puede ser real (cuentas nuevas/spam) o un fallo de lectura: se guarda la evidencia para comprobarlo
        resultado["diagnostico"] = {"cabecera": resumen_cab, "titulos": info.get("titulos")}
    return resultado


# ---------------- Workers ----------------
class _Contexto:
    """Estado compartido de una corrida (un solo hilo de asyncio: no hace falta bloquear)."""

    def __init__(self, resultados, total, guardar):
        self.resultados = resultados
        self.total = total
        self.guardar = guardar
        self.detener = asyncio.Event()
        self.motivo = None
        self.errores_seguidos = 0
        self.hechos = 0           # perfiles resueltos en esta corrida


def _linea(n, total, r):
    if r["estado"] in ("ok", "privado"):
        return f"[{n}/{total}] @{r['usuario']}: {r['seguidores']} seguidores, {r['seguidos']} seguidos ({r['estado']})"
    return f"[{n}/{total}] @{r['usuario']}: {r['estado']}" + (f" - {r['motivo']}" if r["motivo"] else "")


async def _worker(num, cola, contexto, ctx, pausa, descanso):
    pagina = await contexto.new_page()

    async def filtrar(ruta):    # no hacen falta imágenes ni medios para leer contadores
        if ruta.request.resource_type in ("image", "media", "font"):
            await ruta.abort()
        else:
            await ruta.continue_()
    await pagina.route("**/*", filtrar)

    await asyncio.sleep((num - 1) * 1.5)      # arranque escalonado
    procesados = 0
    try:
        while not ctx.detener.is_set():
            try:
                usuario = cola.get_nowait()
            except asyncio.QueueEmpty:
                break
            try:
                ahora = await procesar_perfil(pagina, usuario)
                ctx.errores_seguidos = 0
            except Bloqueo as e:
                ctx.motivo = str(e)
                ctx.detener.set()
                print(f"\n[!] {ctx.motivo}. Se detiene; lo capturado queda guardado.")
                break
            except Exception as e:
                msg = (str(e).splitlines() or [type(e).__name__])[0]
                ahora = {"usuario": usuario, "seguidores": None, "seguidos": None, "publicaciones": None,
                         "estado": "error", "motivo": msg}
                ctx.errores_seguidos += 1
                if ctx.errores_seguidos >= MAX_ERRORES_SEGUIDOS:
                    ctx.motivo = (f"{ctx.errores_seguidos} errores seguidos (posible límite de Instagram); "
                                  f"último: {msg}")
                    ctx.detener.set()

            ahora["fecha_consulta"] = datetime.now(ZONA).strftime("%Y-%m-%d %H:%M:%S")
            ctx.resultados[usuario] = ahora
            ctx.hechos += 1
            procesados += 1
            print(_linea(len(ctx.resultados), ctx.total, ahora))
            if ctx.hechos % CHECKPOINT_CADA == 0:
                ctx.guardar()

            if procesados % DESCANSO_CADA == 0:
                await asyncio.sleep(descanso())
            else:
                await asyncio.sleep(pausa())
    finally:
        await pagina.close()


async def procesar_pendientes(contexto, pendientes, resultados, total, guardar, workers=WORKERS_POR_DEFECTO,
                              pausa=lambda: random.uniform(PAUSA_MIN, PAUSA_MAX),
                              descanso=lambda: random.uniform(DESCANSO_MIN, DESCANSO_MAX)):
    """Reparte los usuarios pendientes entre `workers` pestañas. Devuelve el motivo de parada (o None)."""
    cola = asyncio.Queue()
    for u in pendientes:
        cola.put_nowait(u)
    ctx = _Contexto(resultados, total, guardar)
    n = max(1, min(workers, len(pendientes) or 1))
    try:
        await asyncio.gather(*(_worker(i, cola, contexto, ctx, pausa, descanso) for i in range(1, n + 1)))
    finally:
        guardar()
    return ctx.motivo


# ---------------- Archivos ----------------
def _guardar_json(ruta, contenido):
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)


def _leer_json(ruta):
    if not os.path.exists(ruta):
        return None
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


# ---------------- Programa principal ----------------
async def _ejecutar(usuario, lista, resultados, workers, ver, rutas, limite):
    pendientes = [u for u in lista if resultados.get(u, {}).get("estado") not in ESTADOS_RESUELTOS]
    if limite:
        pendientes = pendientes[:limite]
    meta = {"motivo": None}

    def guardar():
        ordenados = [resultados[u] for u in lista if u in resultados]
        resueltos = sum(1 for r in ordenados if r["estado"] in ESTADOS_RESUELTOS)
        _guardar_json(rutas.contadores_json, {
            "usuario": usuario,
            "estado": "completo" if resueltos == len(lista) else "parcial",
            "fecha": datetime.now(ZONA).strftime("%Y-%m-%d %H:%M"),
            "total_lista": len(lista),
            "resueltos": resueltos,
            "motivo_parada": meta["motivo"],
            "resultados": ordenados,
        })

    sin_resolver = [u for u in lista if resultados.get(u, {}).get("estado") not in ESTADOS_RESUELTOS]
    print(f"[Contadores] {len(lista)} seguidores en la lista | ya resueltos: {len(lista) - len(sin_resolver)} | "
          f"a procesar ahora: {len(pendientes)} | workers: {workers}")
    if not pendientes:
        guardar()
        return meta["motivo"]

    async with async_playwright() as p:
        opciones = {"headless": not ver, "args": ["--disable-blink-features=AutomationControlled"]}
        try:
            navegador = await p.chromium.launch(channel="chrome", **opciones)
        except Exception:
            navegador = await p.chromium.launch(**opciones)
        try:
            contexto = await navegador.new_context(storage_state=ARCHIVO_SESION, user_agent=USER_AGENT,
                                                   viewport={"width": 1280, "height": 900})
            meta["motivo"] = await procesar_pendientes(contexto, pendientes, resultados, len(lista),
                                                       guardar, workers=workers)
            guardar()
        finally:
            await navegador.close()
    return meta["motivo"]


def extraer_contadores(usuario, workers=WORKERS_POR_DEFECTO, limite=None, ver=False, confirmar=True,
                       reiniciar=False):
    rutas = rutas_usuario(usuario)
    datos = _leer_json(rutas.seguidores_json)
    if not datos or not datos.get("seguidores"):
        raise SystemExit(f"No hay lista de seguidores en {rutas.raw}. Ejecuta primero:  "
                         f"python main.py seguidores {usuario}")
    if not os.path.isfile(ARCHIVO_SESION):
        raise SystemExit("No existe sesion.json. Ejecuta primero:  python main.py sesion")
    if datos.get("estado") == "parcial":
        print("[Contadores] AVISO: la lista de seguidores está incompleta (estado 'parcial'). "
              "Se procesará lo que hay; puedes completarla con 'seguidores' y repetir este comando.")

    lista = []
    for r in datos["seguidores"]:          # sin duplicados, en el orden de la lista
        if r["usuario"] not in lista:
            lista.append(r["usuario"])

    workers = max(1, min(workers, 6))      # tope de seguridad
    print(f"\nPerfil base: @{usuario}  |  Salida: {rutas.contadores_json}")
    if confirmar:
        input("ENTER para continuar o Ctrl+C para cancelar... ")

    previo = None if reiniciar else _leer_json(rutas.contadores_json)
    resultados = {r["usuario"]: r for r in (previo or {}).get("resultados", [])}

    motivo = None
    try:
        motivo = asyncio.run(_ejecutar(usuario, lista, resultados, workers, ver, rutas, limite))
    except KeyboardInterrupt:
        motivo = "interrumpido por el usuario"
        print("\nInterrumpido: lo capturado hasta ahora quedó guardado.")

    por_estado = {}
    for r in resultados.values():
        por_estado[r["estado"]] = por_estado.get(r["estado"], 0) + 1
    resueltos = sum(n for e, n in por_estado.items() if e in ESTADOS_RESUELTOS)
    print("\n--- CONTADORES ---")
    print(f"resueltos: {resueltos} de {len(lista)}   |   por estado: {por_estado}")
    if motivo:
        print(f"parada: {motivo}")
    if resueltos < len(lista):
        print("Para continuar con los pendientes (y reintentar los errores), repite el mismo comando.")
    print(f"archivo: {rutas.contadores_json}")
    return {"resueltos": resueltos, "total": len(lista), "por_estado": por_estado, "motivo": motivo}
