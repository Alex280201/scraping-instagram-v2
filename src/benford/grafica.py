"""Fase 5: gráfica de la Ley de Benford (observado vs teórico) con el veredicto en el encabezado.

Se genera junto con el análisis:   python main.py benford <usuario>        (opciones: --sin-grafica, --abrir)

Salida (datos/<usuario>/resultados/):
    benford.png    imagen para informes
    benford.html   gráfica interactiva (se abre en el navegador; funciona sin internet)

Qué se ve:
    * Barras azules  = % observado de cada primer dígito (los datos recolectados).
    * Línea roja     = % esperado por la Ley de Benford (la "original").
    * Banda gris     = rango en el que una muestra de este tamaño que SÍ cumpla Benford caería el 95 % de las veces
                       (Nigrini: z·√(p(1-p)/n) + 1/2n). Una barra fuera de la banda es un dígito anómalo.
    * Panel inferior = diferencia observado − Benford en puntos porcentuales.
    * Encabezado     = n, χ², valor p, MAD y veredicto (HUMANO / POSIBLE BOT / BOT / MUESTRA INSUFICIENTE).
"""
import math
import os

from src.benford.benford import BOT, HUMANO, INSUFICIENTE, POSIBLE_BOT

COLOR_VEREDICTO = {HUMANO: "#2E7D32", POSIBLE_BOT: "#E08A00", BOT: "#C62828", INSUFICIENTE: "#757575"}
AZUL, ROJO, GRIS = "#4C78A8", "#D62728", "#BDBDBD"
NARANJA, VERDE_AZUL = "#E8833A", "#2A9D8F"      # desviación por encima / por debajo de Benford
Z95 = 1.96


def _banda(r):
    """(inferior, superior) en % por dígito: intervalo de aceptación al 95 % para n datos que cumplen Benford."""
    n = r["n_validos"]
    bajo, alto = [], []
    for pb in r["pct_benford"]:
        p = pb / 100
        margen = Z95 * math.sqrt(p * (1 - p) / n) + 1 / (2 * n)
        bajo.append(max(0.0, (p - margen) * 100))
        alto.append((p + margen) * 100)
    return bajo, alto


def _textos(usuario, r):
    titulo = f"Ley de Benford · seguidores de los seguidores de @{usuario}"
    if r["valor_p"] is None:
        raise ValueError("No hay datos válidos para graficar.")
    p = r["valor_p"]
    p_txt = f"{p:.2e}" if p < 0.0001 else f"{p:.4f}"
    resumen = (f"n = {r['n_validos']}   ·   χ² = {r['chi2']:.2f} (crítico 5 %: {r['critico_5pct']}, "
               f"1 %: {r['critico_1pct']})   ·   p = {p_txt}{' (simulación)' if not r.get('confiable', True) else ''}   ·   MAD = {r['mad']:.4f}"
               + (" (referencial)" if r.get("mad_referencial") else ""))
    veredicto = r["veredicto"]
    if veredicto != INSUFICIENTE and not r.get("confiable", True):
        veredicto_txt = f"{veredicto} (muestra reducida)"
    else:
        veredicto_txt = veredicto
    return titulo, resumen, veredicto_txt, r.get("aviso", "")


def generar_barra_navegacion(activo="benford"):
    """Genera el HTML de la barra de navegación unificada para los 3 archivos del mini-sitio."""
    return f"""
    <nav style="background: #111827; padding: 1rem 2rem; display: flex; gap: 2rem; align-items: center; font-family: sans-serif; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <span style="color: #ffffff; font-weight: bold; font-size: 1.1rem; margin-right: auto;">🔍 Auditoría Instagram</span>
        <a href="informe.html" style="color: {'#38bdf8' if activo == 'informe' else '#9ca3af'}; text-decoration: none; font-weight: {'bold' if activo == 'informe' else 'normal'};">Informe Ejecutivo</a>
        <a href="benford.html" style="color: {'#38bdf8' if activo == 'benford' else '#9ca3af'}; text-decoration: none; font-weight: {'bold' if activo == 'benford' else 'normal'};">Benford Interactivo</a>
        <a href="bigfive.html" style="color: {'#38bdf8' if activo == 'bigfive' else '#9ca3af'}; text-decoration: none; font-weight: {'bold' if activo == 'bigfive' else 'normal'};">Big Five (Radar)</a>
    </nav>
    """


