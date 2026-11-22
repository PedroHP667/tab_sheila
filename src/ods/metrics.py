"""Métricas interseccionais (gênero x raça) sobre o DataFrame de vw_candidato_receita."""
import numpy as np
import pandas as pd

FONTES = {
    "FEFC": "receita_fefc",
    "Fundo partidário": "receita_fundo_partidario",
    "Doação de pessoa física": "receita_doacao_pf",
    "Recursos próprios": "receita_proprios",
    "Partido/outros candidatos": "receita_partido_outros",
    "Outros": "receita_outros",
}


def funil(df: pd.DataFrame) -> pd.DataFrame:
    """Candidaturas -> candidaturas com recurso -> eleitos, por perfil."""
    g = df.groupby("perfil")
    out = pd.DataFrame({
        "candidaturas": g.size(),
        "com_recurso": g["receita_total"].apply(lambda s: int((s > 0).sum())),
        "eleitos": g["eleito"].sum().astype(int),
    })
    out["taxa_com_recurso"] = out["com_recurso"] / out["candidaturas"]
    out["taxa_eleicao"] = out["eleitos"] / out["candidaturas"]
    return out.reset_index().sort_values("candidaturas", ascending=False)


def recursos_por_perfil(df: pd.DataFrame) -> pd.DataFrame:
    """Média, mediana e índice de paridade (% dos recursos / % das candidaturas)."""
    g = df.groupby("perfil")["receita_total"]
    out = pd.DataFrame({
        "candidaturas": g.size(), "total": g.sum(), "media": g.mean(), "mediana": g.median(),
    })
    out["share_candidaturas"] = out["candidaturas"] / out["candidaturas"].sum()
    out["share_recursos"] = out["total"] / out["total"].sum() if out["total"].sum() else np.nan
    out["indice_paridade"] = out["share_recursos"] / out["share_candidaturas"]
    return out.reset_index().sort_values("total", ascending=False)


def composicao_fontes(df: pd.DataFrame) -> pd.DataFrame:
    """Participação de cada fonte no total recebido por perfil (linhas somam 1)."""
    soma = df.groupby("perfil")[list(FONTES.values())].sum()
    total = soma.sum(axis=1).replace(0, np.nan)
    share = soma.div(total, axis=0).fillna(0.0)
    share.columns = list(FONTES.keys())
    return share.reset_index()


def eficiencia(df: pd.DataFrame) -> pd.DataFrame:
    """Votos por R$ 1.000 gastos (razão das somas, não média de razões)."""
    g = df.groupby("perfil")[["votos", "receita_total"]].sum()
    g["votos_por_mil_reais"] = np.where(g["receita_total"] > 0, g["votos"] / (g["receita_total"] / 1000), np.nan)
    g["custo_por_voto"] = np.where(g["votos"] > 0, g["receita_total"] / g["votos"], np.nan)
    return g.reset_index().sort_values("votos_por_mil_reais", ascending=False)


def paridade_por_partido(df: pd.DataFrame, perfil_alvo: str, min_candidaturas: int = 20, top: int = 15) -> pd.DataFrame:
    """Por partido: % de candidaturas do perfil x % dos recursos do partido que foram a esse perfil."""
    d = df[df["partido"].notna()].copy()
    d["alvo"] = d["perfil"] == perfil_alvo
    g = d.groupby("partido")
    out = pd.DataFrame({
        "candidaturas": g.size(),
        "share_candidaturas": g["alvo"].mean(),
        "recursos_partido": g["receita_total"].sum(),
        "recursos_alvo": d[d["alvo"]].groupby("partido")["receita_total"].sum(),
    }).fillna({"recursos_alvo": 0.0})
    out["share_recursos"] = np.where(out["recursos_partido"] > 0, out["recursos_alvo"] / out["recursos_partido"], np.nan)
    out["diferenca_pp"] = (out["share_recursos"] - out["share_candidaturas"]) * 100
    out = out[out["candidaturas"] >= min_candidaturas]
    return out.sort_values("candidaturas", ascending=False).head(top).reset_index()
