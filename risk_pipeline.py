"""Modelo temporal de risco de violação de OLA no momento da triagem.

O pipeline usa apenas atributos conhecidos quando o incidente é aberto. Outubro e
novembro de 2025 são usados para escolher e calibrar o ensemble; dezembro fica
intocado até o teste final. O resultado é um risco probabilístico auditável, e não
uma regra criada manualmente para parecer predição.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder


CATEGORICAS = ["Produto", "Categoria", "Grupo designado"]
NUMERICAS = [
    "Prioridade_Cod",
    "hora_abertura",
    "dia_semana",
    "mes",
    "dias_desde_inicio",
]
FEATURES_RISCO = ["Prioridade_Cod", *CATEGORICAS, *NUMERICAS[1:]]
ROTULOS_FEATURES = {
    "Prioridade_Cod": "Prioridade",
    "Produto": "Produto",
    "Categoria": "Categoria",
    "Grupo designado": "Grupo designado",
    "hora_abertura": "Hora de abertura",
    "dia_semana": "Dia da semana",
    "mes": "Mês",
    "dias_desde_inicio": "Tendência temporal",
}


@dataclass
class ResultadoRiscoOLA:
    modelos: dict[str, Pipeline]
    calibrador: LogisticRegression
    peso_extra_trees: float
    benchmark_validacao: pd.DataFrame
    metricas_holdout: dict[str, float]
    backtest: pd.DataFrame
    calibracao: pd.DataFrame
    importancias: pd.DataFrame
    limiar_medio: float
    limiar_alto: float
    inicio_base: pd.Timestamp
    inicio_holdout: pd.Timestamp
    fim_holdout: pd.Timestamp

    def prever(
        self,
        prioridade: int,
        produto: str,
        categoria: str,
        grupo: str,
        data_hora: datetime | pd.Timestamp,
    ) -> dict[str, float | str]:
        momento = pd.Timestamp(data_hora)
        entrada = pd.DataFrame(
            [
                {
                    "Prioridade_Cod": int(prioridade),
                    "Produto": produto or "Não informado",
                    "Categoria": categoria or "Não informado",
                    "Grupo designado": grupo or "Não informado",
                    "hora_abertura": momento.hour,
                    "dia_semana": momento.dayofweek,
                    "mes": momento.month,
                    "dias_desde_inicio": (momento.normalize() - self.inicio_base).days,
                }
            ]
        )
        p_et = self.modelos["Extra Trees"].predict_proba(entrada[FEATURES_RISCO])[:, 1]
        p_hist = self.modelos["HistGradientBoosting"].predict_proba(entrada[FEATURES_RISCO])[:, 1]
        bruto = self.peso_extra_trees * p_et + (1 - self.peso_extra_trees) * p_hist
        probabilidade = float(self.calibrador.predict_proba(bruto.reshape(-1, 1))[0, 1])
        if probabilidade >= self.limiar_alto:
            faixa = "Alto"
        elif probabilidade >= self.limiar_medio:
            faixa = "Moderado"
        else:
            faixa = "Baixo"
        return {
            "probabilidade": probabilidade,
            "faixa": faixa,
            "limiar_medio": self.limiar_medio,
            "limiar_alto": self.limiar_alto,
        }


def preparar_base_risco(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra o universo elegível e cria somente features disponíveis na abertura."""
    base = df[df["Elegivel_KPI_Regra"].astype(bool)].copy()
    base["Aberto"] = pd.to_datetime(base["Aberto"])
    base = base.sort_values("Aberto").reset_index(drop=True)
    for coluna in CATEGORICAS:
        base[coluna] = base[coluna].fillna("Não informado").astype(str)
    base["hora_abertura"] = base["Aberto"].dt.hour
    base["dia_semana"] = base["Aberto"].dt.dayofweek
    base["mes"] = base["Aberto"].dt.month
    inicio = base["Aberto"].min().normalize()
    base["dias_desde_inicio"] = (base["Aberto"].dt.normalize() - inicio).dt.days
    base["alvo"] = base["OLA_Violado_KPI_Regra"].astype(bool).astype(int)
    return base


