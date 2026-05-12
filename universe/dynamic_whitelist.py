PHASE0_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


def phase_universe(phase: int) -> tuple[str, ...]:
    if phase <= 0:
        return PHASE0_SYMBOLS
    if phase == 1:
        return PHASE0_SYMBOLS + ("BNBUSDT", "XRPUSDT")
    return PHASE0_SYMBOLS + ("BNBUSDT", "XRPUSDT", "AAVEUSDT", "LINKUSDT", "AVAXUSDT")
