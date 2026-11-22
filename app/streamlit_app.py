import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ods import metrics  # noqa: E402
from ods.data import anos_disponiveis, load_wide  # noqa: E402
from ods.db import Db  # noqa: E402
from ods.formato import brl, brl_compacto, inteiro, pct, pp  # noqa: E402

st.set_page_config(page_title="Financiamento eleitoral × gênero e raça", layout="wide")


def _db_url() -> str:
    try:
        return st.secrets["DATABASE_URL"]
    except Exception:
        return os.environ.get("DATABASE_URL", "")


@st.cache_resource
def get_db(url: str) -> Db:
    return Db(url) 


@st.cache_data(ttl=3600, show_spinner="Consultando o banco...")
def get_data(url: str, anos: tuple) -> pd.DataFrame:
    return load_wide(get_db(url), list(anos))


def estilizar(fig, titulo_y=None, pct_y=False, linha_ref=None):
    """Padroniza os gráficos: sem título de eixo X, rótulos legíveis, linha de referência opcional."""
    fig.update_xaxes(title=None, tickangle=-25, automargin=True)
    fig.update_yaxes(title=titulo_y, automargin=True, **({"tickformat": ".0%"} if pct_y else {}))
    fig.update_layout(margin=dict(t=60, b=10, l=10, r=10), legend_title_text=None)
    if linha_ref is not None:
        fig.add_hline(y=linha_ref, line_dash="dash", line_color="gray")
    return fig


def mostrar(fig):
    st.plotly_chart(fig, use_container_width=True)


url = _db_url()
if not url:
    st.error("Configure DATABASE_URL em st.secrets (Streamlit Cloud) ou na variável de ambiente.")
    st.stop()

st.title("Quem recebe o dinheiro das campanhas? Gênero × raça")
st.caption("ODS 5 (Igualdade de Gênero) e ODS 18 (Igualdade Étnico-Racial) · Dados abertos do TSE")

anos_ok = anos_disponiveis(get_db(url))
if not anos_ok:
    st.warning("Banco vazio. Rode o ETL primeiro (ver README).")
    st.stop()

with st.sidebar:
    st.header("Filtros")
    anos = st.multiselect("Ano da eleição", anos_ok, default=anos_ok[-1:])
    if not anos:
        st.info("Escolha ao menos um ano.")
        st.stop()
    base = get_data(url, tuple(anos))
    cargos = st.multiselect("Cargo", sorted(base["cargo"].unique()))
    ufs = st.multiselect("UF", sorted(base["uf"].unique()))
    partidos = st.multiselect("Partido", sorted(base["partido"].dropna().unique()))

df = base
if cargos:
    df = df[df["cargo"].isin(cargos)]
if ufs:
    df = df[df["uf"].isin(ufs)]
if partidos:
    df = df[df["partido"].isin(partidos)]
if df.empty:
    st.warning("Nenhuma candidatura com esses filtros.")
    st.stop()

total = df["receita_total"].sum()
mn = df["perfil"].eq("Mulher · Negra")
share_cand = mn.mean()
share_rec = df.loc[mn, "receita_total"].sum() / total if total else 0.0
n_eleitos = int(df["eleito"].sum())
share_eleitas = (df["eleito"] & mn).sum() / n_eleitos if n_eleitos else 0.0

a, b, c = st.columns(3)
a.metric("Candidaturas", inteiro(len(df)))
b.metric("Eleitos", inteiro(n_eleitos))
c.metric("Receita total", brl_compacto(total), help=brl(total))

d, e, f_ = st.columns(3)
d.metric("Mulheres negras · % das candidaturas", pct(share_cand))
e.metric("Mulheres negras · % dos recursos", pct(share_rec), delta=pp(share_rec - share_cand),
         help="Diferença em relação ao % de candidaturas. Negativo = recebem menos do que seu peso entre os candidatos.")
f_.metric("Mulheres negras · % dos eleitos", pct(share_eleitas), delta=pp(share_eleitas - share_cand),
          help="Diferença em relação ao % de candidaturas.")

t1, t2, t3, t4 = st.tabs(["Funil", "Distribuição de recursos", "Fontes de recursos", "Eficiência e partidos"])

