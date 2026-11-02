"""Configuración por defecto: índices vigilados y parámetros recomendados.

Los parámetros por defecto NO son los "mejores" del backtest (eso sería
sobreajuste); son los valores estándar publicados para cada estrategia más una
gestión de riesgo que, en el histórico, recorta la peor operación sin destruir
la ventaja. Ver README para los resultados.
"""

# Índice (símbolo de Yahoo Finance) -> instrumentos con los que se puede operar.
# Comprueba siempre en tu bróker el ticker exacto, el KID/folleto y la liquidez.
WATCHLIST = {
    "^GSPC": {
        "name": "S&P 500",
        "x3": "UPRO / SPXL (EE.UU.), 3USL (WisdomTree, Europa)",
        "x5": "ETP x5 sobre S&P 500 o CFD/futuro (MES) con apalancamiento x5",
    },
    "^NDX": {
        "name": "Nasdaq-100",
        "x3": "TQQQ (EE.UU.), QQQ3 (WisdomTree, Europa)",
        "x5": "ETP x5 sobre Nasdaq-100 o CFD/futuro (MNQ) con apalancamiento x5",
    },
    "^GDAXI": {
        "name": "DAX 40",
        "x3": "ETP/ETF x3 sobre DAX o CFD x3",
        "x5": "CFD/futuro (FDXS) con apalancamiento x5",
    },
    "^STOXX50E": {
        "name": "Euro Stoxx 50",
        "x3": "ETP x3 sobre Euro Stoxx 50 o CFD x3",
        "x5": "CFD/futuro (micro FESX) con apalancamiento x5",
    },
}

# Estrategias que superaron la validación (profit factor >= 1.3 a x3 tanto en
# 1995-2014 como en 2015-2026). El escáner sólo da "COMPRA" en estas; el resto
# las muestra como informativas. El DAX no pasó con ninguna.
VALIDATED = {
    "^GSPC": ["pullback", "rsi2"],
    "^NDX": ["pullback", "rsi2"],
    "^STOXX50E": ["pullback", "rsi2"],
    "^GDAXI": [],
}

# Configuración recomendada para operar (ver README, sección Resultados).
DEFAULT_STRATEGIES = ["pullback", "rsi2", "ibs", "tom"]
DEFAULT_LEVERAGE = 3
DEFAULT_TAKE_PROFIT = 0.05   # +5 % sobre la posición apalancada
DEFAULT_STOP_LOSS = 0.10     # -10 % sobre la posición apalancada
DEFAULT_ALLOCATION = 0.5     # % del capital por operación (con x3 => exposición 1.5x)
