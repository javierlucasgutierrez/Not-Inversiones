"""1) ¿Un algoritmo que combine muchos indicadores (RSI, MACD, Bollinger, volumen,
Fibonacci, medias, rachas, volatilidad, VIX...) acierta el día o la semana siguiente?
Se entrena con 1990-2012 y se comprueba en 2013-hoy (datos que el modelo no ha visto).
2) ¿Aguantar siempre recupera? Comprar x3/x5 en los peores momentos y esperar."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from swingbot import data
from swingbot.indicators import add_indicators, rsi
f = add_indicators(data.load("^GSPC", start="1950-01-01"))
vix = data.load("^VIX", start="1990-01-01")["Close"].reindex(f.index).ffill()
C, V = f.Close, f.Volume.replace(0, np.nan)
X = pd.DataFrame(index=f.index)
X["rsi2"], X["rsi14"] = f.rsi2, rsi(C, 14)
ema12, ema26 = C.ewm(span=12).mean(), C.ewm(span=26).mean()
macd = ema12 - ema26; X["macd"] = (macd - macd.ewm(span=9).mean()) / C
m20, s20 = C.rolling(20).mean(), C.rolling(20).std(); X["bollinger_b"] = (C - m20) / (2 * s20)
X["vol_rel"] = V / V.rolling(20).mean()
for n in (20, 60, 120):                                    # posición en el rango (niveles Fibonacci)
    lo, hi = f.Low.rolling(n).min(), f.High.rolling(n).max()
    pos = (C - lo) / (hi - lo); X[f"rango{n}"] = pos
    X[f"fibo{n}"] = np.min([abs(pos - l) for l in (0.236, 0.382, 0.5, 0.618, 0.786)], axis=0)
for n in (5, 20, 50, 200): X[f"dist_sma{n}"] = C / C.rolling(n).mean() - 1
for n in (1, 2, 3, 5, 10, 20): X[f"ret{n}"] = C.pct_change(n)
X["ibs"], X["racha_baja"] = f.ibs, f.down_streak
X["volat20"] = C.pct_change().rolling(20).std()
X["vix"], X["vix_rel"] = vix, vix / vix.rolling(20).mean()
X["dia_semana"], X["dias_fin_mes"] = f.index.dayofweek, f.days_left_month
r1 = C.shift(-1) / C - 1; r5 = C.shift(-5) / C - 1
D = X.join(pd.DataFrame({"r1": r1, "r5": r5})).loc["1990-01-01":].dropna(subset=list(X.columns))
tr, te = D.loc[:"2012-12-31"], D.loc["2013-01-01":].dropna(subset=["r1"])
print(f"{len(X.columns)} indicadores · entreno {len(tr)} días (1990-2012) · prueba {len(te)} días (2013-hoy)\n")
for tgt, H in (("r1", 1), ("r5", 5)):
    trd = tr.dropna(subset=[tgt]); ted = te.dropna(subset=[tgt])
    y = (trd[tgt] > 0).astype(int)
    print(f"== Predecir si sube {'mañana' if H == 1 else 'en 5 días'} · base: sube el {(ted[tgt]>0).mean():.0%} de los días ==")
    for name, mdl in (("Regresión logística", LogisticRegression(max_iter=3000, C=0.1)),
                      ("Árboles (boosting)", HistGradientBoostingClassifier(max_depth=3, learning_rate=0.03, max_iter=300))):
        if name.startswith("Reg"):
            mu, sd = trd[X.columns].mean(), trd[X.columns].std()
            mdl.fit((trd[X.columns] - mu) / sd, y); p = mdl.predict_proba((ted[X.columns] - mu) / sd)[:, 1]
        else:
            mdl.fit(trd[X.columns], y); p = mdl.predict_proba(ted[X.columns])[:, 1]
        p = pd.Series(p, index=ted.index)
        for q in (0.5, 0.8, 0.95):                     # opera sólo el % de días más 'seguros'
            sel = ted[p >= p.quantile(q)]
            ops = len(sel) / H                          # sin solapar, aprox.
            g5 = 5 * sel[tgt].mean() - H * 4 * 0.05 / 252 - 0.002
            print(f"  {name:20} días más seguros {1-q:4.0%}: acierta {(sel[tgt]>0).mean():4.0%} · "
                  f"sube {sel[tgt][sel[tgt]>0].mean():+.2%} / baja {sel[tgt][sel[tgt]<=0].mean():+.2%} · "
                  f"x5 por op: 100 € {g5*100-2:+.2f} € · 1.000 € {g5*1000-2:+.2f} €")
    print()

print("== 2) ¿Aguantar siempre recupera? Comprar en el peor momento y no vender ==")
r = C.pct_change().fillna(0)
for L in (1, 3, 5):
    for top in ("1987-08-25", "2000-03-24", "2007-10-09", "2020-02-19", "2022-01-03"):
        s = (1 + (L * r.loc[top:].iloc[1:] - (L - 1) * 0.05 / 252)).clip(lower=0).cumprod()
        if s.min() == 0:
            print(f"  x{L} comprado el {pd.Timestamp(top):%d/%m/%Y}: a CERO el {s[s==0].index[0]:%d/%m/%Y}, perdido todo"); continue
        mn = s.min(); back = s[s >= 1]
        rec = back.index[0] if len(back) else None
        txt = f"recuperado en {rec:%m/%Y} ({(rec - pd.Timestamp(top)).days/365.25:.1f} años)" if rec is not None else f"NO recuperado hoy: vale {s.iloc[-1]:.2f}×"
        print(f"  x{L} comprado el {pd.Timestamp(top):%d/%m/%Y}: peor momento {mn-1:+.0%} · {txt}")
    print()
