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


# --- Brókers --------------------------------------------------------------------
# Costes aproximados para simular. COMPRUÉBALOS en la app / tarifas oficiales:
# cambian y dependen del producto concreto (mira siempre el KID).
BROKERS = {
    "trade_republic": {
        "name": "Trade Republic",
        "fixed_fee": 1.0,          # 1 € de costes externos por orden
        "cost_per_side": 0.0015,   # horquilla típica de un certificado sobre índice (0,1-0,3 %)
        "hours": "Lang & Schwarz Exchange aprox. 7:30-23:00 (hora España): puedes operar "
                 "antes del cierre de EE.UU. (22:00, o 21:00 algunas semanas de mar/nov).",
    },
    "degiro": {
        "name": "DEGIRO",
        "fixed_fee": 2.0,          # aprox. 1 € comisión + 1 € costes externos (verificar por mercado)
        "cost_per_side": 0.0015,
        "hours": "Según el mercado del producto; los turbos/certificados suelen cotizar en "
                 "horario extendido, compruébalo en la ficha.",
    },
    "ninguno": {"name": "Sin bróker (costes genéricos)", "fixed_fee": 0.0,
                "cost_per_side": 0.0005, "hours": ""},
}

# Tipos de producto apalancado disponibles para un inversor de la UE.
# (Los ETFs apalancados de EE.UU. como UPRO o TQQQ NO se pueden comprar desde la
# UE por la normativa PRIIPs: no tienen KID.)
PRODUCTS = {
    "factor": {
        "name": "Certificado factor (Faktor-Zertifikat) Long x3/x5",
        "mode": "etf",              # reinicio diario del apalancamiento
        "annual_rate": 0.05,        # financiación del emisor (tipo de referencia + margen)
        "expense_ratio": 0.005,     # comisión de gestión del emisor (aprox.)
        "search": "En la app busca: '<índice> Faktor Long <x>' o 'Factor Long <x>' "
                  "(p. ej. 'S&P 500 Faktor Long 3x'). Mira el apalancamiento y el emisor.",
    },
    "knockout": {
        "name": "Knock-out / Turbo Long",
        "mode": "knockout",         # palanca fija desde la entrada, se 'quema' en la barrera
        "annual_rate": 0.05,
        "expense_ratio": 0.0,
        "search": "En la app: Derivados > Knock-out > Long sobre el índice, eligiendo "
                  "una barrera cercana a la que indica el bot (palanca ~3 o ~5).",
    },
    "etp": {
        "name": "ETP apalancado UCITS (p. ej. WisdomTree 3x Daily Leveraged)",
        "mode": "etf",
        "annual_rate": 0.04,
        "expense_ratio": 0.0075,
        "search": "Busca 'WisdomTree S&P 500 3x' (ISIN IE00B7Y34M31) o 'Nasdaq 100 3x' "
                  "(ISIN IE00BLRPRL42); comprueba que tu bróker lo tenga.",
    },
}

# Índices cotizados en USD -> resultado en € expuesto al EUR/USD.
USD_INDICES = {"^GSPC", "^NDX"}
FX_SYMBOL = "EURUSD=X"
