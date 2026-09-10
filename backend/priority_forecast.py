"""Previsão diária P2/P3 com seleção anterior ao teste e somente contagens passadas.

D+7 é o volume do sétimo dia, não a soma da semana. Dias sem incidentes
permanecem na série. Nenhum resultado de OLA entra nas variáveis preditoras.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def serie_prioridade(df: pd.DataFrame, prioridade: int) -> pd.Series:
    datas = pd.to_datetime(df["Aberto"]).dt.normalize()
    calendario = pd.date_range(datas.min(), datas.max(), freq="D")
    mascara = pd.to_numeric(df["Prioridade_Cod"], errors="coerce").eq(prioridade)
    return datas[mascara].value_counts().reindex(calendario, fill_value=0).sort_index().astype(float)


def preparar_features(serie: pd.Series, dias: int) -> tuple[pd.DataFrame, list[str]]:
    dados = pd.DataFrame(index=serie.index)
    for lag in (0, 1, 6, 7, 13, 14, 27, 28):
        dados[f"volume_lag_{lag}"] = serie.shift(lag)
    for janela in (7, 14, 28):
        dados[f"media_{janela}"] = serie.rolling(janela).mean()
        dados[f"desvio_{janela}"] = serie.rolling(janela).std()
    alvo = serie.index + pd.Timedelta(days=dias)
    for dia in range(7):
        dados[f"dia_alvo_{dia}"] = (alvo.dayofweek == dia).astype(int)
    features = list(dados.columns)
    dados["data_alvo"] = alvo
    dados["real"] = serie.shift(-dias)
    dados["baseline"] = serie.shift(7 - dias)
    return dados.dropna(subset=features), features


def _modelo():
    return make_pipeline(StandardScaler(), Ridge(alpha=100))


def _mae(real, previsto) -> float:
    return float(np.abs(np.asarray(real) - np.asarray(previsto)).mean())


def prever_prioridades(df: pd.DataFrame) -> dict:
    fim = pd.to_datetime(df["Aberto"]).max().normalize()
    inicio_teste = fim - pd.Timedelta(days=30)
    inicio_validacao = inicio_teste - pd.Timedelta(days=61)
    resultados = []
    for prioridade in (2, 3):
        serie = serie_prioridade(df, prioridade)
        if len(serie) < 180 or serie.sum() == 0:
            raise ValueError(f"Histórico insuficiente para avaliar P{prioridade}: mínimo de 180 dias e incidentes observados.")
        for dias in (1, 7):
            dados, features = preparar_features(serie, dias)
            conhecidos = dados.dropna(subset=["real"])
            treino = conhecidos[conhecidos.data_alvo < inicio_validacao]
            validacao = conhecidos[(conhecidos.index >= inicio_validacao) & (conhecidos.data_alvo < inicio_teste)]
            teste = conhecidos[conhecidos.index >= inicio_teste]
            if min(len(treino), len(validacao), len(teste)) < 14:
                raise ValueError("Janelas insuficientes para treino, seleção e teste temporal.")

            modelo = _modelo().fit(treino[features], treino.real)
            estimativa_validacao = np.maximum(0, modelo.predict(validacao[features]))
            usar_ridge = _mae(validacao.real, estimativa_validacao) < _mae(validacao.real, validacao.baseline)
            previsto_validacao = estimativa_validacao if usar_ridge else validacao.baseline.to_numpy()
            # A escolha do modelo e a faixa ficam congeladas antes do teste.
            residuos = validacao.real.to_numpy() - previsto_validacao
            margem = float(np.quantile(np.abs(residuos), .80))
            treino_teste = conhecidos[conhecidos.data_alvo < inicio_teste]
            modelo_teste = _modelo().fit(treino_teste[features], treino_teste.real)
            previsto_teste = np.maximum(0, modelo_teste.predict(teste[features])) if usar_ridge else teste.baseline.to_numpy()
            mae = _mae(teste.real, previsto_teste)
            mae_baseline = _mae(teste.real, teste.baseline)
            soma_real = float(teste.real.sum())

            modelo_final = _modelo().fit(conhecidos[features], conhecidos.real)
            ultima = dados.iloc[[-1]]
            ponto = max(0., float(modelo_final.predict(ultima[features])[0])) if usar_ridge else float(ultima.baseline.iloc[0])
            resultados.append({
                "prioridade": prioridade, "horizonte": f"D+{dias}",
                "dataAlvo": ultima.data_alvo.iloc[0].date().isoformat(),
                "ponto": round(ponto, 1), "inferior": round(max(0., ponto - margem), 1),
                "superior": round(ponto + margem, 1),
                "modelo": "Ridge com histórico diário" if usar_ridge else "Repetição do mesmo dia da semana anterior",
                "validacao": {
                    "inicio": teste.data_alvo.min().date().isoformat(),
                    "fim": teste.data_alvo.max().date().isoformat(),
                    "dias": len(teste), "mae": round(mae, 2),
                    "maeBaseline": round(mae_baseline, 2),
                    "ganho": round(1 - mae / mae_baseline, 4) if mae_baseline > 0 else None,
                    "wape": round(float(np.abs(teste.real - previsto_teste).sum()) / soma_real, 4) if soma_real > 0 else None,
                    "coberturaFaixa": round(float((np.abs(teste.real - previsto_teste) <= margem).mean()), 4),
                },
                "selecao": {"fim": validacao.data_alvo.max().date().isoformat(), "maeRidge": round(_mae(validacao.real, estimativa_validacao), 2), "maeBaseline": round(_mae(validacao.real, validacao.baseline), 2)},
                "backtest": [{"data": data.date().isoformat(), "real": int(real), "previsto": round(float(previsto), 2), "baseline": int(baseline)} for data, real, previsto, baseline in zip(teste.data_alvo, teste.real, previsto_teste, teste.baseline)],
            })
    return {
        "snapshot": fim.date().isoformat(), "previsoes": resultados,
        "nota": "Previsões independentes por prioridade original, com todos os incidentes P2/P3. Não somam necessariamente à previsão total. D+7 representa um dia, não o acumulado semanal. A faixa usa 80% dos erros absolutos de validação, sem garantia de cobertura futura.",
        "metodo": "Seleção entre Ridge e repetição semanal em janela anterior ao teste. Treino usa somente alvos conhecidos antes de cada janela. Avaliação usa contagens disponíveis no fechamento de cada dia-base. Reajuste final usa o histórico completo para prever após o fim da base.",
    }
