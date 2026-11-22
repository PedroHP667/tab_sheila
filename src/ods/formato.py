"""Formatação em pt-BR para o dashboard."""


def brl(v: float) -> str:
    """R$ 1.234.567 (sem centavos)."""
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def brl_compacto(v: float) -> str:
    """R$ 110,4 mi / R$ 850 mil / R$ 1,2 bi: cabe em cartões estreitos."""
    a = abs(v)
    if a >= 1e9:
        s = f"{v / 1e9:.1f} bi"
    elif a >= 1e6:
        s = f"{v / 1e6:.1f} mi"
    elif a >= 1e3:
        s = f"{v / 1e3:.0f} mil"
    else:
        s = f"{v:.0f}"
    return "R$ " + s.replace(".", ",")


def inteiro(n: float) -> str:
    return f"{int(n):,}".replace(",", ".")


def pct(x: float, casas: int = 1) -> str:
    return f"{x * 100:.{casas}f}%".replace(".", ",")


def pp(x: float, casas: int = 1) -> str:
    """Diferença em pontos percentuais, com sinal: +2,5 p.p. / -1,0 p.p."""
    return f"{x * 100:+.{casas}f}".replace(".", ",") + " p.p."