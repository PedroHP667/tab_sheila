"""Orquestra extração (download/zip) -> transformação -> carga."""
import logging
import re
import zipfile
from collections import Counter
from pathlib import Path

import pandas as pd
import requests

from .config import BASE_URL, DATASETS, SCHEMA_SQL
from .db import Db
from .transform import aggregate_receitas, aggregate_votos, transform_candidatos

log = logging.getLogger("ods.pipeline")


def zip_path(source_dir: Path, key: str, ano: int) -> Path:
    rel, _ = DATASETS[key]
    return Path(source_dir) / Path(rel.format(ano=ano)).name


def ensure_file(source_dir: Path, key: str, ano: int, download: bool) -> Path:
    path = zip_path(source_dir, key, ano)
    if path.exists():
        return path
    if not download:
        raise FileNotFoundError(f"{path} não existe. Use --download ou coloque o zip em {source_dir}.")
    url = f"{BASE_URL}/{DATASETS[key][0].format(ano=ano)}"
    path.parent.mkdir(parents=True, exist_ok=True)
    log.info("baixando %s", url)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for part in r.iter_content(1 << 20):
                f.write(part)
    return path


def select_members(names: list[str], prefix: str, ano: int) -> list[str]:
    """Prefere o arquivo *_BRASIL.csv. Sem ele, usa os arquivos por UF."""
    pat = re.compile(rf"^{re.escape(prefix)}_{ano}_([A-Z]{{2,6}})\.csv$", re.I)
    achados = {n: pat.match(n.split("/")[-1]) for n in names}
    achados = {n: m.group(1).upper() for n, m in achados.items() if m}
    brasil = [n for n, uf in achados.items() if uf == "BRASIL"]
    return brasil or sorted(achados)


def iter_csv(zip_file: Path, prefix: str, ano: int, usecols: set, chunksize: int):
    with zipfile.ZipFile(zip_file) as z:
        membros = select_members(z.namelist(), prefix, ano)
        if not membros:
            raise FileNotFoundError(f"Nenhum CSV '{prefix}_{ano}_*' em {zip_file}")
        for m in membros:
            log.info("lendo %s", m)
            with z.open(m) as f:
                yield from pd.read_csv(
                    f, sep=";", encoding="latin-1", dtype=str, quotechar='"',
                    usecols=lambda c: c in usecols, chunksize=chunksize,
                )


def process_year(ano, source_dir, db: Db, cargos=None, ufs=None, download=False, chunksize=200_000):
    from .transform import CAND_COLS, RECEITA_COLS, VOTO_COLS

    stats = {}
    # 1) candidatos
    zc = ensure_file(source_dir, "cand", ano, download)
    partes = list(iter_csv(zc, DATASETS["cand"][1], ano, set(CAND_COLS), chunksize))
    cand = transform_candidatos(pd.concat(partes, ignore_index=True), cargos, ufs)
    if cand.empty:
        raise ValueError(f"Nenhum candidato deferido para {ano} com os filtros informados.")
    validos = set(cand["sq_candidato"])
    stats["candidatos_lidos"] = sum(len(p) for p in partes)

    # 2) receitas (em pedaços, só candidatos válidos)
    zr = ensure_file(source_dir, "receitas", ano, download)
    ag, lidas = [], 0
    for ch in iter_csv(zr, DATASETS["receitas"][1], ano, set(RECEITA_COLS) | {"AA_ELEICAO"}, chunksize):
        lidas += len(ch)
        ag.append(aggregate_receitas(ch, validos, ano))
    receitas = pd.concat(ag, ignore_index=True) if ag else pd.DataFrame(
        columns=["ano", "sq_candidato", "categoria", "valor"])
    if lidas > 0 and receitas.empty:
        raise ValueError(
            f"{lidas} linhas de receitas lidas, mas nenhuma casou com os candidatos filtrados. "
            "Verifique SQ_CANDIDATO, o ano e as colunas do arquivo de receitas.")
    receitas = receitas.groupby(["ano", "sq_candidato", "categoria"], as_index=False)["valor"].sum()
    receitas["valor"] = receitas["valor"].round(2)
    receitas["ano"] = pd.to_numeric(receitas["ano"]).astype("int16")
    stats["receitas_lidas"] = lidas

    # 3) votos
    zv = ensure_file(source_dir, "votacao", ano, download)
    vs = [aggregate_votos(ch, validos) for ch in
          iter_csv(zv, DATASETS["votacao"][1], ano, set(VOTO_COLS), chunksize)]
    votos = pd.concat(vs, ignore_index=True).groupby(["ano", "sq_candidato"], as_index=False)["votos"].sum() \
        if vs else pd.DataFrame(columns=["ano", "sq_candidato", "votos"])
    if votos.empty:
        log.warning("Nenhum voto casou com os candidatos: 'votos' ficará 0. Verifique o arquivo de votação.")
    votos["ano"] = pd.to_numeric(votos["ano"]).astype("int16")
    cand = cand.merge(votos, on=["ano", "sq_candidato"], how="left")
    cand["votos"] = cand["votos"].fillna(0).astype("int64")

    # 4) carga idempotente por ano
    ano_i = int(ano)
    db.execute(f"DELETE FROM receita_candidato WHERE ano = {ano_i}")
    db.execute(f"DELETE FROM candidato WHERE ano = {ano_i}")
    stats["candidatos_gravados"] = db.write(cand, "candidato")
    stats["receitas_gravadas"] = db.write(receitas, "receita_candidato")
    log_rows = pd.DataFrame([
        {"ano": ano_i, "tabela": "candidato", "linhas_lidas": stats["candidatos_lidos"],
         "linhas_gravadas": stats["candidatos_gravados"], "observacao": f"cargos={cargos} ufs={ufs}"},
        {"ano": ano_i, "tabela": "receita_candidato", "linhas_lidas": stats["receitas_lidas"],
         "linhas_gravadas": stats["receitas_gravadas"], "observacao": "agregado por categoria"},
    ])
    db.write(log_rows, "etl_execucao")
    log.info("ano %s: %s", ano, stats)
    return stats


def run(anos, source_dir, db_url, cargos=None, ufs=None, reset=False, download=False):
    db = Db(db_url)
    try:
        if reset:
            for obj in ("DROP VIEW IF EXISTS vw_candidato_receita", "DROP TABLE IF EXISTS receita_candidato",
                        "DROP TABLE IF EXISTS candidato", "DROP TABLE IF EXISTS etl_execucao"):
                db.execute(obj)
        db.run_script(SCHEMA_SQL.read_text(encoding="utf-8"))
        resultados = {}
        for ano in anos:
            resultados[ano] = process_year(ano, Path(source_dir), db, cargos, ufs, download)
        return resultados
    finally:
        db.close()