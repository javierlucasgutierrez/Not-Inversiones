"""¿Pasaría un examen de cuenta de fondeo con los patrones de 1 día?
Objetivo +10 %, pérdida máxima diaria -5 %, pérdida máxima total -10 %.
CFD del S&P 500 (sin comisión fija; coste ~0,03 % por lado de horquilla)."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import data
from swingbot.indicators import add_indicators
f = add_indicators(data.load("^GSPC", start="1993-01-01")).loc["1995-01-01":]
c = f.Close
pats = {
    "RSI2<5 + 3 días bajando": (f.rsi2 < 5) & (f.down_streak >= 3),
    "IBS<0.2 + lunes": (f.ibs < 0.2) & (f.index.dayofweek == 0),
    "Cualquiera de los buenos": ((f.rsi2 < 5) & (f.down_streak >= 3)) | ((f.ibs < 0.2) & (f.index.dayofweek == 0)) | (f.down_streak >= 3),
}
nxt = (c.shift(-1) / c - 1)                       # cierre a cierre siguiente
low_next = (f.Low.shift(-1) / c - 1)              # peor punto del día siguiente
COST = 0.0006
def attempt(idx, L, max_days=None):
    eq, i0 = 1.0, idx[0]
    for k, t in enumerate(idx):
        worst = L * low_next.iloc[t]
        if worst <= -0.05 or eq * (1 + worst) <= 0.90:   # salta límite diario o total
            return "suspende", k + 1
        eq *= 1 + L * nxt.iloc[t] - COST
        if eq >= 1.10: return "aprueba", k + 1
        if eq <= 0.90: return "suspende", k + 1
    return "sin terminar", len(idx)
for name, m in pats.items():
    pos = np.where(m.fillna(False).to_numpy()[:-1])[0]
    per_year = len(pos) / ((f.index[-1] - f.index[0]).days / 365.25)
    print(f"\n{name}: {per_year:.0f} señales/año")
    for L in (2, 5, 10, 20):
        res = []
        for s in range(0, len(pos) - 5, 3):            # empezar en cada 3ª señal de la historia
            res.append(attempt(pos[s:], L))
        r = pd.Series([x[0] for x in res]); n = pd.Series([x[1] for x in res])
        ok = r == "aprueba"
        print(f"  apalancamiento x{L:<2}: aprueba {ok.mean():5.0%} | suspende {(r=='suspende').mean():5.0%} | "
              f"operaciones hasta aprobar (mediana) {n[ok].median() if ok.any() else float('nan'):5.0f} "
              f"(~{(n[ok].median() / per_year * 12 if ok.any() else float('nan')):.0f} meses)")
