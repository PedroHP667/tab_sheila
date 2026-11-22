-- Esquema portátil (PostgreSQL / SQLite). Sem ponto e vírgula dentro de comentários.

CREATE TABLE IF NOT EXISTS candidato (
    ano                  SMALLINT      NOT NULL,
    sq_candidato         VARCHAR(20)   NOT NULL,
    cargo                VARCHAR(60)   NOT NULL,
    uf                   VARCHAR(2)    NOT NULL,
    partido              VARCHAR(20),
    genero               VARCHAR(20)   NOT NULL,
    cor_raca             VARCHAR(30)   NOT NULL,
    grupo_raca           VARCHAR(20)   NOT NULL,
    perfil               VARCHAR(50)   NOT NULL,
    situacao_candidatura VARCHAR(40),
    situacao_turno       VARCHAR(40),
    eleito               BOOLEAN       NOT NULL,
    votos                BIGINT        NOT NULL DEFAULT 0,
    PRIMARY KEY (ano, sq_candidato)
);

CREATE TABLE IF NOT EXISTS receita_candidato (
    ano           SMALLINT      NOT NULL,
    sq_candidato  VARCHAR(20)   NOT NULL,
    categoria     VARCHAR(30)   NOT NULL,
    valor         NUMERIC(16,2) NOT NULL,
    PRIMARY KEY (ano, sq_candidato, categoria)
);

CREATE TABLE IF NOT EXISTS etl_execucao (
    executado_em    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ano             SMALLINT,
    tabela          VARCHAR(40),
    linhas_lidas    BIGINT,
    linhas_gravadas BIGINT,
    observacao      TEXT
);

CREATE INDEX IF NOT EXISTS idx_candidato_filtros ON candidato (ano, cargo, uf);
CREATE INDEX IF NOT EXISTS idx_candidato_perfil ON candidato (ano, perfil);

DROP VIEW IF EXISTS vw_candidato_receita;

CREATE VIEW vw_candidato_receita AS
SELECT
    c.ano, c.sq_candidato, c.cargo, c.uf, c.partido, c.genero, c.cor_raca,
    c.grupo_raca, c.perfil, c.situacao_turno, c.eleito, c.votos,
    COALESCE(SUM(r.valor), 0)                                                     AS receita_total,
    COALESCE(SUM(CASE WHEN r.categoria = 'FEFC' THEN r.valor END), 0)             AS receita_fefc,
    COALESCE(SUM(CASE WHEN r.categoria = 'FUNDO_PARTIDARIO' THEN r.valor END), 0) AS receita_fundo_partidario,
    COALESCE(SUM(CASE WHEN r.categoria = 'DOACAO_PF' THEN r.valor END), 0)        AS receita_doacao_pf,
    COALESCE(SUM(CASE WHEN r.categoria = 'PROPRIOS' THEN r.valor END), 0)         AS receita_proprios,
    COALESCE(SUM(CASE WHEN r.categoria = 'PARTIDO_OUTROS' THEN r.valor END), 0)   AS receita_partido_outros,
    COALESCE(SUM(CASE WHEN r.categoria = 'OUTROS' THEN r.valor END), 0)           AS receita_outros
FROM candidato c
LEFT JOIN receita_candidato r ON r.ano = c.ano AND r.sq_candidato = c.sq_candidato
GROUP BY c.ano, c.sq_candidato, c.cargo, c.uf, c.partido, c.genero, c.cor_raca,
         c.grupo_raca, c.perfil, c.situacao_turno, c.eleito, c.votos;
