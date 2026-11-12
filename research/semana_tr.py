"""Fórmulas de una semana con los costes reales de Trade Republic (1 € al comprar
+ 1 € al vender, horquilla ~0,2 %), en potenciador x3 y x5 con reinicio diario.
Dinero aparte; fuera de operación, liquidez al 2 %. Incluye el crack de 1987."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import data
from swingbot.indicators import add_indicators
f = add_indicators(data.load("^GSPC", start="1950-01-01")).dropna(subset=["sma200"])
c = f.Close; r = c.pct_change().fillna(0).to_numpy(); d = f.index
above = c > f.sma200
F = {
    "A · cae ≥3 % en 3 días + tendencia sana → 5 días": (((c / c.shift(3) - 1) <= -0.03) & above, 5),
    "B · cae ≥5 % en 5 días + tendencia sana → 5 días": (((c / c.shift(5) - 1) <= -0.05) & above, 5),
    "E · cae ≥4 % en 3 días + tendencia sana → 5 días": (((c / c.shift(3) - 1) <= -0.04) & above, 5),
}
def sim(mask, H, lo, cap, L):
    m = mask.to_numpy(); eq = cap; i = np.searchsorted(d, pd.Timestamp(lo)); out = []; curve = []
    while i < len(d) - 1:
        if m[i] and i + H < len(d):
            v = np.prod(np.maximum(1 + L * r[i + 1:i + H + 1] - (L - 1) * 0.04 / 252 - 0.01 / 252, 0))
            ret = v - 1 - 0.002 - 2 / max(eq, 1)
            eq = max(eq * (1 + ret), 0); out.append((d[i], ret)); curve.append(eq); i += H
        else:
            eq *= 1 + 0.02 / 252; curve.append(eq)
        i += 1
    curve = pd.Series(curve); yrs = (d[-1] - pd.Timestamp(lo)).days / 365.25
    t = pd.DataFrame(out, columns=["fecha", "ret"])
    return eq, (eq / cap) ** (1 / yrs) - 1, (curve / curve.cummax() - 1).min(), t
for k, (m, H) in F.items():
    print(f"\n{k}")
    for L in (3, 5):
        for lo, lab in (("1951-01-01", "1951-hoy"), ("2000-01-01", "2000-hoy"), ("2016-11-01", "10 años")):
            for cap in (100, 500):
                eq, cagr, dd, t = sim(m, H, lo, cap, L)
                print(f"  x{L} {lab:9} {cap:>4} € → {eq:>9,.0f} € · {cagr:+6.1%}/año · caída máx {dd:+.0%} · "
                      f"{len(t)/((d[-1]-pd.Timestamp(lo)).days/365.25):.1f} ops/año · ganan {(t.ret>0).mean():.0%} · "
                      f"peor op {t.ret.min():+.0%} · mejor {t.ret.max():+.0%}")
# x5 operación a operación en los últimos 10 años
m, H = F["A · cae ≥3 % en 3 días + tendencia sana → 5 días"]
_, _, _, t = sim(m, H, "2016-11-01", 500, 5)
print("\nA en x5, últimos 10 años, cada operación:")
print(t.assign(ret=t.ret.map("{:+.1%}".format), fecha=t.fecha.dt.strftime("%d/%m/%Y")).to_string(index=False))
