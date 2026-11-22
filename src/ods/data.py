"""Leitura da visão analítica (vw_candidato_receita) com tipos normalizados."""
import pandas as pd

from .db import Db

NUM_COLS = [
    "receita_total", "receita_fefc", "receita_fundo_partidario", "receita_doacao_pf",
    "receita_proprios", "receita_partido_outros", "receita_outros", "votos",
]


def load_wide(db: Db, anos: list[int] | None = None) -> pd.DataFrame:
    where = ""
    if anos:
        where = " WHERE ano IN (%s)" % ",".join(str(int(a)) for a in anos)  # ints validados
    df = db.read_sql("SELECT * FROM vw_candidato_receita" + where)
    for c in NUM_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).astype(float)  # NUMERIC -> float
    df["eleito"] = df["eleito"].astype(bool)
    return df


def anos_disponiveis(db: Db) -> list[int]:
    return sorted(int(a) for a in db.read_sql("SELECT DISTINCT ano FROM candidato")["ano"])
