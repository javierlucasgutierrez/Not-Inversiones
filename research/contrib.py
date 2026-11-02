import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import compare as c, data, trend
from swingbot.indicators import add_indicators
from swingbot.strategies import get
spy = data.load("SPY", start="1993-01-01")["Close"]
full = add_indicators(data.load("^GSPC", start="1990-01-01"))
sig = get("combo").entry_signal(full) | (full.rsi2 < 10)
f = full.loc["1994-01-01":]; d = f.index; sig = sig.reindex(d).fillna(False)
r = spy.reindex(d).ffill().pct_change().fillna(0)
rate = pd.Series(d.year, index=d).map(trend.USD_RATE).fillna(3.7) / 100
r3 = (3 * r - (2 * (rate + 0.01) + 0.005) / 252).clip(lower=-1)
per = d.to_period("M")
left = pd.Series(1, index=d).groupby(per).cumcount(ascending=False)
eom = (left == 0)
inn = (f.Close > f.sma200).where(eom).ffill().fillna(True).astype(float).shift(1).fillna(1)
ret = (inn * r3 + (1 - inn) * r).to_numpy()
def contrib_days(mode):
    days = set()
    for m, idx in pd.Series(d, index=d).groupby(per):
        idx = list(idx)
        if mode == "dia1": days.add(idx[0])
        elif mode == "bajada":   # primera señal de bajada del mes; si no hay, último día
            s = [x for x in idx if sig.loc[x]]
            days.add(s[0] if s else idx[-1])
        elif mode == "ultimo": days.add(idx[-1])
        elif mode == "mitad": days.add(idx[len(idx)//2])
    return days
def sim(mode, lo, hi):
    days = contrib_days(mode); v = 0.0; cash = 0.0; inv = 0.0; flows = []
    m = np.where((d >= lo) & (d <= hi))[0]
    for j, t in enumerate(m):
        if j > 0: v *= 1 + ret[t]
        if d[t].day <= 7 and (j == 0 or d[m[j-1]].month != d[t].month):   # cobras el día 1: 50 € a la cuenta
            cash += 50; inv += 50; flows.append((d[t], -50))
        if d[t] in days and cash > 0:
            v += cash - 1.0; cash = 0.0          # 1 € de comisión por compra
    final = v + cash
    flows.append((d[m[-1]], final))
    return final, c.xirr(flows)
for mode, lab in (("dia1", "Día 1 del mes (actual)"), ("mitad", "Mitad de mes"), ("ultimo", "Último día del mes"), ("bajada", "Esperar a una bajada (señal)")):
    a = sim(mode, "1994-01-01", "2009-12-31"); b = sim(mode, "2010-01-01", "2026-12-31")
    print(f"{lab:32} 1994-2009: {a[0]:>9,.0f} (TIR {a[1]:+.1%})   2010-2026: {b[0]:>9,.0f} (TIR {b[1]:+.1%})")
