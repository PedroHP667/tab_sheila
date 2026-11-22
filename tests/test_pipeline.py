"""Rodar:  python tests/test_pipeline.py   (ou pytest)"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import pandas as pd  # noqa: E402

from make_sample_data import make  # noqa: E402
from ods import metrics  # noqa: E402
from ods.classify import classify_receita  # noqa: E402
from ods.data import load_wide  # noqa: E402
from ods.db import Db  # noqa: E402
from ods.pipeline import run  # noqa: E402
from ods.transform import parse_money  # noqa: E402


def test_unitarios():
    assert classify_receita("Recursos de partido político", "Fundo Especial de Financiamento de Campanha") == "FEFC"
    assert classify_receita("Recursos de partido político", "Fundo Partidário") == "FUNDO_PARTIDARIO"
    assert classify_receita("Recursos de pessoas físicas", "Doações") == "DOACAO_PF"
    assert classify_receita("x", "y") == "OUTROS"
    s = parse_money(pd.Series(["1234,56", "1.234,56", "#NULO", "abc", "10"]))
    assert s.iloc[0] == 1234.56 and s.iloc[1] == 1234.56 and s.iloc[4] == 10
    assert pd.isna(s.iloc[2]) and pd.isna(s.iloc[3])


def test_pipeline_ponta_a_ponta():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        esp = make(tmp / "raw")
        url = f"sqlite:///{tmp / 'teste.db'}"
        for _ in range(2):  # 2 execuções: carga deve ser idempotente
            run([2022], tmp / "raw", url)
        db = Db(url)
        cand = db.read_sql("SELECT * FROM candidato")
        rec = db.read_sql("SELECT * FROM receita_candidato")
        assert set(cand["sq_candidato"]) == set(esp["validos"]), "só candidaturas deferidas"
        assert not cand.duplicated(["ano", "sq_candidato"]).any(), "sem duplicatas (turno 2 / reexecução)"
        assert int(cand["eleito"].sum()) == esp["eleitos"]
        assert not rec["sq_candidato"].eq("999999").any(), "receita órfã descartada"
        for cat, v in esp["receita"].items():
            got = rec[rec["categoria"] == cat]["valor"].sum()
            assert abs(got - v) < 0.01, (cat, got, v)
        votos = cand.set_index("sq_candidato")["votos"].to_dict()
        assert all(votos[k] == v for k, v in esp["votos"].items()), "votos: só 1º turno"
        assert set(cand["grupo_raca"]) <= {"Branca", "Negra", "Amarela", "Indígena", "Não informada"}
        assert (cand.loc[cand["cor_raca"] == "Parda", "grupo_raca"] == "Negra").all()
        assert len(db.read_sql("SELECT * FROM etl_execucao")) == 4

        df = load_wide(db, [2022])
        assert abs(df["receita_total"].sum() - sum(esp["receita"].values())) < 0.05
        f = metrics.funil(df)
        assert f["candidaturas"].sum() == len(df)
        r = metrics.recursos_por_perfil(df)
        assert abs(r["share_recursos"].sum() - 1) < 1e-9 and abs(r["share_candidaturas"].sum() - 1) < 1e-9
        c = metrics.composicao_fontes(df)
        assert ((c.drop(columns="perfil").sum(axis=1) - 1).abs() < 1e-9).all()
        e = metrics.eficiencia(df)
        assert e["votos"].sum() == df["votos"].sum()
        p = metrics.paridade_por_partido(df, "Mulher · Negra", min_candidaturas=5)
        assert len(p) > 0 and p["share_candidaturas"].between(0, 1).all()
        db.close()


if __name__ == "__main__":
    test_unitarios()
    test_pipeline_ponta_a_ponta()
    print("OK: todos os testes passaram")
