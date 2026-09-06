"""Pipeline reproduzível de previsão de volume usado pelo painel.

A construção das 18 features segue a Sprint 3. A validação mantém o corte
temporal 80/20 original; os modelos finais são então reajustados com todo o
histórico cujo alvo já é conhecido para produzir as previsões seguintes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


FEATURES = [
    "ano", "mes", "dia", "dia_semana", "semana_ano", "fim_de_semana",
    "incidentes_total_lag_1", "incidentes_total_lag_7",
    "incidentes_kpi_lag_1", "incidentes_kpi_lag_7",
    "ola_violados_lag_1", "ola_violados_lag_7",
    "media_7d_incidentes_total", "media_14d_incidentes_total",
    "media_30d_incidentes_total", "media_7d_incidentes_kpi",
    "media_7d_ola_violados", "tendencia_7_vs_14",
]

FEATURE_LABELS = {
    "ano": "Ano", "mes": "Mês", "dia": "Dia do mês",
    "dia_semana": "Dia da semana", "semana_ano": "Semana do ano",
    "fim_de_semana": "Fim de semana",
    "incidentes_total_lag_1": "Volume de ontem",
    "incidentes_total_lag_7": "Volume há 7 dias",
    "incidentes_kpi_lag_1": "Elegíveis ao KPI ontem",
    "incidentes_kpi_lag_7": "Elegíveis ao KPI há 7 dias",
    "ola_violados_lag_1": "Violações OLA-base ontem",
    "ola_violados_lag_7": "Violações OLA-base há 7 dias",
    "media_7d_incidentes_total": "Média de volume — 7 dias",
    "media_14d_incidentes_total": "Média de volume — 14 dias",
    "media_30d_incidentes_total": "Média de volume — 30 dias",
    "media_7d_incidentes_kpi": "Média de elegíveis — 7 dias",
    "media_7d_ola_violados": "Média de violações OLA-base — 7 dias",
    "tendencia_7_vs_14": "Tendência 7d vs. 14d",
}


@dataclass
class ResultadoModelo:
    serie: pd.DataFrame
    backtest: pd.DataFrame
    metricas: pd.DataFrame
    benchmark: pd.DataFrame
    coeficientes: pd.DataFrame
    backtest_operacional: pd.DataFrame
    metricas_operacionais: pd.DataFrame
    importancias_operacionais: pd.DataFrame
    previsoes: dict[str, dict[str, float | pd.Timestamp]]
    corte_treino: pd.Timestamp
    inicio_teste: pd.Timestamp
    fim_teste: pd.Timestamp


def preparar_serie(df: pd.DataFrame) -> pd.DataFrame:
    """Cria a série diária e as features sem usar nenhuma informação futura."""
    base = df.copy()
    base["data"] = pd.to_datetime(base["Aberto"]).dt.normalize()
    base["_elegivel"] = base["Elegivel_KPI_Regra"].astype(bool).astype(int)
    # A Sprint 3 usou violações sobre a base inteira como sinal histórico.
    # O KPI mostrado no painel usa, separadamente, a interseção elegível correta.
    base["_ola_base"] = base["OLA_Violado_Regra"].astype(bool).astype(int)

    serie = (
        base.groupby("data")
        .agg(
            incidentes_total=("Aberto", "size"),
            incidentes_kpi=("_elegivel", "sum"),
            ola_violados=("_ola_base", "sum"),
        )
        .asfreq("D", fill_value=0)
        .reset_index()
    )

    serie["ano"] = serie["data"].dt.year
    serie["mes"] = serie["data"].dt.month
    serie["dia"] = serie["data"].dt.day
    serie["dia_semana"] = serie["data"].dt.dayofweek
    serie["semana_ano"] = serie["data"].dt.isocalendar().week.astype(int)
    serie["fim_de_semana"] = (serie["dia_semana"] >= 5).astype(int)

    for coluna in ["incidentes_total", "incidentes_kpi", "ola_violados"]:
        for lag in [1, 7]:
            serie[f"{coluna}_lag_{lag}"] = serie[coluna].shift(lag)

    for janela in [7, 14, 30]:
        serie[f"media_{janela}d_incidentes_total"] = (
            serie["incidentes_total"].shift(1).rolling(janela).mean()
        )
    serie["media_7d_incidentes_kpi"] = serie["incidentes_kpi"].shift(1).rolling(7).mean()
    serie["media_7d_ola_violados"] = serie["ola_violados"].shift(1).rolling(7).mean()
    serie["tendencia_7_vs_14"] = (
        serie["media_7d_incidentes_total"] - serie["media_14d_incidentes_total"]
    )
    serie["target_incidentes_d1"] = serie["incidentes_total"].shift(-1)
    serie["target_incidentes_d7"] = serie["incidentes_total"].shift(-7)
    return serie


def _metricas(real: np.ndarray, previsto: np.ndarray) -> dict[str, float]:
    residuo = real - previsto
    return {
        "MAE": float(mean_absolute_error(real, previsto)),
        "RMSE": float(np.sqrt(mean_squared_error(real, previsto))),
        "R2": float(r2_score(real, previsto)),
        "WAPE": float(np.abs(residuo).sum() / max(float(np.sum(real)), 1.0)),
        "media_real": float(np.mean(real)),
        "media_prevista": float(np.mean(previsto)),
        "vies_real_menos_previsto": float(np.mean(residuo)),
        "residuo_q10": float(np.quantile(residuo, 0.10)),
        "residuo_q90": float(np.quantile(residuo, 0.90)),
    }


FEATURES_OPERACIONAIS = (
    ["total_atual", "kpi_atual", "ola_base_atual"]
    + [f"{coluna}_lag_{lag}" for coluna in ["total", "kpi", "ola"] for lag in [1, 2, 6, 7, 13, 14, 27, 28]]
    + [f"{coluna}_media_{janela}" for coluna in ["total", "kpi", "ola"] for janela in [3, 7, 14, 28]]
    + [f"total_desvio_{janela}" for janela in [7, 14, 28]]
    + ["tendencia_7_vs_14_op", "razao_7_vs_28"]
    + [
        "alvo_dia_semana", "alvo_fim_semana", "alvo_dia_mes", "alvo_mes",
        "alvo_dia_semana_sin", "alvo_dia_semana_cos",
        "alvo_mes_sin", "alvo_mes_cos",
    ]
)


def _rotulo_operacional(feature: str) -> str:
    fixos = {
        "total_atual": "Volume do dia-base",
        "kpi_atual": "Elegíveis no dia-base",
        "ola_base_atual": "OLA-base no dia-base",
        "tendencia_7_vs_14_op": "Tendência de volume 7d vs. 14d",
        "razao_7_vs_28": "Razão de volume 7d vs. 28d",
        "alvo_dia_semana": "Dia da semana do alvo",
        "alvo_fim_semana": "Alvo em fim de semana",
        "alvo_dia_mes": "Dia do mês do alvo",
        "alvo_mes": "Mês do alvo",
        "alvo_dia_semana_sin": "Ciclo semanal — seno",
        "alvo_dia_semana_cos": "Ciclo semanal — cosseno",
        "alvo_mes_sin": "Ciclo mensal — seno",
        "alvo_mes_cos": "Ciclo mensal — cosseno",
    }
    if feature in fixos:
        return fixos[feature]
    nomes = {"total": "Volume", "kpi": "Elegíveis", "ola": "OLA-base"}
    for prefixo, nome in nomes.items():
        if feature.startswith(f"{prefixo}_lag_"):
            return f"{nome} há {feature.rsplit('_', 1)[1]} dias"
        if feature.startswith(f"{prefixo}_media_"):
            return f"Média de {nome.lower()} — {feature.rsplit('_', 1)[1]}d"
    if feature.startswith("total_desvio_"):
        return f"Volatilidade de volume — {feature.rsplit('_', 1)[1]}d"
    return feature


def preparar_serie_operacional(serie: pd.DataFrame, horizonte_dias: int) -> pd.DataFrame:
    """Features conhecidas no fechamento do dia-base, incluindo o próprio volume observado."""
    op = serie[["data", "incidentes_total", "incidentes_kpi", "ola_violados"]].rename(
        columns={
            "incidentes_total": "total_atual",
            "incidentes_kpi": "kpi_atual",
            "ola_violados": "ola_base_atual",
        }
    ).copy()
    fontes = {"total": "total_atual", "kpi": "kpi_atual", "ola": "ola_base_atual"}
    for nome, origem in fontes.items():
        for lag in [1, 2, 6, 7, 13, 14, 27, 28]:
            op[f"{nome}_lag_{lag}"] = op[origem].shift(lag)
        for janela in [3, 7, 14, 28]:
            op[f"{nome}_media_{janela}"] = op[origem].rolling(janela).mean()
    for janela in [7, 14, 28]:
        op[f"total_desvio_{janela}"] = op["total_atual"].rolling(janela).std()
    op["tendencia_7_vs_14_op"] = op["total_media_7"] - op["total_media_14"]
    op["razao_7_vs_28"] = op["total_media_7"] / op["total_media_28"].replace(0, np.nan)

    op["data_alvo"] = op["data"] + pd.to_timedelta(horizonte_dias, unit="D")
    op["alvo_dia_semana"] = op["data_alvo"].dt.dayofweek
    op["alvo_fim_semana"] = (op["alvo_dia_semana"] >= 5).astype(int)
    op["alvo_dia_mes"] = op["data_alvo"].dt.day
    op["alvo_mes"] = op["data_alvo"].dt.month
    op["alvo_dia_semana_sin"] = np.sin(2 * np.pi * op["alvo_dia_semana"] / 7)
    op["alvo_dia_semana_cos"] = np.cos(2 * np.pi * op["alvo_dia_semana"] / 7)
    op["alvo_mes_sin"] = np.sin(2 * np.pi * op["alvo_mes"] / 12)
    op["alvo_mes_cos"] = np.cos(2 * np.pi * op["alvo_mes"] / 12)
    op["target"] = op["total_atual"].shift(-horizonte_dias)
    return op


def _componente_operacional(horizonte_dias: int):
    if horizonte_dias == 1:
        return Pipeline(
            [("scaler", StandardScaler()), ("model", Ridge(alpha=100))]
        ), pd.Timestamp("2023-01-01"), "Ridge com sinais do dia-base"
    return ExtraTreesRegressor(
        n_estimators=250, max_depth=8, min_samples_leaf=3,
        max_features=0.8, random_state=42, n_jobs=-1,
    ), pd.Timestamp("2025-09-01"), "Extra Trees no regime recente"


def _avaliar_modelo_operacional(serie: pd.DataFrame):
    """Seleciona pesos em out/nov e preserva dezembro como holdout final."""
    folds = [
        (pd.Timestamp("2025-10-16"), pd.Timestamp("2025-10-31")),
        (pd.Timestamp("2025-11-01"), pd.Timestamp("2025-11-15")),
        (pd.Timestamp("2025-11-16"), pd.Timestamp("2025-11-30")),
    ]
    pesos_candidatos = np.arange(0.0, 1.01, 0.1)
    metricas_saida: list[dict[str, float | str]] = []
    backtests_saida: list[pd.DataFrame] = []
    importancias_saida: list[pd.DataFrame] = []
    previsoes: dict[str, dict[str, float | pd.Timestamp]] = {}
    ultima_data = pd.Timestamp(serie["data"].max())

    for horizonte, dias in [("D+1", 1), ("D+7", 7)]:
        alvo_baseline = f"target_incidentes_d{dias}"
        baseline = serie.dropna(subset=FEATURES + [alvo_baseline]).copy()
        baseline["data_alvo"] = baseline["data"] + pd.to_timedelta(dias, unit="D")
        operacional = preparar_serie_operacional(serie, dias).dropna(
            subset=FEATURES_OPERACIONAIS + ["target"]
        )
        componente, inicio_componente, nome_componente = _componente_operacional(dias)

        previsoes_cv: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        for inicio, fim in folds:
            validacao_base = baseline[
                (baseline["data_alvo"] >= inicio) & (baseline["data_alvo"] <= fim)
            ]
            validacao_op = operacional[
                (operacional["data_alvo"] >= inicio) & (operacional["data_alvo"] <= fim)
            ]
            treino_base = baseline[baseline["data_alvo"] < inicio]
            treino_op = operacional[
                (operacional["data_alvo"] < inicio)
                & (operacional["data_alvo"] >= inicio_componente)
            ]
            if not validacao_base["data_alvo"].reset_index(drop=True).equals(
                validacao_op["data_alvo"].reset_index(drop=True)
            ):
                raise ValueError("Datas desalinhadas entre baseline e componente operacional")
            modelo_base = LinearRegression().fit(treino_base[FEATURES], treino_base[alvo_baseline])
            modelo_op = clone(componente).fit(treino_op[FEATURES_OPERACIONAIS], treino_op["target"])
            real = validacao_base[alvo_baseline].to_numpy()
            pred_base = np.clip(modelo_base.predict(validacao_base[FEATURES]), 0, None)
            pred_op = np.clip(modelo_op.predict(validacao_op[FEATURES_OPERACIONAIS]), 0, None)
            previsoes_cv.append((real, pred_base, pred_op))

        scores = []
        for peso_base in pesos_candidatos:
            maes = [
                mean_absolute_error(real, peso_base * pred_base + (1 - peso_base) * pred_op)
                for real, pred_base, pred_op in previsoes_cv
            ]
            scores.append(float(np.mean(maes)))
        peso_base = float(pesos_candidatos[int(np.argmin(scores))])
        peso_op = 1.0 - peso_base
        residuos_cv = np.concatenate(
            [real - (peso_base * pred_base + peso_op * pred_op) for real, pred_base, pred_op in previsoes_cv]
        )

        inicio_holdout, fim_holdout = pd.Timestamp("2025-12-01"), pd.Timestamp("2025-12-31")
        teste_base = baseline[
            (baseline["data_alvo"] >= inicio_holdout) & (baseline["data_alvo"] <= fim_holdout)
        ]
        teste_op = operacional[
            (operacional["data_alvo"] >= inicio_holdout) & (operacional["data_alvo"] <= fim_holdout)
        ]
        treino_base = baseline[baseline["data_alvo"] < inicio_holdout]
        treino_op = operacional[
            (operacional["data_alvo"] < inicio_holdout)
            & (operacional["data_alvo"] >= inicio_componente)
        ]
        modelo_base = LinearRegression().fit(treino_base[FEATURES], treino_base[alvo_baseline])
        modelo_op = clone(componente).fit(treino_op[FEATURES_OPERACIONAIS], treino_op["target"])
        pred_base = np.clip(modelo_base.predict(teste_base[FEATURES]), 0, None)
        pred_op = np.clip(modelo_op.predict(teste_op[FEATURES_OPERACIONAIS]), 0, None)
        pred_ensemble = peso_base * pred_base + peso_op * pred_op
        real = teste_base[alvo_baseline].to_numpy()
        med = _metricas(real, pred_ensemble)
        med_base = _metricas(real, pred_base)
        metricas_saida.append(
            {
                "horizonte": horizonte,
                "modelo": f"{peso_base:.0%} Linear Sprint 3 + {peso_op:.0%} {nome_componente}",
                "peso_baseline": peso_base,
                "peso_operacional": peso_op,
                "cv_mae": min(scores),
                **{f"holdout_{chave}": valor for chave, valor in med.items()},
                "baseline_holdout_MAE": med_base["MAE"],
                "ganho_mae": (med_base["MAE"] - med["MAE"]) / med_base["MAE"],
            }
        )
        backtests_saida.append(
            pd.DataFrame(
                {
                    "data_alvo": teste_base["data_alvo"].to_numpy(),
                    "horizonte": horizonte,
                    "real": real,
                    "previsto": pred_ensemble,
                    "baseline": pred_base,
                    "componente_operacional": pred_op,
                    "residuo": real - pred_ensemble,
                }
            )
        )

        modelo_base_final = LinearRegression().fit(baseline[FEATURES], baseline[alvo_baseline])
        treino_op_final = operacional[operacional["data_alvo"] >= inicio_componente]
        modelo_op_final = clone(componente).fit(
            treino_op_final[FEATURES_OPERACIONAIS], treino_op_final["target"]
        )
        ultima_base = serie.dropna(subset=FEATURES).iloc[[-1]]
        ultima_op = preparar_serie_operacional(serie, dias).dropna(
            subset=FEATURES_OPERACIONAIS
        ).iloc[[-1]]
        forecast_base = max(0.0, float(modelo_base_final.predict(ultima_base[FEATURES])[0]))
        forecast_op = max(0.0, float(modelo_op_final.predict(ultima_op[FEATURES_OPERACIONAIS])[0]))
        ponto = peso_base * forecast_base + peso_op * forecast_op
        q10, q90 = np.quantile(residuos_cv, [0.10, 0.90])
        previsoes[horizonte] = {
            "data_base": ultima_data,
            "data_alvo": ultima_data + pd.Timedelta(dias, unit="D"),
            "ponto": ponto,
            "limite_inferior_80": max(0.0, ponto + float(q10)),
            "limite_superior_80": max(0.0, ponto + float(q90)),
            "baseline": forecast_base,
            "componente_operacional": forecast_op,
            "peso_baseline": peso_base,
            "peso_operacional": peso_op,
        }

        if dias == 1:
            valores = modelo_op_final.named_steps["model"].coef_
            tipo = "Coeficiente padronizado do componente Ridge"
            valor_plot = valores
        else:
            valores = modelo_op_final.feature_importances_
            tipo = "Importância do componente Extra Trees"
            valor_plot = valores
        importancias_saida.append(
            pd.DataFrame(
                {
                    "horizonte": horizonte,
                    "feature": FEATURES_OPERACIONAIS,
                    "variavel": [_rotulo_operacional(c) for c in FEATURES_OPERACIONAIS],
                    "valor": valor_plot,
                    "impacto_absoluto": np.abs(valores),
                    "tipo": tipo,
                }
            )
        )

    return (
        pd.concat(backtests_saida, ignore_index=True),
        pd.DataFrame(metricas_saida),
        pd.concat(importancias_saida, ignore_index=True),
        previsoes,
    )


def executar_pipeline(df: pd.DataFrame) -> ResultadoModelo:
    serie = preparar_serie(df)
    modelagem = serie.dropna(
        subset=FEATURES + ["target_incidentes_d1", "target_incidentes_d7"]
    ).copy()
    corte = int(len(modelagem) * 0.8)
    treino = modelagem.iloc[:corte]
    teste = modelagem.iloc[corte:]

    candidatos = {
        "Regressão Linear": LinearRegression(),
        "Random Forest": RandomForestRegressor(
            n_estimators=80, random_state=42, max_depth=6, min_samples_leaf=3
        ),
        "Gradient Boosting": GradientBoostingRegressor(
            n_estimators=80, learning_rate=0.05, max_depth=3, random_state=42
        ),
        "Extra Trees": ExtraTreesRegressor(
            n_estimators=80, random_state=42, max_depth=6, min_samples_leaf=3
        ),
    }

    linhas_benchmark: list[dict[str, float | str]] = []
    linhas_metricas: list[dict[str, float | str]] = []
    backtests: list[pd.DataFrame] = []
    coeficientes: list[pd.DataFrame] = []
    residuos_validacao: dict[str, np.ndarray] = {}

    for horizonte, dias in [("D+1", 1), ("D+7", 7)]:
        alvo = f"target_incidentes_d{dias}"
        y_treino = treino[alvo]
        y_teste = teste[alvo].to_numpy()

        for nome, candidato in candidatos.items():
            candidato.fit(treino[FEATURES], y_treino)
            pred = np.clip(candidato.predict(teste[FEATURES]), 0, None)
            med = _metricas(y_teste, pred)
            linhas_benchmark.append(
                {"horizonte": horizonte, "modelo": nome,
                 **{k: med[k] for k in ["MAE", "RMSE", "R2"]}}
            )
            if nome == "Regressão Linear":
                residuos_validacao[horizonte] = y_teste - pred
                linhas_metricas.append({"horizonte": horizonte, **med})
                backtests.append(
                    pd.DataFrame(
                        {
                            "data_base": teste["data"].to_numpy(),
                            "data_alvo": teste["data"].to_numpy() + pd.to_timedelta(dias, unit="D"),
                            "horizonte": horizonte,
                            "real": y_teste,
                            "previsto": pred,
                            "residuo": y_teste - pred,
                        }
                    )
                )

        interpretador = Pipeline(
            [("scaler", StandardScaler()), ("regressor", LinearRegression())]
        ).fit(treino[FEATURES], y_treino)
        valores = interpretador.named_steps["regressor"].coef_
        coeficientes.append(
            pd.DataFrame(
                {
                    "horizonte": horizonte,
                    "feature": FEATURES,
                    "variavel": [FEATURE_LABELS[c] for c in FEATURES],
                    "coeficiente": valores,
                    "impacto_absoluto": np.abs(valores),
                }
            )
        )

    backtest_op, metricas_op, importancias_op, previsoes = _avaliar_modelo_operacional(serie)

    return ResultadoModelo(
        serie=serie,
        backtest=pd.concat(backtests, ignore_index=True),
        metricas=pd.DataFrame(linhas_metricas),
        benchmark=pd.DataFrame(linhas_benchmark),
        coeficientes=pd.concat(coeficientes, ignore_index=True),
        backtest_operacional=backtest_op,
        metricas_operacionais=metricas_op,
        importancias_operacionais=importancias_op,
        previsoes=previsoes,
        corte_treino=pd.Timestamp(treino["data"].max()),
        inicio_teste=pd.Timestamp(teste["data"].min()),
        fim_teste=pd.Timestamp(teste["data"].max()),
    )
