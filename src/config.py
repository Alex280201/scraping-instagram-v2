"""Configuración central: rutas, variables del .env (API key, modelos) y carpetas por usuario."""
import os
from dotenv import load_dotenv

from src import corridas

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# ---------------- API de Gemini ----------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_MODEL_RESPALDO = os.getenv("GEMINI_MODEL_RESPALDO", "")  # opcional, si el principal está saturado
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
if GEMINI_EMBEDDING_MODEL in ("text-embedding-004", "embedding-001", "models/text-embedding-004"):
    print(f"[Config] AVISO: '{GEMINI_EMBEDDING_MODEL}' está dado de baja; se usa gemini-embedding-001. "
          "Actualiza GEMINI_EMBEDDING_MODEL en tu .env.")
    GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"

# ---------------- Instagram ----------------
INSTAGRAM_TARGET = os.getenv("INSTAGRAM_TARGET", "")
ARCHIVO_SESION = os.path.join(ROOT_DIR, "sesion.json")        # privado (en .gitignore)
PERFIL_CHROME = os.path.join(ROOT_DIR, ".chrome_perfil")      # privado (en .gitignore)

# ---------------- Datos ----------------
DATOS_DIR = os.path.join(ROOT_DIR, "datos")


def normalizar_usuario(usuario):
    return (usuario or "").strip().lstrip("@").lower()


def resolver_usuario(argumento=None):
    """Perfil a procesar: argumento de consola > INSTAGRAM_TARGET del .env."""
    usuario = normalizar_usuario(argumento or INSTAGRAM_TARGET)
    if not usuario or usuario == "usuario_objetivo":
        raise SystemExit("Indica el perfil:  python main.py <comando> <usuario>   o define INSTAGRAM_TARGET en el .env")
    return usuario


class Rutas:
    """Carpetas y archivos de un usuario:  datos/<usuario>/<corrida>/{raw, embeddings, resultados, seguidores}"""

    def __init__(self, usuario, corrida=None):
        self.usuario = usuario
        self.corrida_nombre = corrida
        if corrida:
            base = os.path.join(DATOS_DIR, usuario, corrida)
            if not os.path.isdir(base):
                # intenta buscarla
                encontrada = corridas.buscar_corrida(usuario, corrida)
                if encontrada:
                    base = encontrada
            self.base = base
        else:
            encontrada = corridas.buscar_corrida(usuario)
            if encontrada:
                self.base = encontrada
            else:
                self.base = os.path.join(DATOS_DIR, usuario)
        self.raw = os.path.join(self.base, "raw")                 # lo recolectado por el scraping
        self.imagenes = os.path.join(self.raw, "imagenes")
        self.embeddings = os.path.join(self.base, "embeddings")   # vectores generados con Gemini
        self.resultados = os.path.join(self.base, "resultados")   # perfil Big Five
        self.seguidores = os.path.join(self.base, "seguidores")
        self.datos_json = os.path.join(self.raw, "instagram_datos.json")
        self.datos_csv = os.path.join(self.raw, "instagram_publicaciones.csv")
        self.datos_xlsx = os.path.join(self.raw, "instagram_publicaciones.xlsx")
        self.conexiones_json = os.path.join(self.raw, "instagram_conexiones.json")
        self.emb_npy = os.path.join(self.embeddings, "embeddings.npy")
        self.emb_meta = os.path.join(self.embeddings, "metadatos.json")
        self.bigfive_json = os.path.join(self.resultados, "perfil_bigfive.json")

    def crear(self):
        for carpeta in (self.raw, self.embeddings, self.resultados, self.seguidores):
            os.makedirs(carpeta, exist_ok=True)
        return self


def rutas_usuario(usuario, corrida=None):
    return Rutas(usuario, corrida=corrida)
