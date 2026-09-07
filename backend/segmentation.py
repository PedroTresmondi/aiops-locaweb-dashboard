"""Segmentação de criticidade operacional por K-Means.

Porta a Seção 17 do notebook de Machine Learning da Sprint 3 para dentro da API,
recalculada sobre o mesmo snapshot que o resto do app usa. Método idêntico ao do
notebook: agrega produto/categoria/grupo, deriva a taxa de violação, aplica log1p
nas variáveis de contagem/duração (reduz o efeito de outliers de escala sobre o
centróide), padroniza e escolhe K pelo maior Coeficiente de Silhueta entre 2 e 6.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

DIMENSOES = {"Produto": "produto", "Categoria": "categoria", "Grupo designado": "grupo"}
_FEATURES = ["log_incidentes_total", "log_ola_violados", "log_duracao_media", "taxa_violacao_ola"]


def _rotulos(k: int) -> list[str]:
    if k == 2:
        return ["Alto risco operacional", "Baixo risco operacional"]
    if k == 3:
        return ["Alto risco operacional", "Risco moderado", "Baixo risco operacional"]
    return [f"Cluster de risco {i + 1} (do mais para o menos crítico)" for i in range(k)]


def _agregar(df: pd.DataFrame, dimensao: str) -> pd.DataFrame:
    base = df.copy()
    base["entidade"] = base[dimensao].astype("string").str.strip()
    base = base[base["entidade"].notna() & (base["entidade"] != "")]
    agregado = (
        base.groupby("entidade")
        .agg(
            incidentes_total=("Aberto", "size"),
            incidentes_kpi=("Elegivel_KPI_Regra", "sum"),
            ola_violados=("OLA_Violado_Regra", "sum"),
            duracao_media=("Duracao_Horas", "mean"),
        )
        .reset_index()
    )
    return agregado


def segmentar(df: pd.DataFrame, dimensao: str, k_min: int = 2, k_max: int = 6) -> dict:
    if dimensao not in DIMENSOES:
        raise ValueError(f"Dimensão inválida: {dimensao!r}. Use uma de {list(DIMENSOES)}.")

    agregado = _agregar(df, dimensao)
    if len(agregado) < k_min + 1:
        raise ValueError("Entidades insuficientes para segmentar nesta dimensão.")

    agregado["taxa_violacao_ola"] = np.where(
        agregado["incidentes_total"] > 0,
        agregado["ola_violados"] / agregado["incidentes_total"],
        0.0,
    )
    agregado["log_incidentes_total"] = np.log1p(agregado["incidentes_total"])
    agregado["log_ola_violados"] = np.log1p(agregado["ola_violados"])
    agregado["log_duracao_media"] = np.log1p(agregado["duracao_media"].clip(lower=0))

    x = StandardScaler().fit_transform(agregado[_FEATURES].to_numpy())
    k_max_efetivo = min(k_max, len(agregado) - 1)

    escolha_k = []
    for k in range(k_min, k_max_efetivo + 1):
        modelo = KMeans(n_clusters=k, random_state=42, n_init=10).fit(x)
        escolha_k.append(
            {
                "k": k,
                "silhouette": float(silhouette_score(x, modelo.labels_)),
                "inertia": float(modelo.inertia_),
            }
        )
    melhor_k = max(escolha_k, key=lambda item: item["silhouette"])["k"]

    modelo_final = KMeans(n_clusters=melhor_k, random_state=42, n_init=10).fit(x)
    agregado["cluster"] = modelo_final.labels_

    severidade = (
        agregado.groupby("cluster")["taxa_violacao_ola"].mean().sort_values(ascending=False)
    )
    ordem = {cluster: posicao for posicao, cluster in enumerate(severidade.index)}
    rotulos = _rotulos(melhor_k)
    agregado["rotulo"] = agregado["cluster"].map(lambda c: rotulos[ordem[c]])
    agregado["posicao_risco"] = agregado["cluster"].map(ordem)

    resumo_clusters = (
        agregado.groupby(["posicao_risco", "rotulo"])
        .agg(
            entidades=("entidade", "size"),
            incidentes_total=("incidentes_total", "sum"),
            ola_violados=("ola_violados", "sum"),
            taxa_media=("taxa_violacao_ola", "mean"),
            duracao_media_h=("duracao_media", "mean"),
        )
        .reset_index()
        .sort_values("posicao_risco")
    )

    agregado = agregado.sort_values(["posicao_risco", "ola_violados"], ascending=[True, False])
    return {
        "dimensao": dimensao,
        "kEscolhido": int(melhor_k),
        "criterio": "maior Coeficiente de Silhueta entre K=2 e K=6",
        "escolhaK": escolha_k,
        "clusters": [
            {
                "posicao": int(linha.posicao_risco),
                "rotulo": str(linha.rotulo),
                "entidades": int(linha.entidades),
                "incidentesTotal": int(linha.incidentes_total),
                "olaViolados": int(linha.ola_violados),
                "taxaMedia": float(linha.taxa_media),
                "duracaoMediaH": float(linha.duracao_media_h),
            }
            for linha in resumo_clusters.itertuples()
        ],
        "entidades": [
            {
                "entidade": str(linha.entidade),
                "cluster": int(linha.posicao_risco),
                "rotulo": str(linha.rotulo),
                "incidentesTotal": int(linha.incidentes_total),
                "incidentesKpi": int(linha.incidentes_kpi),
                "olaViolados": int(linha.ola_violados),
                "taxaViolacao": float(linha.taxa_violacao_ola),
                "duracaoMediaH": float(linha.duracao_media),
            }
            for linha in agregado.itertuples()
        ],
    }
