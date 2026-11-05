"""Descarga y caché de datos diarios OHLC."""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent.parent / "data_cache"


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def load(symbol: str, start: str = "1990-01-01", refresh: bool = False,
         max_age_hours: float = 12.0) -> pd.DataFrame:
    """Devuelve OHLCV diario ajustado. Cachea en CSV para no descargar cada vez."""
    CACHE_DIR.mkdir(exist_ok=True)
    safe = symbol.replace("^", "IDX_").replace("=", "_").replace("/", "_")
    path = CACHE_DIR / f"{safe}.csv"

    fresh = path.exists() and (time.time() - path.stat().st_mtime) < max_age_hours * 3600
    if fresh and not refresh:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
    else:
        import yfinance as yf

        # Siempre se descarga el histórico completo; luego se recorta a `start`.
        df = yf.download(symbol, start="1950-01-01", auto_adjust=True, progress=False)
        df = _flatten(df)
        if df.empty:
            if path.exists():
                df = pd.read_csv(path, index_col=0, parse_dates=True)
            else:
                raise RuntimeError(f"No hay datos para {symbol}")
        else:
            df.to_csv(path)

    df = df[["Open", "High", "Low", "Close"] + (["Volume"] if "Volume" in df else [])]
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df = df[(df["High"] >= df["Low"]) & (df["Close"] > 0)]
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)
    return df.loc[df.index >= pd.Timestamp(start)]
