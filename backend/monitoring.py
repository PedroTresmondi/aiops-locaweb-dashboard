"""Monitor de deriva de dados (data drift) para o modelo de risco de OLA.

Compara a janela usada para treinar o classificador (incidentes elegíveis abertos
antes de 01/10/2025) com os 30 dias finais do snapshot. Usa o Population Stability
Index (PSI), métrica padrão de monitoramento: < 0,10 estável, 0,10–0,20 atenção,
> 0,20 mudança relevante que pede revalidação. Tudo é calculado sobre o snapshot
real — nenhuma distribuição é sintética.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

_EPS = 1e-6
_CORTE_TREINO = pd.Timestamp("2025-10-01")
_DIAS_JANELA_RECENTE = 30


def _nivel(psi: float) -> str:
    if psi < 0.10:
        return "estável"
    if psi < 0.20:
        return "atenção"
    return "alto"


def _psi_de_shares(esperado: pd.Series, atual: pd.Series) -> tuple[float, list[dict]]:
    categorias = esperado.index.union(atual.index)
    e = esperado.reindex(categorias).fillna(0.0).astype(float).clip(lower=_EPS)
    a = atual.reindex(categorias).fillna(0.0).astype(float).clip(lower=_EPS)
    e, a = e / e.sum(), a / a.sum()
    contribuicao = (a - e) * np.log(a / e)
    detalhe = sorted(
        (
            {
                "faixa": str(categoria),
                "esperado": float(e[categoria]),
                "atual": float(a[categoria]),
                "psi": float(contribuicao[categoria]),
            }
            for categoria in categorias
        ),
        key=lambda item: abs(item["psi"]),
        reverse=True,
    )
    return float(contribuicao.sum()), detalhe


def _psi_categorico(esperado: pd.Series, atual: pd.Series, top: int = 8) -> tuple[float, list[dict]]:
    esperado = esperado.fillna("Não informado").astype(str)
    atual = atual.fillna("Não informado").astype(str)
    principais = esperado.value_counts().head(top).index
    e = esperado.where(esperado.isin(principais), "Outros").value_counts(normalize=True)
    a = atual.where(atual.isin(principais), "Outros").value_counts(normalize=True)
    return _psi_de_shares(e, a)


def _psi_numerico(esperado: pd.Series, atual: pd.Series, n_bins: int = 10) -> tuple[float, list[dict]]:
    esperado = pd.to_numeric(esperado, errors="coerce").dropna().astype(float)
    atual = pd.to_numeric(atual, errors="coerce").dropna().astype(float)
    quantis = np.unique(np.quantile(esperado, np.linspace(0, 1, n_bins + 1)))
    if len(quantis) < 3:
        return 0.0, []
    quantis[0], quantis[-1] = -np.inf, np.inf
    e = pd.cut(esperado, bins=quantis).value_counts(normalize=True).sort_index()
    a = pd.cut(atual, bins=quantis).value_counts(normalize=True).sort_index()
    return _psi_de_shares(e, a)


def analisar_deriva(df: pd.DataFrame) -> dict:
    elegivel = df[df["Elegivel_KPI_Regra"].astype(bool)].copy()
    elegivel["Aberto"] = pd.to_datetime(elegivel["Aberto"])
    snapshot = elegivel["Aberto"].max()
    inicio_recente = snapshot.normalize() - timedelta(days=_DIAS_JANELA_RECENTE - 1)

    referencia = elegivel[elegivel["Aberto"] < _CORTE_TREINO]
    recente = elegivel[elegivel["Aberto"] >= inicio_recente]
    if referencia.empty or recente.empty:
        raise ValueError("Janelas de referência ou recente vazias para o cálculo de deriva.")

    volume_ref = referencia.groupby(referencia["Aberto"].dt.normalize()).size()
    volume_rec = recente.groupby(recente["Aberto"].dt.normalize()).size()

    definicoes = [
        ("Volume diário de elegíveis", *_psi_numerico(volume_ref, volume_rec)),
        ("Prioridade", *_psi_categorico(referencia["Prioridade_Cod"].astype(str), recente["Prioridade_Cod"].astype(str))),
        ("Categoria", *_psi_categorico(referencia["Categoria"], recente["Categoria"])),
        ("Grupo designado", *_psi_categorico(referencia["Grupo designado"], recente["Grupo designado"])),
        ("Produto", *_psi_categorico(referencia["Produto"], recente["Produto"])),
        ("Hora de abertura", *_psi_numerico(referencia["Aberto"].dt.hour, recente["Aberto"].dt.hour)),
    ]
    features = [
        {
            "feature": nome,
            "psi": round(psi, 4),
            "nivel": _nivel(psi),
            "detalhe": detalhe[:6],
        }
        for nome, psi, detalhe in definicoes
    ]

    taxa_ref = float(referencia["OLA_Violado_KPI_Regra"].mean())
    taxa_rec = float(recente["OLA_Violado_KPI_Regra"].mean())
    pior_psi = max(item["psi"] for item in features)
    revalidacao = pior_psi >= 0.20 or abs(taxa_rec - taxa_ref) >= 0.05

    return {
        "janelaReferencia": {
            "inicio": referencia["Aberto"].min().date().isoformat(),
            "fim": (referencia["Aberto"].max()).date().isoformat(),
            "incidentes": int(len(referencia)),
            "descricao": "Treino do classificador · abertos antes de 01/10/2025",
        },
        "janelaRecente": {
            "inicio": recente["Aberto"].min().date().isoformat(),
            "fim": recente["Aberto"].max().date().isoformat(),
            "incidentes": int(len(recente)),
            "descricao": f"Últimos {_DIAS_JANELA_RECENTE} dias do snapshot",
        },
        "features": sorted(features, key=lambda item: item["psi"], reverse=True),
        "volumeMedioDia": {
            "referencia": round(float(volume_ref.mean()), 1),
            "recente": round(float(volume_rec.mean()), 1),
            "razao": round(float(volume_rec.mean() / max(volume_ref.mean(), _EPS)), 2),
        },
        "taxaViolacao": {
            "referencia": taxa_ref,
            "recente": taxa_rec,
            "variacaoPP": round((taxa_rec - taxa_ref) * 100, 2),
        },
        "piorPsi": round(pior_psi, 4),
        "revalidacaoRecomendada": bool(revalidacao),
    }
