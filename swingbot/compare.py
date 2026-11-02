"""¿Gana el bot más que aportar periódicamente a un ETF?

Simula, con LAS MISMAS aportaciones (inicial + mensual) y en euros:

1. "Plan ETF"        : plan de inversión periódico en un ETF del S&P 500 con
                       dividendos reinvertidos (SPY ajustado, convertido a €).
                       En Trade Republic los planes de inversión no tienen comisión.
2. "Bot solo"        : todo el dinero en el bot (certificado factor x3). Fuera de
                       las operaciones el dinero está en liquidez.
3. "Bot + interés"   : igual, pero la liquidez cobra un interés anual (TR remunera
                       el efectivo; el tipo ha variado mucho con los años).
4. "ETF + turbo"     : el dinero está SIEMPRE en el ETF; cuando hay señal se vende
                       el ETF y se compra el x3, y al salir se vuelve al ETF.
5. "80 % ETF / 20 % bot": núcleo pasivo + satélite activo.

Comisiones fijas en €: 1 € por orden del bot (y otra por la venta/compra del ETF en
el modo turbo). El plan ETF mensual se considera sin comisión.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import backtest as bt, config, data
from .indicators import add_indicators
from .strategies import get

ETF_TR_SYMBOL = "SPY"   # proxy de un ETF UCITS del S&P 500 con dividendos (TER similar)
ETF_SPREAD = 0.0005     # horquilla al vender/comprar el ETF en el modo turbo

# Escala del ahorro en España (IRPF, base del ahorro). Comprobar cada año.
TAX_BRACKETS_ES = [(6_000, 0.19), (50_000, 0.21), (200_000, 0.23), (300_000, 0.27),
                   (float("inf"), 0.28)]


def tax_es(gain: float) -> float:
    """Impuesto sobre una ganancia patrimonial con la escala del ahorro."""
    tax, prev = 0.0, 0.0
    for top, rate in TAX_BRACKETS_ES:
        if gain <= prev:
            break
        tax += (min(gain, top) - prev) * rate
        prev = top
    return tax


@dataclass
class Path:
    name: str
    value: pd.Series        # valor de la cartera en €
    invested: pd.Series     # dinero aportado acumulado
    twr: pd.Series          # rentabilidad acumulada sin efecto de aportaciones
    flows: list             # [(fecha, importe)] para la TIR
    taxes_paid: float = 0.0 # impuestos pagados (incluida la venta final)


def _contribution_days(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Primera sesión de cada mes."""
    s = pd.Series(index, index=index)
    return pd.DatetimeIndex(s.groupby(index.to_period("M")).first().values)


def _simulate(name, rets, index, initial, monthly, fee_events=None, fee=0.0,
              taxes: str | None = None):
    """Valor en € con aportación inicial + mensual y comisiones fijas puntuales.

    taxes=None      sin impuestos
    taxes="annual"  las ganancias se realizan cada año (bot: cada operación vende);
                    se paga en diciembre y las pérdidas se compensan en años siguientes
    taxes="final"   sólo se paga al vender todo el último día (plan ETF)
    """
    contrib_days = set(_contribution_days(index)[1:])
    fee_events = fee_events if fee_events is not None else pd.Series(0, index=index)
    v, inv = initial, initial
    vals, invs, flows = [], [], [(index[0], -initial)]
    paid, carry = 0.0, 0.0
    year_start_v, year_contrib = v, 0.0
    for t, d in enumerate(index):
        if taxes == "annual" and t > 0 and d.year != index[t - 1].year:
            pnl = vals[-1] - year_start_v - year_contrib - carry
            if pnl > 0:
                tx = tax_es(pnl)
                v -= tx
                paid += tx
                carry = 0.0
            else:
                carry = -pnl
            year_start_v, year_contrib = v, 0.0
        if t > 0:
            v *= 1 + rets.iloc[t]
        if d in contrib_days:
            v += monthly
            inv += monthly
            year_contrib += monthly
            flows.append((d, -monthly))
        n_fees = fee_events.iloc[t]
        if n_fees:
            v = max(v - n_fees * fee, 0.0)
        vals.append(v)
        invs.append(inv)
    # Venta final: se liquidan las plusvalías pendientes.
    if taxes == "annual":
        pending = vals[-1] - year_start_v - year_contrib - carry
    elif taxes == "final":
        pending = vals[-1] - inv
    else:
        pending = 0.0
    if pending > 0:
        tx = tax_es(pending)
        vals[-1] -= tx
        paid += tx
    flows.append((index[-1], vals[-1]))
    twr = (1 + rets.fillna(0)).cumprod()
    return Path(name, pd.Series(vals, index=index), pd.Series(invs, index=index), twr, flows,
                paid)


