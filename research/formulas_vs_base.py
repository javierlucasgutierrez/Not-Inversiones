"""Las mejores fórmulas de % frente a nuestra base (x3 con tendencia mensual → x1),
y la base con turbo x5 durante H días tras la caída (sólo con tendencia sana).
100 € de partida, coste 0,3 % por cambio de marcha, financiación incluida."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import data
from swingbot.indicators import add_indicators
f = add_indicators(data.load("^GSPC", start="1950-01-01")).dropna(subset=["sma200"])
c = f.Close; r = c.pct_change().fillna(0)
d = f.index
rate = 0.03 / 252
lev = {L: (L * r - (L - 1) * rate).clip(lower=-1) for L in (1, 3, 5)}
eom = pd.Series(pd.Series(1, index=d).groupby(d.to_period("M")).cumcount(ascending=False).values == 0, index=d)
base = (c > f.sma200).where(eom).ffill().fillna(True).map({True: 3, False: 1}).shift(1).fillna(3)
above = c > f.sma200
signals = {
    "cae ≥2 % en 3 días (10 d)": ((c / c.shift(3) - 1) <= -0.02, 10),
    "cae ≥3 % en 5 días (20 d)": ((c / c.shift(5) - 1) <= -0.03, 20),
    "cae ≥5 % en 5 días (5 d)": ((c / c.shift(5) - 1) <= -0.05, 5),
    "≥3 % bajo máx. 20 días (20 d)": ((c / c.rolling(20).max() - 1) <= -0.03, 20),
}
def overlay(sig, H):
    g = base.copy().to_numpy().astype(float)
    s = (sig & above).to_numpy(); i = 0
    while i < len(d) - 1:
        if s[i] and g[i + 1] == 3:
            for j in range(i + 1, min(i + 1 + H, len(d))):
                if g[j] == 3: g[j] = 5
            i += H
        i += 1
    return pd.Series(g, index=d)
def perf(g, lo, hi):
    m = (d >= lo) & (d <= hi)
    ret = sum((g == L) * lev[L] for L in (1, 3, 5)) - (g.diff().abs() > 0) * 0.003
    eq = (1 + ret[m]).cumprod()
    yrs = (d[m][-1] - d[m][0]).days / 365.25
    return 100 * eq.iloc[-1], eq.iloc[-1] ** (1 / yrs) - 1, (eq / eq.cummax() - 1).min(), (g[m].diff().abs() > 0).sum() / yrs
for lab, lo, hi in (("1951-1999 (descubrimiento)", "1951-01-01", "1999-12-31"), ("2000-2026 (comprobación)", "2000-01-01", "2026-12-31"),
                    ("Últimos 10 años", "2016-11-01", "2026-12-31")):
    print(f"\n{lab}")
    rows = [("Pasiva x1", pd.Series(1, index=d)), ("Base x3 → x1 (lo nuestro)", base)]
    rows += [(f"Base + turbo x5: {k}", overlay(*v)) for k, v in signals.items()]
    for k, g in rows:
        v, cagr, dd, sw = perf(g, lo, hi)
        print(f"  {k:46} 100 € → {v:>12,.0f} € · {cagr:+6.1%}/año · peor caída {dd:+.0%} · {sw:4.1f} cambios/año")
