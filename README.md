# Scraping de Instagram → Embeddings (Gemini) → Perfil Big Five

Proyecto académico. **Solo se debe usar con cuentas cuya titular haya dado su autorización.**
Los datos recolectados quedan en `datos/` (excluida de Git) y nunca se suben a GitHub.

## Estructura

```
├── main.py                    único punto de entrada
├── .env  (.env.example)       API key de Gemini, modelos y perfil por defecto
├── requirements.txt
├── src/
│   ├── config.py              rutas, .env, modelos
│   ├── scraping/              scraper.py · conexiones.py · sesion_util.py · guardar_sesion.py
│   ├── embeddings/            embeddings.py       (vectores con Gemini)
│   ├── gemini/                cliente.py          (API key / cliente)
│   └── analisis/              cargador.py · privacidad.py · bigfive.py
├── datos/<usuario>/
│   ├── raw/                   lo recolectado: JSON, CSV, Excel, imagenes/
│   ├── embeddings/            embeddings.npy, metadatos.json
│   └── resultados/            perfil_bigfive.json
└── legacy/                    scripts y datos de versiones anteriores
```

## Instalación

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
copy .env.example .env      # y completa GEMINI_API_KEY
```

## Uso

```powershell
python main.py sesion                  # una vez (o si caduca): guarda tu sesión de Instagram
python main.py scrape usuario          # scraping + imágenes -> datos/usuario/raw/
python main.py analizar usuario        # embeddings + Big Five -> datos/usuario/
python main.py todo usuario            # las dos cosas
```

Opciones: `--si` (sin confirmación) · `--sin-imagenes` · `--conexiones` (seguidores/seguidos) · `--limite N` · `--forzar` (regenera embeddings).
Si omites `usuario` se usa `INSTAGRAM_TARGET` del `.env`.

## Flujo

1. **Scraping:** publicaciones (fecha, likes, descripción, imagen) del perfil indicado.
2. **Embeddings:** biografía y descripciones se anonimizan (correos, teléfonos, enlaces) y se vectorizan con `gemini-embedding-001`.
3. **Big Five:** se recupera la evidencia por rasgo y Gemini estima puntaje y confianza de cada rasgo OCEAN, con un tope de confianza según la cantidad de texto.

## Limitaciones y ética

- El resultado es una **estimación exploratoria**, no una medición psicológica válida.
- Requiere consentimiento de la titular; respeta los términos de uso de Instagram y la Ley de Protección de Datos Personales.
- No se recolectan comentarios de terceros.
