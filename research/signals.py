import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import compare as c, data, trend
from swingbot.indicators import add_indicators, sma
spy = data.load("SPY", start="1993-01-01")["Close"]
f = add_indicators(data.load("^GSPC", start="1985-01-01"))
f["sma50"] = sma(f.Close, 50)
f["mom12"] = f.Close / f.Close.shift(252) - 1
f["vol20"] = f.Close.pct_change().rolling(20).std() * np.sqrt(252)
f["vol60"] = f.Close.pct_change().rolling(60).std() * np.sqrt(252)
f = f.loc["1994-01-01":]
d = f.index
r = spy.reindex(d).ffill().pct_change().fillna(0)
rate = pd.Series(d.year, index=d).map(trend.USD_RATE).fillna(3.7) / 100
lev = {L: (L * r - ((L - 1) * (rate + 0.01) + 0.005) / 252).clip(lower=-1) for L in (1, 2, 3)}
lev[1] = r
eom = pd.Series(pd.Series(1, index=d).groupby(d.to_period("M")).cumcount(ascending=False).values == 0, index=d)
above = f.Close > f.sma200
rules = {
    "1 Media 200 (actual)":            np.where(above, 3, 1),
    "2 Cruce dorado (200 + 50>200)":   np.where(above & (f.sma50 > f.sma200), 3, 1),
    "3 Impulso 12 meses > 0":          np.where(f.mom12 > 0, 3, 1),
    "4 Media 200 o impulso (cualq.)":  np.where(above | (f.mom12 > 0), 3, 1),
    "5 Media 200 y impulso (ambas)":   np.where(above & (f.mom12 > 0), 3, 1),
    "6 Media 200 + vol20 < 20%":       np.where(above & (f.vol20 < 0.20), 3, 1),
    "7 Media 200 + vol60 < 20%":       np.where(above & (f.vol60 < 0.20), 3, 1),
    "8 Escalones vol20 (3/2/1)":       np.where(above & (f.vol20 < 0.15), 3, np.where(above & (f.vol20 < 0.25), 2, 1)),
    "9 Escalones vol60 (3/2/1)":       np.where(above & (f.vol60 < 0.15), 3, np.where(above & (f.vol60 < 0.25), 2, 1)),
}
def sim(levels, lo, hi):
    L = pd.Series(levels, index=d, dtype=float).where(eom).ffill().fillna(3).shift(1).fillna(3)
    ret = sum((L == k) * lev[k] for k in (1, 2, 3))
    m = (d >= lo) & (d <= hi)
    sw = (L.diff().abs() > 0).astype(int)
    p = c._simulate("", ret[m], d[m], 50, 50, sw[m], 2.0, "annual")
    return p.value.iloc[-1], c.xirr(p.flows), (p.twr / p.twr.cummax() - 1).min(), sw[m].sum() / ((d[m][-1] - d[m][0]).days / 365.25)
print(f"{'Señal':34} {'TIR 94-09':>9} {'TIR 10-26':>9} {'caída 94-09':>11} {'caída 10-26':>11} {'cambios/año':>11}")
res = {}
for k, lv in rules.items():
    a = sim(lv, "1994-01-01", "2009-12-31"); b = sim(lv, "2010-01-01", "2026-12-31")
    res[k] = lv
    print(f"{k:34} {a[1]:>+9.1%} {b[1]:>+9.1%} {a[2]:>+11.0%} {b[2]:>+11.0%} {(a[3]+b[3])/2:>11.1f}")
# ventanas de 10 años frente a la regla actual y a la pasiva
print("\n23 ventanas de 10 años (1994-2025):")
base_p = []; out = {k: [] for k in rules}
for y in range(1994, 2017):
    lo, hi = f"{y}-01-01", f"{y+9}-12-31"; m = (d >= lo) & (d <= hi)
    base_p.append(c._simulate("", r[m], d[m], 50, 50, taxes="final").value.iloc[-1])
    for k, lv in rules.items(): out[k].append(sim(lv, lo, hi)[0])
bp = np.array(base_p); cur = np.array(out["1 Media 200 (actual)"])
for k, v in out.items():
    v = np.array(v)
    print(f"  {k:34} gana a pasiva {(v>bp).sum():>2}/23 | gana a la actual {(v>cur).sum():>2}/23 | media vs actual {np.mean(v/cur-1):+5.0%} | peor vs actual {np.min(v/cur-1):+5.0%}")
