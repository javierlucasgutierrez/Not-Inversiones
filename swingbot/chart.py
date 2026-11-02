"""Gráfico de velas del S&P 500 con los indicadores y las señales del sistema.

python -m swingbot grafico [--meses 8] [--out reports/velas.png]

Panel superior: velas diarias, media de 200 sesiones (tendencia), media de 5
sesiones (salida de los trades), revisiones de fin de mes (DENTRO/FUERA) y
señales de entrada de corto plazo (combo: pullback, RSI(2) o IBS).
Panel inferior: RSI(2) con su umbral de 10.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import data
from .indicators import add_indicators
from .strategies import get

UP, DOWN = "#1baf7a", "#e34948"
SMA200, SMA5, SIGNAL, MUTED = "#2a78d6", "#eb6834", "#6250d6", "#8a8984"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"


def plot(months: int = 8, out: str = "reports/velas.png") -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    full = add_indicators(data.load("^GSPC", start="2023-01-01"))
    entries = get("combo").entry_signal(full)
    df = full.loc[full.index[-1] - pd.DateOffset(months=months):].copy()
    ent = entries.reindex(df.index).fillna(False)
    x = np.arange(len(df))

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(12, 7.5), sharex=True, facecolor=SURF,
                                  gridspec_kw={"height_ratios": [3, 1], "hspace": 0.06})
    for a in (ax, ax2):
        a.set_facecolor(SURF)
        a.grid(axis="y", color=GRID, lw=0.8)
        a.set_axisbelow(True)
        for s in ("top", "right", "left"):
            a.spines[s].set_visible(False)
        a.spines["bottom"].set_color(GRID)
        a.tick_params(colors=INK2, length=0, labelsize=9)

    # Velas
    o, h, l, c = (df[k].to_numpy() for k in ("Open", "High", "Low", "Close"))
    col = np.where(c >= o, UP, DOWN)
    ax.vlines(x, l, h, color=col, lw=0.8)
    body_lo, body_hi = np.minimum(o, c), np.maximum(o, c)
    ax.bar(x, np.maximum(body_hi - body_lo, (h.max() - l.min()) * 0.002), bottom=body_lo,
           width=0.6, color=col, edgecolor=col)

    ax.plot(x, df["sma200"], color=SMA200, lw=2, label="Media 200 sesiones (tendencia)")
    ax.plot(x, df["sma5"], color=SMA5, lw=1.4, label="Media 5 sesiones (salida de trades)")

    # Revisiones de fin de mes
    eom = df.index.to_series().groupby(df.index.to_period("M")).transform("max") == df.index
    for i in np.where(eom.values)[0]:
        inside = c[i] > df["sma200"].iloc[i]
        ax.axvline(i, color=MUTED, lw=0.8, ls=":", zorder=0)
        ax.annotate("DENTRO" if inside else "FUERA", (i, h.max()), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=8,
                    color=UP if inside else DOWN, fontweight="bold")

    # Señales de entrada de corto plazo
    idx = np.where(ent.values)[0]
    ax.scatter(idx, l[idx] - (h.max() - l.min()) * 0.025, marker="^", s=55, color=SIGNAL,
               zorder=5, label="Señal de entrada (pullback / RSI2 / IBS)")

    last = len(df) - 1
    ax.annotate(f"Último cierre {c[-1]:,.0f}".replace(",", "."), (last, c[-1]),
                xytext=(-10, -28), textcoords="offset points", ha="right", fontsize=9, color=INK,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.annotate(f"Media 200: {df['sma200'].iloc[-1]:,.0f}".replace(",", "."),
                (last, df["sma200"].iloc[-1]), xytext=(-10, -16), textcoords="offset points",
                ha="right", fontsize=9, color=SMA200)
    ax.set_title("S&P 500: velas diarias, indicadores y señales del sistema", loc="left",
                 fontsize=12, color=INK, pad=22)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=INK2, ncol=3,
              bbox_to_anchor=(0, 1.0))
    ax.set_ylim(l.min() - (h.max() - l.min()) * 0.06, h.max() + (h.max() - l.min()) * 0.12)

    # RSI(2)
    ax2.plot(x, df["rsi2"], color=SIGNAL, lw=1.3)
    ax2.axhline(10, color=DOWN, lw=1, ls="--")
    ax2.fill_between(x, 0, 10, color=DOWN, alpha=0.08)
    ax2.text(0.995, 0.93, "Zona roja: RSI(2) < 10, sobreventa", transform=ax2.transAxes, ha="right",
             va="top", fontsize=8.5, color=DOWN,
             bbox=dict(boxstyle="round,pad=0.25", fc=SURF, ec="none"))
    ax2.set_ylim(0, 100)
    ax2.set_yticks([0, 10, 50, 90, 100])
    ax2.set_ylabel("RSI(2)", fontsize=9, color=INK2)

    months_idx = [i for i in range(len(df)) if i == 0 or df.index[i].month != df.index[i - 1].month]
    ax2.set_xticks(months_idx)
    names = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    ax2.set_xticklabels([f"{names[df.index[i].month - 1]} {str(df.index[i].year)[2:]}" for i in months_idx])
    ax2.set_xlim(-1, len(df) + 1)

    fig.text(0.01, 0.005, "Datos: Yahoo Finance (^GSPC). Las señales se calculan con el cierre del día. "
             "No es asesoramiento financiero.", fontsize=8, color=INK2)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.9, bottom=0.08)
    fig.savefig(out, dpi=150, facecolor=SURF)
    plt.close(fig)
    return out


if __name__ == "__main__":
    print(plot())
