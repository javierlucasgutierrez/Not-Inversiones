"""¿Qué ha salido SIEMPRE bien? Planes de 50 €/mes empezados en cualquier mes desde 1951,
durando 5, 10, 15 y 20 años. Se mira si acabaron con más dinero del aportado y si la
base (x3 → x1 con media 200 a fin de mes) ganó a la pasiva x1. Dividendos y tipos de
interés aproximados por año (el x3 cobra 3× dividendos y paga 2× (tipo + 1 %) + 0,5 %);
1 € por orden."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import data
from swingbot.indicators import add_indicators
f = add_indicators(data.load("^GSPC", start="1950-01-01")).dropna(subset=["sma200"])
from swingbot.trend import USD_RATE
RATE = {**{y: 2.5 for y in range(1950, 1960)}, **{y: 4.0 for y in range(1960, 1970)},
        1970: 7, 1971: 4.5, 1972: 4.5, 1973: 8.7, 1974: 10.5, 1975: 5.8, 1976: 5, 1977: 5.5,
        1978: 7.9, 1979: 11.2, 1980: 13.4, 1981: 16.4, 1982: 12.3, 1983: 9.1, 1984: 10.2,
        1985: 8.1, 1986: 6.8, 1987: 6.7, 1988: 7.6, 1989: 9.2, 1990: 8.1, 1991: 5.7, 1992: 3.5, **USD_RATE}
DIV = {**{y: 4.5 for y in range(1950, 1960)}, **{y: 3.2 for y in range(1960, 1970)},
       **{y: 4.0 for y in range(1970, 1980)}, **{y: 4.2 for y in range(1980, 1990)},
       **{y: 2.3 for y in range(1990, 2000)}, **{y: 1.8 for y in range(2000, 2010)},
       **{y: 2.0 for y in range(2010, 2020)}, **{y: 1.5 for y in range(2020, 2031)}}
yr = pd.Series(f.index.year, index=f.index)
rate = yr.map(RATE).fillna(4) / 100; div = yr.map(DIV) / 100
r = f.Close.pct_change().fillna(0) + div / 252
eom = f.days_left_month == 0
inside = (f.Close > f.sma200).where(eom).ffill().fillna(True).shift(1).fillna(True)
r3 = (3 * r - (2 * (rate + 0.01) + 0.005) / 252).clip(lower=-1)
plans = {"Pasiva x1": r, "Base x3→x1": np.where(inside, r3, r), "x3 siempre (sin regla)": r3}
months = f.index.to_period("M")
first_day = ~months.duplicated()
sw = inside.astype(int).diff().abs().fillna(0).to_numpy()
def run(rets, i0, i1, base):
    v = 0.0; aport = 0.0
    for i in range(i0, i1):
        if first_day[i]:
            v += 50 - 1; aport += 50
        v *= 1 + rets[i]
        if base and sw[i]: v -= 2
    return v, aport
idx = np.flatnonzero(first_day)
for Y in (5, 10, 15, 20):
    res = {k: [] for k in plans}; ap = []
    for j in range(0, len(idx) - Y * 12, 3):          # cada trimestre
        i0, i1 = idx[j], idx[j + Y * 12]
        for k, rr in plans.items():
            v, a = run(np.asarray(rr), i0, i1, k == "Base x3→x1"); res[k].append(v)
        ap.append(a)
    ap = np.array(ap); p = np.array(res["Pasiva x1"]); b = np.array(res["Base x3→x1"])
    print(f"\n{Y} años ({len(ap)} planes distintos desde 1951):")
    for k, v in res.items():
        v = np.array(v)
        print(f"  {k:24} acaba con más de lo aportado: {(v > ap).mean():6.1%} · peor caso {np.min(v/ap):.2f}× lo aportado · mediana {np.median(v/ap):.2f}×")
    print(f"  Base gana a la pasiva en {(b > p).mean():.0%} de los planes; peor caso base/pasiva {np.min(b/p):.2f}")
