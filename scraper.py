"""Scraper todo-en-uno: perfil + publicaciones -> datos limpios en JSON, CSV y Excel.

Uso:
    python guardar_sesion.py   (solo cuando no hay sesión o caducó)
    python scraper.py
"""
import csv
import json
import random
import re
from zoneinfo import ZoneInfo

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from conexiones import exportar_conexiones, extraer_conexiones
from sesion_util import abrir_con_sesion

# ---------------- Configuración ----------------
USUARIO = "sausage_player"
EXTRAER_CONEXIONES = True   # True = también extrae seguidores y seguidos (documento aparte)
LIMITE = None          # None = todas las publicaciones; o un número para probar (ej. 5)
MAX_ENLACES = 500      # tope de seguridad al hacer scroll
ZONA = ZoneInfo("America/Guayaquil")  # Ecuador (UTC-5)

SALIDA_JSON = "instagram_datos.json"
SALIDA_CSV = "instagram_publicaciones.csv"
SALIDA_XLSX = "instagram_publicaciones.xlsx"


# ---------------- Utilidades ----------------
def pausa(minimo=2, maximo=4):
    return random.randint(minimo * 1000, maximo * 1000)


def a_entero(texto):
    """Convierte '16', '1.234', '1,2 K' o '3 M' en un entero."""
    if texto is None:
        return None
    t = str(texto).strip().upper().replace(" ", "")
    mult = 1
    if t.endswith("K"):
        mult, t = 1_000, t[:-1]
    elif t.endswith("M"):
        mult, t = 1_000_000, t[:-1]
    if mult > 1:
        try:
            return int(float(t.replace(",", ".")) * mult)
        except ValueError:
            return None
    t = re.sub(r"[.,]", "", t)
    return int(t) if t.isdigit() else None


# ---------------- Extracción ----------------
def parsear_cabecera(texto_cabecera, usuario):
    """Convierte el texto visible de la cabecera del perfil en datos limpios."""
    lineas = [l.strip() for l in texto_cabecera.split("\n") if l.strip()]

    def numero(patron):
        for l in lineas:
            m = re.match(r"^([\d.,]+\s?[KMkm]?)\s+(?:" + patron + r")$", l, re.IGNORECASE)
            if m:
                return a_entero(m.group(1))
        return None

    bio, despues = [], False
    for l in lineas:
        if re.search(r"(seguidos|siguiendo|following)$", l, re.IGNORECASE):
            despues = True
            continue
        if despues:
            if l in ("Seguir", "Siguiendo", "Mensaje", "Destacada", "Follow", "Message"):
                break
            bio.append(l)

    return {
        "usuario": usuario,
        "nombre": lineas[1] if len(lineas) > 1 else None,
        "publicaciones": numero(r"publicaciones|posts"),
        "seguidores": numero(r"seguidores|followers"),
        "seguidos": numero(r"seguidos|siguiendo|following"),
        "biografia": "\n".join(bio),
    }


def extraer_perfil_y_enlaces(pagina):
    pagina.goto(f"https://www.instagram.com/{USUARIO}/")
    pagina.wait_for_selector("header", timeout=20000)
    pagina.wait_for_timeout(pausa())

    perfil = parsear_cabecera(pagina.locator("header").inner_text(), USUARIO)

    enlaces, sin_cambios = set(), 0
    while sin_cambios < 3 and len(enlaces) < MAX_ENLACES:
        hrefs = pagina.eval_on_selector_all(
            'a[href*="/p/"], a[href*="/reel/"]',
            "els => els.map(e => e.getAttribute('href'))",
        )
        antes = len(enlaces)
        enlaces.update(h for h in hrefs if h)
        sin_cambios = sin_cambios + 1 if len(enlaces) == antes else 0
        pagina.mouse.wheel(0, 2500)
        pagina.wait_for_timeout(pausa())
        print(f"Publicaciones encontradas: {len(enlaces)}")
    return perfil, sorted(enlaces)


def extraer_publicacion(pagina, href):
    url = "https://www.instagram.com" + href
    pagina.goto(url)
    pagina.wait_for_selector("time", timeout=15000)
    pagina.wait_for_timeout(pausa(1, 2))

    soup = BeautifulSoup(pagina.content(), "lxml")
    og = soup.find("meta", property="og:description")
    og_texto = og["content"] if og else ""
    tiempo = soup.find("time")
    imagen = soup.find("meta", property="og:image")
    return {
        "url": url,
        "href": href,
        "fecha_iso": tiempo["datetime"] if tiempo and tiempo.has_attr("datetime") else None,
        "og_texto": og_texto,
        "imagen": imagen["content"] if imagen else None,
    }


