import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import compare as c, data, trend
from swingbot.indicators import add_indicators
spy = data.load("SPY", start="1993-01-01")["Close"]
full = add_indicators(data.load("^GSPC", start="1990-01-01")).loc["1994-01-01":]
d = full.index
r = spy.reindex(d).ffill().pct_change().fillna(0)
rate = pd.Series(d.year, index=d).map(trend.USD_RATE).fillna(3.7) / 100
r3 = (3 * r - (2 * (rate + 0.01) + 0.005) / 252).clip(lower=-1)
left = pd.Series(1, index=d).groupby(d.to_period("M")).cumcount(ascending=False)
eom = (left == 0).to_numpy()
C, S = full.Close.to_numpy(), full.sma200.to_numpy()
def state(k=None, dd=None):
    st, out, peak = 1.0, [], C[0]
    for i in range(len(d)):
        if st == 1:
            peak = max(peak, C[i])
            if k is not None and C[i] < S[i] * (1 - k): st = 0.0          # emergencia: muy por debajo de la media
            if dd is not None and C[i] < peak * (1 - dd): st = 0.0        # emergencia: caída desde máximo
        if eom[i]:
            st = 1.0 if C[i] > S[i] else 0.0
            peak = C[i]
        out.append(st)
    return pd.Series(out, index=d).shift(1).fillna(1)
def run(inn, lo, hi):
    m = (d >= lo) & (d <= hi); sw = (inn.diff().abs() > 0).astype(int)
    p = c._simulate("", (inn * r3 + (1 - inn) * r)[m], d[m], 50, 50, sw[m], 2.0, "annual")
    return c.xirr(p.flows), (p.twr / p.twr.cummax() - 1).min()
rules = {"Sólo fin de mes (nuestra)": state()}
for k in (0.03, 0.05, 0.08): rules[f"+ salir si cae {k:.0%} bajo la media"] = state(k=k)
for dd in (0.10, 0.15, 0.20): rules[f"+ salir si cae {dd:.0%} desde máximo"] = state(dd=dd)
print(f"{'Regla':38} {'1994-2009':>10} {'2010-2026':>10} {'peor caída':>11}")
for k, inn in rules.items():
    a, da = run(inn, "1994-01-01", "2009-12-31"); b, db = run(inn, "2010-01-01", "2026-12-31")
    print(f"{k:38} {a:>+10.1%} {b:>+10.1%} {min(da, db):>+11.0%}")
