"""¿Comprar x3 cuando el S&P 500 cae ≥4 % en una semana (5 sesiones)?
Compra al cierre de la señal, venta a los 5/10/20 sesiones. x3 con reinicio diario y
financiación; 1 € + 1 € de comisión y 0,2 % de horquilla con 100 € por operación.
Separado según el índice esté por encima o por debajo de su media 200."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import data
from swingbot.indicators import add_indicators
f = add_indicators(data.load("^GSPC", start="1950-01-01")).dropna(subset=["sma200"])
r = f.Close.pct_change().fillna(0).to_numpy(); d = f.index; C = f.Close
sig = ((C / C.shift(5) - 1) <= -0.04).to_numpy(); above = (C > f.sma200).to_numpy()
def x3(i, H):
    return np.prod(np.clip(1 + 3 * r[i + 1:i + H + 1] - 2 * 0.05 / 252, 0, None)) - 1 - 0.002 - 0.02
for lo, lab in (("1951", "1951-hoy"), ("2000", "2000-hoy")):
    i0 = np.searchsorted(d, pd.Timestamp(lo))
    print(f"\n== {lab} ==")
    for cond, name in ((above, "tendencia sana (sobre media 200)"), (~above, "tendencia rota (bajo media 200) ← como ahora")):
        for H in (5, 10, 20):
            rets = []; i = i0
            while i < len(d) - H - 1:
                if sig[i] and cond[i]:
                    rets.append(x3(i, H)); i += H       # sin solapar operaciones
                i += 1
            a = np.array(rets)
            print(f"  {name:45} {H:>2} sesiones: {len(a):3} ops · ganan {np.mean(a>0):4.0%} · media {a.mean():+6.1%} · "
                  f"peor {a.min():+5.0%} · mejor {a.max():+5.0%} · encadenadas 100 € → {100*np.prod(1+a):,.0f} €")
print("\nSeñales de este mes:")
m = pd.Series(sig, index=d).loc["2026-11-01":]
for day in m[m].index:
    i = d.get_loc(day); out = {H: (C.iloc[i+H]/C.iloc[i]-1) if i+H < len(d) else None for H in (1, 2, 3)}
    print(f"  {day:%d/%m} cierre {C.iloc[i]:,.0f} · semana {C.iloc[i]/C.iloc[i-5]-1:+.1%} · después índice: "
          + " · ".join(f"{h}d {v:+.1%}" for h, v in out.items() if v is not None))
