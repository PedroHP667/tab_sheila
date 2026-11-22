import argparse
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from ods.config import DATASETS  # noqa: E402
from ods.db import Db  # noqa: E402
from ods.pipeline import select_members, zip_path  # noqa: E402
from ods.transform import parse_money  # noqa: E402


def le_receitas(zp: Path, ano: int, sqs: set) -> pd.DataFrame:
    partes = []
    with zipfile.ZipFile(zp) as z:
        m = select_members(z.namelist(), DATASETS["receitas"][1], ano)[0]
        with z.open(m) as f:
            for ch in pd.read_csv(f, sep=";", encoding="latin-1", dtype=str, chunksize=200_000):
                partes.append(ch[ch["SQ_CANDIDATO"].isin(sqs)])
    df = pd.concat(partes, ignore_index=True)
    df["valor"] = parse_money(df["VR_RECEITA"])
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, default=2022)
    ap.add_argument("--source-dir", default=str(ROOT / "data" / "raw"))
    ap.add_argument("--db-url", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--top", type=int, default=3, help="N candidatos com maior receita no banco")
    ap.add_argument("--sq", nargs="*", help="SQ_CANDIDATO específicos")
    ap.add_argument("--detalhe", action="store_true", help="Imprime as linhas de receita de cada candidato")
    a = ap.parse_args()
    db = Db(a.db_url)
    if a.sq:
        sqs = list(a.sq)
    else:
        t = db.read_sql(f"SELECT sq_candidato FROM vw_candidato_receita WHERE ano = {int(a.ano)} "
                        f"ORDER BY receita_total DESC LIMIT {int(a.top)}")
        sqs = list(t["sq_candidato"])
    banco = db.read_sql("SELECT sq_candidato, receita_total, votos, eleito FROM vw_candidato_receita "
                        f"WHERE ano = {int(a.ano)}")
    banco = banco[banco["sq_candidato"].isin(sqs)].set_index("sq_candidato")

    cols = {"SQ_CANDIDATO", "NM_URNA_CANDIDATO", "NM_CANDIDATO", "NR_CANDIDATO", "SG_UF", "DS_CARGO", "SG_PARTIDO"}
    with zipfile.ZipFile(zip_path(Path(a.source_dir), "cand", a.ano)) as z:
        m = select_members(z.namelist(), DATASETS["cand"][1], a.ano)[0]
        cand = pd.read_csv(z.open(m), sep=";", encoding="latin-1", dtype=str, usecols=lambda c: c in cols)
    cand = cand.drop_duplicates("SQ_CANDIDATO").set_index("SQ_CANDIDATO")

    bruto = le_receitas(zip_path(Path(a.source_dir), "receitas", a.ano), a.ano, set(sqs))
    for sq in sqs:
        d = bruto[bruto["SQ_CANDIDATO"] == sq]
        nome = cand.loc[sq].get("NM_URNA_CANDIDATO", cand.loc[sq].get("NM_CANDIDATO", "?")) if sq in cand.index else "?"
        num = cand.loc[sq].get("NR_CANDIDATO", "?") if sq in cand.index else "?"
        info = cand.loc[sq][["SG_UF", "DS_CARGO", "SG_PARTIDO"]].tolist() if sq in cand.index and \
            {"SG_UF", "DS_CARGO", "SG_PARTIDO"} <= set(cand.columns) else ""
        print(f"\n=== {nome} | nº {num} | {info} | SQ {sq}")
        print(f"  Banco (ETL atual) .................. R$ {float(banco.loc[sq, 'receita_total']):>16,.2f}"
              f"   votos={int(banco.loc[sq, 'votos'])} eleito={bool(banco.loc[sq, 'eleito'])}")
        print(f"  Arquivo, todas as linhas ........... R$ {d['valor'].sum():>16,.2f}  ({len(d)} linhas)")
        print(f"  Sem linhas 100% idênticas .......... R$ {d.drop_duplicates()['valor'].sum():>16,.2f}")
        if "SQ_RECEITA" in d.columns:
            print(f"  Sem repetir SQ_RECEITA ............. R$ {d.drop_duplicates('SQ_RECEITA')['valor'].sum():>16,.2f}")
    if a.detalhe:
        mostrar = ["SQ_CANDIDATO", "TP_PRESTACAO_CONTAS", "DT_RECEITA", "DS_FONTE_RECEITA", "DS_ORIGEM_RECEITA",
                   "DS_NATUREZA_RECEITA", "DS_ESPECIE_RECEITA", "DS_RECEITA", "NM_DOADOR", "VR_RECEITA"]
        mostrar = [c for c in mostrar if c in bruto.columns]
        import pandas as _pd
        _pd.set_option("display.width", 250)
        _pd.set_option("display.max_colwidth", 38)
        for sq in sqs:
            print(f"\n--- linhas de {sq} ---")
            print(bruto[bruto["SQ_CANDIDATO"] == sq][mostrar].to_string(index=False))
    print("\nCompare com 'Total de receitas' do candidato em divulgacandcontas.tse.jus.br "
          "(eleição 2022, mesmo cargo e UF). O método que bater com o site é o correto.")
    db.close()


if __name__ == "__main__":
    main()