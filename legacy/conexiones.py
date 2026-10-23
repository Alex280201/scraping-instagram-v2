"""Seguidores y seguidos: extracción + limpieza + exportación (documento aparte).

Metodología (adaptada del proyecto Instagram_scraperV2):
    1. Abrir el modal de "seguidores" / "seguidos" del perfil.
    2. Hacer scroll dentro del modal hasta que ya no aparezcan usuarios nuevos.
    3. Recoger los usuarios (y el nombre visible) de cada fila.
    4. Limpiar, quitar duplicados y cruzar ambas listas.

Se usa en dos modos:
    - Automático: scraper.py lo llama después de las publicaciones.
    - Independiente:  python conexiones.py
"""
import csv
import json
import random
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

# ---------------- Configuración ----------------
LIMITE_CONEXIONES = None   # None = todos; o un número por lista para probar (ej. 30)
MAX_SCROLLS = 300          # tope de seguridad de scrolls por lista
MAX_SIN_PROGRESO = 6       # scrolls seguidos sin usuarios nuevos antes de parar
ZONA = ZoneInfo("America/Guayaquil")  # Ecuador (UTC-5)

SALIDA_XLSX = "instagram_conexiones.xlsx"
SALIDA_JSON = "instagram_conexiones.json"
SALIDA_CSV_SEGUIDORES = "instagram_seguidores.csv"
SALIDA_CSV_SEGUIDOS = "instagram_seguidos.csv"

# Rutas de Instagram que parecen un usuario pero no lo son
RESERVADOS = {
    "explore", "accounts", "direct", "reels", "reel", "stories", "p", "tv",
    "about", "legal", "web", "privacy", "developer", "press", "api", "challenge",
}
# Textos de botones/etiquetas que aparecen en cada fila y no son el nombre
ETIQUETAS = {
    "seguir", "siguiendo", "eliminar", "mensaje", "seguir también", "seguir tambien",
    "follow", "following", "remove", "message", "follow back", "verificado",
    "verified", "·", "•",
}

# ---------------- JavaScript que corre dentro de la página ----------------
JS_FILAS = r"""
() => {
  const dialogo = document.querySelector('div[role="dialog"]');
  if (!dialogo) return [];
  const RE = /^\/([A-Za-z0-9._]+)\/?$/;
  const usuariosEn = n => new Set(
    [...n.querySelectorAll('a[href^="/"]')]
      .map(x => (x.getAttribute('href').match(RE) || [])[1])
      .filter(Boolean)
  );
  const filas = {};
  dialogo.querySelectorAll('a[href^="/"]').forEach(a => {
    const m = a.getAttribute('href').match(RE);
    if (!m) return;
    const usuario = m[1];
    // Sube mientras el contenedor siga conteniendo UN solo usuario (= la fila)
    let nodo = a;
    while (nodo.parentElement && nodo.parentElement !== dialogo &&
           usuariosEn(nodo.parentElement).size === 1) {
      nodo = nodo.parentElement;
    }
    if (!filas[usuario] || (nodo.innerText || '').length > filas[usuario].length) {
      filas[usuario] = nodo.innerText || '';
    }
  });
  return Object.entries(filas).map(([usuario, texto]) => ({usuario, texto}));
}
"""

JS_SCROLL = r"""
() => {
  const dialogo = document.querySelector('div[role="dialog"]');
  if (!dialogo) return false;
  let mejor = null;
  dialogo.querySelectorAll('div').forEach(d => {
    const o = getComputedStyle(d).overflowY;
    if ((o === 'auto' || o === 'scroll') && d.scrollHeight > d.clientHeight + 5) {
      if (!mejor || d.scrollHeight > mejor.scrollHeight) mejor = d;
    }
  });
  if (!mejor) return false;
  mejor.scrollTop = mejor.scrollHeight;
  return true;
}
"""


# ---------------- Utilidades ----------------
def pausa(minimo=1.5, maximo=3):
    return random.randint(int(minimo * 1000), int(maximo * 1000))


def limpiar_conexion(usuario, texto):
    """Convierte una fila cruda del modal en un registro limpio."""
    usuario = (usuario or "").strip().lower()
    if not usuario or usuario in RESERVADOS:
        return None
    lineas = [l.strip() for l in (texto or "").split("\n") if l.strip()]
    candidatos = [
        l for l in lineas
        if l.lower() != usuario and l.lower() not in ETIQUETAS
    ]
    nombre = re.sub(r"\s+", " ", candidatos[0]).strip() if candidatos else ""
    return {
        "usuario": usuario,
        "nombre": nombre,
        "tiene_nombre": "Sí" if nombre else "No",
        "url": f"https://www.instagram.com/{usuario}/",
    }


# ---------------- Extracción ----------------
def _hay_dialogo(pagina, espera=4000):
    try:
        pagina.wait_for_selector('div[role="dialog"]', timeout=espera)
        return True
    except Exception:
        return False


