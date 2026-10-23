import json
import re
from zoneinfo import ZoneInfo

import pandas as pd

ZONA = ZoneInfo("America/Guayaquil")  # zona horaria de Ecuador (UTC-5)


def a_entero(texto):
    """Convierte '16', '1.234', '1,2 K' o '3 M' en un número entero."""
    if texto is None:
        return None
    t = str(texto).strip().upper().replace(" ", "")
    multiplicador = 1
    if t.endswith("K"):
        multiplicador, t = 1_000, t[:-1]
    elif t.endswith("M"):
        multiplicador, t = 1_000_000, t[:-1]

    if multiplicador > 1:
        try:
            return int(float(t.replace(",", ".")) * multiplicador)
        except ValueError:
            return None

    t = re.sub(r"[.,]", "", t)  # quita separadores de miles
    return int(t) if t.isdigit() else None


# 1. Leer el archivo CRUDO (nunca se modifica)
with open("datos_completos.json", encoding="utf-8") as f:
    crudo = json.load(f)

# 2. Perfil limpio: solo los campos útiles, con números reales
perfil = {
    "usuario": crudo["usuario"],
    "nombre": crudo["nombre"],
    "publicaciones": a_entero(crudo["publicaciones"]),
    "seguidores": a_entero(crudo["seguidores"]),
    "seguidos": a_entero(crudo["seguidos"]),
    "biografia": crudo["biografia"],
}

# 3. Publicaciones limpias
filas = []
for p in crudo["publicaciones_detalle"]:
    fecha = pd.to_datetime(p["fecha"], utc=True, errors="coerce")
    hay_fecha = pd.notna(fecha)
    if hay_fecha:
        fecha = fecha.tz_convert(ZONA)

    codigo = re.search(r"/(?:p|reel)/([^/]+)/", p["url"])
    descripcion = (p["descripcion"] or "").strip()

    filas.append({
        "codigo": codigo.group(1) if codigo else None,
        "tipo": p["tipo"],
        "fecha": fecha.strftime("%Y-%m-%d") if hay_fecha else None,
        "hora": fecha.strftime("%H:%M") if hay_fecha else None,
        "anio": fecha.year if hay_fecha else None,
        "likes": a_entero(p["likes"]),
        "comentarios": a_entero(p["comentarios"]),
        "descripcion": descripcion,
        "tiene_descripcion": "Sí" if descripcion else "No",
        "url": p["url"],
    })

df = pd.DataFrame(filas)
df[["anio", "likes", "comentarios"]] = df[["anio", "likes", "comentarios"]].astype("Int64")
df = df.sort_values(["fecha", "hora"], na_position="last").reset_index(drop=True)
df.insert(0, "n", df.index + 1)

# 4. Guardar los archivos limpios
with open("perfil_limpio.json", "w", encoding="utf-8") as f:
    json.dump(perfil, f, ensure_ascii=False, indent=2)

df.to_csv("publicaciones_limpias.csv", index=False, encoding="utf-8-sig")

with pd.ExcelWriter("publicaciones_limpias.xlsx", engine="openpyxl") as escritor:
    df.to_excel(escritor, index=False, sheet_name="Publicaciones")
    hoja = escritor.sheets["Publicaciones"]
    for columna in hoja.columns:
        ancho = max(len(str(c.value)) if c.value is not None else 0 for c in columna)
        hoja.column_dimensions[columna[0].column_letter].width = min(ancho + 2, 60)
    hoja.freeze_panes = "A2"

# 5. Resumen
print("Perfil:", perfil)
print(f"\nPublicaciones limpias: {len(df)}")
print(f"Con descripción: {(df['tiene_descripcion'] == 'Sí').sum()}")
print(f"Likes (promedio): {df['likes'].mean():.1f}")
print("\n", df.drop(columns=["url"]).to_string(index=False))