def _modelo_arvore(tipo: str) -> Pipeline:
    transformador = ColumnTransformer(
        [
            (
                "categoricas",
                OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                CATEGORICAS,
            ),
            ("numericas", "passthrough", NUMERICAS),
        ]
    )
    if tipo == "Extra Trees":
        estimador = ExtraTreesClassifier(
            n_estimators=300,
            max_depth=14,
            min_samples_leaf=12,
            max_features=0.8,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
    else:
        estimador = HistGradientBoostingClassifier(
            max_iter=180,
            learning_rate=0.05,
            max_leaf_nodes=20,
            l2_regularization=3,
            class_weight="balanced",
            random_state=42,
        )
    return Pipeline([("preprocessamento", transformador), ("classificador", estimador)])


def _probabilidade_ensemble(
    modelos: dict[str, Pipeline], x: pd.DataFrame, peso_extra_trees: float
) -> np.ndarray:
    p_et = modelos["Extra Trees"].predict_proba(x)[:, 1]
    p_hist = modelos["HistGradientBoosting"].predict_proba(x)[:, 1]
    return peso_extra_trees * p_et + (1 - peso_extra_trees) * p_hist


def _metricas_classificacao(y: pd.Series, p: np.ndarray) -> dict[str, float]:
    return {
        "ROC_AUC": float(roc_auc_score(y, p)),
        "PR_AUC": float(average_precision_score(y, p)),
        "Brier": float(brier_score_loss(y, p)),
    }


def executar_pipeline_risco(df: pd.DataFrame) -> ResultadoRiscoOLA:
    base = preparar_base_risco(df)
    inicio_base = base["Aberto"].min().normalize()
    treino = base["Aberto"] < pd.Timestamp("2025-10-01")
    validacao = (base["Aberto"] >= pd.Timestamp("2025-10-01")) & (
        base["Aberto"] < pd.Timestamp("2025-12-01")
    )
    holdout = base["Aberto"] >= pd.Timestamp("2025-12-01")
    if min(int(treino.sum()), int(validacao.sum()), int(holdout.sum())) == 0:
        raise ValueError("A base não contém as janelas temporais esperadas para o modelo de risco.")

    x_treino, y_treino = base.loc[treino, FEATURES_RISCO], base.loc[treino, "alvo"]
    x_valid, y_valid = base.loc[validacao, FEATURES_RISCO], base.loc[validacao, "alvo"]
    x_holdout, y_holdout = base.loc[holdout, FEATURES_RISCO], base.loc[holdout, "alvo"]

    modelos = {
        "Extra Trees": _modelo_arvore("Extra Trees"),
        "HistGradientBoosting": _modelo_arvore("HistGradientBoosting"),
    }
    for modelo in modelos.values():
        modelo.fit(x_treino, y_treino)

    p_valid_componentes = {
        nome: modelo.predict_proba(x_valid)[:, 1] for nome, modelo in modelos.items()
    }
    candidatos: list[dict[str, float | str]] = []
    pesos = [0.0, 0.25, 0.5, 0.75, 1.0]
    for peso in pesos:
        p = peso * p_valid_componentes["Extra Trees"] + (1 - peso) * p_valid_componentes["HistGradientBoosting"]
        med = _metricas_classificacao(y_valid, p)
        candidatos.append(
            {
                "modelo": f"{peso:.0%} Extra Trees + {1-peso:.0%} HistGB",
                "peso_extra_trees": peso,
                **med,
            }
        )
    benchmark = pd.DataFrame(candidatos).sort_values("PR_AUC", ascending=False).reset_index(drop=True)
    peso_escolhido = float(benchmark.iloc[0]["peso_extra_trees"])
    p_valid_bruto = (
        peso_escolhido * p_valid_componentes["Extra Trees"]
        + (1 - peso_escolhido) * p_valid_componentes["HistGradientBoosting"]
    )

    # Platt scaling transforma o score balanceado em probabilidade observável.
    calibrador = LogisticRegression(C=1_000_000, max_iter=500)
    calibrador.fit(p_valid_bruto.reshape(-1, 1), y_valid)
    p_valid = calibrador.predict_proba(p_valid_bruto.reshape(-1, 1))[:, 1]
    limiar_medio = float(np.quantile(p_valid, 0.50))
    limiar_alto = float(np.quantile(p_valid, 0.80))

    p_holdout_bruto = _probabilidade_ensemble(modelos, x_holdout, peso_escolhido)
    p_holdout = calibrador.predict_proba(p_holdout_bruto.reshape(-1, 1))[:, 1]
    metricas_holdout = _metricas_classificacao(y_holdout, p_holdout)
    selecionados = p_holdout >= limiar_alto
    metricas_holdout.update(
        {
            "prevalencia": float(y_holdout.mean()),
            "taxa_revisada": float(selecionados.mean()),
            "precisao_fila_alta": float(y_holdout[selecionados].mean()),
            "captura_violacoes": float(y_holdout[selecionados].sum() / max(1, y_holdout.sum())),
            "lift_fila_alta": float(y_holdout[selecionados].mean() / max(1e-9, y_holdout.mean())),
            "n_holdout": int(holdout.sum()),
            "n_violacoes_holdout": int(y_holdout.sum()),
        }
    )

    backtest = base.loc[holdout, ["Aberto", "Prioridade_Cod", "Produto", "Categoria", "Grupo designado", "alvo"]].copy()
    backtest["probabilidade"] = p_holdout
    backtest["fila_alta"] = selecionados

    cortes = np.unique(np.quantile(p_holdout, np.linspace(0, 1, 11)))
    backtest["faixa_calibracao"] = pd.cut(
        backtest["probabilidade"], bins=cortes, include_lowest=True, duplicates="drop"
    )
    calibracao = (
        backtest.groupby("faixa_calibracao", observed=True)
        .agg(
            risco_previsto=("probabilidade", "mean"),
            taxa_observada=("alvo", "mean"),
            incidentes=("alvo", "size"),
            violacoes=("alvo", "sum"),
        )
        .reset_index(drop=True)
    )
    calibracao["decil"] = np.arange(1, len(calibracao) + 1)

    # Importância operacional por queda de PR-AUC no holdout após embaralhar uma feature.
    rng = np.random.default_rng(42)
    ap_base = average_precision_score(y_holdout, p_holdout)
    importancias = []
    for feature in FEATURES_RISCO:
        embaralhado = x_holdout.copy()
        embaralhado[feature] = rng.permutation(embaralhado[feature].to_numpy())
        p_perm_bruto = _probabilidade_ensemble(modelos, embaralhado, peso_escolhido)
        p_perm = calibrador.predict_proba(p_perm_bruto.reshape(-1, 1))[:, 1]
        importancias.append(
            {
                "variavel": ROTULOS_FEATURES[feature],
                "queda_pr_auc": max(0.0, float(ap_base - average_precision_score(y_holdout, p_perm))),
            }
        )
    importancias_df = pd.DataFrame(importancias).sort_values("queda_pr_auc", ascending=False)

    return ResultadoRiscoOLA(
        modelos=modelos,
        calibrador=calibrador,
        peso_extra_trees=peso_escolhido,
        benchmark_validacao=benchmark,
        metricas_holdout=metricas_holdout,
        backtest=backtest,
        calibracao=calibracao,
        importancias=importancias_df,
        limiar_medio=limiar_medio,
        limiar_alto=limiar_alto,
        inicio_base=inicio_base,
        inicio_holdout=base.loc[holdout, "Aberto"].min().normalize(),
        fim_holdout=base.loc[holdout, "Aberto"].max().normalize(),
    )
