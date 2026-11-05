"""CLI.

Ejemplos:
  python -m swingbot scan                      # señales de hoy (x3 por defecto)
  python -m swingbot scan --leverage 5
  python -m swingbot backtest ^GSPC pullback --leverage 3 --tp 0.05 --sl 0.10
  python -m swingbot report                    # informe completo -> reports/
  python -m swingbot backtest ^GSPC pullback --broker trade_republic --product factor --capital 2000
  python -m swingbot broker-report --broker trade_republic   # costes reales de TR por tamaño de cuenta
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
    s.add_argument("--broker", choices=list(config.BROKERS), default="trade_republic")

    b = sub.add_parser("backtest", help="Backtest de una estrategia")
    b.add_argument("symbol")
    b.add_argument("strategy", choices=list(STRATEGIES))
    b.add_argument("--leverage", type=float, default=config.DEFAULT_LEVERAGE)
    b.add_argument("--mode", choices=["etf", "cfd", "knockout"], default=None,
                   help="Fuerza el modelo de apalancamiento (por defecto lo da --product)")
    b.add_argument("--broker", choices=list(config.BROKERS), default="ninguno")
    b.add_argument("--product", choices=list(config.PRODUCTS), default="etp")
    b.add_argument("--capital", type=float, default=10_000, help="Capital inicial en €")
    b.add_argument("--eur", action="store_true", help="Medir resultado en € (EUR/USD incluido)")
    b.add_argument("--entry", choices=["close", "next_open"], default="close")
    b.add_argument("--tp", type=_opt_float, default=config.DEFAULT_TAKE_PROFIT)
    b.add_argument("--sl", type=_opt_float, default=config.DEFAULT_STOP_LOSS)
    b.add_argument("--stop-atr", type=_opt_float, default=None)
    b.add_argument("--allocation", type=float, default=1.0)
    b.add_argument("--start", default="1995-01-01")
    b.add_argument("--trades", action="store_true", help="Muestra las últimas operaciones")

    br = sub.add_parser("broker-report", help="Backtest con costes del bróker por tamaño de cuenta")
    br.add_argument("--broker", choices=list(config.BROKERS), default="trade_republic")
    br.add_argument("--out", default="reports")

    t = sub.add_parser("tendencia", help="Señal mensual de la estrategia x3 con tendencia")
    t.add_argument("--leverage", type=float, default=3)
    t.add_argument("--out", choices=["x1", "cash"], default="x1",
                   help="Dónde estar cuando la señal es FUERA (ETF x1 o liquidez)")
    t.add_argument("--backtest", action="store_true", help="Mostrar también el histórico")
    t.add_argument("--initial", type=float, default=50)
    t.add_argument("--monthly", type=float, default=50)

    sub.add_parser("resumen", help="Parte diario del S&P 500 y de la estrategia")
    sub.add_parser("alerta", help="Alertas de movimientos fuertes durante la sesión")

    fo = sub.add_parser("fondeo", help="Operativa de 1 día para una cuenta de fondeo")
    fo.add_argument("--cuenta", type=float, default=10_000, help="Saldo de la cuenta")
    fo.add_argument("--historial", action="store_true", help="Señales de los últimos 6 meses")

    c = sub.add_parser("compare", help="Bot frente a aportar periódicamente a un ETF")
    c.add_argument("--initial", type=float, default=1_000)
    c.add_argument("--monthly", type=float, default=200)
    c.add_argument("--start", default="2004-01-01")
    c.add_argument("--leverage", type=float, default=3)
    c.add_argument("--strategy", choices=list(STRATEGIES), default="pullback")
    c.add_argument("--no-taxes", action="store_true", help="Ignorar impuestos")
    c.add_argument("--plot", action="store_true", help="Guardar gráfico en reports/")
    c.add_argument("--out", default="reports")

    r = sub.add_parser("report", help="Informe de robustez completo")
    r.add_argument("--symbols", nargs="*")
    r.add_argument("--out", default="reports")

    a = p.parse_args(argv)

    if a.cmd == "scan":
        sigs = scanner.scan(a.symbols, a.strategies, a.leverage, a.tp, a.sl)
        print(scanner.format_signals(sigs, a.leverage, a.broker))

    elif a.cmd == "backtest":
        df = add_indicators(data.load(a.symbol, start=a.start))
        over = dict(entry=a.entry, take_profit=a.tp, stop_loss=a.sl, stop_atr=a.stop_atr,
                    allocation=a.allocation, capital=a.capital)
        if a.mode:
            over["mode"] = a.mode
        cfg = bt.make_config(a.leverage, a.product, a.broker, **over)
        fx = None
        if a.eur and a.symbol in config.USD_INDICES:
            fx = data.load(config.FX_SYMBOL, start="2003-12-01")["Close"]
            df = df.loc[fx.index[0]:]
        res = bt.run(df, get(a.strategy), cfg, a.symbol, fx=fx)
        st = res.stats()
        print(f"{a.symbol} | {a.strategy} | {cfg}")
        for k, v in st.items():
            print(f"  {k:16} {v:.4f}" if isinstance(v, float) else f"  {k:16} {v}")
        if a.trades and not res.trades.empty:
            print(res.trades.tail(20).to_string(index=False))

    elif a.cmd == "broker-report":
        out = Path(a.out)
        out.mkdir(exist_ok=True)
        tab = report.broker_report(a.broker)
        tab.to_csv(out / f"broker_{a.broker}.csv", index=False)
        print(f"## {config.BROKERS[a.broker]['name']} — x3/x5, TP5 % SL10 %, resultado en €, 2004-hoy\n")
        print(report.fmt(tab))

    elif a.cmd == "tendencia":
        from . import trend, compare as cmp
        print(trend.format_status(trend.status(), a.leverage, a.out))
        if a.backtest:
            print(f"\nHistórico ({cmp._eur(a.initial)} + {cmp._eur(a.monthly)}/mes, en €, "
                  "con costes e impuestos):")
            for start in ("2004", "2016"):
                base = cmp.build_paths(start=f"{start}-01-01", initial=a.initial,
                                       monthly=a.monthly, funds=False)[0]
                print(f"  desde {start} pasivo x1: aportado {cmp._eur(base.invested.iloc[-1])} -> "
                      f"{cmp._eur(base.value.iloc[-1])}  TIR {cmp.xirr(base.flows):+.1%}  "
                      f"peor caída {(base.twr / base.twr.cummax() - 1).min():+.0%}")
                for lev, out in ((2, "cash"), (a.leverage, "cash"), (a.leverage, "x1")):
                    p = trend.backtest(lev, f"{start}-01-01", initial=a.initial,
                                       monthly=a.monthly, out=out)
                    dd = (p.twr / p.twr.cummax() - 1).min()
                    print(f"  desde {start} x{lev:g} tendencia, fuera->{out}: aportado "
                          f"{cmp._eur(p.invested.iloc[-1])} -> {cmp._eur(p.value.iloc[-1])}  "
                          f"TIR {cmp.xirr(p.flows):+.1%}  peor caída {dd:+.0%}")

    elif a.cmd == "alerta":
        from . import alerta
        msgs = alerta.check()
        print("\n".join(msgs) if msgs else "Sin alertas nuevas.")

    elif a.cmd == "resumen":
        from . import resumen
        print(resumen.build())

    elif a.cmd == "fondeo":
        from . import fondeo
        print(fondeo.report(a.cuenta))
        if a.historial:
            h = fondeo.history()
            print("\nSeñales de los últimos 6 meses y resultado al día siguiente:")
            print(h.to_string(formatters={"Close": "{:,.0f}".format, "indice_dia_sig": "{:+.2%}".format,
                                          "cuenta_x2": "{:+.2%}".format}))
            ok = h.cuenta_x2.dropna()
            print(f"Total: {len(ok)} operaciones, {(ok > 0).mean():.0%} ganadoras, suma {ok.sum():+.1%} de la cuenta")

    elif a.cmd == "compare":
        from . import compare as cmp
        kw = dict(initial=a.initial, monthly=a.monthly, leverage=a.leverage,
                  strategy=a.strategy, taxes=not a.no_taxes)
        paths = cmp.build_paths(start=a.start, **kw)
        print(f"## {a.initial:,.0f} € iniciales + {a.monthly:,.0f} €/mes desde {a.start[:4]}"
              f" ({'con' if not a.no_taxes else 'sin'} impuestos)\n")
        print(cmp.fmt_summary(cmp.summarize(paths)))
        roll = cmp.rolling_windows(years=10, **kw)
        etf = roll["Plan ETF/fondo periódico"]
        print("\n## Ventanas de 10 años: veces que gana al plan ETF")
        for col in roll.columns[3:]:
            print(f"  {col:26} {(roll[col] > etf).sum()}/{len(roll)}  "
                  f"(diferencia media {(roll[col] / etf - 1).mean():+.1%})")
        if a.plot:
            Path(a.out).mkdir(exist_ok=True)
            f = cmp.plot(paths, roll, f"{a.out}/comparacion.png",
                         f"{cmp._eur(a.initial)} + {cmp._eur(a.monthly)}/mes en el S&P 500 desde "
                         f"{a.start[:4]} (en €, con costes e impuestos)")
            print(f"\nGráfico: {f}")

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
