import numpy as np
import pandas as pd
import pytest

from swingbot import backtest as bt
from swingbot.indicators import add_indicators, rsi
from swingbot.strategies import Strategy


def _df(closes, spread=0.0):
    idx = pd.bdate_range("2020-01-01", periods=len(closes))
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"Open": c.shift(1).fillna(c.iloc[0]), "High": c * (1 + spread),
                         "Low": c * (1 - spread), "Close": c})


def _one_trade_strategy(entry_pos, hold):
    def entry(df, p):
        s = pd.Series(False, index=df.index)
        s.iloc[entry_pos] = True
        return s
    return Strategy("t", "", entry, lambda df, p: pd.Series(False, index=df.index), {}, hold)


def _prepared(closes):
    df = add_indicators(_df(closes))
    df["sma200"] = df["sma200"].fillna(0)
    df["atr14"] = df["atr14"].fillna(1)
    return df


ZERO_COST = dict(cost_per_side=0, annual_rate=0, expense_ratio=0, take_profit=None)


def test_etf_leverage_compounds_daily():
    closes = [100, 100, 102, 99, 101, 103, 103]
    df = _prepared(closes)
    res = bt.run(df, _one_trade_strategy(1, 4), bt.BTConfig(leverage=3, **ZERO_COST))
    r = np.diff(closes[1:6]) / np.array(closes[1:5])
    expected = np.prod(1 + 3 * r) - 1
    assert res.trades["ret"].iloc[0] == pytest.approx(expected)
    # Distinto del x3 "estático" -> existe el efecto de reinicio diario
    assert expected != pytest.approx(3 * (closes[5] / closes[1] - 1))


def test_cfd_leverage_is_linear():
    closes = [100, 100, 102, 99, 101, 103, 103]
    df = _prepared(closes)
    res = bt.run(df, _one_trade_strategy(1, 4), bt.BTConfig(leverage=5, mode="cfd", **ZERO_COST))
    assert res.trades["ret"].iloc[0] == pytest.approx(5 * (103 / 100 - 1))


def test_take_profit_hits_exact_level():
    closes = [100, 100, 101, 104, 104]
    df = _prepared(closes)
    df["High"] = df["Close"] * 1.01
    cfg = bt.BTConfig(leverage=3, **{**ZERO_COST, "take_profit": 0.05})
    res = bt.run(df, _one_trade_strategy(1, 10), cfg)
    t = res.trades.iloc[0]
    assert t["reason"] == "take_profit"
    assert t["ret"] == pytest.approx(0.05)


def test_stop_beats_take_profit_same_day():
    closes = [100, 100, 100, 100]
    df = _prepared(closes)
    df.loc[df.index[2], ["High", "Low"]] = [110, 90]
    cfg = bt.BTConfig(leverage=3, **{**ZERO_COST, "take_profit": 0.05, "stop_loss": 0.10})
    res = bt.run(df, _one_trade_strategy(1, 10), cfg)
    assert res.trades.iloc[0]["reason"] == "stop"
    assert res.trades.iloc[0]["ret"] == pytest.approx(-0.10)


def test_gap_fills_at_open():
    closes = [100, 100, 90, 90]
    df = _prepared(closes)
    df["Open"] = [100, 100, 90, 90]
    cfg = bt.BTConfig(leverage=3, **{**ZERO_COST, "stop_loss": 0.10})
    res = bt.run(df, _one_trade_strategy(1, 10), cfg)
    assert res.trades.iloc[0]["ret"] == pytest.approx(-0.30)  # el gap salta el stop


def test_rsi_bounds():
    s = pd.Series(np.random.default_rng(0).normal(0, 1, 300).cumsum() + 100)
    r = rsi(s, 2).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_fixed_fee_weighs_more_on_small_accounts():
    closes = [100, 100, 102, 104, 104]
    df = _prepared(closes)
    base = dict(ZERO_COST, leverage=3, fixed_fee=1.0)
    small = bt.run(df, _one_trade_strategy(1, 2), bt.BTConfig(capital=200, **base))
    big = bt.run(df, _one_trade_strategy(1, 2), bt.BTConfig(capital=20_000, **base))
    gross = bt.run(df, _one_trade_strategy(1, 2), bt.BTConfig(leverage=3, **ZERO_COST))
    g = gross.trades["ret"].iloc[0]
    assert small.trades["ret"].iloc[0] == pytest.approx(g - 2 / 200)
    assert big.trades["ret"].iloc[0] == pytest.approx(g - 2 / 20_000)


def test_knockout_is_knocked_out_at_barrier():
    closes = [100, 100, 95, 60, 60]
    df = _prepared(closes)
    cfg = bt.BTConfig(leverage=3, mode="knockout", **ZERO_COST)
    t = bt.run(df, _one_trade_strategy(1, 10), cfg).trades.iloc[0]
    assert t["reason"] == "knock_out"
    assert t["ret"] == pytest.approx(-1.0)


def test_eur_conversion():
    closes = [100, 100, 110, 110]
    df = _prepared(closes)
    fx = pd.Series([1.0, 1.0, 1.1, 1.1], index=df.index)  # el dólar se deprecia un 10 %
    t = bt.run(df, _one_trade_strategy(1, 1), bt.BTConfig(leverage=1, **ZERO_COST), fx=fx).trades.iloc[0]
    assert t["ret"] == pytest.approx(1.10 / 1.10 - 1)
