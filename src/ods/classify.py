"""Normalização e classificação de campos (gênero, raça, situação, fonte de receita)."""
import re
import unicodedata

import pandas as pd

from .config import NULL_TOKENS


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def norm(text) -> str:
    """Maiúsculas, sem acentos, espaços colapsados. Nulo -> ''."""
    if text is None or (isinstance(text, float) and pd.isna(text)) or text is pd.NA:
        return ""
    return re.sub(r"\s+", " ", strip_accents(str(text)).upper()).strip()


def norm_series(s: pd.Series) -> pd.Series:
    out = s.fillna("").astype(str).map(norm)
    return out.mask(out.isin(NULL_TOKENS), "")


def classify_receita(fonte: str, origem: str, natureza: str = "") -> str:
    """Heurística por texto. Valide com o relatório de categorias gerado pelo ETL."""
    t = norm(f"{fonte} {origem} {natureza}")
    if "FUNDO ESPECIAL" in t or "FEFC" in t:
        return "FEFC"
    if "FUNDO PARTIDARIO" in t:
        return "FUNDO_PARTIDARIO"
    if "RECURSOS PROPRIOS" in t:
        return "PROPRIOS"
    if "PESSOAS FISICAS" in t or "PESSOA FISICA" in t or "FINANCIAMENTO COLETIVO" in t:
        return "DOACAO_PF"
    if "PARTIDO" in t or "COMITE" in t or "OUTROS CANDIDATOS" in t:
        return "PARTIDO_OUTROS"
    return "OUTROS"


GRUPO_RACA = {
    "BRANCA": "Branca",
    "PRETA": "Negra",   # convenção IBGE: negros = pretos + pardos
    "PARDA": "Negra",
    "AMARELA": "Amarela",
    "INDIGENA": "Indígena",
}
COR_LABEL = {
    "BRANCA": "Branca", "PRETA": "Preta", "PARDA": "Parda",
    "AMARELA": "Amarela", "INDIGENA": "Indígena",
}


def normalize_raca(s: pd.Series) -> tuple[pd.Series, pd.Series]:
    n = norm_series(s)
    cor = n.map(COR_LABEL).fillna("Não informada")
    grupo = n.map(GRUPO_RACA).fillna("Não informada")
    return cor, grupo


def normalize_genero(s: pd.Series) -> pd.Series:
    n = norm_series(s)
    return n.map({"MASCULINO": "Homem", "FEMININO": "Mulher"}).fillna("Não informado")


def is_eleito(s: pd.Series) -> pd.Series:
    """'ELEITO', 'ELEITO POR QP', 'ELEITO POR MEDIA' (e não 'NAO ELEITO')."""
    return norm_series(s).str.startswith("ELEITO")


def make_perfil(genero: pd.Series, grupo_raca: pd.Series) -> pd.Series:
    return genero + " · " + grupo_raca
