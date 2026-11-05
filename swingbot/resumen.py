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
    if st["inside"] != (c > float(last.sma200)):
        lines.append("⚠️ Alerta temprana: hoy está al otro lado de la media 200. No se actúa hasta la revisión.")
    elif abs(st["dist"]) < 0.02:
        lines.append("👀 Vigilancia: a menos del 2 % de la media 200.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(build())
