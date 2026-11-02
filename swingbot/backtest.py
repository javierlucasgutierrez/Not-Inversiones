"""Motor de backtest con apalancamiento realista.

Dos modelos de apalancamiento:

- "etf": producto apalancado con REINICIO DIARIO (TQQQ, UPRO, ETPs x3/x5 de
  WisdomTree / Leverage Shares...). Se construye una serie sintética
      N_t = N_{t-1} * (1 + L * r_t - coste_diario)
  donde r_t es el retorno diario del índice y coste_diario incluye la comisión
  de gestión del ETP y la financiación de (L-1) veces el capital. Así aparece
  el "volatility decay" real que sufren estos productos.

- "cfd": CFD / futuro con apalancamiento FIJO desde la entrada:
      valor = 1 + L * (P / P_entrada - 1) - financiación acumulada
  Si el valor llega a 0 la posición se liquida (pierdes lo asignado).

Las señales se calculan con el cierre del día t (sin mirar el futuro). Take
profit y stop se comprueban dentro del día con máximo/mínimo; si en el mismo día
se tocan ambos se asume el STOP (supuesto conservador). Si el precio abre más
allá del nivel (gap) se ejecuta en la apertura.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from .indicators import add_indicators
from .strategies import Strategy


@dataclass
class BTConfig:
    leverage: float = 1.0
    mode: str = "etf"                 # "etf" | "cfd"
    entry: str = "close"              # "close" (orden MOC) | "next_open"
    take_profit: float | None = 0.05  # objetivo sobre la posición (0.05 = +5%)
    stop_loss: float | None = None    # pérdida máx. sobre la posición (0.10 = -10%)
    stop_atr: float | None = None     # stop en el subyacente: entrada - k * ATR14
    cost_per_side: float = 0.0005     # comisión + deslizamiento por lado (sobre el nocional)
    annual_rate: float = 0.04         # tipo de financiación anual del apalancamiento
    expense_ratio: float = 0.0095     # comisión anual del ETP apalancado (solo modo etf, L>1)
    allocation: float = 1.0           # fracción del capital asignada a cada operación


@dataclass
class Result:
    trades: pd.DataFrame
    equity: pd.Series
    config: BTConfig
    strategy: str
    symbol: str

    def stats(self) -> dict:
        return compute_stats(self.trades, self.equity)


def run(df: pd.DataFrame, strategy: Strategy, cfg: BTConfig, symbol: str = "") -> Result:
    if "sma200" not in df:
        df = add_indicators(df)
    df = df.dropna(subset=["sma200", "atr14"])

    O = df["Open"].to_numpy(float)
    H = df["High"].to_numpy(float)
    Lo = df["Low"].to_numpy(float)
    C = df["Close"].to_numpy(float)
    ATR = df["atr14"].to_numpy(float)
    dates = df.index
    entry_sig = strategy.entry_signal(df).to_numpy()
    exit_sig = strategy.exit_signal(df).to_numpy()
    n = len(df)

    L = float(cfg.leverage)
    etf = cfg.mode == "etf"
    if etf:
        er = cfg.expense_ratio if L > 1 else 0.0
        daily_cost = (er + max(L - 1, 0) * cfg.annual_rate) / 252
        side_cost = cfg.cost_per_side
    else:
        daily_cost = L * cfg.annual_rate / 252
        side_cost = cfg.cost_per_side * L

    # Serie sintética del producto apalancado (modo etf).
    r = np.zeros(n)
    r[1:] = C[1:] / C[:-1] - 1
    nav = np.cumprod(np.maximum(1 + L * r - daily_cost, 0.0)) if etf else None

    def value_at(P: float, t: int, st: dict) -> float:
        """Valor de la posición (1.0 = entrada) si el subyacente cotiza a P en el día t."""
        if etf:
            return nav[t - 1] * max(1 + L * (P / C[t - 1] - 1), 0.0) / st["nav_entry"]
        return max(1 + L * (P / st["px"] - 1) - st["fin"], 0.0)

    def price_for_value(V: float, t: int, st: dict) -> float:
        """Precio del subyacente al que la posición vale V en el día t (inversa de value_at)."""
        if etf:
            return C[t - 1] * (1 + (V * st["nav_entry"] / nav[t - 1] - 1) / L)
        return st["px"] * (1 + (V - 1 + st["fin"]) / L)

    def open_position(t: int, at_open: bool) -> dict:
        px = O[t] if at_open else C[t]
        atr_ref = ATR[t - 1] if at_open else ATR[t]
        st = {"i": t, "px": px, "fin": 0.0, "mae": 1.0, "cash": cash, "at_open": at_open,
              "stop_px": px - cfg.stop_atr * atr_ref if cfg.stop_atr else None}
        if etf:
            st["nav_entry"] = nav[t - 1] * (1 + L * (O[t] / C[t - 1] - 1)) if at_open else nav[t]
        return st

    trades = []
    equity = np.empty(n)
    cash = 1.0
    st: dict | None = None
    pending = False

    for t in range(n):
        # 1) Entrada pendiente en la apertura de hoy.
        if st is None and pending:
            pending = False
            st = open_position(t, at_open=True)

        # 2) Gestión de la posición abierta.
        if st is not None and (t > st["i"] or st["at_open"]):
            if not etf and t > st["i"]:
                st["fin"] += daily_cost
            exit_px = reason = None
            tp_px = price_for_value(1 + cfg.take_profit, t, st) if cfg.take_profit else None
            sl_levels = []
            if cfg.stop_loss:
                sl_levels.append(price_for_value(1 - cfg.stop_loss, t, st))
            if st["stop_px"] is not None:
                sl_levels.append(st["stop_px"])
            if not etf:  # nivel de liquidación del CFD
                sl_levels.append(price_for_value(0.0, t, st))
            sl_px = max(sl_levels) if sl_levels else None
            gap_ok = t > st["i"]  # el día de entrada en apertura no hay gap posible

            if sl_px is not None and gap_ok and O[t] <= sl_px:
                exit_px, reason = O[t], "stop"
            elif tp_px is not None and gap_ok and O[t] >= tp_px:
                exit_px, reason = O[t], "take_profit"
            elif sl_px is not None and Lo[t] <= sl_px:
                exit_px, reason = sl_px, "stop"
            elif tp_px is not None and H[t] >= tp_px:
                exit_px, reason = tp_px, "take_profit"
            elif exit_sig[t] and t > st["i"]:
                exit_px, reason = C[t], "signal"
            elif (t - st["i"]) >= strategy.max_hold:
                exit_px, reason = C[t], "time"

            low_seen = Lo[t] if exit_px is None else max(Lo[t], min(exit_px, C[t]))
            st["mae"] = min(st["mae"], value_at(low_seen, t, st))

            if exit_px is not None:
                v = value_at(exit_px, t, st)
                if not etf and v <= 0:
                    reason = "liquidated"
                ret = v * (1 - side_cost) ** 2 - 1
                cash = st["cash"] * (1 + cfg.allocation * ret)
                trades.append({
                    "entry_date": dates[st["i"]], "exit_date": dates[t],
                    "entry_px": st["px"], "exit_px": exit_px,
                    "days": t - st["i"], "ret": ret,
                    "underlying_ret": exit_px / st["px"] - 1,
                    "mae": st["mae"] - 1, "reason": reason,
                })
                st = None

        # 3) Valoración diaria (mark-to-market).
        if st is None:
            equity[t] = cash
        elif t == st["i"] and not st["at_open"]:
            equity[t] = st["cash"] * (1 - cfg.allocation * side_cost)
        else:
            v = value_at(C[t], t, st)
            equity[t] = st["cash"] * (1 + cfg.allocation * (v * (1 - side_cost) - 1))

        # 4) Nueva señal al cierre (sólo si estamos fuera).
        if st is None and not pending and entry_sig[t]:
            if cfg.entry == "close":
                st = open_position(t, at_open=False)
            elif t + 1 < n:
                pending = True

    trades_df = pd.DataFrame(trades)
    eq = pd.Series(equity, index=dates, name="equity")
    return Result(trades_df, eq, cfg, strategy.name, symbol)


def compute_stats(trades: pd.DataFrame, equity: pd.Series) -> dict:
    if trades.empty:
        return {"trades": 0}
    rets = trades["ret"]
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = equity.iloc[-1] ** (1 / years) - 1 if equity.iloc[-1] > 0 else -1.0
    dd = equity / equity.cummax() - 1
    daily = equity.pct_change().dropna()
    sharpe = daily.mean() / daily.std() * np.sqrt(252) if daily.std() > 0 else 0.0
    monthly = equity.resample("ME").last().pct_change().dropna()
    days_in = trades["days"].sum()
    return {
        "trades": int(len(trades)),
        "trades_per_year": len(trades) / years,
        "win_rate": len(wins) / len(trades),
        "avg_trade": rets.mean(),
        "median_trade": rets.median(),
        "avg_win": wins.mean() if len(wins) else 0.0,
        "avg_loss": losses.mean() if len(losses) else 0.0,
        "worst_trade": rets.min(),
        "profit_factor": wins.sum() / -losses.sum() if losses.sum() < 0 else np.inf,
        "hit_5pct": (rets >= 0.045).mean(),  # TP del 5% menos costes
        "avg_days": trades["days"].mean(),
        "exposure": days_in / len(equity),
        "cagr": cagr,
        "max_dd": dd.min(),
        "sharpe": sharpe,
        "months_pos": (monthly > 0).mean(),
        "months_ge_5pct": (monthly >= 0.05).mean(),
        "worst_month": monthly.min(),
        "final_equity": equity.iloc[-1],
    }


def config_dict(cfg: BTConfig) -> dict:
    return asdict(cfg)
