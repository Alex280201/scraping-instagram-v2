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
python main.py seguidores usuario      # lista de seguidores (usuario, nombre, foto) -> datos/usuario/raw/
python main.py contadores usuario      # seguidos/seguidores de cada seguidor de la lista (3 workers) -> raw/seguidores_contadores.json
python main.py excel usuario           # Excel de seguidores: foto, nombre, seguidos, seguidores y primer dígito (fórmula) -> raw/instagram_seguidores_stats.xlsx
python main.py benford usuario         # Ley de Benford + chi-cuadrada + MAD -> veredicto humano / posible bot / bot (resultados/benford.json)
python main.py completo usuario        # PRUEBA GLOBAL: publicaciones → seguidores → contadores → Benford → Excel → Big Five → informe
python main.py informe usuario         # informe final HTML: datos del perfil + Benford + Big Five (texto, sin gráfica) -> resultados/informe.html
python main.py analizar usuario        # embeddings + Big Five -> datos/usuario/
python main.py todo usuario            # las dos cosas
```

`seguidores` guarda el avance cada 20 usuarios; si Instagram corta o bloquea, repite el mismo comando y continúa donde quedó (`--reiniciar` empieza de cero, `--sin-fotos` omite las fotos).

`contadores` visita el perfil de cada seguidor de la lista (`--workers N`, por defecto 3 y máximo 6; `--limite N` para pruebas; `--ver` muestra el navegador). Se detiene solo si Instagram pide login/verificación, responde 429 o falla varias veces seguidas, y al repetir el comando continúa con los pendientes. Cada perfil queda como `ok`, `privado` (los contadores siguen siendo visibles), `no_existe` o `error` (se reintenta).

`benford` analiza el primer dígito del número de seguidores de los seguidores (solo perfiles `ok`/`privado` con seguidores > 0). Veredicto por valor p de la chi-cuadrada (8 g.l.): p ≥ 0.05 humano · 0.01 ≤ p < 0.05 posible bot · p < 0.01 bot. Funciona con cualquier cantidad de seguidores por cuenta (los de 1 a 9 seguidores cuentan con su propio número; solo los de 0 no tienen primer dígito y se cuentan aparte). Con 110 datos o más se usa la chi-cuadrada clásica; con 30 a 109 el valor p se calcula por simulación Monte Carlo (exacto para ese tamaño, pero con poca potencia: solo detecta desviaciones grandes); con menos de 30 no se da veredicto (`--minimo N` lo cambia). El MAD de Nigrini se muestra como control, referencial con menos de 1000 datos. `benford` también genera la gráfica (`resultados/benford.png` y `benford.html` interactivo, `--abrir` lo abre en el navegador, `--sin-grafica` la omite): barras = observado, línea roja = Benford, banda gris = rango del 95 % para una muestra de ese tamaño, panel inferior = diferencia en puntos porcentuales, y el veredicto con χ², p y MAD en el encabezado. El Excel (`excel`) incluye la hoja `Benford` con la misma prueba en fórmulas. El resultado describe a la audiencia en conjunto, no a cuentas individuales.

`completo` encadena todos los pasos (cada uno es reanudable; si Instagram corta, repite el mismo comando). `--sin-publicaciones` omite el scraping de publicaciones y el Big Five, `--sin-bigfive` solo el Big Five, `--limite N` limita los seguidores capturados. El Big Five del informe es texto y tabla; `--radar` añade un gráfico radar si se necesita.

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
