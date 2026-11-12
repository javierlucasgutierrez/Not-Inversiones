"""¿Se puede acertar el día siguiente? Patrones de 1 día en x5 con costes de Trade Republic
(1 € entrar + 1 € salir, horquilla 0,2 %). Compra al cierre, venta al cierre siguiente."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import data
from swingbot.indicators import add_indicators
f = add_indicators(data.load("^GSPC", start="1950-01-01")).dropna(subset=["sma200"]).loc["2000-01-01":]
nxt = f.Close.shift(-1) / f.Close - 1
above = f.Close > f.sma200
P = {
    "Cualquier día (al azar)": pd.Series(True, index=f.index),
    "Tendencia sana": above,
    "Ayer subió + tendencia sana": (f.Close > f.Close.shift(1)) & above,
    "Ayer bajó + tendencia sana": (f.Close < f.Close.shift(1)) & above,
    "RSI2<10 + tendencia sana": (f.rsi2 < 10) & above,
    "RSI2<5 + 3 días bajando + sana": (f.rsi2 < 5) & (f.down_streak >= 3) & above,
    "Cierra en mínimo del día + sana": (f.ibs < 0.1) & above,
}
print(f"{'patrón':34}{'días/año':>9}{'aciertos':>9}{'sube de media':>14}{'baja de media':>14}{'neto x5':>9}  "
      f"{'100 €/op':>9}{'1.000 €/op':>11}")
yrs = len(f) / 252
for k, m in P.items():
    x = nxt[m].dropna()
    up, dn = x[x > 0], x[x <= 0]
    g5 = 5 * x.mean() - 4 * 0.05 / 252 - 0.002                # x5 menos financiación y horquilla
    print(f"{k:34}{len(x)/yrs:9.0f}{(x>0).mean():9.0%}{up.mean():+14.2%}{dn.mean():+14.2%}{g5:+9.2%}  "
          f"{g5*100-2:+8.2f}€{g5*1000-2:+10.2f}€")
