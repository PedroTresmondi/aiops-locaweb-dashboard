"""Pipeline reproduzível de previsão de volume usado pelo painel.

A construção das 18 features segue a Sprint 3. A validação mantém o corte
temporal 80/20 original; os modelos finais são então reajustados com todo o
histórico cujo alvo já é conhecido para produzir as previsões seguintes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
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
        "media_real": float(np.mean(real)),
        "media_prevista": float(np.mean(previsto)),
        "vies_real_menos_previsto": float(np.mean(residuo)),
        "residuo_q10": float(np.quantile(residuo, 0.10)),
        "residuo_q90": float(np.quantile(residuo, 0.90)),
    }


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

    ultima_linha = serie.dropna(subset=FEATURES).iloc[[-1]]
    data_base = pd.Timestamp(ultima_linha["data"].iloc[0])
    previsoes: dict[str, dict[str, float | pd.Timestamp]] = {}
    for horizonte, dias in [("D+1", 1), ("D+7", 7)]:
        alvo = f"target_incidentes_d{dias}"
        dados_finais = serie.dropna(subset=FEATURES + [alvo])
        modelo_final = LinearRegression().fit(dados_finais[FEATURES], dados_finais[alvo])
        ponto = max(0.0, float(modelo_final.predict(ultima_linha[FEATURES])[0]))
        q10, q90 = np.quantile(residuos_validacao[horizonte], [0.10, 0.90])
        previsoes[horizonte] = {
            "data_base": data_base,
            "data_alvo": data_base + pd.Timedelta(dias, unit="D"),
            "ponto": ponto,
            "limite_inferior_80": max(0.0, ponto + float(q10)),
            "limite_superior_80": max(0.0, ponto + float(q90)),
            "linhas_treino_final": float(len(dados_finais)),
        }

    return ResultadoModelo(
        serie=serie,
        backtest=pd.concat(backtests, ignore_index=True),
        metricas=pd.DataFrame(linhas_metricas),
        benchmark=pd.DataFrame(linhas_benchmark),
        coeficientes=pd.concat(coeficientes, ignore_index=True),
        previsoes=previsoes,
        corte_treino=pd.Timestamp(treino["data"].max()),
        inicio_teste=pd.Timestamp(teste["data"].min()),
        fim_teste=pd.Timestamp(teste["data"].max()),
    )
