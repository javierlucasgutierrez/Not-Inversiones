"""¿Salir cuando cae y entrar cuando sube? Reglas de seguimiento de los vaivenes
de corto plazo en x3, frente a mantener el x3 (nuestra base, que en estos meses
ha estado siempre DENTRO). Cambio al cierre, coste 0,3 % por cambio (horquilla +
comisión), sin impuestos (favorece a las reglas activas)."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import data
from swingbot.indicators import add_indicators, sma
f = add_indicators(data.load("^GSPC", start="1990-01-01"))
c = f.Close
r = c.pct_change().fillna(0)
r3 = 3 * r - 0.06 / 252
COST = 0.003
rules = {
    "Mantener x3 (nuestra base)": pd.Series(1.0, index=f.index),
    "Fuera si cierra bajo media 5": (c > f.sma5).astype(float),
    "Fuera si cierra bajo media 10": (c > f.sma10).astype(float),
    "Fuera si cierra bajo media 20": (c > sma(c, 20)).astype(float),
    "Fuera si cae 2 días seguidos": (~(f.down_streak >= 2)).astype(float),
}
def run(pos, lo, hi):
    p = pos.shift(1).fillna(1)               # decide al cierre, se aplica al día siguiente
    m = (f.index >= lo) & (f.index <= hi)
    sw = p.diff().abs().fillna(0)
    ret = (p * r3 - sw * COST)[m]            # fuera = liquidez (0 %)
    eq = (1 + ret).cumprod()
    return eq.iloc[-1] - 1, (eq / eq.cummax() - 1).min(), sw[m].sum() / max((m.sum() / 252), 0.01)
periods = [("Últimos 6 meses (tu gráfico)", "2026-05-01", "2026-12-31"),
           ("2010-2026", "2010-01-01", "2026-12-31"), ("1994-2009", "1994-01-01", "2009-12-31")]
for lab, lo, hi in periods:
    print(f"\n{lab}")
    for k, pos in rules.items():
        tot, dd, n = run(pos, lo, hi)
        if lab.startswith("Últimos"):
            print(f"  {k:32} resultado {tot:+7.1%} | peor caída {dd:+5.0%} | {n:5.0f} cambios/año")
        else:
            yrs = (pd.Timestamp(hi).year - pd.Timestamp(lo).year + 1)
            print(f"  {k:32} anual {(1 + tot) ** (1 / yrs) - 1:+6.1%} | peor caída {dd:+5.0%} | {n:5.0f} cambios/año")
