import sys
exec(open("research/mine.py").read().split("rows = []")[0])
import numpy as np, pandas as pd
lun = cond["lunes"]
pats = {
    "RSI2<10": cond["RSI2<10"],
    "3 días bajando": cond["3 días bajando"],
    "RSI2<5 + 3 días bajando": cond["RSI2<5"] & cond["3 días bajando"],
    "IBS<0.2 + lunes": cond["IBS<0.2"] & lun,
    "Cualquiera (RSI2<10 o 3 días o IBS<0.2+lunes)": cond["RSI2<10"] | cond["3 días bajando"] | (cond["IBS<0.2"] & lun),
}
r1 = f["fwd1"]
for L in (3, 5):
    for slip in (0.0015, 0.003):            # coste por lado del producto (horquilla + deslizamiento)
        print(f"\n--- x{L}, compra al cierre y venta al cierre siguiente, coste {slip*100:.2f}% por lado + 2 € de comisión (cuenta 1.000 €) ---")
        for k, m in pats.items():
            for lab, per in (("94-09", IS), ("10-26", OOS)):
                x = r1[m.to_numpy() & per].dropna()
                tr = L * x - 2 * slip - 2 / 1000 - (L - 1) * 0.04 / 252
                yrs = 16 if lab == "94-09" else 16.8
                anual = (1 + tr).prod() ** (1 / yrs) - 1
                print(f"  {k:45} {lab}: {len(tr)/yrs:5.1f} ops/año | media op {tr.mean():+.2%} | ganadoras {(tr>0).mean():.0%} | resultado anual {anual:+.1%} | peor op {tr.min():+.0%}")
