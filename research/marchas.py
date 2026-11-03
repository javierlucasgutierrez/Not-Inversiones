"""Sistema de 3 marchas: x1 (tendencia rota) / x3 (tendencia sana) / x5 un día tras
una bajada fuerte con tendencia sana. 50 $/mes, financiación, comisiones e impuestos
anuales; coste extra por cada cambio de marcha (horquilla + deslizamiento)."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import compare as c, data, trend
from swingbot.indicators import add_indicators
spy = data.load("SPY", start="1993-01-01")["Close"]
f = add_indicators(data.load("^GSPC", start="1990-01-01")).loc["1994-01-01":]
d = f.index
r = spy.reindex(d).ffill().pct_change().fillna(0)
rate = pd.Series(d.year, index=d).map(trend.USD_RATE).fillna(3.7) / 100
lev = {1: r}
for L in (3, 5):
    lev[L] = (L * r - ((L - 1) * (rate + 0.01) + 0.005) / 252).clip(lower=-1)
eom = pd.Series(pd.Series(1, index=d).groupby(d.to_period("M")).cumcount(ascending=False).values == 0, index=d)
base = (f.Close > f.sma200).where(eom).ffill().fillna(True).map({True: 3.0, False: 1.0})
mon = pd.Series(d.dayofweek == 0, index=d)
dips = {
    "sin turbo (base actual)": pd.Series(False, index=d),
    "turbo: RSI2<5 + 3 días bajando": (f.rsi2 < 5) & (f.down_streak >= 3),
    "turbo: + IBS<0,2 en lunes": ((f.rsi2 < 5) & (f.down_streak >= 3)) | ((f.ibs < 0.2) & mon),
    "turbo: 3 días bajando": f.down_streak >= 3,
}
def gears(dip):
    g = base.copy()
    g[(base == 3) & dip] = 5.0          # al cierre del día de la bajada sube a x5...
    return g.shift(1).fillna(3.0)       # ...y se aplica al día siguiente (1 día)
def sim(g, lo, hi, cost):
    m = (d >= lo) & (d <= hi)
    ret = sum((g == k) * lev[k] for k in (1, 3, 5))
    sw = (g.diff().abs() > 0).astype(int)
    ret = ret - sw * cost
    p = c._simulate("", ret[m], d[m], 50, 50, sw[m], 1.0, "annual")
    return p.value.iloc[-1], c.xirr(p.flows), (p.twr / p.twr.cummax() - 1).min(), sw[m].sum() / ((d[m][-1] - d[m][0]).days / 365.25)
for cost in (0.0015, 0.003, 0.005):
    print(f"\n=== coste por cambio de marcha {cost*100:.2f} % (además de 1 € por orden) ===")
    for k, dip in dips.items():
        g = gears(dip)
        a = sim(g, "1994-01-01", "2009-12-31", cost); b = sim(g, "2010-01-01", "2026-12-31", cost)
        print(f"  {k:32} 1994-09 TIR {a[1]:+6.1%} (caída {a[2]:+.0%}) | 2010-26 TIR {b[1]:+6.1%} (caída {b[2]:+.0%}) | {(a[3]+b[3])/2:4.0f} cambios/año")
print("\n=== 23 ventanas de 10 años, coste 0,30 % ===")
res = {k: [] for k in dips}
for y in range(1994, 2017):
    for k, dip in dips.items():
        res[k].append(sim(gears(dip), f"{y}-01-01", f"{y+9}-12-31", 0.003)[0])
b0 = np.array(res["sin turbo (base actual)"])
for k, v in res.items():
    v = np.array(v)
    print(f"  {k:32} gana a la base {(v > b0).sum():>2}/23 | media {np.mean(v / b0 - 1):+5.1%} | peor {np.min(v / b0 - 1):+5.1%} | mejor {np.max(v / b0 - 1):+5.1%}")
