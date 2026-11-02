"""Genera los ficheros JSON del panel "Cartera x3 Tendencia".

python -m swingbot.dashboard_data [carpeta]   (por defecto reports/dashboard)

- senal.json        estado de la señal hoy
- indice.json       S&P 500 y su media de 200 sesiones (último año)
- calendario.json   revisiones de los próximos 12 meses (estado según la fecha)
- operaciones.json  NO se genera: es el registro de tus operaciones reales y se
                    mantiene a mano en reports/dashboard/operaciones.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessMonthEnd

from . import data, trend
from .indicators import add_indicators

START_PLAN = "2026-11-01"


def build(out_dir: str = "reports/dashboard") -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    st = trend.status()
    df = add_indicators(data.load(trend.SYMBOL, start="2024-01-01"))

    senal = [{
        "fecha": f"{st['date']:%Y-%m-%d}",
        "cierre": round(st["close"], 2),
        "media200": round(st["sma200"], 2),
        "distancia": round(st["dist"], 4),
        "estado": "DENTRO" if st["inside"] else "FUERA",
        "estado_hoy": "DENTRO" if st["close"] > st["sma200"] else "FUERA",
        "revision_anterior": f"{st['check_date']:%Y-%m-%d}",
        "proxima_revision": f"{st['next_check']:%Y-%m-%d}",
        "producto": "Certificado factor Long x3 S&P 500" if st["inside"] else "ETF S&P 500 (x1)",
    }]

    last = df.loc[df.index >= df.index[-1] - pd.DateOffset(years=1)]
    indice = [{"fecha": f"{d:%Y-%m-%d}", "cierre": round(float(r.Close), 2),
               "media200": round(float(r.sma200), 2)} for d, r in last.iterrows()]

    cal_off = CustomBusinessMonthEnd(calendar=USFederalHolidayCalendar())
    dates = pd.date_range(START_PLAN, periods=12, freq=cal_off)
    eom = df[df.index.isin(dates)]
    calendario = []
    for d in dates:
        if d in eom.index:
            r = eom.loc[d]
            res = "DENTRO" if r.Close > r.sma200 else "FUERA"
            calendario.append({"fecha": f"{d:%Y-%m-%d}", "estado": "Hecha", "resultado": res,
                               "cierre": round(float(r.Close), 2)})
        else:
            calendario.append({"fecha": f"{d:%Y-%m-%d}", "estado": "Pendiente",
                               "resultado": "", "cierre": None})

    written = []
    for name, rows in (("senal", senal), ("indice", indice), ("calendario", calendario)):
        p = out / f"{name}.json"
        p.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        written.append(p)
    ops = out / "operaciones.json"
    if not ops.exists():
        ops.write_text("[]")
    written.append(ops)
    return written


if __name__ == "__main__":
    for p in build(*sys.argv[1:]):
        print(p)
