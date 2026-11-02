import sys; sys.path.insert(0, "/tmp/claude-0/-home-user-Not-Inversiones/9bac7233-faa4-5760-b3e8-0ec3d28dfa3a/scratchpad")
exec(open("research/mine.py").read().split("rows = []")[0])
import numpy as np, pandas as pd, itertools
names = list(cond)
out = []
for H in ("fwd1", "fwd5", "fwd10", "fwd20"):
    hd = int(H[3:])
    b_is, b_oos = f.loc[IS, H].mean(), f.loc[OOS, H].mean()
    for k in (1, 2, 3):
        for combo in itertools.combinations(names, k):
            if "sobre media200" in combo and "bajo media200" in combo: continue
            m = np.logical_and.reduce([cond[n].to_numpy() for n in combo])
            xi = f.loc[m & IS, H].dropna(); xo = f.loc[m & OOS, H].dropna()
            if len(xi) < 25 or len(xo) < 25: continue
            ti = (xi.mean() - b_is) / (xi.std() / np.sqrt(max(len(xi) / hd, 2)))
            to = (xo.mean() - b_oos) / (xo.std() / np.sqrt(max(len(xo) / hd, 2)))
            out.append(dict(h=hd, patron=" + ".join(combo), n_is=len(xi), ex_is=xi.mean() - b_is, gana_is=(xi > 0).mean(), t_is=ti,
                            n_oos=len(xo), ex_oos=xo.mean() - b_oos, gana_oos=(xo > 0).mean(), t_oos=to))
R = pd.DataFrame(out)
print("Patrones evaluados (todos los plazos):", len(R))
for H in (1, 5, 10, 20):
    s = R[R.h == H]
    prom = s[s.t_is > 1.5]
    ok = prom[(prom.ex_oos > 0) & (prom.t_oos > 1.0)]
    print(f"  {H:>2} días: prometedores en 94-09 {len(prom):>3} | siguen ganando al mercado en 10-26 {int((prom.ex_oos>0).sum()):>3} | con fuerza (t>1) {len(ok):>3}")
best = R[(R.t_is > 1.5) & (R.ex_oos > 0) & (R.t_oos > 1.0)].copy()
best["score"] = np.minimum(best.t_is, best.t_oos)
best = best.sort_values("score", ascending=False).drop_duplicates("patron").head(15)
print("\nLos que aguantan en las dos épocas (exceso = rentabilidad por encima de la normal en ese plazo):")
print(best[["h","patron","n_is","ex_is","gana_is","n_oos","ex_oos","gana_oos"]].to_string(index=False,
      formatters={"ex_is": "{:+.2%}".format, "ex_oos": "{:+.2%}".format, "gana_is": "{:.0%}".format, "gana_oos": "{:.0%}".format}))
# Azar: con patrones aleatorios de la misma frecuencia, ¿cuántos "aguantan" por suerte?
rng = np.random.default_rng(0); lucky = 0; trials = 400
for _ in range(trials):
    p = rng.uniform(0.02, 0.2); m = rng.random(len(f)) < p; H = "fwd5"
    xi = f.loc[m & IS, H].dropna(); xo = f.loc[m & OOS, H].dropna()
    ti = (xi.mean() - f.loc[IS, H].mean()) / (xi.std() / np.sqrt(len(xi) / 5)); to = (xo.mean() - f.loc[OOS, H].mean()) / (xo.std() / np.sqrt(len(xo) / 5))
    lucky += (ti > 1.5) and (to > 1.0)
print(f"\nControl: patrones AL AZAR que 'aguantan' igual: {lucky}/{trials} ({lucky/trials:.1%})")
