from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from model_pipeline import executar_pipeline
from risk_pipeline import executar_pipeline_risco

from backend import datasource, legacy_forecast, monitoring, optimization, segmentation, store
from backend.telemetry import configurar_telemetria


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset_limpo.parquet"
FRONTEND_DIST = ROOT / "frontend" / "dist"

CAMPOS_FILA = ["id", "prioridade", "produto", "categoria", "grupo", "dataHora"]

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

configurar_telemetria(app)


@app.on_event("startup")
def _preparar_estado() -> None:
    store.inicializar()


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
    """Incidentes tratados. Origem controlada por ``VISIONOPS_DATASOURCE`` (parquet | mysql)."""
    return datasource.carregar()


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


# ---------------------------------------------------------------------------
# Fila operacional em lote (Sprint 4)
# ---------------------------------------------------------------------------

class ItemFila(BaseModel):
    id: str | None = None
    prioridade: int = Field(default=3, ge=1, le=5)
    produto: str = "Não informado"
    categoria: str = "Não informado"
    grupo: str = "Não informado"
    dataHora: datetime | None = None


class LoteFilaRequest(BaseModel):
    itens: list[ItemFila]
    referencia: str | None = None
    persistir: bool = False


class AcaoRequest(BaseModel):
    ticketRef: str
    acao: Literal["atribuido", "escalado", "resolvido", "dispensado"]
    loteId: str | None = None
    prioridade: int | None = None
    faixa: str | None = None
    probabilidade: float | None = None
    nota: str | None = None
    perfil: str | None = None


def _tabelas_taxa(eligible: pd.DataFrame) -> dict[str, dict[str, tuple[int, float]]]:
    tabelas: dict[str, dict[str, tuple[int, float]]] = {}
    for chave, coluna in [
        ("Prioridade", "Prioridade_Cod"),
        ("Produto", "Produto"),
        ("Categoria", "Categoria"),
        ("Grupo", "Grupo designado"),
    ]:
        valores = eligible[coluna].map(_clean_label) if coluna != "Prioridade_Cod" else eligible[coluna].astype(str)
        agrupado = eligible.assign(_v=valores).groupby("_v")["OLA_Violado_KPI_Regra"]
        tabelas[chave] = {str(k): (int(v.size), float(v.mean())) for k, v in agrupado}
    return tabelas


def _janela_modelo(momento: pd.Timestamp) -> str:
    if momento >= pd.Timestamp("2025-12-01"):
        return "holdout — dezembro/2025, não visto no treino do modelo de risco"
    if momento >= pd.Timestamp("2025-10-01"):
        return "validação — out/nov 2025, usada para calibrar o modelo"
    return "treino — anterior a out/2025"


def _entradas_frame(itens: list[ItemFila]) -> pd.DataFrame:
    registros = []
    for posicao, item in enumerate(itens):
        registros.append(
            {
                "id": (item.id or f"linha-{posicao + 1}").strip(),
                "prioridade": item.prioridade,
                "produto": _clean_label(item.produto),
                "categoria": _clean_label(item.categoria),
                "grupo": _clean_label(item.grupo),
                "data_hora": item.dataHora or pd.Timestamp("2026-01-01T09:00:00"),
            }
        )
    return pd.DataFrame(registros)


def _pontuar_fila(entradas: pd.DataFrame) -> tuple[list[dict], dict]:
    modelo = risk_model()
    eligible = load_data()
    eligible = eligible[eligible["Elegivel_KPI_Regra"]]
    tabelas = _tabelas_taxa(eligible)

    pontuado = modelo.pontuar_lote(entradas)
    combinado = entradas.reset_index(drop=True).join(pontuado.reset_index(drop=True))
    combinado = combinado.sort_values("probabilidade", ascending=False).reset_index(drop=True)

    fila: list[dict] = []
    for linha in combinado.itertuples():
        momento = pd.Timestamp(linha.data_hora)
        fatores = []
        for chave, valor in [
            ("Prioridade", str(int(linha.prioridade))),
            ("Produto", linha.produto),
            ("Categoria", linha.categoria),
            ("Grupo", linha.grupo),
        ]:
            amostra, taxa = tabelas.get(chave, {}).get(valor, (0, None))
            fatores.append(
                {
                    "fator": chave,
                    "valor": valor,
                    "contribuicao": round(float(getattr(linha, f"contribuicao_{chave}")), 4),
                    "taxaHistorica": None if taxa is None else round(taxa, 4),
                    "amostra": amostra,
                }
            )
        fatores.sort(key=lambda item: abs(item["contribuicao"]), reverse=True)
        fila.append(
            {
                "id": linha.id,
                "prioridade": int(linha.prioridade),
                "produto": linha.produto,
                "categoria": linha.categoria,
                "grupo": linha.grupo,
                "aberto": momento.isoformat(),
                "probabilidade": round(float(linha.probabilidade), 4),
                "faixa": linha.faixa,
                "fatores": fatores,
            }
        )

    probabilidades = combinado["probabilidade"].to_numpy()
    total = len(fila)
    corte_top = max(1, int(np.ceil(total * 0.2)))
    resumo = {
        "total": total,
        "filaAlta": int((combinado["faixa"] == "Alto").sum()),
        "filaModerada": int((combinado["faixa"] == "Moderado").sum()),
        "violacoesEsperadas": round(float(probabilidades.sum()), 1),
        "corteFilaAlta": round(float(modelo.limiar_alto), 4),
        "capturaTop20Pct": (
            round(float(probabilidades[:corte_top].sum() / probabilidades.sum()), 3)
            if probabilidades.sum() > 0
            else 0.0
        ),
    }
    return fila, resumo


