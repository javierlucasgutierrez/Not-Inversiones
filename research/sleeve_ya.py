"""Fórmulas de 'comprar tras caída' operadas por separado en x3 (dinero aparte),
de 1951 a hoy (incluye el crack de 1987), con 0,3 % de horquilla y 2 € de comisión
por operación (Trade Republic: 1 € al comprar + 1 € al vender). Fuera de operación,
el dinero está en liquidez al 2 %."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import data
from swingbot.indicators import add_indicators
f = add_indicators(data.load("^GSPC", start="1950-01-01", refresh=True)).dropna(subset=["sma200"])
c = f.Close; r = c.pct_change().fillna(0).to_numpy(); d = f.index
above = (c > f.sma200)
F = {
    "A · cae ≥3 % en 3 días + tendencia sana → 5 días": (((c / c.shift(3) - 1) <= -0.03) & above, 5),
    "B · cae ≥5 % en 5 días + tendencia sana → 5 días": (((c / c.shift(5) - 1) <= -0.05) & above, 5),
    "C · cae ≥2 % en 3 días + tendencia sana → 10 días": (((c / c.shift(3) - 1) <= -0.02) & above, 10),
    "D · RSI(2) < 5 + 3 días bajando + tendencia sana → 1 día": (((f.rsi2 < 5) & (f.down_streak >= 3)) & above, 1),
}
def sim(mask, H, lo, cap, L=3):
    m = mask.to_numpy(); eq = cap; i = np.searchsorted(d, pd.Timestamp(lo)); out = []; curve = []
    while i < len(d) - 1:
        if m[i] and i + H < len(d):
            v = np.prod(np.maximum(1 + L * r[i + 1:i + H + 1] - (L - 1) * 0.03 / 252, 0))
            ret = v - 1 - 0.003 - 2 / max(eq, 1)
            eq = max(eq * (1 + ret), 0); out.append((d[i], ret)); curve.append(eq); i += H
        else:
            eq *= 1 + 0.02 / 252; curve.append(eq)
        i += 1
    curve = pd.Series(curve)
    yrs = (d[-1] - pd.Timestamp(lo)).days / 365.25
    t = pd.DataFrame(out, columns=["fecha", "ret"])
    return eq, (eq / cap) ** (1 / yrs) - 1, (curve / curve.cummax() - 1).min(), t
for k, (m, H) in F.items():
    print(f"\n{k}")
    for lo, lab in (("1951-01-01", "1951-hoy"), ("2000-01-01", "2000-hoy"), ("2016-11-01", "10 años")):
        for cap in (100, 500, 2000):
            eq, cagr, dd, t = sim(m, H, lo, cap)
            print(f"  {lab:9} cuenta {cap:>5} € → {eq:>10,.0f} € · {cagr:+6.1%}/año · peor caída {dd:+.0%} · "
                  f"{len(t)} ops ({len(t)/((d[-1]-pd.Timestamp(lo)).days/365.25):.1f}/año) · ganan {(t.ret>0).mean():.0%} · peor op {t.ret.min():+.0%}")
    last = m[m].index[-3:]
    print(f"  últimas señales: {[x.strftime('%d/%m/%Y') for x in last]} · ¿activa hoy ({d[-1]:%d/%m})? {'SÍ' if m.iloc[-1] else 'no'}")
print(f"\nHoy {d[-1]:%d/%m/%Y}: cierre {c.iloc[-1]:,.0f}, 3 días {c.iloc[-1]/c.iloc[-4]-1:+.1%}, 5 días {c.iloc[-1]/c.iloc[-6]-1:+.1%}, RSI2 {f.rsi2.iloc[-1]:.0f}")
