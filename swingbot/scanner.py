"""Escáner diario: ¿hay señal de entrada hoy al cierre en algún índice?

Pensado para ejecutarse ~15-20 min antes del cierre (con el precio casi
definitivo) o justo después del cierre para entrar en la apertura siguiente.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import config, data
from .indicators import add_indicators
from .strategies import get


@dataclass
class Signal:
    symbol: str
    name: str
    strategy: str
    date: pd.Timestamp
    close: float
    regime_ok: bool
    signal: bool
    validated: bool
    detail: str
    tp_price: float | None
    sl_price: float | None
    exit_by: pd.Timestamp


def _detail(strategy: str, row: pd.Series) -> str:
    if strategy == "rsi2":
        return f"RSI(2)={row['rsi2']:.1f} (entra < 10)"
    if strategy == "ibs":
        return f"IBS={row['ibs']:.2f} (entra < 0.20), cierre {'<' if row['Close'] < row['sma5'] else '>='} SMA5"
    if strategy == "pullback":
        return f"{int(row['down_streak'])} cierres bajistas seguidos (entra >= 3)"
    if strategy == "tom":
        return f"quedan {int(row['days_left_month'])} sesiones de mes (entra con 4)"
    if strategy == "combo":
        return f"RSI2={row['rsi2']:.1f} IBS={row['ibs']:.2f} racha={int(row['down_streak'])}"
    return ""


def scan(symbols: list[str] | None = None, strategies: list[str] | None = None,
         leverage: float = config.DEFAULT_LEVERAGE,
         take_profit: float = config.DEFAULT_TAKE_PROFIT,
         stop_loss: float = config.DEFAULT_STOP_LOSS,
         refresh: bool = True) -> list[Signal]:
    symbols = symbols or list(config.WATCHLIST)
    strategies = strategies or config.DEFAULT_STRATEGIES
    out: list[Signal] = []
    for sym in symbols:
        df = add_indicators(data.load(sym, start="2015-01-01", refresh=refresh))
        last = df.iloc[-1]
        date = df.index[-1]
        regime = bool(last["Close"] > last["sma200"])
        for name in strategies:
            strat = get(name)
            sig = bool(strat.entry_signal(df).iloc[-1])
            close = float(last["Close"])
            # Movimiento del subyacente necesario para +TP / -SL con apalancamiento L
            # (aprox. el primer día; después varía ligeramente por el reinicio diario).
            tp = close * (1 + take_profit / leverage) if take_profit else None
            sl = close * (1 - stop_loss / leverage) if stop_loss else None
            exit_by = date + pd.offsets.BDay(strat.max_hold)
            out.append(Signal(sym, config.WATCHLIST.get(sym, {}).get("name", sym), name, date,
                              close, regime, sig, name in config.VALIDATED.get(sym, []),
                              _detail(name, last), tp, sl, exit_by))
    return out


def format_signals(signals: list[Signal], leverage: float) -> str:
    lines = []
    active = [s for s in signals if s.signal and s.validated]
    info = [s for s in signals if s.signal and not s.validated]
    if active:
        lines.append(f"=== SEÑALES DE COMPRA (x{leverage:g}) ===")
        for s in active:
            inst = config.WATCHLIST.get(s.symbol, {})
            prod = inst.get("x5" if leverage >= 5 else "x3", "")
            lines.append(
                f"* {s.name} [{s.strategy}] cierre {s.close:,.2f} ({s.date:%Y-%m-%d})\n"
                f"    {s.detail}\n"
                f"    Objetivo índice ~{s.tp_price:,.2f} | Stop índice ~{s.sl_price:,.2f} | "
                f"Salida máx. {s.exit_by:%Y-%m-%d} o cuando la estrategia dé salida\n"
                f"    Instrumentos: {prod}"
            )
    else:
        lines.append("Sin señales de compra hoy.")
    if info:
        lines.append("")
        lines.append("Señales NO validadas (sólo informativas, no operar):")
        for s in info:
            lines.append(f"  - {s.name} [{s.strategy}] {s.detail}")
    lines.append("")
    lines.append("--- Estado por índice ---")
    for s in signals:
        flag = ("SEÑAL" if s.validated else "info") if s.signal else ("  ok " if s.regime_ok else "BAJISTA")
        lines.append(f"[{flag:7}] {s.name:14} {s.strategy:8} {s.detail}")
    if any(not s.regime_ok for s in signals):
        lines.append("\nBAJISTA = índice bajo su SMA200: no se abren largos apalancados.")
    return "\n".join(lines)
