import sys, itertools; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import data
from swingbot.indicators import add_indicators, sma
f = add_indicators(data.load("^GSPC", start="1985-01-01"))
vix = data.load("^VIX", start="1985-01-01")["Close"].reindex(f.index).ffill()
c = f.Close
f["sma50"] = sma(c, 50)
f["ret1"] = c.pct_change()
f["vol20"] = f.ret1.rolling(20).std() * np.sqrt(252)
f["low20"] = c.rolling(20).min(); f["high252"] = c.rolling(252).max()
for h in (1, 5, 10, 20):
    f[f"fwd{h}"] = c.shift(-h) / c - 1
cond = {
    "sobre media200": c > f.sma200,
    "bajo media200": c < f.sma200,
    "media50>media200": f.sma50 > f.sma200,
    "RSI2<10": f.rsi2 < 10,
    "RSI2<5": f.rsi2 < 5,
    "RSI2>90": f.rsi2 > 90,
    "IBS<0.2": f.ibs < 0.2,
    "IBS>0.8": f.ibs > 0.8,
    "3 días bajando": f.down_streak >= 3,
    "cierre en mín. 20d": c <= f.low20,
    "a <2% del máx. anual": c >= f.high252 * 0.98,
    "caída diaria >2%": f.ret1 < -0.02,
    "VIX>25": vix > 25,
    "VIX dispara (+20% vs 10d)": vix > vix.rolling(10).mean() * 1.2,
    "volatilidad baja (<12%)": f.vol20 < 0.12,
    "lunes": pd.Series(f.index.dayofweek == 0, index=f.index),
    "viernes": pd.Series(f.index.dayofweek == 4, index=f.index),
    "últimos 2 días del mes": f.days_left_month <= 1,
}
f = f.loc["1994-01-01":]
cond = {k: v.reindex(f.index).fillna(False).astype(bool) for k, v in cond.items()}
IS = f.index <= "2009-12-31"; OOS = f.index >= "2010-01-01"
H = "fwd5"
base_is, base_oos = f.loc[IS, H].mean(), f.loc[OOS, H].mean()
def stats(mask, period):
    x = f.loc[mask & period, H].dropna()
    n = len(x)
    if n < 25: return None
    # t-stat con muestras solapadas: se divide n efectivo por el horizonte
    neff = max(n / 5, 2)
    t = (x.mean() - f.loc[period, H].mean()) / (x.std() / np.sqrt(neff) + 1e-12)
    return n, x.mean(), (x > 0).mean(), t
rows = []
names = list(cond)
for k in (1, 2, 3):
    for combo in itertools.combinations(names, k):
        if "sobre media200" in combo and "bajo media200" in combo: continue
        m = np.logical_and.reduce([cond[n].to_numpy() for n in combo])
        a = stats(m, IS); b = stats(m, OOS)
        if a is None or b is None: continue
        rows.append(dict(patron=" + ".join(combo), k=k, n_is=a[0], med_is=a[1], gana_is=a[2], t_is=a[3],
                         n_oos=b[0], med_oos=b[1], gana_oos=b[2], t_oos=b[3]))
R = pd.DataFrame(rows)
print(f"Patrones evaluados: {len(R)} | media 5 días sin condición: 1994-09 {base_is:+.2%}, 2010-26 {base_oos:+.2%}")
top = R[R.t_is > 2].copy()
top["confirma"] = (top.t_oos > 1.5) & (top.med_oos > base_oos)
print(f"Prometedores en 1994-2009 (t>2): {len(top)} | se confirman en 2010-2026: {top.confirma.sum()} ({top.confirma.mean():.0%})")
bot = R[R.t_is < -2].copy(); bot["confirma"] = (bot.t_oos < -1.5) & (bot.med_oos < base_oos)
print(f"Patrones bajistas en 1994-2009: {len(bot)} | se confirman: {bot.confirma.sum()}")
fmt = lambda df: df[["patron","n_is","med_is","gana_is","n_oos","med_oos","gana_oos","t_oos"]].to_string(index=False,
      formatters={"med_is": "{:+.2%}".format, "med_oos": "{:+.2%}".format, "gana_is": "{:.0%}".format, "gana_oos": "{:.0%}".format, "t_oos": "{:.1f}".format})
print("\n=== ALCISTAS confirmados (5 días después), los 20 más fuertes en 2010-2026 ===")
print(fmt(top[top.confirma].sort_values("t_oos", ascending=False).head(20)))
print("\n=== BAJISTAS confirmados ===")
print(fmt(bot[bot.confirma].sort_values("t_oos").head(10)))
R.to_csv("research/patrones.csv", index=False)