def _guardar_diagnostico(pagina, tipo):
    """Guarda captura y HTML de la cabecera para ver qué encontró el script."""
    try:
        pagina.screenshot(path=f"debug_{tipo}.png")
        with open(f"debug_{tipo}.html", "w", encoding="utf-8") as f:
            f.write(pagina.locator("header").first.evaluate("e => e.outerHTML"))
        hrefs = pagina.eval_on_selector_all(
            "header a", "els => els.map(e => e.getAttribute('href'))")
        print(f"  Enlaces dentro del header: {hrefs}")
        print(f"  Diagnóstico guardado: debug_{tipo}.png y debug_{tipo}.html")
    except Exception as e:
        print(f"  (no se pudo guardar el diagnóstico: {str(e).splitlines()[0]})")


def abrir_modal(pagina, usuario, tipo):
    """Abre el modal de 'followers' o 'following' probando varias estrategias."""
    pagina.keyboard.press("Escape")  # cierra cualquier aviso que tape la página
    if tipo == "followers":
        texto = re.compile(r"\d[\d.,\s]*[KkMm]?\s*(seguidores|followers)", re.I)
    else:
        texto = re.compile(r"\d[\d.,\s]*[KkMm]?\s*(seguidos|siguiendo|following)", re.I)

    candidatos = [
        pagina.locator(f'a[href="/{usuario}/{tipo}/"]'),
        pagina.locator(f'a[href*="/{tipo}"]'),
        pagina.locator("header").get_by_text(texto),
        pagina.get_by_text(texto),
    ]
    for loc in candidatos:
        try:
            if loc.count() == 0:
                continue
            elemento = loc.first
            for modo in ("normal", "js"):
                try:
                    if modo == "normal":
                        elemento.click(timeout=3000)
                    else:
                        elemento.evaluate("e => e.click()")
                except Exception:
                    continue
                if _hay_dialogo(pagina):
                    return
        except Exception:
            continue

    _guardar_diagnostico(pagina, tipo)
    raise RuntimeError(f"No se pudo abrir el modal de {tipo}")


def extraer_lista(pagina, usuario_propio, tipo, esperado):
    """Abre el modal ('followers' o 'following'), hace scroll y devuelve las filas limpias."""
    abrir_modal(pagina, usuario_propio, tipo)
    pagina.wait_for_timeout(pausa(2, 3))

    encontrados = {}
    sin_progreso = scrolls = 0
    propio = usuario_propio.lower()

    while sin_progreso < MAX_SIN_PROGRESO and scrolls < MAX_SCROLLS:
        antes = len(encontrados)
        for fila in pagina.evaluate(JS_FILAS):
            reg = limpiar_conexion(fila["usuario"], fila["texto"])
            if reg and reg["usuario"] != propio and reg["usuario"] not in encontrados:
                encontrados[reg["usuario"]] = reg

        sin_progreso = sin_progreso + 1 if len(encontrados) == antes else 0
        print(f"  {tipo}: {len(encontrados)}" + (f"/{esperado}" if esperado else ""))

        if esperado and len(encontrados) >= esperado:
            break
        if LIMITE_CONEXIONES and len(encontrados) >= LIMITE_CONEXIONES:
            break

        pagina.evaluate(JS_SCROLL)
        pagina.wait_for_timeout(pausa())
        scrolls += 1

    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(pausa(1, 2))

    lista = list(encontrados.values())
    return lista[:LIMITE_CONEXIONES] if LIMITE_CONEXIONES else lista


def extraer_conexiones(pagina, usuario, perfil=None):
    """Extrae seguidores y seguidos. `perfil` (opcional) trae los totales declarados."""
    resultado = {}
    for tipo, clave in (("followers", "seguidores"), ("following", "seguidos")):
        print(f"\nExtrayendo {clave}...")
        pagina.goto(f"https://www.instagram.com/{usuario}/")
        pagina.wait_for_selector("header", timeout=20000)
        pagina.wait_for_timeout(pausa(2, 4))

        esperado = (perfil or {}).get(clave)
        try:
            filas, error = extraer_lista(pagina, usuario, tipo, esperado), None
        except Exception as e:
            filas, error = [], str(e).splitlines()[0]
            print(f"  ERROR extrayendo {clave}: {error}")
        resultado[clave] = {"filas": filas, "esperado": esperado, "error": error}
        pagina.wait_for_timeout(pausa(3, 6))
    return resultado


# ---------------- Tratamiento y exportación ----------------
COLUMNAS_BASE = ["usuario", "nombre", "tiene_nombre", "url"]


def _tabla(filas, columna_cruce, otros):
    df = pd.DataFrame(filas, columns=COLUMNAS_BASE)
    df = df.sort_values("usuario").reset_index(drop=True)
    df.insert(0, "n", df.index + 1)
    df[columna_cruce] = df["usuario"].map(lambda u: "Sí" if u in otros else "No")
    return df


