"""Estrategias de swing corto (días a ~3 semanas) sobre índices.

Todas son SOLO LARGOS y comparten un filtro de régimen: sólo se opera cuando el
índice está por encima de su media de 200 sesiones (tendencia alcista de fondo).
Con apalancamiento x3/x5 operar a la contra de la tendencia principal es la forma
más rápida de destruir la cuenta, así que ese filtro no es opcional.

Base empírica de cada idea:
- rsi2: reversión a la media de corto plazo en índices (L. Connors & C. Alvarez,
  "Short Term Trading Strategies That Work", 2008). Uno de los efectos más
  replicados en índices de renta variable estadounidenses.
- ibs: Internal Bar Strength bajo -> rebote al día siguiente (Pagonidis, 2013,
  "The IBS Effect: Mean Reversion in Equity ETFs").
- pullback: caídas de varios días consecutivos dentro de una tendencia alcista.
- tom: efecto cambio de mes (Ariel 1987; Lakonishok & Smidt 1988; McConnell & Xu
  2008): gran parte del retorno del mercado se concentra entre los últimos días
  de un mes y los primeros del siguiente.

Señal: se evalúa con el CIERRE del día t. La entrada la hace el backtester
(al cierre de t o a la apertura de t+1, según configuración).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd


@dataclass
class Strategy:
    name: str
    description: str
    entry: Callable[[pd.DataFrame, dict], pd.Series]
    exit: Callable[[pd.DataFrame, dict], pd.Series]
    params: dict = field(default_factory=dict)
    max_hold: int = 10  # sesiones; garantiza horizonte intra-semana / intra-mes

    def entry_signal(self, df: pd.DataFrame) -> pd.Series:
        return self.entry(df, self.params).fillna(False).astype(bool)

    def exit_signal(self, df: pd.DataFrame) -> pd.Series:
        return self.exit(df, self.params).fillna(False).astype(bool)

    def with_params(self, **kw) -> "Strategy":
        p = dict(self.params)
        max_hold = kw.pop("max_hold", self.max_hold)
        p.update(kw)
        return Strategy(self.name, self.description, self.entry, self.exit, p, max_hold)


def _regime(df: pd.DataFrame, p: dict) -> pd.Series:
    ok = df["Close"] > df["sma200"]
    if p.get("vol_max") is not None:
        ok &= df["vol20"] < p["vol_max"]
    return ok


# --- RSI(2) -----------------------------------------------------------------
def _rsi2_entry(df, p):
    return _regime(df, p) & (df["rsi2"] < p.get("rsi_entry", 10))


def _rsi2_exit(df, p):
    return df["Close"] > df["sma5"]


# --- IBS --------------------------------------------------------------------
def _ibs_entry(df, p):
    return _regime(df, p) & (df["ibs"] < p.get("ibs_entry", 0.2)) & (df["Close"] < df["sma5"])


def _ibs_exit(df, p):
    return (df["ibs"] > p.get("ibs_exit", 0.8)) | (df["Close"] > df["High"].shift(1))


# --- Pullback de N días -------------------------------------------------------
def _pullback_entry(df, p):
    return _regime(df, p) & (df["down_streak"] >= p.get("down_days", 3))


def _pullback_exit(df, p):
    return df["Close"] > df["sma5"]


# --- Cambio de mes ------------------------------------------------------------
def _tom_entry(df, p):
    # Entrar al cierre cuando quedan N sesiones para fin de mes.
    return _regime(df, p) & (df["days_left_month"] == p.get("days_before", 4))


def _tom_exit(df, p):
    # Salir al cierre de la sesión K del mes nuevo.
    return df["day_of_month"] == p.get("exit_day", 3)


# --- Combinada: cualquier señal de reversión ----------------------------------
def _combo_entry(df, p):
    return _rsi2_entry(df, p) | _ibs_entry(df, p) | _pullback_entry(df, p)


def _combo_exit(df, p):
    return df["Close"] > df["sma5"]


STRATEGIES: dict[str, Strategy] = {
    "rsi2": Strategy(
        "rsi2",
        "Cierre > SMA200 y RSI(2) < 10. Sale cuando cierra > SMA5.",
        _rsi2_entry, _rsi2_exit, {"rsi_entry": 10}, max_hold=10,
    ),
    "ibs": Strategy(
        "ibs",
        "Cierre > SMA200, IBS < 0.2 y cierre < SMA5. Sale con IBS > 0.8 o cierre > máximo previo.",
        _ibs_entry, _ibs_exit, {"ibs_entry": 0.2, "ibs_exit": 0.8}, max_hold=7,
    ),
    "pullback": Strategy(
        "pullback",
        "Cierre > SMA200 y 3 cierres bajistas seguidos. Sale cuando cierra > SMA5.",
        _pullback_entry, _pullback_exit, {"down_days": 3}, max_hold=10,
    ),
    "tom": Strategy(
        "tom",
        "Cambio de mes: entra 4 sesiones antes de fin de mes, sale al cierre de la 3ª sesión del mes.",
        _tom_entry, _tom_exit, {"days_before": 4, "exit_day": 3}, max_hold=9,
    ),
    "combo": Strategy(
        "combo",
        "Cualquiera de rsi2 / ibs / pullback (más operaciones). Sale cuando cierra > SMA5.",
        _combo_entry, _combo_exit,
        {"rsi_entry": 10, "ibs_entry": 0.2, "down_days": 3}, max_hold=10,
    ),
}


def get(name: str, **params) -> Strategy:
    if name not in STRATEGIES:
        raise KeyError(f"Estrategia desconocida '{name}'. Opciones: {', '.join(STRATEGIES)}")
    s = STRATEGIES[name]
    return s.with_params(**params) if params else s