@app.get("/api/queue/template", response_class=PlainTextResponse)
def queue_template() -> str:
    df = load_data()
    produto = next((v for v in df["Produto"].dropna().astype(str).unique() if v), "lemn")
    categoria = next((v for v in df["Categoria"].dropna().astype(str).unique() if v), "cat45")
    grupos = sorted(df["Grupo designado"].dropna().astype(str).unique())[:2] or ["Team05", "Team11"]
    linhas = [
        ",".join(CAMPOS_FILA),
        f"INC-EXEMPLO-1,3,{produto},{categoria},{grupos[0]},2026-01-05T09:30:00",
        f"INC-EXEMPLO-2,2,Não informado,Não informado,{grupos[-1]},2026-01-05T14:00:00",
    ]
    return "\n".join(linhas) + "\n"


@app.get("/api/queue/sample")
def queue_sample(
    data: str | None = None,
    dias: int = Query(default=1, ge=1, le=14),
) -> dict:
    df = load_data()
    eligible = df[df["Elegivel_KPI_Regra"]].copy()
    if eligible.empty:
        raise HTTPException(status_code=404, detail="Sem incidentes elegíveis no snapshot.")
    ultimo_dia = eligible["Aberto"].max().normalize()
    try:
        inicio = pd.Timestamp(data).normalize() if data else ultimo_dia
    except ValueError:
        raise HTTPException(status_code=422, detail="Data inválida (use AAAA-MM-DD).")
    fim = inicio + timedelta(days=dias)
    recorte = eligible[(eligible["Aberto"] >= inicio) & (eligible["Aberto"] < fim)].copy()
    if recorte.empty:
        raise HTTPException(status_code=404, detail="Nenhum incidente elegível nessa janela do snapshot.")

    itens = [
        ItemFila(
            id=str(numero),
            prioridade=int(prioridade),
            produto=_clean_label(produto),
            categoria=_clean_label(categoria),
            grupo=_clean_label(grupo),
            dataHora=pd.Timestamp(aberto).to_pydatetime(),
        )
        for numero, prioridade, produto, categoria, grupo, aberto in zip(
            recorte["Número"], recorte["Prioridade_Cod"], recorte["Produto"],
            recorte["Categoria"], recorte["Grupo designado"], recorte["Aberto"],
        )
    ]
    fila, resumo = _pontuar_fila(_entradas_frame(itens))

    violou = dict(zip(recorte["Número"].astype(str), recorte["OLA_Violado_KPI_Regra"].astype(bool)))
    violacoes_reais = int(sum(violou.values()))
    corte_top = max(1, int(np.ceil(len(fila) * 0.2)))
    capturadas_top = sum(1 for item in fila[:corte_top] if violou.get(item["id"], False))
    for item in fila:
        item["violouReal"] = bool(violou.get(item["id"], False))

    return {
        "origem": "snapshot",
        "referencia": f"{inicio:%Y-%m-%d} (+{dias}d)" if dias > 1 else f"{inicio:%Y-%m-%d}",
        "janelaModelo": _janela_modelo(inicio),
        "resumo": {
            **resumo,
            "violacoesReais": violacoes_reais,
            "violacoesReaisNoTop20": capturadas_top,
        },
        "fila": fila,
    }


@app.post("/api/queue/score")
def queue_score(payload: LoteFilaRequest) -> dict:
    if not payload.itens:
        raise HTTPException(status_code=422, detail="Envie ao menos um chamado.")
    if len(payload.itens) > 5000:
        raise HTTPException(status_code=422, detail="Limite de 5000 chamados por lote.")
    fila, resumo = _pontuar_fila(_entradas_frame(payload.itens))

    lote_id = None
    if payload.persistir:
        lote_id = f"lote-{datetime.now(timezone.utc):%Y%m%d%H%M%S}"
        store.registrar_lote(
            lote_id, "csv", payload.referencia, resumo["total"],
            resumo["filaAlta"], resumo["violacoesEsperadas"],
        )
    return {"origem": "csv", "loteId": lote_id, "referencia": payload.referencia, "resumo": resumo, "fila": fila}


