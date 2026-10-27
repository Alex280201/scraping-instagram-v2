# src/exportar/informe.py
"""Generador del mini-sitio de auditoría estructurado en tres archivos HTML enlazados:
1. informe.html: Página principal liviana, estática y optimizada para impresión PDF.
2. benford.html: Módulo interactivo de la Ley de Benford.
3. bigfive.html: Módulo interactivo del radar Big Five con confianzas y justificaciones.
"""
import base64
import html
import io
import json
import os
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from src.benford.benford import (BOT, HUMANO, INSUFICIENTE, POSIBLE_BOT, analizar, seguidores_validos)
from src.config import rutas_usuario

ZONA = ZoneInfo("America/Guayaquil")  # Ecuador (UTC-5)
COLOR_VEREDICTO = {HUMANO: "#2E7D32", POSIBLE_BOT: "#E08A00", BOT: "#C62828", INSUFICIENTE: "#757575"}

ORDEN_RASGOS = ["apertura", "responsabilidad", "extraversion", "amabilidad", "neuroticismo"]
NOMBRES = {
    "apertura": "Apertura a la experiencia",
    "responsabilidad": "Responsabilidad",
    "extraversion": "Extroversión",
    "amabilidad": "Amabilidad",
    "neuroticismo": "Neuroticismo",
}
DEFINICIONES = {
    "apertura": "Curiosidad, imaginación e interés por el arte, las ideas nuevas y las experiencias distintas.",
    "responsabilidad": "Organización, constancia, disciplina y orientación a metas y compromisos.",
    "extraversion": "Energía social, sociabilidad y tendencia a buscar la compañía y la estimulación de otros.",
    "amabilidad": "Empatía, cooperación, confianza y preocupación por los demás.",
    "neuroticismo": "Tendencia a experimentar emociones negativas como ansiedad, tristeza o estrés "
                    "(lo opuesto es la estabilidad emocional).",
}


def _e(valor):
    """Escapa para HTML (los nombres, biografías y justificaciones vienen de terceros o de un modelo)."""
    return html.escape("" if valor is None else str(valor), quote=True)


def _leer_json(ruta):
    if not os.path.exists(ruta):
        return None
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _clave_rasgo(nombre):
    return unicodedata.normalize("NFD", nombre or "").encode("ascii", "ignore").decode().lower().strip()


def _nivel(puntaje):
    return "Bajo" if puntaje < 40 else "Medio" if puntaje <= 60 else "Alto"


def _num(v):
    return f"{v:,}".replace(",", ".") if isinstance(v, int) else _e(v if v is not None else "—")


def _png_base64(ruta):
    try:
        with open(ruta, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except OSError:
        return None


def generar_barra_navegacion(activo="informe"):
    """Genera el HTML de la barra de navegación unificada para los 3 archivos del mini-sitio."""
    return f"""
    <nav style="background: #111827; padding: 1rem 2rem; display: flex; gap: 2rem; align-items: center; font-family: sans-serif; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <span style="color: #ffffff; font-weight: bold; font-size: 1.1rem; margin-right: auto;">🔍 Auditoría Instagram</span>
        <a href="informe.html" style="color: {'#38bdf8' if activo == 'informe' else '#9ca3af'}; text-decoration: none; font-weight: {'bold' if activo == 'informe' else 'normal'};">Informe Ejecutivo</a>
        <a href="benford.html" style="color: {'#38bdf8' if activo == 'benford' else '#9ca3af'}; text-decoration: none; font-weight: {'bold' if activo == 'benford' else 'normal'};">Benford Interactivo</a>
        <a href="bigfive.html" style="color: {'#38bdf8' if activo == 'bigfive' else '#9ca3af'}; text-decoration: none; font-weight: {'bold' if activo == 'bigfive' else 'normal'};">Big Five (Radar)</a>
    </nav>
    """


# ---------------------------------------------------------------- secciones
def _seccion_perfil(usuario, perfil, datos, lista):
    filas = [
        ("Nombre", _e(perfil.get("nombre") or "—")),
        ("Usuario", f'<a href="https://www.instagram.com/{_e(usuario)}/">@{_e(usuario)}</a>'),
        ("Publicaciones", _num(perfil.get("publicaciones"))),
        ("Seguidores", _num(perfil.get("seguidores"))),
        ("Seguidos", _num(perfil.get("seguidos"))),
        ("Biografía", _e(perfil.get("biografia") or "—").replace("\n", "<br>")),
    ]
    resumen = (datos or {}).get("resumen") or {}
    if resumen:
        filas.append(("Publicaciones analizadas",
                      f"{_num(resumen.get('total_publicaciones_extraidas'))} "
                      f"({_num(resumen.get('con_descripcion'))} con descripción; "
                      f"{_e(resumen.get('primera_fecha') or '—')} a {_e(resumen.get('ultima_fecha') or '—')})"))
    cuerpo = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in filas)
    return f'<h2>1. Datos del perfil</h2><table class="ficha">{cuerpo}</table>'


