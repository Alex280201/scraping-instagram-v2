# 📊 Auditoría y Análisis Modular de Instagram (v2)

Proyecto académico de arquitectura de software para la auditoría y análisis avanzado de cuentas de Instagram. El sistema integra un pipeline modular que combina web scraping persistente, análisis estadístico forense mediante la **Ley de Benford** (para detección de anomalías y crecimiento artificial de audiencias), procesamiento de lenguaje natural con **Embeddings**, evaluación psicométrica automatizada (**Big Five / OCEAN**) y la generación automática de un **mini-sitio web interactivo**.

> **Nota ética:** Proyecto académico. Solo se debe utilizar con cuentas cuya titular haya dado su autorización explícita. Los datos recolectados se almacenan localmente en la carpeta `datos/` (excluida del control de versiones mediante `.gitignore`) y nunca se suben al repositorio público.

---

## 🏗️ Arquitectura y Estructura del Proyecto

```text
scraping-instagram-v2/
│
├── src/
│   ├── analisis/       # Módulo psicométrico Big Five, cargador de textos y privacidad
│   ├── benford/        # Análisis estadístico de la Ley de Benford y graficador interactivo
│   ├── embeddings/     # Generación y gestión de vectores semánticos con Gemini
│   ├── exportar/       # Generadores de reportes en Excel y mini-sitio web HTML
│   ├── scraping/       # Scrapers de perfil, publicaciones, seguidores y contadores
│   └── pipeline.py     # Orquestador principal del flujo end-to-end
│
├── datos/              # Almacenamiento local de perfiles, raw, embeddings y resultados (.gitignore)
├── legacy/             # Scripts y respaldos de versiones anteriores
├── tests/              # Pruebas unitarias y validación de corridas
├── main.py             # Único punto de entrada centralizado (CLI)
├── requirements.txt    # Dependencias de Python
└── .env.example        # Plantilla de configuración de variables de entorno

```

---

## ⚙️ Instalación y Configuración

1. **Clonar el repositorio:**
```bash
git clone https://github.com/Alex280201/scraping-instagram-v2.git
cd scraping-instagram-v2

```


2. **Crear y activar el entorno virtual:**
```bash
python -m venv venv
# En Windows (PowerShell):
.\venv\Scripts\Activate.ps1

```


3. **Instalar dependencias y navegadores:**
```bash
pip install -r requirements.txt
playwright install chromium

```


4. **Configurar variables de entorno:**
```bash
copy .env.example .env

```


*(Abre el archivo `.env` resultante y configura tu clave `GEMINI_API_KEY` y los parámetros del objetivo).*

---

## 🚀 Guía de Uso (CLI Centralizada en `main.py`)

El sistema se opera mediante comandos modulares desde la terminal:

```powershell
python main.py sesion                  # Configura y guarda la sesión persistente de Instagram
python main.py scrape usuario          # Scraping de publicaciones, métricas e imágenes
python main.py seguidores usuario      # Extracción de la lista completa de seguidores
python main.py contadores usuario      # Análisis de seguidos/seguidores por cada seguidor (soporta workers)
python main.py excel usuario           # Genera reporte Excel con estadísticas y fórmula de primer dígito
python main.py benford usuario         # Aplica la Ley de Benford (Chi-cuadrada, simulación Monte Carlo, MAD)
python main.py informe usuario --abrir # Genera y abre el mini-sitio web HTML con radar interactivo del Big Five
python main.py analizar usuario        # Ejecuta la vectorización de textos y la evaluación Big Five (OCEAN)
python main.py completo usuario        # Ejecuta el pipeline global encadenado de todos los módulos

```

---

## 🔍 Descripción Detallada de Módulos

1. **Scraping y Conexiones (`src/scraping/`):**
Extracción automatizada y resiliente de perfiles, publicaciones e interacciones mediante Playwright con soporte para sesiones persistentes y mecanismos de recuperación ante bloqueos temporales.
2. **Ley de Benford (`src/benford/`):**
Auditoría estadística sobre el primer dígito del conteo de seguidores para evaluar la autenticidad de la audiencia. Emplea pruebas de Chi-cuadrada clásica, simulación Monte Carlo para muestras medianas y la desviación MAD de Nigrini, generando gráficos interactivos detallados (`.html` y `.png`).
3. **Procesamiento y Embeddings (`src/embeddings/`):**
Anonimización y vectorización de biografías y descripciones de publicaciones para capturar patrones semánticos locales utilizando modelos de lenguaje avanzados.
4. **Perfil Psicométrico Big Five (`src/analisis/`):**
Estimación de los 5 grandes rasgos de la personalidad (Apertura, Responsabilidad, Extraordinariedad/Extraversión, Amabilidad y Neuroticismo) a partir de los textos del usuario, con un sistema inteligente de respaldo y reintentos ante limitaciones de API.
5. **Mini-sitio Web e Informes (`src/exportar/`):**
Consolidación de toda la auditoría en un reporte web estructurado con diseño ejecutivo, tablas de métricas y gráficos de radar interactivos.

---

## 👨‍💻 Autor

Desarrollado por **Alex** para proyectos de Arquitectura de Software.