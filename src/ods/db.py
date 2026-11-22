"""Acesso a banco: PostgreSQL (Aiven) em produção, SQLite para testes locais."""
import sqlite3

import pandas as pd


def _clean_sql(sql: str) -> list[str]:
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


class Db:
    def __init__(self, url: str):
        self.url = url
        if url.startswith("sqlite"):
            path = url.split("///", 1)[1] if "///" in url else ":memory:"
            self.kind = "sqlite"
            self._engine = None
            self.con = sqlite3.connect(path, check_same_thread=False)
        else:
            from sqlalchemy import create_engine

            for old in ("postgres://", "postgresql://"):
                if url.startswith(old):
                    url = "postgresql+psycopg2://" + url[len(old):]
            self.kind = "postgres"
            # O plano gratuito aceita no máximo 20 conexões e não tem pooler: pool mínimo.
            self._engine = create_engine(url, pool_size=2, max_overflow=0, pool_pre_ping=True)
            self.con = self._engine

    def execute(self, sql: str) -> None:
        if self.kind == "sqlite":
            self.con.execute(sql)
            self.con.commit()
        else:
            with self._engine.begin() as c:
                c.exec_driver_sql(sql)

    def run_script(self, sql: str) -> None:
        for stmt in _clean_sql(sql):
            self.execute(stmt)

    def read_sql(self, sql: str) -> pd.DataFrame:
        return pd.read_sql_query(sql, self.con)

    def write(self, df: pd.DataFrame, table: str) -> int:
        if df.empty:
            return 0
        kwargs = {} if self.kind == "sqlite" else {"method": "multi", "chunksize": 2000}
        df.to_sql(table, self.con, if_exists="append", index=False, **kwargs)
        return len(df)

    def close(self) -> None:
        if self.kind == "sqlite":
            self.con.close()
        else:
            self._engine.dispose()
