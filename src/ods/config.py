"""Configurações: URLs do TSE, nomes de colunas e tokens de nulo.

ATENÇÃO: confirme URLs e nomes de colunas contra os arquivos reais do ano escolhido
(o TSE ocasionalmente muda o layout entre eleições). Ver o dicionário no README.
"""
from pathlib import Path

BASE_URL = "https://cdn.tse.jus.br/estatistica/sead/odsele"

# chave -> (caminho relativo no CDN, prefixo do CSV dentro do zip)
DATASETS = {
    "cand": ("consulta_cand/consulta_cand_{ano}.zip", "consulta_cand"),
    "receitas": (
        "prestacao_contas/prestacao_de_contas_eleitorais_candidatos_{ano}.zip",
        "receitas_candidatos",
    ),
    "votacao": (
        "votacao_candidato_munzona/votacao_candidato_munzona_{ano}.zip",
        "votacao_candidato_munzona",
    ),
}

NULL_TOKENS = {"#NULO", "#NE", "#NULO#", "NULL", "NAO DIVULGAVEL", ""}

# Candidatura válida: eleições antigas usam "DEFERIDO"/"DEFERIDO COM RECURSO",
# as recentes (ex.: 2022) usam "APTO" (e "INAPTO" para as barradas).
SITUACOES_VALIDAS_PREFIXO = "DEFERIDO"
SITUACOES_VALIDAS_EXATAS = {"APTO"}

SCHEMA_SQL = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"

CATEGORIAS_RECEITA = [
    "FEFC", "FUNDO_PARTIDARIO", "DOACAO_PF", "PROPRIOS", "PARTIDO_OUTROS", "OUTROS",
]