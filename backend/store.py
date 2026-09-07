"""Armazenamento operacional leve (SQLite) para a fila da Sprint 4.

O snapshot ``dataset_limpo.parquet`` continua sendo a fonte histórica auditada e
imutável. Este banco guarda somente o **estado operacional** gerado pelo uso da
ferramenta: lotes pontuados e ações registradas pelos analistas. Ele é
propositalmente separado do snapshot e pode ser apagado sem afetar os modelos.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

ACOES_VALIDAS = ("atribuido", "escalado", "resolvido", "dispensado")

_DEFAULT_DB = Path(__file__).resolve().parents[1] / "operacional.db"


def _db_path() -> Path:
    return Path(os.environ.get("VISIONOPS_DB", str(_DEFAULT_DB)))


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_ultimo_db_inicializado: str | None = None


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    _garantir_esquema()
    conexao = sqlite3.connect(_db_path(), check_same_thread=False)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA journal_mode=WAL")
    conexao.execute("PRAGMA foreign_keys=ON")
    try:
        yield conexao
        conexao.commit()
    finally:
        conexao.close()


def _garantir_esquema() -> None:
    """Cria as tabelas na primeira operação contra um caminho de banco novo."""
    global _ultimo_db_inicializado
    caminho = str(_db_path())
    if _ultimo_db_inicializado == caminho:
        return
    conexao = sqlite3.connect(caminho, check_same_thread=False)
    try:
        conexao.executescript(_ESQUEMA)
        conexao.commit()
    finally:
        conexao.close()
    _ultimo_db_inicializado = caminho


def inicializar() -> None:
    _garantir_esquema()


_ESQUEMA = """
            CREATE TABLE IF NOT EXISTS lote (
                id TEXT PRIMARY KEY,
                origem TEXT NOT NULL,
                referencia TEXT,
                total INTEGER NOT NULL,
                fila_alta INTEGER NOT NULL,
                violacoes_esperadas REAL NOT NULL,
                criado_em TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS acao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lote_id TEXT,
                ticket_ref TEXT NOT NULL,
                prioridade INTEGER,
                faixa TEXT,
                probabilidade REAL,
                acao TEXT NOT NULL,
                nota TEXT,
                perfil TEXT,
                criado_em TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_acao_ticket ON acao(ticket_ref);
            CREATE INDEX IF NOT EXISTS idx_acao_criado ON acao(criado_em);
            CREATE TABLE IF NOT EXISTS previsao_legado (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                criado_em TEXT NOT NULL,
                alvo TEXT NOT NULL,
                horizonte TEXT NOT NULL,
                modelo_vencedor TEXT NOT NULL,
                mae REAL,
                rmse REAL,
                r2 REAL,
                valor_previsto REAL
            );
            CREATE INDEX IF NOT EXISTS idx_previsao_criado ON previsao_legado(criado_em);
"""


def registrar_previsoes_legado(resultados: list[dict]) -> None:
    criado_em = _agora()
    with conectar() as conexao:
        conexao.executemany(
            """
            INSERT INTO previsao_legado
                (criado_em, alvo, horizonte, modelo_vencedor, mae, rmse, r2, valor_previsto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    criado_em,
                    r["alvo"],
                    r["horizonte"],
                    r["modelo"],
                    r.get("mae"),
                    r.get("rmse"),
                    r.get("r2"),
                    r.get("previsao"),
                )
                for r in resultados
            ],
        )


def historico_previsoes_legado(limite: int = 200) -> list[dict]:
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT id, criado_em, alvo, horizonte, modelo_vencedor, mae, rmse, r2, valor_previsto
            FROM previsao_legado ORDER BY id DESC LIMIT ?
            """,
            (int(limite),),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def registrar_lote(
    lote_id: str,
    origem: str,
    referencia: str | None,
    total: int,
    fila_alta: int,
    violacoes_esperadas: float,
) -> None:
    with conectar() as conexao:
        conexao.execute(
            """
            INSERT OR REPLACE INTO lote
                (id, origem, referencia, total, fila_alta, violacoes_esperadas, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (lote_id, origem, referencia, int(total), int(fila_alta), float(violacoes_esperadas), _agora()),
        )


