"""Transformações puras (pandas) sobre os CSVs do TSE. Sem I/O de banco."""
import logging

import pandas as pd

from .classify import (
    classify_receita, is_eleito, make_perfil, norm_series, normalize_genero, normalize_raca,
)
from .config import NULL_TOKENS, SITUACOES_VALIDAS_EXATAS, SITUACOES_VALIDAS_PREFIXO

log = logging.getLogger("ods.transform")

CAND_COLS = {
    "ANO_ELEICAO": "ano", "NR_TURNO": "turno", "SQ_CANDIDATO": "sq_candidato",
    "SG_UF": "uf", "DS_CARGO": "cargo", "SG_PARTIDO": "partido",
    "DS_GENERO": "genero_raw", "DS_COR_RACA": "cor_raca_raw",
    "DS_SITUACAO_CANDIDATURA": "situacao_candidatura", "DS_SIT_TOT_TURNO": "situacao_turno",
}
RECEITA_COLS = ["ANO_ELEICAO", "SQ_CANDIDATO", "DS_FONTE_RECEITA", "DS_ORIGEM_RECEITA",
                "DS_NATUREZA_RECEITA", "VR_RECEITA"]
VOTO_COLS = ["ANO_ELEICAO", "NR_TURNO", "SQ_CANDIDATO", "QT_VOTOS_NOMINAIS"]


def require(df: pd.DataFrame, cols: list[str], nome: str) -> None:
    faltam = [c for c in cols if c not in df.columns]
    if faltam:
        raise ValueError(f"{nome}: colunas ausentes {faltam}. Colunas lidas: {list(df.columns)}")


def clean_nulls(df: pd.DataFrame) -> pd.DataFrame:
    """Tira espaços e converte tokens de nulo do TSE (#NULO, #NE...) em NA."""
    out = df.copy()
    for c in out.columns:
        s = out[c].astype("string").str.strip()
        out[c] = s.mask(s.str.upper().isin(NULL_TOKENS))
    return out


def parse_money(s: pd.Series) -> pd.Series:
    """'1234,56' ou '1.234,56' -> 1234.56. Inválido -> NaN."""
    s = s.astype("string").str.strip()
    has_comma = s.str.contains(",", na=False)
    fixed = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s.where(~has_comma, fixed), errors="coerce").astype("float64")


def transform_candidatos(raw: pd.DataFrame, cargos=None, ufs=None) -> pd.DataFrame:
    require(raw, ["ANO_ELEICAO", "SQ_CANDIDATO", "SG_UF", "DS_CARGO"], "candidatos")
    df = clean_nulls(raw)
    for col in CAND_COLS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df.rename(columns=CAND_COLS)[list(CAND_COLS.values())]
    n0 = len(df)

    sit = norm_series(df["situacao_candidatura"])
    valido = sit.str.startswith(SITUACOES_VALIDAS_PREFIXO) | sit.isin(SITUACOES_VALIDAS_EXATAS)
    log.info("situações encontradas: %s", sit.value_counts().head(8).to_dict())
    df = df[valido].copy()
    log.info("candidatos: %d lidos, %d com candidatura válida", n0, len(df))

    if cargos:
        alvo = {norm_series(pd.Series([c])).iloc[0] for c in cargos}
        df = df[norm_series(df["cargo"]).isin(alvo)]
    if ufs:
        df = df[df["uf"].str.upper().isin({u.upper() for u in ufs})]

    # Candidatos de 2º turno aparecem em duas linhas: mantém a última (resultado final).
    df["turno"] = pd.to_numeric(df["turno"], errors="coerce").fillna(1)
    df = df.sort_values("turno").drop_duplicates(["ano", "sq_candidato"], keep="last")

    out = pd.DataFrame({
        "ano": pd.to_numeric(df["ano"]).astype("int16"),
        "sq_candidato": df["sq_candidato"].astype(str),
        "cargo": df["cargo"].astype(str),
        "uf": df["uf"].astype(str).str.upper(),
        "partido": df["partido"].astype("object"),
    })
    out["genero"] = normalize_genero(df["genero_raw"]).values
    cor, grupo = normalize_raca(df["cor_raca_raw"])
    out["cor_raca"], out["grupo_raca"] = cor.values, grupo.values
    out["perfil"] = make_perfil(out["genero"], out["grupo_raca"])
    out["situacao_candidatura"] = df["situacao_candidatura"].astype("object").values
    out["situacao_turno"] = df["situacao_turno"].astype("object").values
    out["eleito"] = is_eleito(df["situacao_turno"]).values
    if df["situacao_turno"].isna().all():
        log.warning("DS_SIT_TOT_TURNO vazia/ausente: 'eleito' ficará falso para todos. Verifique o arquivo.")
    return out.reset_index(drop=True)


def aggregate_receitas(chunk: pd.DataFrame, validos: set, ano=None) -> pd.DataFrame:
    """Agrega um pedaço do arquivo de receitas por (ano, candidato, categoria)."""
    # No arquivo de receitas de 2022 a coluna do ano se chama AA_ELEICAO (nos outros, ANO_ELEICAO).
    chunk = chunk.rename(columns={"AA_ELEICAO": "ANO_ELEICAO"})
    require(chunk, ["SQ_CANDIDATO", "VR_RECEITA"], "receitas")
    for c in RECEITA_COLS:
        if c not in chunk.columns:
            chunk[c] = pd.NA
    if ano is not None and chunk["ANO_ELEICAO"].isna().all():
        chunk["ANO_ELEICAO"] = str(ano)
    df = clean_nulls(chunk[RECEITA_COLS])
    df = df[df["SQ_CANDIDATO"].isin(validos)].copy()
    chaves = ["DS_FONTE_RECEITA", "DS_ORIGEM_RECEITA", "DS_NATUREZA_RECEITA"]
    df[chaves] = df[chaves].fillna("").astype(object)
    df["valor"] = parse_money(df["VR_RECEITA"])
    df = df.dropna(subset=["valor"])
    combos = df[chaves].drop_duplicates()
    combos["categoria"] = [classify_receita(*row) for row in combos.itertuples(index=False)]
    df = df.merge(combos, on=chaves, how="left")
    return (
        df.groupby(["ANO_ELEICAO", "SQ_CANDIDATO", "categoria"], as_index=False)["valor"].sum()
        .rename(columns={"ANO_ELEICAO": "ano", "SQ_CANDIDATO": "sq_candidato"})
    )


def aggregate_votos(chunk: pd.DataFrame, validos: set) -> pd.DataFrame:
    """Votos nominais do 1º turno por candidato (evita dupla contagem com o 2º turno)."""
    require(chunk, VOTO_COLS, "votacao")
    df = clean_nulls(chunk[VOTO_COLS])
    df = df[(df["NR_TURNO"] == "1") & df["SQ_CANDIDATO"].isin(validos)].copy()
    df["votos"] = pd.to_numeric(df["QT_VOTOS_NOMINAIS"], errors="coerce").fillna(0)
    return (
        df.groupby(["ANO_ELEICAO", "SQ_CANDIDATO"], as_index=False)["votos"].sum()
        .rename(columns={"ANO_ELEICAO": "ano", "SQ_CANDIDATO": "sq_candidato"})
    )