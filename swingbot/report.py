"""Informe de robustez: varios índices, apalancamientos, gestión de riesgo y
validación fuera de muestra (in-sample hasta 2014, out-of-sample 2015+)."""
from __future__ import annotations

import pandas as pd

from . import backtest as bt, config, data
from .indicators import add_indicators
from .strategies import get

SPLIT = "2015-01-01"


def _row(sym, strat, lev, label, s):
    return {
        "indice": config.WATCHLIST.get(sym, {}).get("name", sym), "estrategia": strat,
        "lev": lev, "gestion": label, "ops": s.get("trades", 0),
        "ops/año": round(s.get("trades_per_year", 0), 1),
        "aciertos": s.get("win_rate", 0), "media_op": s.get("avg_trade", 0),
        "peor_op": s.get("worst_trade", 0), "PF": s.get("profit_factor", 0),
        "op>=5%": s.get("hit_5pct", 0), "dias": round(s.get("avg_days", 0), 1),
        "CAGR": s.get("cagr", 0), "maxDD": s.get("max_dd", 0),
        "Sharpe": s.get("sharpe", 0), "meses>=5%": s.get("months_ge_5pct", 0),
    }


RISK_VARIANTS = {
    "sin TP/SL": dict(take_profit=None, stop_loss=None),
    "TP5%": dict(take_profit=0.05, stop_loss=None),
    "TP5% SL10%": dict(take_profit=0.05, stop_loss=0.10),
    "TP5% SL10% 50%cap": dict(take_profit=0.05, stop_loss=0.10, allocation=0.5),
}


def full_report(symbols=None, strategies=None, leverages=(1, 3, 5), start="1995-01-01"):
    symbols = symbols or list(config.WATCHLIST)
    strategies = strategies or config.DEFAULT_STRATEGIES + ["combo"]
    rows, oos = [], []
    for sym in symbols:
        df = add_indicators(data.load(sym, start=start))
        for name in strategies:
            strat = get(name)
            for lev in leverages:
                for label, kw in RISK_VARIANTS.items():
                    if lev == 1 and label != "sin TP/SL":
                        continue
                    cfg = bt.BTConfig(leverage=lev, **kw)
                    rows.append(_row(sym, name, lev, label, bt.run(df, strat, cfg, sym).stats()))
            # Validación fuera de muestra con la configuración recomendada.
            cfg = bt.BTConfig(leverage=3, take_profit=config.DEFAULT_TAKE_PROFIT,
                              stop_loss=config.DEFAULT_STOP_LOSS)
            for period, part in (("IS <2015", df.loc[:SPLIT]), ("OOS 2015+", df.loc[SPLIT:])):
                if len(part) > 300:
                    oos.append(_row(sym, name, 3, period, bt.run(part, strat, cfg, sym).stats()))
    return pd.DataFrame(rows), pd.DataFrame(oos)


def fmt(df: pd.DataFrame) -> str:
    df = df.copy()
    pct = ["aciertos", "media_op", "peor_op", "op>=5%", "CAGR", "maxDD", "meses>=5%"]
    for c in pct:
        if c in df:
            df[c] = df[c].map(lambda v: f"{v:+.1%}" if c in ("media_op", "peor_op", "CAGR", "maxDD") else f"{v:.0%}")
    for c in ("PF", "Sharpe"):
        if c in df:
            df[c] = df[c].map(lambda v: f"{v:.2f}")
    return df.to_markdown(index=False) if _has_tabulate() else df.to_string(index=False)


def _has_tabulate() -> bool:
    try:
        import tabulate  # noqa: F401
        return True
    except ImportError:
        return False


def broker_report(broker: str = "trade_republic", symbols=("^GSPC", "^NDX"),
                  strategies=("pullback", "rsi2"), capitals=(500, 1_000, 3_000, 10_000),
                  products=("factor", "knockout"), leverages=(3, 5)):
    """Mismo sistema, pero con los costes reales del bróker, en euros y desde 2004
    (inicio del histórico EUR/USD)."""
    fx = data.load(config.FX_SYMBOL, start="2003-12-01")["Close"]
    rows = []
    for sym in symbols:
        df = add_indicators(data.load(sym, start="1995-01-01")).loc[fx.index[0]:]
        f = fx if sym in config.USD_INDICES else None
        for name in strategies:
            for prod in products:
                for lev in leverages:
                    for cap in capitals:
                        cfg = bt.make_config(lev, prod, broker, take_profit=config.DEFAULT_TAKE_PROFIT,
                                             stop_loss=config.DEFAULT_STOP_LOSS, capital=cap)
                        s = bt.run(df, get(name), cfg, sym, fx=f).stats()
                        row = _row(sym, name, lev, prod, s)
                        row["capital_€"] = cap
                        row["final_€"] = round(cap * s.get("final_equity", 1))
                        rows.append(row)
    cols = ["indice", "estrategia", "gestion", "lev", "capital_€", "ops/año", "aciertos",
            "media_op", "peor_op", "PF", "CAGR", "maxDD", "final_€"]
    return pd.DataFrame(rows)[cols].rename(columns={"gestion": "producto"})
