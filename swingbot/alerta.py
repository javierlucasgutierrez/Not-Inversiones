"""Alertas durante la sesión: movimientos fuertes del S&P 500 y de tu x3.

python -m swingbot alerta

Compara el precio actual del S&P 500 con el cierre anterior y avisa cuando cruza
un umbral por primera vez en el día (cada umbral se avisa una sola vez):
  - caídas del índice de −1,5 %, −2,5 % y −4 % (≈ −4,5 %, −7,5 % y −12 % en el x3)
  - subidas de +2,5 % (≈ +7,5 % en el x3)
  - cruce de la media de 200 sesiones
  - VIX (miedo) por encima de 25 y de 30
Las alertas son informativas: la estrategia no vende a mitad de mes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import data
from .indicators import add_indicators

STATE = Path(__file__).resolve().parent.parent / "data_cache" / "alertas_hoy.json"
DROPS = (-0.015, -0.025, -0.04)
RISES = (0.025,)
VIX_LEVELS = (25, 30)


def _es(v: float, d: int = 1) -> str:
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v: float) -> str:
    return ("+" if v >= 0 else "−") + _es(abs(v) * 100) + " %"


def check() -> list[str]:
    df = add_indicators(data.load("^GSPC", start="2024-01-01", refresh=True, max_age_hours=0))
    vix = data.load("^VIX", start="2026-01-01", refresh=True, max_age_hours=0)["Close"]
    today = pd.Timestamp.now(tz="Europe/Madrid").tz_localize(None).normalize()
    if df.index[-1].normalize() != today:
        return []                                   # hoy no hay sesión (o aún no abrió)
    price, prev = float(df.Close.iloc[-1]), float(df.Close.iloc[-2])
    sma200 = float(df.sma200.iloc[-1])
    chg = price / prev - 1
    x3 = 3 * chg

    try:
        state = json.loads(STATE.read_text())
    except (OSError, ValueError):
        state = {}
    if state.get("fecha") != f"{today:%Y-%m-%d}":
        state = {"fecha": f"{today:%Y-%m-%d}", "avisadas": []}
    done = set(state["avisadas"])
    out = []

    base = f"S&P 500 {_es(price, 0)} ({_pct(chg)} hoy) → tu x3 ≈ {_pct(x3)}."
    new_drops = [l for l in DROPS if chg <= l and f"caida{l}" not in done]
    if new_drops:
        done.update(f"caida{l}" for l in new_drops)
        out.append(f"📉 Caída fuerte (índice por debajo de {_pct(min(new_drops))}): {base}")
    new_rises = [l for l in RISES if chg >= l and f"subida{l}" not in done]
    if new_rises:
        done.update(f"subida{l}" for l in new_rises)
        out.append(f"📈 Subida fuerte: {base}")
    above_prev = prev > float(df.sma200.iloc[-2])
    if (price > sma200) != above_prev and "cruce" not in done:
        done.add("cruce")
        lado = "POR DEBAJO" if price < sma200 else "POR ENCIMA"
        out.append(f"⚠️ El S&P 500 ({_es(price, 0)}) está ahora {lado} de su media 200 ({_es(sma200, 0)}). "
                   "Alerta temprana: no se actúa hasta la revisión de fin de mes.")
    v = float(vix.iloc[-1])
    for lvl in VIX_LEVELS:
        key = f"vix{lvl}"
        if v >= lvl and key not in done:
            done.add(key)
            out.append(f"😨 VIX (miedo) en {_es(v)}: por encima de {lvl}. Días de mucha volatilidad.")

    state["avisadas"] = sorted(done)
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state))
    if out:
        out.append(f"Distancia a la media 200: {_pct(price / sma200 - 1)}. "
                   "Regla: no vender a mitad de mes; la decisión es el día de revisión.")
    return out


if __name__ == "__main__":
    msgs = check()
    print("\n".join(msgs) if msgs else "Sin alertas nuevas.")
