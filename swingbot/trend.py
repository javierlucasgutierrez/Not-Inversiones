"""Estrategia de tendencia mensual apalancada (Faber 2007; Gayed & Bilello 2016).

Regla: el ÚLTIMO día hábil de cada mes, con el cierre del S&P 500:
  - cierre > media de 200 sesiones  -> DENTRO: mantener / comprar el producto x2 o x3
  - cierre <= media de 200 sesiones -> FUERA: vender todo y quedarse en liquidez
Entre revisiones no se hace nada (ni stops ni operaciones intermedias).
"""
from __future__ import annotations

import pandas as pd

from . import compare as c, config, data
from .indicators import add_indicators

# Tipo de interés USD aprox. (media anual de los fondos federales), para la
# financiación de los productos apalancados. Aproximación, no datos oficiales.
USD_RATE = {1993: 3.0, 1994: 4.2, 1995: 5.8, 1996: 5.3, 1997: 5.5, 1998: 5.4, 1999: 5.0,
            2000: 6.2, 2001: 3.9, 2002: 1.7, 2003: 1.1, 2004: 1.4, 2005: 3.2, 2006: 5.0,
            2007: 5.0, 2008: 1.9, 2009: .2, 2010: .2, 2011: .1, 2012: .1, 2013: .1, 2014: .1,
            2015: .1, 2016: .4, 2017: 1.0, 2018: 1.8, 2019: 2.2, 2020: .4, 2021: .1, 2022: 1.7,
            2023: 5.0, 2024: 5.1, 2025: 4.2, 2026: 3.7}
SYMBOL = "^GSPC"


def status(refresh: bool = True) -> dict:
    df = add_indicators(data.load(SYMBOL, start="2015-01-01", refresh=refresh))
    last = df.iloc[-1]
    eom_mask = df.index.to_series().groupby(df.index.to_period("M")).transform("max") == df.index
    eom = df[eom_mask.values]
    # Si el último dato es el último día del mes en curso, ya cuenta como revisión.
    month_end_today = (df.index[-1] + pd.offsets.BMonthEnd(0)).normalize()
    last_check = eom.iloc[-1] if df.index[-1] < month_end_today else df.iloc[-1]
    last_check_date = eom.index[-1] if df.index[-1] < month_end_today else df.index[-1]
    next_check = (df.index[-1] + pd.offsets.BMonthEnd(1 if df.index[-1] >= month_end_today else 0))
    return {
        "date": df.index[-1], "close": float(last["Close"]), "sma200": float(last["sma200"]),
        "dist": float(last["Close"] / last["sma200"] - 1),
        "check_date": last_check_date, "check_close": float(last_check["Close"]),
        "check_sma200": float(last_check["sma200"]),
        "inside": bool(last_check["Close"] > last_check["sma200"]),
        "next_check": next_check.normalize(),
    }


def backtest(leverage: float = 3, start: str = "2004-01-01", end=None, initial=50.0,
             monthly=50.0, fee: float = 1.0) -> c.Path:
    """Simulación en € con aportaciones, financiación, comisiones e impuestos anuales."""
    fx = data.load(config.FX_SYMBOL, start="2003-12-01")["Close"]
    spy = data.load("SPY", start="1993-01-01")["Close"]
    df = add_indicators(data.load(SYMBOL, start="1995-01-01")).loc[start:end]
    d = df.index
    fxa = fx.reindex(d).ffill().bfill()
    fxr = (fxa.shift(1) / fxa).fillna(1)
    r = spy.reindex(d).ffill().pct_change().fillna(0)
    rate = pd.Series(d.year, index=d).map(USD_RATE).fillna(0.03) / 100
    r_lev = (leverage * r - ((leverage - 1) * (rate + 0.01) + 0.005) / 252).clip(lower=-1)
    eom = (df.index.to_series().groupby(df.index.to_period("M")).transform("max").values
           == df.index)
    inside = (df["Close"] > df["sma200"]).where(eom).ffill().fillna(True).astype(float)
    inside = inside.shift(1).fillna(1)
    rets = inside * ((1 + r_lev) * fxr - 1) + (1 - inside) * c.eur_cash_daily(d, fee=0)
    switches = (inside.diff().abs() > 0).astype(int)
    return c._simulate(f"x{leverage:g} con tendencia", rets, d, initial, monthly, switches, fee,
                       "annual")


def format_status(st: dict, leverage: float) -> str:
    estado = "DENTRO ✅" if st["inside"] else "FUERA ⛔"
    accion = (f"Mantener / comprar el certificado factor Long x{leverage:g} sobre el S&P 500."
              if st["inside"] else
              "Vender todo el producto apalancado y quedarse en liquidez.")
    return "\n".join([
        f"Estrategia de tendencia mensual (S&P 500, x{leverage:g})",
        f"  Última revisión ({st['check_date']:%d/%m/%Y}): cierre {st['check_close']:,.2f} vs "
        f"media 200 {st['check_sma200']:,.2f}  ->  {estado}",
        f"  Qué hacer ahora: {accion}",
        f"  Hoy ({st['date']:%d/%m/%Y}): cierre {st['close']:,.2f}, "
        f"{st['dist']:+.1%} respecto a la media de 200 sesiones",
        f"  Próxima revisión: último día hábil del mes, {st['next_check']:%d/%m/%Y} "
        "(mirar hacia las 21:45, hora de España; confirmar festivos de EE.UU.)",
    ])