def _seccion_seguidores(lista, contadores, r):
    declarados = (lista or {}).get("seguidores_declarados")
    capturados = len((lista or {}).get("seguidores") or [])
    estados = {}
    for x in (contadores or {}).get("resultados", []):
        estados[x["estado"]] = estados.get(x["estado"], 0) + 1
    total = r["n_validos"] + r["n_ceros"] + r["n_sin_dato"]
    pct0 = f" ({r['n_ceros'] / total * 100:.1f} %)" if total else ""
    estados_txt = ", ".join(f"{_e(k)}: {v}" for k, v in sorted(estados.items())) or "—"
    filas = [
        ("Seguidores declarados por Instagram", _num(declarados)),
        ("Seguidores capturados en la lista", _num(capturados)
         + (" <span class='aviso'>(lista incompleta)</span>" if (lista or {}).get("estado") in ("parcial",) else "")),
        ("Perfiles consultados (por estado)", estados_txt),
        ("Con número de seguidores utilizable (≥ 1)", _num(r["n_validos"])),
        ("Con 0 seguidores (no tienen primer dígito)", _num(r["n_ceros"]) + pct0),
    ]
    cuerpo = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in filas)
    return f'<h2>2. Seguidores analizados</h2><table class="ficha">{cuerpo}</table>'


def _seccion_benford(r, usuario, ruta_png):
    if not r["n_validos"]:
        return ('<h2>3. Ley de Benford</h2><p class="aviso">No hay seguidores con número de seguidores mayor a 0; '
                'no se puede aplicar la prueba.</p>')
    color = COLOR_VEREDICTO[r["veredicto"]]
    etiqueta = r["veredicto"] + (" (muestra reducida)" if r["veredicto"] != INSUFICIENTE and not r["confiable"] else "")
    p = r["valor_p"]
    p_txt = f"{p:.2e}" if p < 0.0001 else f"{p:.4f}"
    filas_dig = "".join(
        f"<tr><td>{d}</td><td>{r['conteos'][i]}</td><td>{r['pct_real'][i]:.2f} %</td>"
        f"<td>{r['pct_benford'][i]:.2f} %</td><td>{r['esperados'][i]:.1f}</td></tr>"
        for i, d in enumerate(r["digitos"]))
    img = _png_base64(ruta_png)
    figura = (f'<img class="grafica" alt="Gráfica de la Ley de Benford" src="data:image/png;base64,{img}">'
              if img else "")
    avisos = "".join(f'<p class="aviso">{_e(r[k])}</p>' for k in ("aviso", "nota") if r.get(k))
    return f"""
<h2>3. Ley de Benford — seguidores de los seguidores</h2>
<p><span class="badge" style="background:{color}">{_e(etiqueta)}</span></p>
<p class="stats">n = <b>{r['n_validos']}</b> · χ² = <b>{r['chi2']:.3f}</b> (crítico 5 %: {r['critico_5pct']}, 1 %: {r['critico_1pct']},
8 g.l.) · valor p = <b>{p_txt}</b> <small>({_e(r['metodo_p'])})</small> · MAD = {r['mad']:.4f}
({'referencial, n &lt; 1000' if r['mad_referencial'] else _e(r['mad_nivel'])})</p>
{avisos}
{figura}
<table class="datos"><thead><tr><th>Dígito</th><th>Casos</th><th>% observado</th><th>% Benford</th><th>Esperado</th></tr></thead>
<tbody>{filas_dig}</tbody></table>
<p class="nota"><b>Cómo leerlo:</b> p ≥ 0.05 → HUMANO (compatible con Benford) · 0.01 ≤ p &lt; 0.05 → POSIBLE BOT ·
p &lt; 0.01 → BOT. El veredicto describe a la <i>audiencia en conjunto</i>; es un indicio estadístico, no una prueba
definitiva. Los primeros seguidores que muestra Instagram no son una muestra aleatoria.</p>"""