def xirr(flows) -> float:
    """TIR anual de flujos irregulares (rentabilidad real del dinero aportado)."""
    t0 = flows[0][0]
    yrs = np.array([(d - t0).days / 365.25 for d, _ in flows])
    cf = np.array([c for _, c in flows], dtype=float)
    f = lambda r: np.sum(cf / (1 + r) ** yrs)
    lo, hi = -0.99, 5.0
    if f(lo) * f(hi) > 0:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def build_paths(start="2004-01-01", end=None, initial=1_000.0, monthly=200.0,
                strategy="pullback", leverage=3, product="factor", broker="trade_republic",
                cash_rate=0.02, satellite=0.2, symbol="^GSPC", taxes=True) -> list[Path]:
    fx = data.load(config.FX_SYMBOL, start="2003-12-01")["Close"]
    etf = data.load(ETF_TR_SYMBOL, start="1995-01-01")["Close"]
    idx_df = add_indicators(data.load(symbol, start="1995-01-01"))
    start = max(pd.Timestamp(start), fx.index[0])
    idx_df = idx_df.loc[start:end]
    dates = idx_df.index
    fxa = fx.reindex(dates).ffill().bfill()

    # ETF en euros (dividendos incluidos).
    etf_eur = etf.reindex(dates).ffill() / fxa
    r_etf = etf_eur.pct_change().fillna(0)

    # Bot: comisión fija a 0 aquí; se cobra en € dentro de la simulación.
    fee = config.BROKERS[broker]["fixed_fee"]
    cfg = bt.make_config(leverage, product, broker, fixed_fee=0.0,
                         take_profit=config.DEFAULT_TAKE_PROFIT,
                         stop_loss=config.DEFAULT_STOP_LOSS)
    res = bt.run(idx_df, get(strategy), cfg, symbol,
                 fx=fx if symbol in config.USD_INDICES else None)
    eq = res.equity.reindex(dates).ffill()
    r_bot = eq.pct_change().fillna(0)

    in_pos = pd.Series(False, index=dates)
    events = pd.Series(0, index=dates)
    for tr in res.trades.itertuples():
        in_pos.loc[(dates > tr.entry_date) & (dates <= tr.exit_date)] = True
        events.loc[tr.entry_date] += 1
        events.loc[tr.exit_date] += 1
    flat = ~in_pos

    r_cash = r_bot + flat * (cash_rate / 252)
    # Turbo: ETF cuando no hay operación; se paga la horquilla del ETF al salir y volver.
    r_turbo = r_bot + flat * r_etf - (events > 0) * ETF_SPREAD

    fin, ann = ("final", "annual") if taxes else (None, None)
    paths = [
        _simulate("Plan ETF periódico", r_etf, dates, initial, monthly, taxes=fin),
        _simulate(f"Bot solo (x{leverage:g})", r_bot, dates, initial, monthly, events, fee, ann),
        _simulate(f"Bot + liquidez al {cash_rate:.0%}", r_cash, dates, initial, monthly, events,
                  fee, ann),
        # Al vender el ETF para entrar en el turbo se realizan sus plusvalías: tributa cada año.
        _simulate("ETF + turbo en señales", r_turbo, dates, initial, monthly, events, 2 * fee, ann),
    ]
    # Núcleo-satélite: dos cuentas con el reparto de aportaciones.
    # (Simplificación: cada cuenta calcula su impuesto por separado.)
    core = _simulate("", r_etf, dates, initial * (1 - satellite), monthly * (1 - satellite),
                     taxes=fin)
    sat = _simulate("", r_cash, dates, initial * satellite, monthly * satellite, events, fee, ann)
    w = 1 - satellite
    mix_flows = [(d, c) for d, c in core.flows[:-1]] + [(d, c) for d, c in sat.flows[:-1]]
    mix_flows = sorted(mix_flows) + [(dates[-1], core.value.iloc[-1] + sat.value.iloc[-1])]
    paths.append(Path(f"{w:.0%} ETF / {satellite:.0%} bot", core.value + sat.value,
                      core.invested + sat.invested,
                      (1 + (w * r_etf + satellite * r_cash)).cumprod(), mix_flows,
                      core.taxes_paid + sat.taxes_paid))
    return paths


def summarize(paths: list[Path]) -> pd.DataFrame:
    rows = []
    for p in paths:
        years = (p.value.index[-1] - p.value.index[0]).days / 365.25
        dd = (p.twr / p.twr.cummax() - 1).min()
        rows.append({
            "opción": p.name,
            "aportado_€": round(p.invested.iloc[-1]),
            "valor_final_€": round(p.value.iloc[-1]),
            "impuestos_€": round(p.taxes_paid),
            "ganancia_€": round(p.value.iloc[-1] - p.invested.iloc[-1]),
            "TIR_anual": xirr(p.flows),
            "rent_anual_sin_aport": p.twr.iloc[-1] ** (1 / years) - 1,
            "peor_caída": dd,
        })
    return pd.DataFrame(rows)


def rolling_windows(years=10, initial=1_000.0, monthly=200.0, **kw) -> pd.DataFrame:
    """Repite la comparación empezando cada año (ventanas de `years` años)."""
    out = []
    first, last = 2004, pd.Timestamp.today().year - years
    for y in range(first, last + 1):
        paths = build_paths(start=f"{y}-01-01", end=f"{y + years - 1}-12-31",
                            initial=initial, monthly=monthly, **kw)
        s = summarize(paths).set_index("opción")["valor_final_€"]
        row = {"inicio": y, "fin": y + years - 1, **s.to_dict()}
        out.append(row)
    return pd.DataFrame(out)


