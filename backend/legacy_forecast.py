"""Previsão D+1/D+7 para os 4 alvos monitorados — contrato legado da Sprint 3.

Reproduz a lógica de ``previsao.py`` da aplicação Cloud da Sprint 3 (a que rodou no
Azure Container Instance): para cada alvo — incidentes_total, incidentes_kpi,
ola_violados, duracao — agrega a série diária, constrói lags e médias móveis,
compara 4 algoritmos com split cronológico 80/20 e escolhe o de menor RMSE.

Mantido separado de ``model_pipeline.py`` (que faz a validação temporal rigorosa da
Sprint 4) porque este é o contrato exato que os endpoints ``/previsao`` e
``/previsao/historico`` expõem e que o vídeo pitch e as evidências da Sprint 3 usam.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ALVOS = ["incidentes_total", "incidentes_kpi", "ola_violados", "duracao"]
HORIZONTES = [("D+1", 1), ("D+7", 7)]
FEATURES = ["lag_1", "lag_7", "media_movel_7", "media_movel_30", "dia_semana", "mes"]

_MODELOS = {
    "Regressão Linear": LinearRegression(),
    "Random Forest": RandomForestRegressor(n_estimators=200, random_state=42),
    "Gradient Boosting": GradientBoostingRegressor(random_state=42),
    "Extra Trees": ExtraTreesRegressor(n_estimators=200, random_state=42),
}


def _serie_diaria(df: pd.DataFrame, alvo: str) -> pd.Series:
    base = df.copy()
    base["Aberto"] = pd.to_datetime(base["Aberto"], errors="coerce")
    base["data"] = base["Aberto"].dt.normalize()
    dias = pd.date_range(base["data"].min(), base["data"].max(), freq="D")

    if alvo == "incidentes_total":
        serie = base.groupby("data").size().reindex(dias, fill_value=0)
    elif alvo == "incidentes_kpi":
        serie = base[base["Elegivel_KPI_Regra"].astype(bool)].groupby("data").size().reindex(dias, fill_value=0)
    elif alvo == "ola_violados":
        serie = base[base["OLA_Violado_Regra"].astype(bool)].groupby("data").size().reindex(dias, fill_value=0)
    elif alvo == "duracao":
        serie = base.groupby("data")["Duracao_Horas"].median().reindex(dias).ffill().bfill()
    else:
        raise ValueError(f"Alvo desconhecido: {alvo}")
    return pd.Series(serie.to_numpy(), index=dias)


def _features(serie: pd.Series) -> pd.DataFrame:
    quadro = pd.DataFrame({"y": serie.to_numpy()}, index=serie.index)
    quadro["lag_1"] = quadro["y"].shift(1)
    quadro["lag_7"] = quadro["y"].shift(7)
    quadro["media_movel_7"] = quadro["y"].shift(1).rolling(7).mean()
    quadro["media_movel_30"] = quadro["y"].shift(1).rolling(30).mean()
    quadro["dia_semana"] = quadro.index.dayofweek
    quadro["mes"] = quadro.index.month
    quadro["y_d1"] = quadro["y"].shift(-1)
    quadro["y_d7"] = quadro["y"].shift(-7)
    return quadro.dropna(subset=FEATURES + ["y_d1"])


def _melhor_modelo(x_treino, y_treino, x_teste, y_teste) -> dict:
    melhor: dict | None = None
    for nome, modelo in _MODELOS.items():
        modelo.fit(x_treino, y_treino)
        predito = modelo.predict(x_teste)
        rmse = float(mean_squared_error(y_teste, predito) ** 0.5)
        if melhor is None or rmse < melhor["rmse"]:
            melhor = {
                "modelo": nome,
                "objeto": modelo,
                "rmse": rmse,
                "mae": float(mean_absolute_error(y_teste, predito)),
                "r2": float(r2_score(y_teste, predito)),
            }
    return melhor


def gerar_previsoes(df: pd.DataFrame) -> list[dict]:
    resultados: list[dict] = []
    for alvo in ALVOS:
        dados = _features(_serie_diaria(df, alvo))
        n = len(dados)
        corte = int(n * 0.8) if n >= 30 else max(n - 5, 1)
        for horizonte, _dias in HORIZONTES:
            coluna = "y_d1" if horizonte == "D+1" else "y_d7"
            dados_h = dados.dropna(subset=[coluna])
            x, y = dados_h[FEATURES], dados_h[coluna]
            corte_h = min(corte, len(x) - 1) if len(x) > 1 else 0
            if corte_h <= 0 or len(x) - corte_h == 0:
                continue
            melhor = _melhor_modelo(x.iloc[:corte_h], y.iloc[:corte_h], x.iloc[corte_h:], y.iloc[corte_h:])
            previsto = float(melhor["objeto"].predict(dados[FEATURES].iloc[[-1]])[0])
            resultados.append(
                {
                    "alvo": alvo,
                    "horizonte": horizonte,
                    "modelo": melhor["modelo"],
                    "mae": round(melhor["mae"], 2),
                    "rmse": round(melhor["rmse"], 2),
                    "r2": round(melhor["r2"], 3),
                    "previsao": round(previsto, 2),
                }
            )
    return resultados
