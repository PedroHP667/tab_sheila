"""Gera zips sintéticos no layout do TSE (latin-1, ';', aspas, #NULO, vírgula decimal).
Serve para testar o pipeline offline. NÃO são dados reais."""
import csv
import io
import json
import random
import zipfile
from pathlib import Path

PARTIDOS = ["AAA", "BBB", "CCC", "DDD"]
UFS = ["SP", "BA", "MG"]
CARGOS = ["DEPUTADO FEDERAL", "DEPUTADO ESTADUAL", "GOVERNADOR"]
RACAS = ["BRANCA", "PARDA", "PRETA", "AMARELA", "INDÍGENA", "NÃO INFORMADO", "#NULO"]
FONTES = [  # (fonte, origem, categoria esperada)
    ("Recursos de partido político", "Fundo Especial de Financiamento de Campanha", "FEFC"),
    ("Recursos de partido político", "Fundo Partidário", "FUNDO_PARTIDARIO"),
    ("Recursos de pessoas físicas", "Doações de pessoas físicas", "DOACAO_PF"),
    ("Recursos próprios", "Recursos próprios", "PROPRIOS"),
    ("Recursos de outros candidatos", "Doações de outros candidatos", "PARTIDO_OUTROS"),
    ("Rendimentos de aplicações financeiras", "Rendimentos", "OUTROS"),
]


def _write_csv(zf, name, header, rows):
    buf = io.StringIO(newline="")
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL)
    w.writerow(header)
    w.writerows(rows)
    zf.writestr(name, buf.getvalue().encode("latin-1"))


def make(out_dir: Path, ano=2022, n=240, seed=7) -> dict:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    cand_h = ["ANO_ELEICAO", "NR_TURNO", "SG_UF", "DS_CARGO", "SQ_CANDIDATO", "NM_CANDIDATO", "NR_CPF_CANDIDATO",
              "SG_PARTIDO", "DS_SITUACAO_CANDIDATURA", "DS_GENERO", "DS_COR_RACA", "DS_SIT_TOT_TURNO"]
    cands, rec_rows, vot_rows = [], [], []
    esperado = {"receita": {}, "votos": {}, "validos": set(), "eleitos": 0}
    for i in range(n):
        sq = str(100000 + i)
        cargo, uf = rng.choice(CARGOS), rng.choice(UFS)
        genero = rng.choice(["MASCULINO", "FEMININO"])
        raca = rng.choice(RACAS)
        sit = rng.choices(["DEFERIDO", "DEFERIDO COM RECURSO", "INDEFERIDO"], [80, 10, 10])[0]
        res = rng.choices(["ELEITO", "ELEITO POR QP", "NÃO ELEITO", "SUPLENTE", "#NULO"], [10, 5, 60, 20, 5])[0]
        cands.append([ano, 1, uf, cargo, sq, f"NOME {i}", "#NULO", rng.choice(PARTIDOS), sit, genero, raca, res])
        valido = sit.startswith("DEFERIDO")
        if valido:
            esperado["validos"].add(sq)
            esperado["eleitos"] += res.startswith("ELEITO")
        if cargo == "GOVERNADOR" and valido and rng.random() < 0.5:  # 2º turno: linha duplicada
            cands.append([ano, 2, uf, cargo, sq, f"NOME {i}", "#NULO", cands[-1][7], sit, genero, raca, "ELEITO"])
            esperado["eleitos"] += 1 - res.startswith("ELEITO")
        for _ in range(rng.randint(1, 5)):
            fonte, origem, cat = rng.choice(FONTES)
            v = round(rng.uniform(100, 50000), 2)
            vr = f"{v:.2f}".replace(".", ",")
            rec_rows.append([ano, sq, fonte, origem, "Financeira", vr])
            if valido:
                esperado["receita"][cat] = round(esperado["receita"].get(cat, 0) + v, 2)
        rec_rows.append([ano, sq, "Recursos próprios", "Recursos próprios", "Estimável", "#NULO"])  # valor nulo
        votos = 0
        for _ in range(rng.randint(1, 3)):
            q = rng.randint(0, 5000)
            vot_rows.append([ano, 1, uf, cargo, sq, q])
            votos += q
        if len(cands) and cands[-1][1] == 2:
            vot_rows.append([ano, 2, uf, cargo, sq, 99999])  # não deve ser somado
        if valido:
            esperado["votos"][sq] = votos
    # receita de candidato inexistente (órfã)
    rec_rows.append([ano, "999999", "Recursos próprios", "Recursos próprios", "Financeira", "1000,00"])

    with zipfile.ZipFile(out_dir / f"consulta_cand_{ano}.zip", "w") as z:
        _write_csv(z, f"consulta_cand_{ano}_BRASIL.csv", cand_h, cands)
        _write_csv(z, f"consulta_cand_{ano}_SP.csv", cand_h, cands[:20])  # isca: não deve ser lida
    rec_h = ["ANO_ELEICAO", "SQ_CANDIDATO", "DS_FONTE_RECEITA", "DS_ORIGEM_RECEITA", "DS_NATUREZA_RECEITA", "VR_RECEITA"]
    with zipfile.ZipFile(out_dir / f"prestacao_de_contas_eleitorais_candidatos_{ano}.zip", "w") as z:
        _write_csv(z, f"receitas_candidatos_{ano}_BRASIL.csv", rec_h, rec_rows)
        _write_csv(z, f"receitas_candidatos_doador_originario_{ano}_BRASIL.csv", rec_h, rec_rows[:50])  # isca
    vot_h = ["ANO_ELEICAO", "NR_TURNO", "SG_UF", "DS_CARGO", "SQ_CANDIDATO", "QT_VOTOS_NOMINAIS"]
    with zipfile.ZipFile(out_dir / f"votacao_candidato_munzona_{ano}.zip", "w") as z:
        _write_csv(z, f"votacao_candidato_munzona_{ano}_BRASIL.csv", vot_h, vot_rows)
    esperado["validos"] = sorted(esperado["validos"])
    (out_dir / "esperado.json").write_text(json.dumps(esperado))
    return esperado
