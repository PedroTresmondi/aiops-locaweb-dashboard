from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from model_pipeline import executar_pipeline
from risk_pipeline import executar_pipeline_risco


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset_limpo.parquet"
FRONTEND_DIST = ROOT / "frontend" / "dist"

app = FastAPI(
    title="VisionOps AI API",
    version="1.0.0",
    description="API operacional para previsão de demanda e risco de violação de OLA.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TriageRequest(BaseModel):
    prioridade: int = Field(ge=1, le=5)
    produto: str
    categoria: str
    grupo: str
    data_hora: datetime


class CapacityRequest(BaseModel):
    produtividade: float = Field(default=25, gt=0, le=200)
    ocupacao: float = Field(default=0.80, gt=0.1, le=1)
    indisponibilidade: float = Field(default=0.10, ge=0, lt=0.9)
    analistas_atuais: int = Field(default=40, ge=0, le=10000)
    horizonte: Literal["D+1", "D+7"] = "D+1"


def _clean_label(value: object) -> str:
    if value is None or pd.isna(value):
        return "Não informado"
    text = str(value).strip()
    return text if text else "Não informado"


@lru_cache(maxsize=1)
def load_data() -> pd.DataFrame:
    df = pd.read_parquet(DATASET)
    df["Aberto"] = pd.to_datetime(df["Aberto"])
    if "Resolvido" in df:
        df["Resolvido"] = pd.to_datetime(df["Resolvido"], errors="coerce")
    numero = next((c for c in df.columns if c.endswith("mero")), None)
    if numero and numero != "Número":
        df = df.rename(columns={numero: "Número"})
    status = df["Status"].astype("string")
    if "OLA_Violado_Regra" not in df:
        limites = df["Prioridade_Cod"].map({1: 4, 2: 4, 3: 12, 4: 24, 5: 96})
        df["OLA_Violado_Regra"] = df["Duracao_Horas"].gt(limites)
    if "Elegivel_KPI_Regra" not in df:
        sem_pai = df["Incidente Pai"].isna() | df["Incidente Pai"].astype(str).str.strip().eq("")
        com_intervencao = ~status.str.upper().str.startswith("SEM INTERVEN", na=False)
        df["Elegivel_KPI_Regra"] = df["Prioridade_Cod"].isin([1, 2, 3]) & sem_pai & com_intervencao
    if "OLA_Violado_KPI_Regra" not in df:
        df["OLA_Violado_KPI_Regra"] = df["OLA_Violado_Regra"] & df["Elegivel_KPI_Regra"]
    for column in ["OLA_Violado_Regra", "Elegivel_KPI_Regra", "OLA_Violado_KPI_Regra"]:
        df[column] = df[column].astype(bool)
    return df


@lru_cache(maxsize=1)
def volume_model():
    return executar_pipeline(load_data())


@lru_cache(maxsize=1)
def risk_model():
    return executar_pipeline_risco(load_data())


def _forecast_payload(horizon: str) -> dict:
    forecast = volume_model().previsoes[horizon]
    return {
        "horizonte": horizon,
        "dataAlvo": pd.Timestamp(forecast["data_alvo"]).date().isoformat(),
        "ponto": round(float(forecast["ponto"])),
        "inferior": round(float(forecast["limite_inferior_80"])),
        "superior": round(float(forecast["limite_superior_80"])),
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "dataset": DATASET.name}


@app.get("/api/overview")
def overview() -> dict:
    df = load_data()
    model = volume_model()
    risk = risk_model()
    eligible = df[df["Elegivel_KPI_Regra"]]
    total_violations = int(eligible["OLA_Violado_KPI_Regra"].sum())
    ola_rate = float(eligible["OLA_Violado_KPI_Regra"].mean())

    daily = (
        df.assign(data=df["Aberto"].dt.normalize())
        .groupby("data")
        .size()
        .tail(120)
        .rename("incidentes")
        .reset_index()
    )
    monthly = (
        df.assign(mes=df["Aberto"].dt.to_period("M").dt.to_timestamp())
        .groupby("mes")
        .agg(
            incidentes=("Aberto", "size"),
            elegiveis=("Elegivel_KPI_Regra", "sum"),
            violacoes=("OLA_Violado_KPI_Regra", "sum"),
        )
        .tail(12)
        .reset_index()
    )
    monthly["taxaOla"] = monthly["violacoes"] / monthly["elegiveis"].replace(0, np.nan)

    return {
        "snapshot": {
            "inicio": df["Aberto"].min().date().isoformat(),
            "fim": df["Aberto"].max().date().isoformat(),
            "incidentes": int(len(df)),
            "elegiveis": int(len(eligible)),
            "violacoes": total_violations,
            "taxaOla": ola_rate,
        },
        "forecast": [_forecast_payload("D+1"), _forecast_payload("D+7")],
        "risk": {
            "rocAuc": risk.metricas_holdout["ROC_AUC"],
            "prAuc": risk.metricas_holdout["PR_AUC"],
            "captura": risk.metricas_holdout["captura_violacoes"],
            "filaAlta": risk.metricas_holdout["taxa_revisada"],
            "lift": risk.metricas_holdout["lift_fila_alta"],
        },
        "daily": [
            {"data": row.data.date().isoformat(), "incidentes": int(row.incidentes)}
            for row in daily.itertuples()
        ],
        "monthly": [
            {
                "mes": row.mes.date().isoformat(),
                "incidentes": int(row.incidentes),
                "elegiveis": int(row.elegiveis),
                "violacoes": int(row.violacoes),
                "taxaOla": None if pd.isna(row.taxaOla) else float(row.taxaOla),
            }
            for row in monthly.itertuples()
        ],
        "validation": {
            row.horizonte: {
                "mae": float(row.holdout_MAE),
                "wape": float(row.holdout_WAPE),
                "ganho": float(row.ganho_mae),
            }
            for row in model.metricas_operacionais.itertuples()
        },
    }


@app.get("/api/options")
def options() -> dict:
    df = load_data()
    def values(column: str) -> list[str]:
        return sorted({_clean_label(value) for value in df[column].unique()})
    return {
        "produtos": values("Produto"),
        "categorias": values("Categoria"),
        "grupos": values("Grupo designado"),
        "ultimaData": df["Aberto"].max().date().isoformat(),
    }


@app.post("/api/triage")
def triage(payload: TriageRequest) -> dict:
    result = risk_model().prever(
        payload.prioridade,
        _clean_label(payload.produto),
        _clean_label(payload.categoria),
        _clean_label(payload.grupo),
        payload.data_hora,
    )
    probability = float(result["probabilidade"])
    base = risk_model().metricas_holdout["prevalencia"]
    historical = load_data()
    eligible = historical[historical["Elegivel_KPI_Regra"]].copy()
    masks = {
        "Prioridade": eligible["Prioridade_Cod"].eq(payload.prioridade),
        "Produto": eligible["Produto"].fillna("Não informado").astype(str).eq(_clean_label(payload.produto)),
        "Categoria": eligible["Categoria"].fillna("Não informado").astype(str).eq(_clean_label(payload.categoria)),
        "Grupo": eligible["Grupo designado"].fillna("Não informado").astype(str).eq(_clean_label(payload.grupo)),
    }
    evidence = []
    for label, mask in masks.items():
        cohort = eligible[mask]
        evidence.append(
            {
                "fator": label,
                "amostra": int(len(cohort)),
                "taxa": float(cohort["OLA_Violado_KPI_Regra"].mean()) if len(cohort) else None,
            }
        )
    if result["faixa"] == "Alto":
        action = "Priorizar na fila, confirmar responsável e iniciar acompanhamento preventivo do OLA."
    elif result["faixa"] == "Moderado":
        action = "Validar contexto e capacidade da equipe antes de manter na fila padrão."
    else:
        action = "Manter fluxo padrão e monitorar alterações de prioridade ou responsável."
    return {
        "probabilidade": probability,
        "faixa": result["faixa"],
        "limiarMedio": result["limiar_medio"],
        "limiarAlto": result["limiar_alto"],
        "taxaBase": base,
        "multiplicadorBase": probability / max(base, 1e-9),
        "acao": action,
        "evidencias": evidence,
    }


@app.get("/api/diagnostics")
def diagnostics(
    dimension: Literal["Categoria", "Produto", "Grupo designado"] = "Categoria",
    min_sample: int = Query(default=30, ge=5, le=10000),
    limit: int = Query(default=12, ge=3, le=50),
) -> dict:
    df = load_data()
    eligible = df[df["Elegivel_KPI_Regra"]].copy()
    eligible["entidade"] = eligible[dimension].map(_clean_label)
    ranking = (
        eligible.groupby("entidade")
        .agg(elegiveis=("Aberto", "size"), violacoes=("OLA_Violado_KPI_Regra", "sum"))
        .reset_index()
    )
    ranking = ranking[ranking["elegiveis"] >= min_sample].copy()
    ranking["taxa"] = ranking["violacoes"] / ranking["elegiveis"]
    ranking["participacao"] = ranking["violacoes"] / max(int(ranking["violacoes"].sum()), 1)
    ranking = ranking.sort_values(["violacoes", "taxa"], ascending=False).head(limit)
    return {
        "dimensao": dimension,
        "taxaGeral": float(eligible["OLA_Violado_KPI_Regra"].mean()),
        "items": [
            {
                "nome": str(row.entidade),
                "elegiveis": int(row.elegiveis),
                "violacoes": int(row.violacoes),
                "taxa": float(row.taxa),
                "participacao": float(row.participacao),
            }
            for row in ranking.itertuples()
        ],
    }


@app.post("/api/capacity")
def capacity(payload: CapacityRequest) -> dict:
    forecast = volume_model().previsoes[payload.horizonte]
    effective_capacity = payload.produtividade * payload.ocupacao * (1 - payload.indisponibilidade)
    if effective_capacity <= 0:
        raise HTTPException(status_code=422, detail="Capacidade efetiva inválida")
    scenarios = []
    for name, key in [
        ("Faixa inferior", "limite_inferior_80"),
        ("Previsão", "ponto"),
        ("Faixa superior", "limite_superior_80"),
    ]:
        demand = float(forecast[key])
        required = int(np.ceil(demand / effective_capacity))
        scenarios.append(
            {
                "cenario": name,
                "demanda": round(demand),
                "necessarios": required,
                "gap": required - payload.analistas_atuais,
            }
        )
    point = scenarios[1]
    if point["gap"] > 0:
        action = f"Acionar contingência para {point['gap']} analista(s) equivalente(s) no cenário central."
    else:
        action = f"Capacidade central coberta, com reserva de {abs(point['gap'])} analista(s) equivalente(s)."
    return {
        "horizonte": payload.horizonte,
        "capacidadeEfetiva": effective_capacity,
        "cenarios": scenarios,
        "acao": action,
        "nota": "A produtividade é uma premissa operacional ajustável; a demanda vem do modelo validado.",
    }


@app.get("/api/models")
def models() -> dict:
    volume = volume_model()
    risk = risk_model()
    return {
        "volume": [
            {
                "horizonte": row.horizonte,
                "modelo": row.modelo,
                "mae": float(row.holdout_MAE),
                "rmse": float(row.holdout_RMSE),
                "r2": float(row.holdout_R2),
                "wape": float(row.holdout_WAPE),
                "ganho": float(row.ganho_mae),
            }
            for row in volume.metricas_operacionais.itertuples()
        ],
        "risk": {
            "rocAuc": risk.metricas_holdout["ROC_AUC"],
            "prAuc": risk.metricas_holdout["PR_AUC"],
            "brier": risk.metricas_holdout["Brier"],
            "prevalencia": risk.metricas_holdout["prevalencia"],
            "filaAlta": risk.metricas_holdout["taxa_revisada"],
            "precisaoFila": risk.metricas_holdout["precisao_fila_alta"],
            "captura": risk.metricas_holdout["captura_violacoes"],
            "lift": risk.metricas_holdout["lift_fila_alta"],
            "amostra": risk.metricas_holdout["n_holdout"],
            "violacoes": risk.metricas_holdout["n_violacoes_holdout"],
        },
        "importance": [
            {"variavel": row.variavel, "valor": float(row.queda_pr_auc)}
            for row in risk.importancias.itertuples()
        ],
        "calibration": [
            {
                "decil": int(row.decil),
                "previsto": float(row.risco_previsto),
                "observado": float(row.taxa_observada),
                "incidentes": int(row.incidentes),
            }
            for row in risk.calibracao.itertuples()
        ],
    }


@app.get("/api/audit")
def audit(limit: int = Query(default=100, ge=10, le=500)) -> dict:
    df = load_data()
    missing = [
        {"campo": column, "faltantes": int(df[column].isna().sum()), "taxa": float(df[column].isna().mean())}
        for column in ["Produto", "Categoria", "Grupo designado", "Resolvido"]
        if column in df
    ]
    sample_columns = [
        column for column in ["Número", "Aberto", "Prioridade_Cod", "Produto", "Categoria", "Grupo designado", "Status", "Elegivel_KPI_Regra", "OLA_Violado_KPI_Regra"]
        if column in df
    ]
    sample = df.sort_values("Aberto", ascending=False)[sample_columns].head(limit).copy()
    sample["Aberto"] = sample["Aberto"].dt.strftime("%Y-%m-%d %H:%M")
    sample = sample.where(pd.notna(sample), None)
    return {"missing": missing, "sample": sample.to_dict(orient="records")}


if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        candidate = (FRONTEND_DIST / path).resolve()
        if candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