def registrar_acao(
    ticket_ref: str,
    acao: str,
    *,
    lote_id: str | None = None,
    prioridade: int | None = None,
    faixa: str | None = None,
    probabilidade: float | None = None,
    nota: str | None = None,
    perfil: str | None = None,
) -> dict:
    if acao not in ACOES_VALIDAS:
        raise ValueError(f"Ação inválida: {acao!r}. Use uma de {ACOES_VALIDAS}.")
    ticket_ref = ticket_ref.strip()
    if not ticket_ref:
        raise ValueError("ticket_ref não pode ser vazio.")
    criado_em = _agora()
    with conectar() as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO acao
                (lote_id, ticket_ref, prioridade, faixa, probabilidade, acao, nota, perfil, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lote_id,
                ticket_ref,
                None if prioridade is None else int(prioridade),
                faixa,
                None if probabilidade is None else float(probabilidade),
                acao,
                (nota or "").strip() or None,
                perfil,
                criado_em,
            ),
        )
        registro_id = int(cursor.lastrowid)
    return {
        "id": registro_id,
        "ticketRef": ticket_ref,
        "acao": acao,
        "loteId": lote_id,
        "nota": (nota or "").strip() or None,
        "perfil": perfil,
        "criadoEm": criado_em,
    }


def acoes_recentes(limite: int = 40) -> list[dict]:
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT id, lote_id, ticket_ref, prioridade, faixa, probabilidade, acao, nota, perfil, criado_em
            FROM acao ORDER BY id DESC LIMIT ?
            """,
            (int(limite),),
        ).fetchall()
    return [
        {
            "id": linha["id"],
            "loteId": linha["lote_id"],
            "ticketRef": linha["ticket_ref"],
            "prioridade": linha["prioridade"],
            "faixa": linha["faixa"],
            "probabilidade": linha["probabilidade"],
            "acao": linha["acao"],
            "nota": linha["nota"],
            "perfil": linha["perfil"],
            "criadoEm": linha["criado_em"],
        }
        for linha in linhas
    ]


def estado_atual_por_ticket() -> dict[str, dict]:
    """Última ação registrada de cada chamado (a mais recente vence)."""
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT a.ticket_ref, a.acao, a.faixa, a.probabilidade, a.criado_em
            FROM acao a
            JOIN (SELECT ticket_ref, MAX(id) AS ultimo FROM acao GROUP BY ticket_ref) u
              ON u.ultimo = a.id
            """
        ).fetchall()
    return {
        linha["ticket_ref"]: {
            "acao": linha["acao"],
            "faixa": linha["faixa"],
            "probabilidade": linha["probabilidade"],
            "criadoEm": linha["criado_em"],
        }
        for linha in linhas
    }


def resumo_acoes() -> dict:
    estado = estado_atual_por_ticket()
    contagem = {acao: 0 for acao in ACOES_VALIDAS}
    risco_priorizado = 0.0
    for info in estado.values():
        contagem[info["acao"]] = contagem.get(info["acao"], 0) + 1
        if info["acao"] != "dispensado" and info["probabilidade"] is not None:
            risco_priorizado += float(info["probabilidade"])
    with conectar() as conexao:
        total_eventos = int(conexao.execute("SELECT COUNT(*) FROM acao").fetchone()[0])
        total_lotes = int(conexao.execute("SELECT COUNT(*) FROM lote").fetchone()[0])
    return {
        "ticketsComAcao": len(estado),
        "totalEventos": total_eventos,
        "totalLotes": total_lotes,
        "porAcao": contagem,
        "riscoPriorizado": round(risco_priorizado, 2),
    }


def historico_ticket(ticket_ref: str) -> list[dict]:
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT id, acao, nota, perfil, criado_em FROM acao
            WHERE ticket_ref = ? ORDER BY id DESC
            """,
            (ticket_ref.strip(),),
        ).fetchall()
    return [
        {
            "id": linha["id"],
            "acao": linha["acao"],
            "nota": linha["nota"],
            "perfil": linha["perfil"],
            "criadoEm": linha["criado_em"],
        }
        for linha in linhas
    ]
