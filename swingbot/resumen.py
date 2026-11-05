"""Parte diario del S&P 500 y de la estrategia.

python -m swingbot resumen

Incluye: cierre y variaciones (día, semana, mes, año), tendencia de corto, medio y
largo plazo, distancia a la media de 200, RSI(2), estado de la estrategia y
cuenta atrás hasta la revisión. En fin de semana o festivo indica que el mercado
está cerrado y resume la semana.
"""
from __future__ import annotations

import pandas as pd

from . import data, trend
from .indicators import add_indicators, sma


def _es(v: float, d: int = 2) -> str:
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v: float) -> str:
    return ("+" if v >= 0 else "−") + _es(abs(v) * 100, 1) + " %"


def _tendencia(c: float, s20: float, s50: float, s200: float, slope200: float) -> str:
    if c > s50 > s200 and slope200 > 0:
        return "alcista fuerte" if c > s20 else "alcista, con descanso de corto plazo"
    if c > s200 and slope200 > 0:
        return "alcista moderada"
    if c > s200:
        return "lateral, por encima de la media 200"
    if c < s50 < s200:
        return "bajista"
    return "debilitándose, por debajo de la media 200"


def probabilidad_cambio(dist: float, dias_sesiones: int, inside: bool) -> tuple[float, int]:
    """En situaciones parecidas desde 1960 (distancia a la media 200 ±0,75 puntos y
    ±2 sesiones hasta fin de mes), qué parte acabó con la señal contraria en la revisión."""
    h = add_indicators(data.load("^GSPC", start="1955-01-01"))
    h = h.dropna(subset=["sma200"]).loc["1960-01-01":]
    dist_h = h.Close / h.sma200 - 1
    left = h.days_left_month
    eom_above = (h.Close > h.sma200).where(left == 0).bfill()       # resultado en la próxima revisión
    same_side = (dist_h > 0) == inside
    m = ((dist_h - dist).abs() < 0.0075) & ((left - dias_sesiones).abs() <= 2) & same_side & (left > 0)
    res = eom_above[m].dropna()
    if len(res) < 20:
        return float("nan"), len(res)
    flip = (res.astype(bool) != inside).mean()
    return float(flip), int(len(res))


def proxima_aportacion() -> pd.Timestamp:
    """Cada compra cubre un mes desde noviembre de 2026; la siguiente aportación es el
    primer día hábil del mes siguiente al último cubierto (las adelantadas cuentan)."""
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "reports" / "dashboard" / "operaciones.json"
    try:
        n = sum(1 for o in json.loads(p.read_text()) if o.get("accion") == "Compra")
    except (OSError, ValueError):
        n = 0
    first = pd.Timestamp("2026-11-01") + pd.DateOffset(months=n)
    from pandas.tseries.holiday import USFederalHolidayCalendar
    return first + pd.offsets.CustomBusinessDay(0, calendar=USFederalHolidayCalendar())


def build() -> str:
    df = add_indicators(data.load("^GSPC", start="2023-01-01", refresh=True))
    df["sma20"] = sma(df.Close, 20)
    last, d = df.iloc[-1], df.index[-1]
    c = float(last.Close)
    ago = lambda days: float(df.Close.loc[:d - pd.Timedelta(days=days)].iloc[-1])
    ytd = float(df.Close.loc[:f"{d.year - 1}-12-31"].iloc[-1])
    slope200 = float(df.sma200.iloc[-1] / df.sma200.iloc[-21] - 1)
    st = trend.status(refresh=False)
    now = pd.Timestamp.now(tz="Europe/Madrid").tz_localize(None)
    today = now.normalize()
    hay_datos_hoy = d.normalize() == today
    dias = (st["next_check"] - today).days

    tend = _tendencia(c, float(last.sma20), float(last.sma50), float(last.sma200), slope200)
    lines = []
    if not hay_datos_hoy:
        if today.dayofweek >= 5:
            motivo = "Fin de semana: la bolsa está cerrada."
        elif now.hour + now.minute / 60 < 15.5:
            motivo = "La bolsa de EE.UU. aún no ha abierto hoy (abre a las 15:30)."
        else:
            motivo = "Hoy la bolsa de EE.UU. no ha abierto (festivo)."
        lines.append(f"{motivo} Datos del último cierre: {d:%d/%m/%Y}.")
    elif now.hour < 22:
        lines.append(f"Datos de hoy con la bolsa aún abierta ({now:%H:%M}); el cierre es a las 22:00.")
    lines += [
        f"S&P 500: {_es(c)}  ·  día {_pct(c / float(df.Close.iloc[-2]) - 1)}  ·  semana {_pct(c / ago(7) - 1)}"
        f"  ·  mes {_pct(c / ago(30) - 1)}  ·  año {_pct(c / ytd - 1)}",
        f"Tendencia: {tend}. Media 200 {_es(float(last.sma200), 0)} ({_pct(st['dist'])} de distancia), "
        f"subiendo {_pct(slope200)} en el último mes.",
        f"Corto plazo: RSI(2) {_es(float(last.rsi2), 1)} · media 20 {_es(float(last.sma20), 0)} · "
        f"{'por encima' if c > last.sma20 else 'por debajo'} de ella.",
        f"Estrategia: {'DENTRO → mantener x3' if st['inside'] else 'FUERA → x1'}. "
        f"Revisión el {st['next_check']:%d/%m/%Y} (faltan {dias} días).",
    ]
    # Lo más probable en la próxima revisión
    sesiones = int(last.days_left_month)
    p, n = probabilidad_cambio(float(st["dist"]), max(sesiones, 1), bool(c > float(last.sma200)))
    hoy_dentro = c > float(last.sma200)
    if p == p:  # no es NaN
        seguir = "MANTENER x3" if hoy_dentro else "seguir en x1"
        cambiar = "pasar a x1" if hoy_dentro else "volver al x3"
        principal = seguir if p < 0.5 else cambiar
        prob = 1 - p if p < 0.5 else p
        lines.append(f"Lo más probable el {st['next_check']:%d/%m}: {principal.upper()} "
                     f"({_es(prob * 100, 0)} % de {n} casos parecidos desde 1960; "
                     f"{_es(min(p, 1 - p) * 100, 0)} % acabaron en {cambiar if p < 0.5 else seguir}).")
    prox_aport = proxima_aportacion()
    lines.append(f"Próximas tareas: nada hasta la revisión del {st['next_check']:%d/%m}; "
                 f"siguiente aportación de 50 € el {prox_aport:%d/%m/%Y} al producto que toque.")
    if st["inside"] != (c > float(last.sma200)):
        lines.append("⚠️ Alerta temprana: hoy está al otro lado de la media 200. No se actúa hasta la revisión.")
    elif abs(st["dist"]) < 0.02:
        lines.append("👀 Vigilancia: a menos del 2 % de la media 200.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(build())
