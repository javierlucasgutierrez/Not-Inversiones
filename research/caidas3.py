"""Días en que el S&P 500 cae un 3 % o más: qué pasa después y si compensa comprar
el x3 / x5 en el cierre de esa caída para cazar el rebote."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from swingbot import data
from swingbot.indicators import add_indicators
f = add_indicators(data.load("^GSPC", start="1950-01-01")).dropna(subset=["sma200"])
c = f.Close; r = c.pct_change()
for h in (1, 3, 5, 10, 20):
    f[f"fwd{h}"] = c.shift(-h) / c - 1
end = f.index[-1]
periods = {"Últimos 10 años": end - pd.DateOffset(years=10), "Últimos 40 años": end - pd.DateOffset(years=40),
           "Desde 1951 (75 años)": f.index[0]}
for thr in (-0.03, -0.02):
    print(f"\n######## Días con caída del índice ≤ {thr:.0%} (≈ {3*thr:.0%} en x3, {5*thr:.0%} en x5) ########")
    for name, start in periods.items():
        s = f.loc[start:]; m = r.loc[start:] <= thr
        ev = s[m]
        print(f"\n{name}: {len(ev)} días ({len(ev) / ((end - start).days / 365.25):.1f}/año) · "
              f"con tendencia sana (sobre media 200): {(ev.Close > ev.sma200).sum()}")
        base = {h: s[f'fwd{h}'].mean() for h in (1, 5, 10, 20)}
        for h in (1, 3, 5, 10, 20):
            x = ev[f"fwd{h}"].dropna()
            print(f"  a {h:>2} días: índice sube en {(x > 0).mean():4.0%} de los casos · media {x.mean():+6.2%} "
                  f"(día normal {s[f'fwd{h}'].mean():+.2%}) · peor {x.min():+6.1%} · mejor {x.max():+6.1%}")
        for lab, sub in (("sobre media 200", ev[ev.Close > ev.sma200]), ("bajo media 200", ev[ev.Close <= ev.sma200])):
            x = sub["fwd5"].dropna()
            if len(x):
                print(f"     5 días después, {lab:15}: sube {(x > 0).mean():4.0%} · media {x.mean():+6.2%} · peor {x.min():+6.1%}  (n={len(x)})")

# Estrategia: comprar x3 / x5 al cierre del día de caída; vender tras N días o al primer cierre en positivo
print("\n######## Estrategia: comprar al cierre del día de caída ≤ −3 % ########")
COST = 0.003  # horquilla + comisión aprox. por operación (ida y vuelta, sobre el producto)
def trades(start, L, rule, filt):
    s = f.loc[start:]; idx = s.index; C = s.Close.to_numpy(); rr = s.Close.pct_change().to_numpy()
    sig = (rr <= -0.03) & (filt(s).to_numpy() if filt else True)
    out = []; i = 1
    while i < len(idx) - 1:
        if sig[i]:
            val, j = 1.0, i
            while j + 1 < len(idx):
                j += 1
                val *= max(1 + L * rr[j], 0)              # producto con reinicio diario
                held = j - i
                if (rule == "rebote" and rr[j] > 0) or (rule != "rebote" and held >= rule) or held >= 20:
                    break
            out.append((idx[i], val - 1 - COST, j - i)); i = j
        i += 1
    return pd.DataFrame(out, columns=["fecha", "ret", "dias"])
for name, start in periods.items():
    print(f"\n{name}")
    for filt_name, filt in (("todas", None), ("solo sobre media 200", lambda s: s.Close > s.sma200)):
        for L in (3, 5):
            for rule, lab in ((1, "vender a 1 día"), (5, "vender a 5 días"), ("rebote", "vender al 1er día verde")):
                t = trades(start, L, rule, filt)
                if t.empty: continue
                eq = (1 + t.ret).prod()
                print(f"  x{L} {filt_name:21} {lab:24} ops {len(t):3} · ganan {(t.ret > 0).mean():4.0%} · media {t.ret.mean():+6.1%} · "
                      f"peor {t.ret.min():+5.0%} · mejor {t.ret.max():+5.0%} · 100 € → {100*eq:,.0f} €")
