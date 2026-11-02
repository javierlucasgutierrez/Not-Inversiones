"""Operativa para una cuenta de fondeo con los patrones de 1 día del S&P 500.

python -m swingbot fondeo --cuenta 10000

Reglas (ver research/fondeo.py y research/mine2.py):
- Señal al cierre del día (hacia las 21:45, hora de España), cualquiera de:
    A) RSI(2) < 5 y 3 cierres bajistas seguidos
    B) IBS < 0,2 en lunes (cierra cerca del mínimo del día)
    C) 3 cierres bajistas seguidos
- Entrada: comprar el CFD del S&P 500 (US500) antes del cierre, exposición x2 de la cuenta.
- Salida: al cierre del día siguiente. Si ese día vuelve a haber señal, se mantiene.
- Stop de protección: −1,8 % del índice (≈ −3,6 % de la cuenta), para no tocar
  nunca el límite diario del −5 %.
"""
from __future__ import annotations

import pandas as pd

from . import data
from .indicators import add_indicators

LEVERAGE = 2.0


def _es(v: float, d: int = 2) -> str:
    """Número con formato español: 7.628,54"""
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
STOP_INDEX = 0.018


def patterns(df: pd.DataFrame) -> dict[str, pd.Series]:
    monday = pd.Series(df.index.dayofweek == 0, index=df.index)
    return {
        "A · RSI(2) < 5 + 3 días bajando": (df.rsi2 < 5) & (df.down_streak >= 3),
        "B · IBS < 0,2 en lunes": (df.ibs < 0.2) & monday,
        "C · 3 días bajando": df.down_streak >= 3,
    }


def report(cuenta: float) -> str:
    df = add_indicators(data.load("^GSPC", start="2020-01-01", refresh=True))
    last, date = df.iloc[-1], df.index[-1]
    pats = {k: bool(v.iloc[-1]) for k, v in patterns(df).items()}
    active = [k for k, v in pats.items() if v]
    close = float(last.Close)
    lines = [f"Cuenta de fondeo · S&P 500 (US500) · cierre {date:%d/%m/%Y}: {_es(close)}",
             f"  RSI(2) {last.rsi2:.1f} · IBS {last.ibs:.2f} · cierres bajistas seguidos {int(last.down_streak)}"
             f" · {'lunes' if date.dayofweek == 0 else 'no es lunes'}"]
    for k, v in pats.items():
        lines.append(f"  [{'SEÑAL' if v else '  -  '}] {k}")
    if active:
        nominal = cuenta * LEVERAGE
        stop = close * (1 - STOP_INDEX)
        lines += [
            "",
            "OPERACIÓN: COMPRAR US500 antes del cierre de hoy",
            f"  Exposición: {_es(nominal, 0)} (x{LEVERAGE:g} de {_es(cuenta, 0)}) ≈ {_es(nominal / close)} unidades de US500",
            f"  Stop de protección: {_es(stop, 0)} (−{STOP_INDEX:.1%} del índice ≈ −{STOP_INDEX * LEVERAGE:.1%} de la cuenta)",
            "  Salida: al cierre de mañana (hacia las 21:45). Si mañana vuelve a haber señal, se mantiene.",
        ]
    else:
        lines += ["", "Sin operación hoy. Si tienes una posición abierta de ayer, ciérrala al cierre de hoy."]
    lines.append("\nOjo: si lo miras con la bolsa abierta, el 'cierre' es el precio de ese momento. "
                 "Decide hacia las 21:45 (hora de España).")
    lines.append("No es asesoramiento financiero. Comprueba las reglas de tu empresa de fondeo "
                 "(posiciones de un día para otro, noticias y fines de semana).")
    return "\n".join(lines)


def history(months: int = 6) -> pd.DataFrame:
    """Señales recientes y lo que hizo el índice al día siguiente."""
    df = add_indicators(data.load("^GSPC", start="2020-01-01"))
    p = patterns(df)
    any_sig = p["A · RSI(2) < 5 + 3 días bajando"] | p["B · IBS < 0,2 en lunes"] | p["C · 3 días bajando"]
    nxt = df.Close.shift(-1) / df.Close - 1
    out = df.loc[any_sig, ["Close"]].assign(
        patron=[" + ".join(k[0] for k, v in p.items() if v.loc[d]) for d in df.index[any_sig]],
        indice_dia_sig=nxt[any_sig], cuenta_x2=nxt[any_sig] * LEVERAGE)
    return out.loc[out.index >= df.index[-1] - pd.DateOffset(months=months)]