def fmt_summary(df: pd.DataFrame) -> str:
    d = df.copy()
    for c in ("TIR_anual", "rent_anual_sin_aport", "peor_caída"):
        d[c] = d[c].map(lambda v: f"{v:+.1%}")
    for c in ("aportado_€", "valor_final_€", "impuestos_€", "ganancia_€"):
        d[c] = d[c].map(lambda v: f"{v:,.0f} €".replace(",", "."))
    return d.to_markdown(index=False)


# Paleta categórica de referencia (orden fijo) + gris para el dinero aportado.
_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6"]
_INK, _INK2, _GRID, _SURF = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"


def _eur(v: float) -> str:
    return f"{v:,.0f} €".replace(",", ".")


def plot(paths: list[Path], rolling: pd.DataFrame | None, out: str, title: str) -> str:
    """Gráfico PNG: evolución del valor (con aportaciones) y ventanas de 10 años."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    show = [p for p in paths if not p.name.startswith("Bot solo")]
    nrows = 2 if rolling is not None else 1
    fig, axes = plt.subplots(nrows, 1, figsize=(10, 5.6 * nrows), facecolor=_SURF,
                             gridspec_kw={"height_ratios": [1.3, 1][:nrows]})
    axes = np.atleast_1d(axes)
    eur = FuncFormatter(lambda v, _: f"{v / 1000:,.0f} k€".replace(",", "."))

    ax = axes[0]
    inv = show[0].invested.iloc[:-1]
    ax.plot(inv.index, inv.values, color="#8a8984", lw=1.5, ls="--", label="Dinero aportado")
    ends = []
    for p, col in zip(show, _COLORS):
        v = p.value.iloc[:-1]  # sin el último día (venta e impuestos)
        ax.plot(v.index, v.values, color=col, lw=2, label=p.name)
        net = p.value.iloc[-1]
        # Venta final: caída por impuestos hasta el valor neto (punto).
        ax.plot([v.index[-1], v.index[-1]], [v.iloc[-1], net], color=col, lw=1.2, ls=":")
        ax.plot([v.index[-1]], [net], "o", ms=6, color=col, mec=_SURF, mew=1.5, zorder=5)
        ends.append((net, p, col))
    ends.sort(key=lambda e: e[0])
    span = max(e[0] for e in ends)
    last_y = -1e18
    for y, p, col in ends:
        y_lab = max(y, last_y + span * 0.05)
        ax.annotate(f"{p.name}: {_eur(y)} netos", xy=(p.value.index[-2], y),
                    xytext=(p.value.index[-2] + pd.Timedelta(days=200), y_lab),
                    va="center", fontsize=8.5, color=_INK, annotation_clip=False)
        last_y = y_lab
    ax.set_xlim(show[0].value.index[0], show[0].value.index[-1] + pd.Timedelta(days=120))
    ax.set_title(title, loc="left", fontsize=12, color=_INK, pad=12)
    ax.yaxis.set_major_formatter(eur)
    ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=_INK2)
    ax.text(0, -0.09, "Línea: valor de la cartera antes de vender. Punto final: lo que te queda tras "
            "vender todo y pagar impuestos (el plan ETF los paga de golpe al final).",
            transform=ax.transAxes, fontsize=8.5, color=_INK2)

    if rolling is not None:
        ax = axes[1]
        etf = rolling["Plan ETF periódico"]
        cols = [c for c in rolling.columns[3:] if not c.startswith("Bot solo")]
        n = len(cols)
        w = 0.8 / n
        x = np.arange(len(rolling))
        for i, c in enumerate(cols):
            diff = (rolling[c] / etf - 1) * 100
            ax.bar(x + (i - (n - 1) / 2) * w, diff, width=w * 0.92, color=_COLORS[i + 1],
                   label=c)
        ax.axhline(0, color=_INK2, lw=1)
        ax.set_xticks(x, [f"{a}-{str(b)[2:]}" for a, b in zip(rolling["inicio"], rolling["fin"])],
                      fontsize=8)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f} %"))
        ax.set_title("Ventanas de 10 años: ¿cuánto más (o menos) que el plan ETF? (neto, tras impuestos)",
                     loc="left", fontsize=11, color=_INK, pad=10)
        ax.legend(loc="upper left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=8.5,
                  labelcolor=_INK2, ncol=3)
        ax.set_ylim(top=ax.get_ylim()[1] + 8)

    for ax in axes:
        ax.set_facecolor(_SURF)
        ax.grid(axis="y", color=_GRID, lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(_GRID)
        ax.tick_params(colors=_INK2, length=0)
    fig.tight_layout()
    fig.subplots_adjust(right=0.74, hspace=0.32)
    fig.savefig(out, dpi=150, facecolor=_SURF)
    plt.close(fig)
    return out
