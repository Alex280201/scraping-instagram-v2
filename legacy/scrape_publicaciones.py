import csv
import json
import random
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

from sesion_util import abrir_con_sesion

LIMITE = None


def pausa(minimo=3, maximo=6):
    return random.randint(minimo * 1000, maximo * 1000)


with open("datos_perfil.json", encoding="utf-8") as f:
    perfil = json.load(f)

# 1. Limpiar los datos del perfil usando la cabecera visible
lineas = [l.strip() for l in perfil["texto_cabecera"].split("\n") if l.strip()]


def numero(sufijo):
    for l in lineas:
        m = re.match(r"^([\d.,]+\s?[KMkm]?)\s+" + sufijo, l, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


bio = []
despues = False
for l in lineas:
    if re.search(r"seguidos$", l, re.IGNORECASE):
        despues = True
        continue
    if despues:
        if l in ("Seguir", "Siguiendo", "Mensaje", "Destacada"):
            break
        bio.append(l)

perfil["nombre"] = lineas[1] if len(lineas) > 1 else None
perfil["publicaciones"] = numero("publicaciones")
perfil["seguidores"] = numero("seguidores")
perfil["seguidos"] = numero("seguidos")
perfil["biografia"] = "\n".join(bio)
perfil.pop("descripcion_meta", None)
perfil.pop("texto_cabecera", None)

# 2. Entrar a cada publicación
enlaces = perfil["enlaces_publicaciones"]
if LIMITE:
    enlaces = enlaces[:LIMITE]

publicaciones = []

with sync_playwright() as p:
    navegador, contexto, pagina = abrir_con_sesion(p)

    for i, href in enumerate(enlaces, 1):
        url = "https://www.instagram.com" + href
        try:
            pagina.goto(url)
            pagina.wait_for_selector("time", timeout=15000)
            pagina.wait_for_timeout(pausa(1, 2))

            soup = BeautifulSoup(pagina.content(), "lxml")
            og = soup.find("meta", property="og:description")
            og_texto = og["content"] if og else ""
            tiempo = soup.find("time")
            imagen = soup.find("meta", property="og:image")

            likes = re.search(r"([\d.,]+\s?[KMkm]?)\s+(?:likes?|me gusta)", og_texto, re.IGNORECASE)
            comentarios = re.search(r"([\d.,]+\s?[KMkm]?)\s+(?:comments?|comentarios)", og_texto, re.IGNORECASE)
            descripcion = re.search(r':\s*[“"](.*)[”"]\.?\s*$', og_texto, re.DOTALL)

            publicaciones.append({
                "url": url,
                "tipo": "reel" if "/reel/" in href else "publicacion",
                "fecha": tiempo["datetime"] if tiempo and tiempo.has_attr("datetime") else None,
                "likes": likes.group(1) if likes else None,
                "comentarios": comentarios.group(1) if comentarios else None,
                "descripcion": descripcion.group(1) if descripcion else None,
                "imagen": imagen["content"] if imagen else None,
                "meta_original": og_texto,
            })
            print(f"[{i}/{len(enlaces)}] OK: {url}")
        except Exception as e:
            print(f"[{i}/{len(enlaces)}] ERROR en {url}: {e}")

        pagina.wait_for_timeout(pausa())

    navegador.close()

# 3. Guardar resultados
perfil["publicaciones_detalle"] = publicaciones
with open("datos_completos.json", "w", encoding="utf-8") as f:
    json.dump(perfil, f, ensure_ascii=False, indent=2)

if publicaciones:
    with open("publicaciones.csv", "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=publicaciones[0].keys())
        escritor.writeheader()
        escritor.writerows(publicaciones)

print("\n--- PERFIL ---")
for k in ("usuario", "nombre", "publicaciones", "seguidores", "seguidos", "biografia"):
    print(f"{k}: {perfil[k]}")
print(f"\nPublicaciones extraídas: {len(publicaciones)}")