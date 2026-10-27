"""Fase 4: Ley de Benford sobre el número de seguidores de los seguidores.

Se usa desde main.py:   python main.py benford <usuario> [--minimo N]

Entrada : raw/seguidores_contadores.json (Fase 2)  ->  se usa la columna `seguidores` (> 0) de los perfiles ok/privado
Salida  : resultados/benford.json + benford.png + benford.html (Fase 5, ver grafica.py) + resumen por consola

Qué se calcula:
  * Frecuencia real del primer dígito (1-9) y la esperada por Benford: P(d) = log10(1 + 1/d).
  * Chi-cuadrada de Pearson con 8 grados de libertad y su valor p.
  * MAD de Nigrini (desviación absoluta media, en proporciones) como control cruzado: la chi-cuadrada se vuelve
    hipersensible con muestras grandes y rechaza desviaciones sin importancia práctica.

Veredicto (según el valor p de la chi-cuadrada, como pidió el ingeniero; vale con cualquier número de seguidores por
cuenta, solo se excluyen los 0 porque no tienen primer dígito):
    p >= 0.05          -> HUMANO        (distribución compatible con Benford)
    0.01 <= p < 0.05   -> POSIBLE BOT
    p < 0.01           -> BOT
  Valor p: con n >= 110 datos, chi-cuadrada clásica; con 30 <= n < 110, simulación Monte Carlo (exacta para ese
  tamaño, no exige frecuencias esperadas >= 5). Con menos de 30 datos no se da veredicto. Con pocos datos la prueba
  tiene baja potencia: solo detecta desviaciones grandes.

IMPORTANTE: el veredicto describe a la AUDIENCIA del perfil en conjunto (Benford es una prueba de distribución, no de
cuentas individuales). Una desviación indica una audiencia anómala (p. ej. seguidores comprados), no una prueba definitiva.
"""
import json
import math
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from src.config import rutas_usuario

ZONA = ZoneInfo("America/Guayaquil")  # Ecuador (UTC-5)

DIGITOS = list(range(1, 10))
PROB_BENFORD = [math.log10(1 + 1 / d) for d in DIGITOS]
GRADOS_LIBERTAD = 8
CRITICO_5 = 15.507     # chi-cuadrada crítica, 8 g.l., alfa 0.05
CRITICO_1 = 20.090     # chi-cuadrada crítica, 8 g.l., alfa 0.01
ALFA_HUMANO = 0.05
ALFA_BOT = 0.01
MIN_MUESTRA = 110      # desde aquí la chi-cuadrada clásica (asintótica) es fiable: todo dígito espera >= ~5 casos
MIN_ABSOLUTO = 30      # por debajo de esto ninguna prueba dice algo útil: no se da veredicto
SIMULACIONES = 100_000  # réplicas del valor p exacto por simulación (resolución ~1e-5)
SEMILLA = 20260427      # fija: el mismo dato da siempre el mismo valor p
MIN_MAD_FIABLE = 1000  # los umbrales de MAD de Nigrini están calibrados para muestras grandes (miles de datos)

HUMANO, POSIBLE_BOT, BOT, INSUFICIENTE = "HUMANO", "POSIBLE BOT", "BOT", "MUESTRA INSUFICIENTE"

# Umbrales de Nigrini para el primer dígito (MAD en proporciones)
MAD_NIVELES = [(0.006, "conformidad cercana"), (0.012, "conformidad aceptable"),
               (0.015, "conformidad marginal"), (float("inf"), "no conforme")]


def primer_digito(valor):
    """Primer dígito (1-9) de un número entero positivo; None si no aplica (None, 0, negativos, NaN)."""
    try:
        n = int(abs(valor))
    except (TypeError, ValueError, OverflowError):
        return None
    return int(str(n)[0]) if n > 0 else None


