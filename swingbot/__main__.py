"""CLI.

Ejemplos:
  python -m swingbot scan                      # señales de hoy (x3 por defecto)
  python -m swingbot scan --leverage 5
  python -m swingbot backtest ^GSPC pullback --leverage 3 --tp 0.05 --sl 0.10
  python -m swingbot report                    # informe completo -> reports/
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import backtest as bt, config, data, report, scanner
from .indicators import add_indicators
from .strategies import STRATEGIES, get


def _opt_float(v: str):
    return None if v.lower() in ("none", "0", "no") else float(v)


def main(argv=None):
    p = argparse.ArgumentParser(prog="swingbot", description="Swing trading apalancado en índices")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="Señales de entrada al cierre de hoy")
    s.add_argument("--symbols", nargs="*")
    s.add_argument("--strategies", nargs="*", choices=list(STRATEGIES))
    s.add_argument("--leverage", type=float, default=config.DEFAULT_LEVERAGE)
    s.add_argument("--tp", type=_opt_float, default=config.DEFAULT_TAKE_PROFIT)
    s.add_argument("--sl", type=_opt_float, default=config.DEFAULT_STOP_LOSS)

    b = sub.add_parser("backtest", help="Backtest de una estrategia")
    b.add_argument("symbol")
    b.add_argument("strategy", choices=list(STRATEGIES))
    b.add_argument("--leverage", type=float, default=config.DEFAULT_LEVERAGE)
    b.add_argument("--mode", choices=["etf", "cfd"], default="etf")
    b.add_argument("--entry", choices=["close", "next_open"], default="close")
    b.add_argument("--tp", type=_opt_float, default=config.DEFAULT_TAKE_PROFIT)
    b.add_argument("--sl", type=_opt_float, default=config.DEFAULT_STOP_LOSS)
    b.add_argument("--stop-atr", type=_opt_float, default=None)
    b.add_argument("--allocation", type=float, default=1.0)
    b.add_argument("--start", default="1995-01-01")
    b.add_argument("--trades", action="store_true", help="Muestra las últimas operaciones")

    r = sub.add_parser("report", help="Informe de robustez completo")
    r.add_argument("--symbols", nargs="*")
    r.add_argument("--out", default="reports")

    a = p.parse_args(argv)

    if a.cmd == "scan":
        sigs = scanner.scan(a.symbols, a.strategies, a.leverage, a.tp, a.sl)
        print(scanner.format_signals(sigs, a.leverage))

    elif a.cmd == "backtest":
        df = add_indicators(data.load(a.symbol, start=a.start))
        cfg = bt.BTConfig(leverage=a.leverage, mode=a.mode, entry=a.entry, take_profit=a.tp,
                          stop_loss=a.sl, stop_atr=a.stop_atr, allocation=a.allocation)
        res = bt.run(df, get(a.strategy), cfg, a.symbol)
        st = res.stats()
        print(f"{a.symbol} | {a.strategy} | {cfg}")
        for k, v in st.items():
            print(f"  {k:16} {v:.4f}" if isinstance(v, float) else f"  {k:16} {v}")
        if a.trades and not res.trades.empty:
            print(res.trades.tail(20).to_string(index=False))

    elif a.cmd == "report":
        out = Path(a.out)
        out.mkdir(exist_ok=True)
        full, oos = report.full_report(a.symbols)
        full.to_csv(out / "backtest_grid.csv", index=False)
        oos.to_csv(out / "out_of_sample.csv", index=False)
        print("## Fuera de muestra (x3, TP5%, SL10%)\n")
        print(report.fmt(oos))
        print(f"\nTablas completas en {out}/")


if __name__ == "__main__":
    main()