# ---------------------------------------------------------------- PNG (matplotlib)
def grafica_png(resultado, usuario, ruta):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    r = resultado
    titulo, resumen, veredicto_txt, aviso = _textos(usuario, r)
    color_v = COLOR_VEREDICTO[r["veredicto"]]
    x = r["digitos"]
    real, teo = r["pct_real"], r["pct_benford"]
    bajo, alto = _banda(r)

    fig = plt.figure(figsize=(11, 7.6), dpi=150)
    gs = GridSpec(2, 1, height_ratios=[3.2, 1], hspace=0.12, top=0.78 if aviso else 0.86, bottom=0.10,
                  left=0.08, right=0.97)
    ax = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax)

    ax.fill_between(x, bajo, alto, color=GRIS, alpha=0.45, linewidth=0, label="Banda 95 % esperada (Benford)")
    barras = ax.bar(x, real, width=0.62, color=AZUL, alpha=0.9, label="Observado (datos recolectados)", zorder=2)
    ax.plot(x, teo, color=ROJO, marker="o", linewidth=2.4, markersize=7, label="Ley de Benford (teórica)", zorder=3)
    for xi, valor in zip(x, real):      # etiqueta en la base de la barra: la curva roja nunca pasa por ahí
        if valor >= 2.5:
            ax.text(xi, 0.5, f"{valor:.1f}%", ha="center", va="bottom", fontsize=9.5, color="white",
                    fontweight="bold", zorder=5)
        else:                           # barra demasiado baja para contener el texto
            ax.text(xi, valor + 0.5, f"{valor:.1f}%", ha="center", va="bottom", fontsize=9.5, color="#1f3a5f",
                    fontweight="bold", zorder=5)
    ax.set_ylabel("Frecuencia del primer dígito (%)")
    ax.set_ylim(0, max(max(real), max(alto)) + 6)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(loc="upper right", frameon=True, fontsize=9)
    plt.setp(ax.get_xticklabels(), visible=False)

    dif = [a - b for a, b in zip(real, teo)]
    ax2.bar(x, dif, width=0.62, color=[NARANJA if d >= 0 else VERDE_AZUL for d in dif], zorder=2)
    ax2.axhline(0, color="#444", linewidth=0.9)
    ax2.set_ylabel("Obs. − Benford\n(pts. porcentuales)", fontsize=9)
    ax2.set_xlabel("Primer dígito")
    ax2.set_xticks(x)
    ax2.grid(axis="y", alpha=0.3)
    lim = max(2.0, max(abs(d) for d in dif) * 1.25)
    ax2.set_ylim(-lim, lim)

    fig.text(0.08, 0.945, titulo, fontsize=14, fontweight="bold", color="#1f3a5f", ha="left")
    fig.text(0.08, 0.905, resumen, fontsize=9.5, color="#333", ha="left")
    fig.text(0.97, 0.945, veredicto_txt, fontsize=13, fontweight="bold", color="white", ha="right",
             bbox=dict(boxstyle="round,pad=0.45", facecolor=color_v, edgecolor="none"))
    if aviso:
        fig.text(0.08, 0.862, "⚠ " + _partir(aviso, 125), fontsize=8.5, color="#8a4b00", ha="left", va="top")
    fig.text(0.08, 0.015, "El veredicto describe a la audiencia en conjunto; es un indicio estadístico, no una prueba "
                          "definitiva.", fontsize=8, color="#666", ha="left")

    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    fig.savefig(ruta, dpi=150)
    plt.close(fig)
    return ruta


def _partir(texto, ancho):
    """Salto de línea simple para avisos largos."""
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        if len(actual) + len(p) + 1 > ancho:
            lineas.append(actual)
            actual = p
        else:
            actual = (actual + " " + p).strip()
    lineas.append(actual)
    return "\n".join(lineas)