def chi2_valor_p(chi2, gl=GRADOS_LIBERTAD):
    """P(X >= chi2) para gl PAR (forma cerrada exacta, sin depender de scipy): e^(-x/2) * sum_{k<gl/2} (x/2)^k / k!"""
    if gl % 2:
        raise ValueError("solo se implementan grados de libertad pares")
    mitad = chi2 / 2
    return math.exp(-mitad) * sum(mitad ** k / math.factorial(k) for k in range(gl // 2))


def chi2_valor_p_simulado(n, chi2_obs, simulaciones=SIMULACIONES, semilla=SEMILLA):
    """Valor p EXACTO por simulación Monte Carlo, válido para cualquier n (no exige frecuencias esperadas >= 5).

    Se generan `simulaciones` muestras de tamaño n que cumplen Benford (multinomial) y se mide qué fracción tiene
    una chi-cuadrada >= a la observada. p = (1 + aciertos) / (1 + simulaciones).
    """
    import numpy as np
    rng = np.random.default_rng(semilla)
    prob = np.array(PROB_BENFORD)
    esperado = n * prob
    cont = rng.multinomial(n, prob, size=simulaciones)
    chi = ((cont - esperado) ** 2 / esperado).sum(axis=1)
    return float((1 + np.count_nonzero(chi >= chi2_obs - 1e-9)) / (1 + simulaciones))


def nivel_mad(mad):
    return next(texto for limite, texto in MAD_NIVELES if mad <= limite)


def veredicto_por_p(p):
    return HUMANO if p >= ALFA_HUMANO else POSIBLE_BOT if p >= ALFA_BOT else BOT


def analizar(valores, minimo=MIN_ABSOLUTO):
    """Benford sobre una lista de números (seguidores).

    Los None y los negativos se ignoran. Los 0 no tienen primer dígito: no entran a Benford, pero se cuentan
    aparte (`n_ceros`), porque una proporción alta de cuentas con 0 seguidores es un dato de interés por sí mismo.

    Valor p: con n >= 110 chi-cuadrada clásica (8 g.l.); con 30 <= n < 110 simulación Monte Carlo (exacta para ese n).
    """
    valores = list(valores)
    digitos = [d for d in (primer_digito(v) for v in valores) if d]
    n = len(digitos)
    n_ceros = sum(1 for v in valores if v == 0)
    n_sin_dato = sum(1 for v in valores if v is None)
    conteos = [digitos.count(d) for d in DIGITOS]
    esperados = [n * p for p in PROB_BENFORD]
    real_pct = [c / n * 100 if n else 0.0 for c in conteos]
    benford_pct = [p * 100 for p in PROB_BENFORD]

    chi2 = sum((o - e) ** 2 / e for o, e in zip(conteos, esperados)) if n else float("nan")
    p_asintotico = chi2_valor_p(chi2) if n else None
    p_simulado = chi2_valor_p_simulado(n, chi2) if n else None
    usa_simulacion = n < MIN_MUESTRA
    p_valor = (p_simulado if usa_simulacion else p_asintotico) if n else None
    mad = sum(abs(c / n - p) for c, p in zip(conteos, PROB_BENFORD)) / 9 if n else float("nan")
    contrib = [(o - e) ** 2 / e if n else 0.0 for o, e in zip(conteos, esperados)]
    mayor = max(range(9), key=lambda i: contrib[i]) if n else None

    aviso = ""
    if n < minimo:
        veredicto = INSUFICIENTE
        aviso = f"Solo {n} datos válidos; se necesitan al menos {minimo} para poder emitir un veredicto."
    else:
        veredicto = veredicto_por_p(p_valor)
        if usa_simulacion:
            aviso = (f"Muestra reducida (n={n} < {MIN_MUESTRA}): el valor p se calcula por simulación (exacto para este "
                     f"tamaño). Con pocos datos la prueba solo detecta desviaciones grandes: "
                     + ("'HUMANO' significa que no se detecta desviación de Benford, no que esté demostrado."
                        if veredicto == HUMANO else "el resultado debe confirmarse con más datos."))

    nota = ""
    mad_referencial = n < MIN_MAD_FIABLE
    if n >= minimo:
        if mad_referencial:
            nota = (f"El MAD es solo referencial con n < {MIN_MAD_FIABLE}: sus umbrales (Nigrini) están calibrados para "
                    "muestras grandes y con pocos cientos de datos fluctúa mucho por azar. Decide la chi-cuadrada.")
        else:
            mad_ok = mad <= 0.012                      # conformidad cercana o aceptable
            if veredicto != HUMANO and mad_ok:
                nota = ("Discrepancia: la chi-cuadrada rechaza Benford pero el MAD indica conformidad "
                        f"({nivel_mad(mad)}). Con muestras grandes la chi-cuadrada es hipersensible; interpretar con cautela.")
            elif veredicto == HUMANO and not mad_ok:
                nota = f"Discrepancia: la chi-cuadrada no rechaza Benford pero el MAD indica {nivel_mad(mad)}."

    return {
        "n_validos": n,
        "n_ceros": n_ceros,
        "n_sin_dato": n_sin_dato,
        "n_descartados": n_ceros + n_sin_dato,
        "digitos": DIGITOS,
        "conteos": conteos,
        "esperados": [round(e, 3) for e in esperados],
        "pct_real": [round(x, 3) for x in real_pct],
        "pct_benford": [round(x, 3) for x in benford_pct],
        "contribucion_chi2": [round(x, 4) for x in contrib],
        "chi2": round(chi2, 4) if n else None,
        "grados_libertad": GRADOS_LIBERTAD,
        "valor_p": p_valor,
        "valor_p_asintotico": p_asintotico,
        "valor_p_simulado": p_simulado,
        "metodo_p": ("simulación Monte Carlo (%d réplicas)" % SIMULACIONES) if usa_simulacion
                    else "chi-cuadrada (asintótica, 8 g.l.)",
        "critico_5pct": CRITICO_5,
        "critico_1pct": CRITICO_1,
        "mad": round(mad, 5) if n else None,
        "mad_nivel": nivel_mad(mad) if n else None,
        "mad_referencial": mad_referencial,
        "digito_mayor_desvio": DIGITOS[mayor] if mayor is not None else None,
        "veredicto": veredicto,
        "minimo_muestra": minimo,
        "confiable": n >= MIN_MUESTRA,
        "aviso": aviso,
        "nota": nota,
    }


def seguidores_validos(contadores_json):
    """Número de seguidores de cada seguidor consultado con éxito (ok o privado), sin repetidos."""
    vistos, valores = set(), []
    for r in (contadores_json or {}).get("resultados", []):
        if r.get("estado") in ("ok", "privado") and r["usuario"] not in vistos:
            vistos.add(r["usuario"])
            valores.append(r.get("seguidores"))
    return valores


def _leer_json(ruta):
    if not os.path.exists(ruta):
        return None
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _imprimir(usuario, r):
    print(f"\n=== LEY DE BENFORD — seguidores de los seguidores de @{usuario} ===")
    total = r["n_validos"] + r["n_descartados"]
    print(f"datos válidos: {r['n_validos']} de {total}  |  cuentas con 0 seguidores (sin primer dígito): "
          f"{r['n_ceros']}" + (f" ({r['n_ceros'] / total * 100:.1f} %)" if total else "") +
          (f"  |  sin dato: {r['n_sin_dato']}" if r["n_sin_dato"] else ""))
    print(f"\n{'Dígito':<8}{'Real':>7}{'%Real':>9}{'%Benford':>10}{'Esperado':>10}")
    for i, d in enumerate(r["digitos"]):
        print(f"{d:<8}{r['conteos'][i]:>7}{r['pct_real'][i]:>8.2f}%{r['pct_benford'][i]:>9.2f}%{r['esperados'][i]:>10.1f}")
    if r["n_validos"]:
        print(f"\nchi² = {r['chi2']:.3f}  (gl={r['grados_libertad']}; crítico 5% = {r['critico_5pct']}, "
              f"1% = {r['critico_1pct']})   valor p = {r['valor_p']:.4g}  [{r['metodo_p']}]")
        ref = "  [referencial: n < 1000]" if r["mad_referencial"] else ""
        print(f"MAD = {r['mad']:.5f}  ({r['mad_nivel']}){ref}   |   dígito con mayor desvío: {r['digito_mayor_desvio']}")
    print(f"\n>>> VEREDICTO: {r['veredicto']}")
    for clave in ("aviso", "nota"):
        if r[clave]:
            print(f"    {r[clave]}")
    print("    (Describe a la audiencia en conjunto; es un indicio estadístico, no una prueba definitiva.)")


def analizar_usuario(usuario, minimo=MIN_ABSOLUTO, grafica=True, abrir=False):
    rutas = rutas_usuario(usuario).crear()
    contadores = _leer_json(rutas.contadores_json)
    if not contadores or not contadores.get("resultados"):
        raise SystemExit(f"No hay contadores en {rutas.raw}. Ejecuta primero:  python main.py contadores {usuario}")
    if contadores.get("estado") == "parcial":
        print(f"[Benford] AVISO: los contadores están incompletos ({contadores.get('resueltos')} de "
              f"{contadores.get('total_lista')} resueltos); se analiza lo disponible.")

    resultado = analizar(seguidores_validos(contadores), minimo=minimo)
    resultado = {"usuario": usuario, "fecha": datetime.now(ZONA).strftime("%Y-%m-%d %H:%M"), **resultado}
    with open(rutas.benford_json, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    _imprimir(usuario, resultado)
    print(f"\narchivo: {rutas.benford_json}")

    if grafica and resultado["n_validos"]:
        from src.benford.grafica import generar_graficas
        png, html = generar_graficas(resultado, usuario, rutas.resultados)
        print(f"gráfica PNG:  {png}\ngráfica HTML: {html}")
        if abrir:
            import webbrowser
            webbrowser.open("file:///" + html.replace(os.sep, "/").lstrip("/"))
    return resultado
