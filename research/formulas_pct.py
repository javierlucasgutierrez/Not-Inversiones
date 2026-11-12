"""Búsqueda de fórmulas de porcentaje en el S&P 500 (1951-2026).

Entrada al cierre cuando se cumple la condición; salida al cierre H sesiones después
(sin solapar operaciones). Rentabilidad en x3 con reinicio diario y 0,3 % de coste por
operación. Se compara con entrar en días cualquiera ("ventaja" = media de la fórmula
menos media de una operación al azar del mismo plazo).

Descubrimiento: 1951-1999 · comprobación: 2000-2026.
"""
import sys, itertools; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import data
from swingbot.indicators import add_indicators

f = add_indicators(data.load("^GSPC", start="1950-01-01")).dropna(subset=["sma200"])
c = f.Close
r = c.pct_change().fillna(0).to_numpy()
L, COST = 3, 0.003

conds = {}
for n in (1, 2, 3, 5, 10):
    ch = (c / c.shift(n) - 1)
    for d in (0.01, 0.02, 0.03, 0.05, 0.07, 0.10):
        if n == 1 and d > 0.05: continue
        conds[f"cae ≥{d:.0%} en {n} día(s)"] = ch <= -d
for w, lab in ((20, "máx. 20 días"), (252, "máx. 1 año")):
    dd = c / c.rolling(w).max() - 1
    for d in (0.03, 0.05, 0.07, 0.10, 0.15, 0.20):
        conds[f"≥{d:.0%} bajo el {lab}"] = dd <= -d
for n in (1, 5, 20):
    ch = (c / c.shift(n) - 1)
    for d in (0.01, 0.02, 0.03, 0.05):
        if n == 20: d *= 2
        conds[f"sube ≥{d:.0%} en {n} día(s)"] = ch >= d
above = (c > f.sma200)

def run(mask, H, lo, hi):
    idx = np.where(mask.to_numpy() & (f.index >= lo) & (f.index <= hi))[0]
    out, last_exit = [], -1
    for i in idx:
        if i <= last_exit or i + H >= len(r): continue
        val = np.prod(np.maximum(1 + L * r[i + 1:i + H + 1], 0))
        out.append(val - 1 - COST); last_exit = i + H
    return np.array(out)

def baseline(H, lo, hi):
    m = (f.index >= lo) & (f.index <= hi)
    ii = np.where(m)[0][:-H - 1]
    v = np.array([np.prod(np.maximum(1 + L * r[i + 1:i + H + 1], 0)) - 1 - COST for i in ii[::3]])
    return v.mean()

rows = []
P = {"IS": ("1951-01-01", "1999-12-31"), "OOS": ("2000-01-01", "2026-12-31")}
base = {(H, p): baseline(H, *P[p]) for H in (1, 5, 10, 20) for p in P}
for (name, m), H, filt in itertools.product(conds.items(), (1, 5, 10, 20), ("todas", "tendencia sana")):
    mm = (m & above) if filt == "tendencia sana" else m
    row = {"formula": name, "filtro": filt, "H": H}
    ok = True
    for p in P:
        t = run(mm, H, *P[p])
        if len(t) < 10: ok = False; break
        yrs = (pd.Timestamp(P[p][1]).year - pd.Timestamp(P[p][0]).year + 1)
        row.update({f"n_{p}": len(t), f"ops_año_{p}": len(t) / yrs, f"gana_{p}": (t > 0).mean(),
                    f"media_{p}": t.mean(), f"ventaja_{p}": t.mean() - base[(H, p)],
                    f"peor_{p}": t.min(), f"x100_{p}": 100 * np.prod(1 + t)})
    if ok: rows.append(row)
R = pd.DataFrame(rows)
R.to_csv("reports/formulas_pct.csv", index=False)
print(f"Fórmulas evaluadas: {len(R)}")
good_is = R[R.ventaja_IS > 0.003]
conf = good_is[good_is.ventaja_OOS > 0.003]
print(f"Con ventaja en 1951-1999: {len(good_is)} · y que la mantienen en 2000-2026: {len(conf)} ({len(conf)/max(len(good_is),1):.0%})")
cols = ["formula", "filtro", "H", "ops_año_OOS", "gana_IS", "gana_OOS", "ventaja_IS", "ventaja_OOS", "media_OOS", "peor_OOS", "x100_OOS"]
fmt = {k: "{:+.1%}".format for k in ("ventaja_IS", "ventaja_OOS", "media_OOS", "peor_OOS")}
fmt.update({k: "{:.0%}".format for k in ("gana_IS", "gana_OOS")}); fmt["ops_año_OOS"] = "{:.1f}".format; fmt["x100_OOS"] = "{:,.0f}".format
conf = conf.assign(score=np.minimum(conf.ventaja_IS, conf.ventaja_OOS)).sort_values("score", ascending=False)
print("\n=== Las 25 más sólidas (ventaja en las dos épocas; x3, coste incluido) ===")
print(conf[cols].head(25).to_string(index=False, formatters=fmt))
print("\n=== Las que más ganan en 2000-2026 con al menos 2 operaciones al año ===")
print(conf[conf.ops_año_OOS >= 2].sort_values("x100_OOS", ascending=False)[cols].head(12).to_string(index=False, formatters=fmt))
print("\n=== Fórmulas 'de compra en subidas' (momentum) que se confirman ===")
mom = conf[conf.formula.str.startswith("sube")]
print(mom[cols].head(8).to_string(index=False, formatters=fmt) if len(mom) else "  ninguna")