def exportar_conexiones(usuario, datos):
    """Genera el documento de seguidores y seguidos (xlsx + json + 2 csv)."""
    filas_seg = datos["seguidores"]["filas"]
    filas_sig = datos["seguidos"]["filas"]
    if not filas_seg and not filas_sig:
        print("\nNo se extrajeron seguidores ni seguidos; no se generaron archivos.")
        return None

    set_seguidores = {f["usuario"] for f in filas_seg}
    set_seguidos = {f["usuario"] for f in filas_sig}

    df_seguidores = _tabla(filas_seg, "lo_sigo", set_seguidos)
    df_seguidos = _tabla(filas_sig, "me_sigue", set_seguidores)
    df_no_siguen = df_seguidos[df_seguidos["me_sigue"] == "No"].drop(columns="n")
    df_no_siguen = df_no_siguen.reset_index(drop=True)
    df_no_siguen.insert(0, "n", df_no_siguen.index + 1)

    def completo(clave):
        esp, ext = datos[clave]["esperado"], len(datos[clave]["filas"])
        if datos[clave]["error"]:
            return "No (error)"
        if esp is None:
            return "Sin dato"
        return "Sí" if ext >= esp else f"No ({ext} de {esp})"

    ambas_completas = completo("seguidores") == "Sí" and completo("seguidos") == "Sí"
    resumen = {
        "usuario": usuario,
        "fecha_extraccion": datetime.now(ZONA).strftime("%Y-%m-%d %H:%M"),
        "seguidores_declarados": datos["seguidores"]["esperado"],
        "seguidores_extraidos": len(filas_seg),
        "seguidores_lista_completa": completo("seguidores"),
        "seguidos_declarados": datos["seguidos"]["esperado"],
        "seguidos_extraidos": len(filas_sig),
        "seguidos_lista_completa": completo("seguidos"),
        "mutuos": len(set_seguidores & set_seguidos),
        "solo_me_siguen": len(set_seguidores - set_seguidos),
        "solo_los_sigo": len(set_seguidos - set_seguidores),
        "cruce_confiable": "Sí" if ambas_completas else "No (alguna lista quedó incompleta)",
        "errores": {k: datos[k]["error"] for k in datos if datos[k]["error"]},
    }

    # JSON
    with open(SALIDA_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "resumen": resumen,
            "seguidores": json.loads(df_seguidores.to_json(orient="records", force_ascii=False)),
            "seguidos": json.loads(df_seguidos.to_json(orient="records", force_ascii=False)),
        }, f, ensure_ascii=False, indent=2)

    # CSV (uno por lista)
    df_seguidores.to_csv(SALIDA_CSV_SEGUIDORES, index=False,
                         encoding="utf-8-sig", quoting=csv.QUOTE_NONNUMERIC)
    df_seguidos.to_csv(SALIDA_CSV_SEGUIDOS, index=False,
                       encoding="utf-8-sig", quoting=csv.QUOTE_NONNUMERIC)

    # Excel: Resumen + Seguidores + Seguidos + No me siguen de vuelta
    df_resumen = pd.DataFrame(
        [(k.replace("_", " ").capitalize(), str(v) if isinstance(v, dict) else v)
         for k, v in resumen.items()],
        columns=["Campo", "Valor"],
    )
    with pd.ExcelWriter(SALIDA_XLSX, engine="openpyxl") as w:
        df_resumen.to_excel(w, index=False, sheet_name="Resumen")
        df_seguidores.to_excel(w, index=False, sheet_name="Seguidores")
        df_seguidos.to_excel(w, index=False, sheet_name="Seguidos")
        df_no_siguen.to_excel(w, index=False, sheet_name="No me siguen de vuelta")
        for nombre, hoja in w.sheets.items():
            for col in hoja.columns:
                ancho = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                hoja.column_dimensions[col[0].column_letter].width = min(ancho + 2, 60)
            hoja.freeze_panes = "A2"
            if nombre != "Resumen":
                hoja.auto_filter.ref = hoja.dimensions

    print("\n--- SEGUIDORES Y SEGUIDOS ---")
    for k, v in resumen.items():
        print(f"{k}: {v}")
    print(f"\nArchivos generados: {SALIDA_XLSX}, {SALIDA_JSON}, "
          f"{SALIDA_CSV_SEGUIDORES}, {SALIDA_CSV_SEGUIDOS}")
    return resumen


# ---------------- Modo independiente ----------------
def main():
    from playwright.sync_api import sync_playwright
    from scraper import USUARIO
    from sesion_util import abrir_con_sesion

    with sync_playwright() as p:
        navegador, contexto, pagina = abrir_con_sesion(p)
        datos = extraer_conexiones(pagina, USUARIO)
        navegador.close()
    exportar_conexiones(USUARIO, datos)


if __name__ == "__main__":
    main()