def _seccion_bigfive(bf):
    if not bf:
        return ('<h2>4. Perfil Big Five</h2><p class="aviso">No se generó el perfil Big Five (requiere haber extraído las '
                'publicaciones y tener GEMINI_API_KEY en el .env). Ejecuta: <code>python main.py analizar &lt;usuario&gt;'
                '</code>.</p>')
    por_clave = {_clave_rasgo(x["rasgo"]): x for x in bf.get("rasgos", [])}
    filas = ""
    for k in ORDEN_RASGOS:
        x = por_clave.get(k)
        if not x:
            continue
        filas += (f"<tr><td><b>{_e(NOMBRES[k])}</b><br><small>{_e(DEFINICIONES[k])}</small></td>"
                  f"<td>{_nivel(x['puntaje'])}</td><td>{x['puntaje']}/100</td><td>{x['confianza']:.2f}</td>"
                  f"<td>{_e(x['justificacion'])}</td></tr>")
    meta = bf.get("meta", {})
    return f"""
<h2>4. Perfil Big Five (OCEAN)</h2>
<p>{_e(bf.get('resumen'))}</p>
<p><i>Nota: Puede explorar la visualización interactiva del radar en el menú superior o en la página <a href="bigfive.html">bigfive.html</a>.</i></p>
<table class="datos bf"><thead><tr><th>Rasgo</th><th>Nivel</th><th>Puntaje</th><th>Confianza</th><th>Justificación</th></tr></thead>
<tbody>{filas}</tbody></table>
<p class="nota"><b>Limitaciones:</b> {_e(bf.get('limitaciones'))}<br>
Textos analizados: {_e(meta.get('textos_disponibles', '—'))} · confianza máxima permitida:
{_e(meta.get('techo_confianza', '—'))} · modelo: {_e(meta.get('modelo', '—'))}.
Es una estimación exploratoria, no una medición psicológica válida.</p>"""


