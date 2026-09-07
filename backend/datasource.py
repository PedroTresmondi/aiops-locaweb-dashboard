"""Fonte de dados dos incidentes: snapshot Parquet (padrão) ou Azure MySQL.

O snapshot ``dataset_limpo.parquet`` é a fonte auditada e o modo padrão — todo o
resto do app e os testes dependem dele. Quando ``VISIONOPS_DATASOURCE=mysql`` está
no ambiente (caso do Azure Container Instance), os incidentes são lidos do Azure
Database for MySQL Flexible Server, autenticado sem senha via Managed Identity
(mesmo padrão da aplicação Cloud da Sprint 3). As colunas são normalizadas para o
mesmo formato do Parquet, então nada mais no código precisa saber a origem.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset_limpo.parquet"

_LIMITES_OLA = {1: 4, 2: 4, 3: 12, 4: 24, 5: 96}


def origem() -> str:
    return os.environ.get("VISIONOPS_DATASOURCE", "parquet").strip().lower()


def _garantir_regras(df: pd.DataFrame) -> pd.DataFrame:
    status = df["Status"].astype("string")
    if "OLA_Violado_Regra" not in df:
        limites = df["Prioridade_Cod"].map(_LIMITES_OLA)
        df["OLA_Violado_Regra"] = df["Duracao_Horas"].gt(limites)
    if "Elegivel_KPI_Regra" not in df:
        sem_pai = df["Incidente Pai"].isna() | df["Incidente Pai"].astype(str).str.strip().eq("")
        com_intervencao = ~status.str.upper().str.startswith("SEM INTERVEN", na=False)
        df["Elegivel_KPI_Regra"] = df["Prioridade_Cod"].isin([1, 2, 3]) & sem_pai & com_intervencao
    if "OLA_Violado_KPI_Regra" not in df:
        df["OLA_Violado_KPI_Regra"] = df["OLA_Violado_Regra"] & df["Elegivel_KPI_Regra"]
    for coluna in ["OLA_Violado_Regra", "Elegivel_KPI_Regra", "OLA_Violado_KPI_Regra"]:
        df[coluna] = df[coluna].astype(bool)
    return df


def _carregar_parquet() -> pd.DataFrame:
    df = pd.read_parquet(DATASET)
    df["Aberto"] = pd.to_datetime(df["Aberto"])
    if "Resolvido" in df:
        df["Resolvido"] = pd.to_datetime(df["Resolvido"], errors="coerce")
    numero = next((c for c in df.columns if c.endswith("mero")), None)
    if numero and numero != "Número":
        df = df.rename(columns={numero: "Número"})
    return _garantir_regras(df)


def _carregar_mysql() -> pd.DataFrame:
    """Lê a tabela `incidentes` do Azure MySQL e normaliza para o formato do Parquet."""
    import pymysql
    from azure.identity import DefaultAzureCredential

    host = os.environ["MYSQL_HOST"]
    usuario = os.environ["MYSQL_USER"]
    database = os.environ.get("MYSQL_DATABASE", "aiopsdb")
    escopo = "https://ossrdbms-aad.database.windows.net/.default"
    token = DefaultAzureCredential().get_token(escopo).token

    conexao = pymysql.connect(
        host=host, user=usuario, password=token, database=database,
        ssl={"ssl": {}}, connect_timeout=15, cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        bruto = pd.read_sql(
            """
            SELECT numero, prioridade_num, produto_limpo, categoria_limpa, subcategoria,
                   grupo_designado, aberto, resolvido, encerrado, duracao_horas, status,
                   incidente_pai, entra_kpi_calculado, ola_violado_calculado
            FROM incidentes
            """,
            conexao,
        )
    finally:
        conexao.close()

    df = pd.DataFrame(
        {
            "Número": bruto["numero"].astype("string"),
            "Prioridade_Cod": pd.to_numeric(bruto["prioridade_num"], errors="coerce").round().astype("Int64"),
            "Produto": bruto["produto_limpo"],
            "Categoria": bruto["categoria_limpa"],
            "Subcategoria": bruto.get("subcategoria"),
            "Grupo designado": bruto["grupo_designado"],
            "Aberto": pd.to_datetime(bruto["aberto"], errors="coerce"),
            "Resolvido": pd.to_datetime(bruto["resolvido"], errors="coerce"),
            "Duracao_Horas": pd.to_numeric(bruto["duracao_horas"], errors="coerce"),
            "Status": bruto["status"].astype("string"),
            "Incidente Pai": bruto["incidente_pai"],
        }
    )
    df["OLA_Violado_Regra"] = pd.to_numeric(bruto["ola_violado_calculado"], errors="coerce").fillna(0).astype(bool)
    df["Elegivel_KPI_Regra"] = pd.to_numeric(bruto["entra_kpi_calculado"], errors="coerce").fillna(0).astype(bool)
    df["OLA_Violado_KPI_Regra"] = df["OLA_Violado_Regra"] & df["Elegivel_KPI_Regra"]
    df["Prioridade_Cod"] = df["Prioridade_Cod"].fillna(3).astype(int)
    return df


def carregar() -> pd.DataFrame:
    if origem() == "mysql":
        return _carregar_mysql()
    return _carregar_parquet()
