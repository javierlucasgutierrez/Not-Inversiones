"""Operaciones con objetivo de +4/5 % en el producto (x3 o x5), con orden límite de venta.
Entrada al cierre con señal (siempre con tendencia sana: cierre > media 200).
Salida: al tocar el objetivo (máximo del día), o al cumplirse el plazo máximo, o stop.
Costes: 1 € al entrar + 1 € al salir, horquilla 0,2 %. Cuenta de 100 € reinvirtiendo."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import data
from swingbot.indicators import add_indicators
f = add_indicators(data.load("^GSPC", start="1950-01-01")).dropna(subset=["sma200"])
C, H, L_ = f.Close.to_numpy(), f.High.to_numpy(), f.Low.to_numpy(); d = f.index
ok_hl = (f.High > f.Close * 1.0001).to_numpy()   # antes de ~1962 High/Low no son fiables
above = f.Close > f.sma200
S = {
    "1 día rojo": (f.Close < f.Close.shift(1)) & above,
    "2 días rojos": (f.down_streak >= 2) & above,
    "bajo media 5": (f.Close < f.sma5) & above,
    "RSI2<10": (f.rsi2 < 10) & above,
    "cae≥3% en 3d": ((f.Close / f.Close.shift(3) - 1) <= -0.03) & above,
}
def sim(sig, lev, tp, maxd, sl, lo, cap=100.0):
    m = sig.to_numpy(); i = np.searchsorted(d, pd.Timestamp(lo)); eq = cap; t = []
    fin = (2 * 0.05 / 252)
    while i < len(d) - 1:
        if not m[i]: i += 1; continue
        v = 1.0; j = i; res = None
        while j < len(d) - 1 and j - i < maxd:
            j += 1; prev = C[j - 1]
            hi = v * (1 + lev * (H[j] / prev - 1)) if ok_hl[j] else v * (1 + lev * (C[j] / prev - 1))
            lo_ = v * (1 + lev * (L_[j] / prev - 1)) if ok_hl[j] else v * (1 + lev * (C[j] / prev - 1))
            if sl and lo_ <= 1 - sl: res = 1 - sl - 0.005; break       # stop (con deslizamiento)
            if hi >= 1 + tp: res = 1 + tp; break
            v = max(v * (1 + lev * (C[j] / prev - 1)) - fin * (lev - 1) / 2, 0)
            if v == 0: res = 0; break
        if res is None: res = v
        ret = res - 1 - 0.002 - 2 / max(eq, 1)
        eq = max(eq * (1 + ret), 0); t.append((ret, j - i)); i = j + 1
        if eq < 5: break
    yrs = (d[-1] - pd.Timestamp(lo)).days / 365.25
    t = np.array(t) if t else np.zeros((0, 2))
    return eq, (max(eq, 0.01) / cap) ** (1 / yrs) - 1, t
rows = []
for name, sig in S.items():
    for lev in (3, 5):
        for tp in (0.04, 0.05):
            for maxd in (5, 10, 20):
                for sl in (None, 0.15):
                    r = {"señal": name, "x": lev, "obj": tp, "plazo": maxd, "stop": sl or 0}
                    for lo, lab in (("1963-01-01", "63"), ("2000-01-01", "00"), ("2016-11-01", "10a")):
                        eq, g, t = sim(sig, lev, tp, maxd, sl, lo)
                        r[f"anual_{lab}"] = g
                        if lab == "10a":
                            r["ops_año"] = len(t) / 10; r["aciertan_obj"] = (t[:, 0] > 0).mean() if len(t) else 0
                            r["peor"] = t[:, 0].min() if len(t) else 0; r["dias_medios"] = t[:, 1].mean() if len(t) else 0
                    rows.append(r)
T = pd.DataFrame(rows)
T["minimo"] = T[["anual_63", "anual_00", "anual_10a"]].min(axis=1)
T = T.sort_values("minimo", ascending=False)
T.to_csv("reports/objetivo45.csv", index=False)
pd.set_option("display.width", 200)
print(T.head(20).to_string(index=False, float_format=lambda x: f"{x:.3f}"))

print("\nEfecto del tamaño de la cuenta (señal 'cae≥3% en 3d', x3, objetivo +5 %, plazo 5 días):")
for cap in (50, 100, 200, 500, 1000, 5000):
    out = []
    for lo in ("1963-01-01", "2000-01-01", "2016-11-01"):
        eq, g, t = sim(S["cae≥3% en 3d"], 3, 0.05, 5, None, lo, cap)
        out.append(f"{g:+.1%}")
    print(f"  {cap:>5} € → desde 1963 {out[0]} · desde 2000 {out[1]} · 10 años {out[2]} /año")
print("\nSeñales frecuentes, x3, objetivo +4 %, plazo 10 días, cuenta 1.000 €:")
for name in S:
    eq, g, t = sim(S[name], 3, 0.04, 10, None, "2000-01-01", 1000)
    print(f"  {name:14} {len(t)/26.9:4.1f} ops/año · llegan al +4 % {(t[:,1]<10).mean() if len(t) else 0:.0%} · "
          f"resultado desde 2000 {g:+.1%}/año · peor {t[:,0].min():+.0%}")