# ---------------------------------------------------------------- HTML interactivo (plotly)
def grafica_html(resultado, usuario, ruta):
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        raise SystemExit("Falta plotly para la gráfica interactiva:  pip install plotly")

    r = resultado
    titulo, resumen, veredicto_txt, aviso = _textos(usuario, r)
    color_v = COLOR_VEREDICTO[r["veredicto"]]
    x, real, teo = r["digitos"], r["pct_real"], r["pct_benford"]
    bajo, alto = _banda(r)
    dif = [a - b for a, b in zip(real, teo)]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.76, 0.24], vertical_spacing=0.06)
    fig.add_trace(go.Scatter(x=x + x[::-1], y=alto + bajo[::-1], mode="lines", fill="toself",
                             fillcolor="rgba(150,150,150,0.30)", line=dict(width=0), name="Banda 95 % esperada (Benford)", hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Bar(
        x=x, y=real, name="Observado (datos recolectados)", marker_color=AZUL, opacity=0.9,
        text=[f"{v:.1f}%" for v in real], textposition="inside", insidetextanchor="start",
        textfont=dict(color="white", size=13),
        customdata=[[c, e] for c, e in zip(r["conteos"], r["esperados"])],
        hovertemplate="Dígito %{x}<br>Observado: %{y:.2f}% (%{customdata[0]} casos)<br>"
                      "Esperado Benford: %{customdata[1]:.1f} casos<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=teo, mode="lines+markers", name="Ley de Benford (teórica)",
                             line=dict(color=ROJO, width=3), marker=dict(size=9),
                             hovertemplate="Dígito %{x}<br>Benford: %{y:.2f}%<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Bar(x=x, y=dif, name="Observado − Benford", showlegend=False,
                         marker_color=[NARANJA if d >= 0 else VERDE_AZUL for d in dif],
                         hovertemplate="Dígito %{x}<br>Diferencia: %{y:+.2f} pts<extra></extra>"), row=2, col=1)
    fig.add_hline(y=0, line_width=1, line_color="#444", row=2, col=1)

    encabezado = (f"<b>{titulo}</b><br><span style='font-size:12px;color:#333'>{resumen}</span>"
                  + (f"<br><span style='font-size:11px;color:#8a4b00'>⚠ {aviso}</span>" if aviso else ""))
    fig.update_layout(
        template="plotly_white", height=720, margin=dict(t=130 if aviso else 105, b=60, l=70, r=40),
        title=dict(text=encabezado, x=0.01, xanchor="left", y=0.97, yanchor="top", font=dict(size=17, color="#1f3a5f")),
        legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"), bargap=0.35,
        annotations=[dict(text=f"<b>{veredicto_txt}</b>", xref="paper", yref="paper", x=0.995, y=1.0 + (0.17 if aviso else 0.14),
                          xanchor="right", yanchor="top", showarrow=False, font=dict(size=16, color="white"),
                          bgcolor=color_v, borderpad=8)],
    )
    fig.update_xaxes(tickmode="array", tickvals=x, row=2, col=1, title_text="Primer dígito")
    fig.update_yaxes(title_text="Frecuencia del primer dígito (%)", range=[0, max(max(real), max(alto)) + 6], row=1, col=1)
    fig.update_yaxes(title_text="Obs. − Benford (pts)", row=2, col=1)

    # Generar HTML con Plotly y añadir la barra de navegación compartida
    html_content = fig.to_html(include_plotlyjs=True, full_html=True, config={"displaylogo": False})
    navbar = generar_barra_navegacion('benford')
    
    if "<body>" in html_content:
        html_content = html_content.replace("<body>", "<body>\n" + navbar)

    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html_content)
    return ruta


def generar_graficas(resultado, usuario, carpeta):
    """PNG + HTML en `carpeta`. Devuelve (ruta_png, ruta_html)."""
    png = grafica_png(resultado, usuario, os.path.join(carpeta, "benford.png"))
    html = grafica_html(resultado, usuario, os.path.join(carpeta, "benford.html"))
    return png, html