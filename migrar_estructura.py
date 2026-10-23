"""Se ejecuta UNA sola vez:  python migrar_estructura.py
Mueve los archivos antiguos a legacy/ y reorganiza datos/<usuario>/ en raw / embeddings / resultados.
No borra nada: todo se mueve (puedes revertir con git).
"""
import os
import shutil

RAIZ = os.path.dirname(os.path.abspath(__file__))
LEGACY = os.path.join(RAIZ, "legacy")
LEGACY_DATOS = os.path.join(LEGACY, "datos_antiguos")

SCRIPTS_VIEJOS = ["scraper.py", "conexiones.py", "sesion_util.py", "guardar_sesion.py", "perfil.py",
                  "scrape_perfil.py", "scrape_publicaciones.py", "depurar_datos.py", "prueba.py"]
DATOS_VIEJOS = ["datos_completos.json", "datos_perfil.json", "perfil_limpio.json", "perfil.html",
                "instagram_datos.json", "instagram_conexiones.json", "instagram_conexiones.xlsx",
                "instagram_publicaciones.csv", "instagram_publicaciones.xlsx", "instagram_seguidores.csv",
                "instagram_seguidos.csv", "publicaciones.csv", "publicaciones_limpias.csv",
                "publicaciones_limpias.xlsx"]
# por usuario: archivo/carpeta -> subcarpeta destino
POR_USUARIO = {
    "instagram_datos.json": "raw", "instagram_publicaciones.csv": "raw", "instagram_publicaciones.xlsx": "raw",
    "instagram_conexiones.json": "raw", "instagram_conexiones.xlsx": "raw", "instagram_seguidores.csv": "raw",
    "instagram_seguidos.csv": "raw", "imagenes": "raw",
    "embeddings.npy": "embeddings", "metadatos.json": "embeddings",
    "perfil_bigfive.json": "resultados",
}


def mover(origen, destino_dir):
    if not os.path.exists(origen):
        return False
    os.makedirs(destino_dir, exist_ok=True)
    destino = os.path.join(destino_dir, os.path.basename(origen))
    if os.path.exists(destino):
        base, ext = os.path.splitext(destino)
        destino = f"{base}_anterior{ext}"
    shutil.move(origen, destino)
    print(f"  {os.path.relpath(origen, RAIZ)}  ->  {os.path.relpath(destino, RAIZ)}")
    return True


def main():
    if not os.path.isdir(os.path.join(RAIZ, "src")):
        raise SystemExit("No encuentro la carpeta src/. Extrae primero el zip en la raíz del proyecto.")

    print("Scripts antiguos -> legacy/")
    for n in SCRIPTS_VIEJOS:
        mover(os.path.join(RAIZ, n), LEGACY)
    carpeta_analisis = os.path.join(RAIZ, "analisis")
    if os.path.isdir(carpeta_analisis):
        mover(carpeta_analisis, LEGACY)

    print("Datos sueltos de la raíz -> legacy/datos_antiguos/")
    for n in DATOS_VIEJOS:
        mover(os.path.join(RAIZ, n), LEGACY_DATOS)

    print("Carpetas datos/<usuario>/ -> raw / embeddings / resultados")
    datos = os.path.join(RAIZ, "datos")
    if os.path.isdir(datos):
        for usuario in sorted(os.listdir(datos)):
            carpeta = os.path.join(datos, usuario)
            if not os.path.isdir(carpeta):
                continue
            for nombre, sub in POR_USUARIO.items():
                mover(os.path.join(carpeta, nombre), os.path.join(carpeta, sub))

    gi = os.path.join(RAIZ, ".gitignore")
    texto = open(gi, encoding="utf-8").read() if os.path.exists(gi) else ""
    nuevas = [l for l in ("datos/", "legacy/datos_antiguos/", "sesion.json", ".chrome_perfil/", ".env", "venv/")
              if l not in texto.splitlines()]
    if nuevas:
        with open(gi, "a", encoding="utf-8") as f:
            f.write("\n# Privado: datos de personas, sesión y credenciales\n" + "\n".join(nuevas) + "\n")
        print("Agregado a .gitignore:", ", ".join(nuevas))

    print("\nListo. Prueba con:  python main.py analizar <usuario>")
    print("Cuando confirmes que todo funciona puedes borrar este archivo (migrar_estructura.py).")


if __name__ == "__main__":
    main()