def _generar_bigfive_html(usuario, bf):
    """Genera el archivo independiente bigfive.html con el gráfico de radar interactivo de Plotly."""
    if not bf:
        return
    por_clave = {_clave_rasgo(x["rasgo"]): x for x in bf.get("rasgos", [])}
    rasgos_nombres = [NOMBRES[k] for k in ORDEN_RASGOS if k in por_clave]
    valores = [por_clave[k]["puntaje"] for k in ORDEN_RASGOS if k in por_clave]
    confianzas = [por_clave[k]["confianza"] for k in ORDEN_RASGOS if k in por_clave]
    justificaciones = [por_clave[k]["justificacion"] for k in ORDEN_RASGOS if k in por_clave]

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Perfil Psicométrico Big Five - @{_e(usuario)}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; background: #f3f4f6; color: #1f2937; }}
        .container {{ max-width: 1000px; margin: 2rem auto; background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        h1 {{ color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }}
        .note {{ background: #eff6ff; border-left: 4px solid #3b82f6; padding: 1rem; margin: 1rem 0; font-size: 0.95rem; color: #1e40af; }}
    </style>
</head>
<body>
    {generar_barra_navegacion('bigfive')}
    <div class="container">
        <h1>Perfil Psicométrico Big Five (OCEAN) — @{_e(usuario)}</h1>
        <p>Análisis de personalidad extraído mediante modelos de lenguaje a partir de las metadescripciones del perfil principal.</p>
        <div class="note">
            <strong>Nota de Incertidumbre:</strong> Debido a que el análisis proviene de muestras acotadas de texto público, los índices de confianza operan en rangos controlados (0.45 - 0.65). Pase el mouse sobre cada vértice del radar para ver la justificación detallada y la confianza específica de cada rasgo.
        </div>
        <div id="radar-plot" style="width:100%; height:550px;"></div>
    </div>
    <script>
        const data = [{{
            type: 'scatterpolar',
            r: {valores},
            theta: {rasgos_nombres},
            fill: 'toself',
            name: 'Puntaje Rasgo',
            marker: {{ color: '#2563eb' }},
            text: {json.dumps(justificaciones, ensure_ascii=False)}.map((j, i) => `<b>Rasgo:</b> ${{ {json.dumps(rasgos_nombres, ensure_ascii=False)}[i] }}<br><b>Confianza:</b> ${{ {confianzas}[i] }}<br><b>Justificación:</b> ${{j}}`),
            hoverinfo: 'text+theta'
        }}];
        const layout = {{
            polar: {{
                radialaxis: {{ visible: true, range: [0, 100] }}
            }},
            showlegend: false,
            margin: {{ t: 40, b: 40, l: 40, r: 40 }}
        }};
        Plotly.newPlot('radar-plot', data, layout);
    </script>
</body>
</html>
"""
    rutas = rutas_usuario(usuario)
    ruta_bf_html = os.path.join(rutas.resultados, "bigfive.html")
    with open(ruta_bf_html, "w", encoding="utf-8") as f:
        f.write(html_content)


CSS = """
:root{--fg:#1d2733;--mut:#5b6775;--bg:#fff;--card:#f5f7fa;--line:#dfe4ea;--acc:#1f3a5f}
@media(prefers-color-scheme:dark){:root{--fg:#e6ebf1;--mut:#9aa7b5;--bg:#12171d;--card:#1b222b;--line:#2b3440;--acc:#8db4e2}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,Segoe UI,Roboto,sans-serif}
main{max-width:920px;margin:0 auto;padding:28px 16px 56px}
h1{font-size:26px;color:var(--acc);margin:0 0 4px}h2{font-size:19px;color:var(--acc);margin:34px 0 10px;
border-bottom:2px solid var(--line);padding-bottom:5px}.sub{color:var(--mut);margin:0 0 6px}
table{border-collapse:collapse;width:100%;margin:10px 0}th,td{padding:7px 10px;border-bottom:1px solid var(--line);
text-align:left;vertical-align:top}.ficha th{width:34%;color:var(--mut);font-weight:600}
@media(max-width:640px){.datos{display:block;overflow-x:auto}.ficha th{width:40%}main{overflow-wrap:anywhere}}
.datos thead th{background:var(--card);font-size:13px}.bf td{white-space:normal}.bf td:first-child{width:36%}.bf td:nth-child(2),.bf td:nth-child(3),.bf td:nth-child(4){white-space:nowrap}
.badge{display:inline-block;color:#fff;font-weight:700;font-size:18px;padding:7px 16px;border-radius:8px}
.stats{background:var(--card);padding:10px 14px;border-radius:8px}.aviso{color:#b45f06;background:rgba(224,138,0,.12);
padding:8px 12px;border-radius:8px}.nota{color:var(--mut);font-size:13px}img.grafica{max-width:100%;border:1px solid var(--line);
border-radius:8px;margin:8px 0}code{background:var(--card);padding:1px 5px;border-radius:4px}
footer{margin-top:40px;color:var(--mut);font-size:12.5px;border-top:1px solid var(--line);padding-top:12px}
a{color:var(--acc)}@media print{body{font-size:12px}main{padding:0}h2{break-after:avoid}table,img{break-inside:avoid}}
"""


def generar_informe(usuario, radar=True):
    rutas = rutas_usuario(usuario)
    datos = _leer_json(rutas.datos_json)
    lista = _leer_json(rutas.seguidores_json)
    contadores = _leer_json(rutas.contadores_json)
    bf = _leer_json(rutas.bigfive_json)
    if not (datos or lista):
        raise SystemExit(f"No hay datos de @{usuario} en {rutas.base}. Ejecuta primero:  python main.py completo {usuario}")

    perfil = dict((lista or {}).get("perfil") or {})
    perfil.update({k: v for k, v in ((datos or {}).get("perfil") or {}).items() if v not in (None, "")})
    perfil.setdefault("usuario", usuario)

    # Benford: se recalcula siempre desde los contadores (fuente de verdad) para que informe, tabla y gráfica coincidan.
    benford = analizar(seguidores_validos(contadores)) if contadores else analizar([])
    ruta_png = os.path.join(rutas.resultados, "benford.png")
    if benford["n_validos"]:
        try:
            from src.benford.grafica import grafica_png
            grafica_png(benford, usuario, ruta_png)
        except Exception as e:
            print(f"[Informe] AVISO: no se pudo generar la gráfica de Benford ({str(e).splitlines()[0]})")
            ruta_png = ""

    # Generar bigfive.html interactivo independiente si existen datos de Big Five y se solicita radar
    if radar and bf:
        try:
            _generar_bigfive_html(usuario, bf)
        except Exception as e:
            print(f"[Informe] AVISO: no se pudo generar bigfive.html ({str(e)})")

    ahora = datetime.now(ZONA).strftime("%Y-%m-%d %H:%M")
    cuerpo = "".join([
        _seccion_perfil(usuario, perfil, datos, lista),
        _seccion_seguidores(lista, contadores, benford),
        _seccion_benford(benford, usuario, ruta_png),
        _seccion_bigfive(bf),
    ])
    documento = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Informe @{_e(usuario)}</title><style>{CSS}</style></head>
<body>
{generar_barra_navegacion('informe')}
<main>
<h1>Informe de análisis · @{_e(usuario)}</h1>
<p class="sub">Generado el {ahora} (hora de Ecuador)</p>
{cuerpo}
<footer>Proyecto académico. Datos recolectados solo con la autorización de la titular del perfil; los datos de terceros
(seguidores) se usan únicamente de forma agregada. Los resultados son estimaciones exploratorias, no diagnósticos.</footer>
</main></body></html>"""
    os.makedirs(rutas.resultados, exist_ok=True)
    ruta = os.path.join(rutas.resultados, "informe.html")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(documento)
    print(f"[Informe] {ruta}")
    return ruta
