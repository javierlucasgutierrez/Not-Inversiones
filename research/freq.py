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
above = full.Close > full.sma200
def run(check_mask, lo, hi):
    inn = above.where(check_mask).ffill().fillna(True).astype(float).shift(1).fillna(1)
    m = (d >= lo) & (d <= hi)
    sw = (inn.diff().abs() > 0).astype(int)
    p = c._simulate("", (inn * r3 + (1 - inn) * r)[m], d[m], 50, 50, sw[m], 2.0, "annual")
    years = (d[m][-1] - d[m][0]).days / 365.25
    return c.xirr(p.flows), sw[m].sum() / years
dom = pd.Series(1, index=d).groupby(d.to_period("M")).cumsum()          # sesión del mes (1..)
left = pd.Series(1, index=d).groupby(d.to_period("M")).cumcount(ascending=False)  # 0 = último día
rules = {f"día {k} del mes": (dom == k) for k in (1, 5, 10, 15)}
rules["último día del mes"] = (left == 0)
rules["5 días antes de fin de mes"] = (left == 5)
rules["cada viernes (semanal)"] = pd.Series(d.dayofweek == 4, index=d)
rules["cada 2 semanas"] = pd.Series((d.dayofweek == 4) & (d.isocalendar().week.values % 2 == 0), index=d)
rules["cada día"] = pd.Series(True, index=d)
print(f"{'Cuándo se revisa':28} {'1994-2009':>10} {'2010-2026':>10} {'cambios/año':>12}")
for k, m in rules.items():
    a, _ = run(m, "1994-01-01", "2009-12-31"); b, n = run(m, "2010-01-01", "2026-12-31")
    print(f"{k:28} {a:>+10.1%} {b:>+10.1%} {n:>12.1f}")
