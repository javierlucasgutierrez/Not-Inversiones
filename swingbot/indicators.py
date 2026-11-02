"""Indicadores técnicos (sin dependencias externas aparte de pandas/numpy)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def rsi(s: pd.Series, n: int = 2) -> pd.Series:
    """RSI de Wilder."""
    delta = s.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    avg_up = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_down = down.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = avg_up / avg_down.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.fillna(100.0).where(avg_up.notna())


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def ibs(df: pd.DataFrame) -> pd.Series:
    """Internal Bar Strength: posición del cierre dentro del rango del día (0..1)."""
    rng = (df["High"] - df["Low"]).replace(0, np.nan)
    return ((df["Close"] - df["Low"]) / rng).fillna(0.5)


def realized_vol(s: pd.Series, n: int = 20) -> pd.Series:
    """Volatilidad realizada anualizada."""
    return s.pct_change().rolling(n).std() * np.sqrt(252)


def trading_days_left_in_month(index: pd.DatetimeIndex) -> pd.Series:
    """Nº de sesiones que quedan en el mes DESPUÉS de cada fecha (0 = último día del mes).

    Para el histórico usa las sesiones reales. Para la última barra (hoy) completa
    con días hábiles estimados, porque el futuro no está en los datos.
    """
    idx = pd.DatetimeIndex(index)
    period = idx.to_period("M")
    s = pd.Series(1, index=idx)
    left = s.groupby(period).cumcount(ascending=False)
    # Corrige el mes en curso (incompleto) con días hábiles estimados.
    last = idx[-1]
    month_end = (last + pd.offsets.MonthEnd(0)).normalize()
    future_bdays = len(pd.bdate_range(last + pd.Timedelta(days=1), month_end))
    cur = period == last.to_period("M")
    left[cur] = left[cur] + future_bdays
    return left


def trading_day_of_month(index: pd.DatetimeIndex) -> pd.Series:
    """Nº de sesión dentro del mes (1 = primera sesión)."""
    idx = pd.DatetimeIndex(index)
    return pd.Series(1, index=idx).groupby(idx.to_period("M")).cumsum()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c = df["Close"]
    df["sma5"] = sma(c, 5)
    df["sma10"] = sma(c, 10)
    df["sma50"] = sma(c, 50)
    df["sma200"] = sma(c, 200)
    df["rsi2"] = rsi(c, 2)
    df["rsi3"] = rsi(c, 3)
    df["atr14"] = atr(df, 14)
    df["ibs"] = ibs(df)
    df["vol20"] = realized_vol(c, 20)
    df["low10"] = df["Low"].rolling(10).min()
    df["high10"] = df["High"].rolling(10).max()
    df["down_streak"] = _streak(c.diff() < 0)
    df["days_left_month"] = trading_days_left_in_month(df.index).values
    df["day_of_month"] = trading_day_of_month(df.index).values
    return df


def _streak(cond: pd.Series) -> pd.Series:
    """Longitud de la racha actual en la que `cond` es True."""
    cond = cond.fillna(False).astype(int)
    groups = (cond == 0).cumsum()
    return cond.groupby(groups).cumsum()