@app.post("/api/actions")
def registrar_acao(payload: AcaoRequest) -> dict:
    try:
        return store.registrar_acao(
            payload.ticketRef,
            payload.acao,
            lote_id=payload.loteId,
            prioridade=payload.prioridade,
            faixa=payload.faixa,
            probabilidade=payload.probabilidade,
            nota=payload.nota,
            perfil=payload.perfil,
        )
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro))


@app.get("/api/actions/summary")
def acoes_resumo() -> dict:
    return store.resumo_acoes()


@app.get("/api/actions/recent")
def acoes_recentes(limit: int = Query(default=40, ge=1, le=200)) -> dict:
    return {"itens": store.acoes_recentes(limit)}


# ---------------------------------------------------------------------------
# Monitor de deriva, status do modelo, otimização e segmentação (Sprint 4)
# ---------------------------------------------------------------------------

@app.get("/api/drift")
def drift() -> dict:
    return monitoring.analisar_deriva(load_data())


@app.get("/api/model-status")
def model_status() -> dict:
    df = load_data()
    risco = risk_model()
    volume = volume_model()
    deriva = monitoring.analisar_deriva(df)
    snapshot = df["Aberto"].max()
    dias_desde = int((pd.Timestamp.now() - snapshot).days)
    metricas_op = volume.metricas_operacionais.set_index("horizonte")

    motivos = []
    if deriva["revalidacaoRecomendada"]:
        motivos.append(f"PSI de deriva em {deriva['piorPsi']} (limite 0,20).")
    if dias_desde > 45:
        motivos.append(f"Snapshot com {dias_desde} dias — acima do ciclo de 45 dias.")

    return {
        "snapshot": snapshot.date().isoformat(),
        "diasDesdeSnapshot": dias_desde,
        "cicloRetreinoDias": 45,
        "origemDados": datasource.origem(),
        "risco": {
            "treino": "incidentes elegíveis anteriores a 01/10/2025",
            "validacao": "outubro e novembro de 2025",
            "holdout": f"{risco.inicio_holdout:%d/%m/%Y} a {risco.fim_holdout:%d/%m/%Y}",
            "rocAuc": round(float(risco.metricas_holdout["ROC_AUC"]), 3),
            "prAuc": round(float(risco.metricas_holdout["PR_AUC"]), 3),
        },
        "volume": {
            "holdout": "01–31/12/2025",
            "maeD1": round(float(metricas_op.loc["D+1", "holdout_MAE"]), 1),
            "maeD7": round(float(metricas_op.loc["D+7", "holdout_MAE"]), 1),
        },
        "deriva": {
            "piorPsi": deriva["piorPsi"],
            "volumeRazao": deriva["volumeMedioDia"]["razao"],
            "revalidacaoRecomendada": deriva["revalidacaoRecomendada"],
        },
        "revalidacaoRecomendada": bool(deriva["revalidacaoRecomendada"] or dias_desde > 45),
        "motivos": motivos,
    }


@app.get("/api/optimization")
def optimization_endpoint(
    capacidade: float = Query(default=5, ge=1, le=60),
    limitePorCategoria: int = Query(default=2, ge=1, le=12),
) -> dict:
    df = load_data()
    previsao = volume_model().previsoes["D+1"]["ponto"]
    try:
        return optimization.otimizar_alocacao(
            df, previsao, capacidade=capacidade, limite_por_categoria=limitePorCategoria
        )
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro))


@app.get("/api/segmentation")
def segmentation_endpoint(
    dimension: Literal["Produto", "Categoria", "Grupo designado"] = "Produto",
) -> dict:
    try:
        return segmentation.segmentar(load_data(), dimension)
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro))


# ---------------------------------------------------------------------------
# Contrato legado da Sprint 3 (endpoints usados no vídeo pitch e nas evidências)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _previsao_legado_cache(chave: str) -> list[dict]:
    return legacy_forecast.gerar_previsoes(load_data())


@app.get("/health")
def health_legado() -> dict:
    return {"status": "ok", "servico": "aiops-sla-monitor"}


@app.get("/incidentes/total")
def incidentes_total() -> dict:
    return {"total_incidentes_no_banco": int(len(load_data()))}


@app.get("/previsao")
def previsao_legado() -> list[dict]:
    df = load_data()
    resultados = _previsao_legado_cache(str(df["Aberto"].max()))
    store.registrar_previsoes_legado(resultados)
    return resultados


@app.get("/previsao/historico")
def previsao_historico_legado(limit: int = Query(default=200, ge=1, le=500)) -> list[dict]:
    return store.historico_previsoes_legado(limit)


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