with t1:
    st.caption("Quantas candidaturas de cada perfil chegam a receber recursos e a se eleger.")
    fu = metrics.funil(df)
    etapas = {"candidaturas": "Candidaturas", "com_recurso": "Com recurso", "eleitos": "Eleitos"}
    long = fu.melt("perfil", list(etapas), var_name="Etapa", value_name="Quantidade")
    long["Etapa"] = long["Etapa"].map(etapas)
    fig = px.bar(long, x="perfil", y="Quantidade", color="Etapa", barmode="group",
                 category_orders={"perfil": list(fu["perfil"])})
    mostrar(estilizar(fig, "Candidaturas"))
    tab = fu.rename(columns={"perfil": "Perfil", "candidaturas": "Candidaturas", "com_recurso": "Com recurso",
                             "eleitos": "Eleitos", "taxa_com_recurso": "% com recurso",
                             "taxa_eleicao": "% eleitos"})
    st.dataframe(tab.style.format({"% com recurso": "{:.1%}", "% eleitos": "{:.1%}"}),
                 use_container_width=True, hide_index=True)

with t2:
    st.caption("Medianas são mais robustas que médias, porque poucos candidatos concentram muito dinheiro.")
    r = metrics.recursos_por_perfil(df)
    x, y = st.columns(2)
    rp = r.rename(columns={"media": "Média", "mediana": "Mediana"})
    fig1 = px.bar(rp, x="perfil", y=["Média", "Mediana"], barmode="group",
                  title="Receita por candidatura (R$)")
    x.plotly_chart(estilizar(fig1, "R$ por candidatura"), use_container_width=True)
    fig2 = px.bar(r, x="perfil", y="indice_paridade",
                  title="Índice de paridade (1 = proporcional)")
    y.plotly_chart(estilizar(fig2, "% dos recursos ÷ % das candidaturas", linha_ref=1), use_container_width=True)
    tab = r.rename(columns={"perfil": "Perfil", "candidaturas": "Candidaturas", "total": "Total (R$)",
                            "media": "Média (R$)", "mediana": "Mediana (R$)",
                            "share_candidaturas": "% das candidaturas", "share_recursos": "% dos recursos",
                            "indice_paridade": "Índice de paridade"})
    st.dataframe(tab.style.format({"Total (R$)": "R$ {:,.0f}", "Média (R$)": "R$ {:,.0f}",
                                   "Mediana (R$)": "R$ {:,.0f}", "% das candidaturas": "{:.1%}",
                                   "% dos recursos": "{:.1%}", "Índice de paridade": "{:.2f}"}),
                 use_container_width=True, hide_index=True)

with t3:
    st.caption("De onde vem o dinheiro de cada perfil: fundos públicos (FEFC e partidário) ou doações privadas.")
    comp = metrics.composicao_fontes(df).melt("perfil", var_name="Fonte", value_name="Participação")
    fig = px.bar(comp, x="perfil", y="Participação", color="Fonte", barmode="stack")
    mostrar(estilizar(fig, "Participação na receita do perfil", pct_y=True))

with t4:
    st.caption("Quantos votos cada R$ 1.000 de receita rendeu, e como cada partido distribui seus recursos.")
    ef = metrics.eficiencia(df)
    fig = px.bar(ef, x="perfil", y="votos_por_mil_reais", title="Votos por R$ 1.000 de receita")
    mostrar(estilizar(fig, "Votos por R$ 1.000"))
    alvo = st.selectbox("Perfil para comparar entre partidos", sorted(df["perfil"].unique()), index=0)
    p = metrics.paridade_por_partido(df, alvo)
    if p.empty:
        st.info("Poucos dados por partido com esses filtros (mínimo de 20 candidaturas por partido).")
    else:
        fig = px.bar(p, x="partido", y="diferenca_pp",
                     title=f"{alvo}: % dos recursos menos % das candidaturas do partido")
        mostrar(estilizar(fig, "Diferença (pontos percentuais)", linha_ref=0))

with st.expander("Notas metodológicas"):
    st.markdown(
        "- Raça/cor é **autodeclarada**. 'Negra' = preta + parda (convenção do IBGE).\n"
        "- Considera candidaturas **aptas/deferidas**. Votos = nominais do 1º turno.\n"
        "- Receitas classificadas por texto de fonte/origem (heurística documentada no README).\n"
        "- Para governador, receitas do 1º e do 2º turno são somadas.\n"
        "- Os dados mostram associação, não causalidade."
    )