"""CLI do ETL.  Ex.:
   python etl/run_etl.py --anos 2022 --download --cargos "DEPUTADO FEDERAL" "DEPUTADO ESTADUAL"
"""
import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ods.pipeline import run  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="ETL TSE -> PostgreSQL (Aiven)")
    ap.add_argument("--anos", nargs="+", type=int, required=True)
    ap.add_argument("--source-dir", default=str(ROOT / "data" / "raw"))
    ap.add_argument("--db-url", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--cargos", nargs="*", help="Filtra cargos (reduz tamanho p/ caber em 1 GB)")
    ap.add_argument("--ufs", nargs="*", help="Filtra UFs, ex.: BA SP MG")
    ap.add_argument("--download", action="store_true", help="Baixa os zips do TSE se ausentes")
    ap.add_argument("--reset", action="store_true", help="Recria as tabelas")
    a = ap.parse_args()
    if not a.db_url:
        ap.error("Informe --db-url ou a variável DATABASE_URL")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(a.anos, a.source_dir, a.db_url, a.cargos, a.ufs, a.reset, a.download)


if __name__ == "__main__":
    main()