# ---------------- Limpieza ----------------
def limpiar_publicacion(crudo):
    og = crudo["og_texto"]
    likes = re.search(r"([\d.,]+\s?[KMkm]?)\s+(?:likes?|me gusta)", og, re.IGNORECASE)
    coment = re.search(r"([\d.,]+\s?[KMkm]?)\s+(?:comments?|comentarios)", og, re.IGNORECASE)
    desc = re.search(r':\s*[“"](.*)[”"]\.?\s*$', og, re.DOTALL)
    descripcion = (desc.group(1) if desc else "").strip()

    fecha = pd.to_datetime(crudo["fecha_iso"], utc=True, errors="coerce")
    hay = pd.notna(fecha)
    if hay:
        fecha = fecha.tz_convert(ZONA)

    codigo = re.search(r"/(?:p|reel)/([^/]+)/", crudo["url"])
    return {
        "codigo": codigo.group(1) if codigo else None,
        "tipo": "reel" if "/reel/" in crudo["href"] else "publicacion",
        "fecha": fecha.strftime("%Y-%m-%d") if hay else None,
        "hora": fecha.strftime("%H:%M") if hay else None,
        "anio": int(fecha.year) if hay else None,
        "likes": a_entero(likes.group(1)) if likes else None,
        "comentarios": a_entero(coment.group(1)) if coment else None,
        "descripcion": descripcion,
        "tiene_descripcion": "Sí" if descripcion else "No",
        "url": crudo["url"],
        "imagen": crudo["imagen"],
    }


# ---------------- Exportación ----------------
def exportar(perfil, publicaciones, errores):
    df = pd.DataFrame(publicaciones)
    df = df.sort_values(["fecha", "hora"], na_position="last").reset_index(drop=True)
    df.insert(0, "n", df.index + 1)
    for col in ("anio", "likes", "comentarios"):
        df[col] = df[col].astype("Int64")

    resumen = {
        "total_publicaciones_extraidas": int(len(df)),
        "con_descripcion": int((df["tiene_descripcion"] == "Sí").sum()),
        "likes_promedio": round(float(df["likes"].mean()), 1) if df["likes"].notna().any() else None,
        "primera_fecha": df["fecha"].min(),
        "ultima_fecha": df["fecha"].max(),
        "errores": errores,
    }

    # JSON organizado
    registros = json.loads(df.to_json(orient="records", force_ascii=False))
    with open(SALIDA_JSON, "w", encoding="utf-8") as f:
        json.dump({"perfil": perfil, "resumen": resumen, "publicaciones": registros},
                  f, ensure_ascii=False, indent=2)

    # CSV
    df.to_csv(SALIDA_CSV, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_NONNUMERIC)

    # Excel: hoja Perfil + hoja Publicaciones
    df_perfil = pd.DataFrame(
        [(k.replace("_", " ").capitalize(), v) for k, v in perfil.items()],
        columns=["Campo", "Valor"],
    )
    with pd.ExcelWriter(SALIDA_XLSX, engine="openpyxl") as w:
        df_perfil.to_excel(w, index=False, sheet_name="Perfil")
        df.to_excel(w, index=False, sheet_name="Publicaciones")
        for nombre, hoja in w.sheets.items():
            for col in hoja.columns:
                ancho = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                hoja.column_dimensions[col[0].column_letter].width = min(ancho + 2, 60)
            hoja.freeze_panes = "A2"
        w.sheets["Publicaciones"].auto_filter.ref = w.sheets["Publicaciones"].dimensions
    return df, resumen


# ---------------- Programa principal ----------------
def main():
    crudas, errores, conexiones = [], [], None
    with sync_playwright() as p:
        navegador, contexto, pagina = abrir_con_sesion(p)

        perfil, enlaces = extraer_perfil_y_enlaces(pagina)
        if LIMITE:
            enlaces = enlaces[:LIMITE]
        print(f"\nPerfil: {perfil['nombre']} | {perfil['seguidores']} seguidores | "
              f"{len(enlaces)} publicaciones a procesar\n")

        for i, href in enumerate(enlaces, 1):
            try:
                crudas.append(extraer_publicacion(pagina, href))
                print(f"[{i}/{len(enlaces)}] OK: {href}")
            except Exception as e:
                errores.append({"href": href, "error": str(e).splitlines()[0]})
                print(f"[{i}/{len(enlaces)}] ERROR en {href}: {str(e).splitlines()[0]}")
            pagina.wait_for_timeout(pausa(3, 6))

        # Seguidores y seguidos (misma sesión; si falla no se pierden las publicaciones)
        if EXTRAER_CONEXIONES:
            try:
                conexiones = extraer_conexiones(pagina, USUARIO, perfil)
            except Exception as e:
                print(f"\nERROR en seguidores/seguidos: {str(e).splitlines()[0]}")
        navegador.close()

    if conexiones:
        exportar_conexiones(USUARIO, conexiones)

    if not crudas:
        raise SystemExit("No se extrajo ninguna publicación; no se generaron archivos.")

    publicaciones = [limpiar_publicacion(c) for c in crudas]
    df, resumen = exportar(perfil, publicaciones, errores)

    print("\n--- PERFIL ---")
    for k, v in perfil.items():
        print(f"{k}: {v}")
    print("\n--- RESUMEN ---")
    for k, v in resumen.items():
        print(f"{k}: {v}")
    print(f"\nArchivos generados: {SALIDA_XLSX}, {SALIDA_JSON}, {SALIDA_CSV}")


if __name__ == "__main__":
    main()
