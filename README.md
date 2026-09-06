# visionOps AI — Central de Operações

Aplicação Streamlit do Challenge FIAP × Locaweb 2026. A solução transforma o histórico
anonimizado de incidentes em previsão de volume, priorização de risco de OLA, diagnóstico
de qualidade e plano de ação operacional.

Aplicação pública: <https://fjhkvpspqbtpzlkhpgscvr.streamlit.app/>

## O que é calculado de verdade

- **122.543 incidentes** do snapshot entre 02/01/2023 e 31/12/2025.
- **25.751 elegíveis ao KPI**, conforme prioridade 1–3, ausência de incidente pai e status
  diferente de `Sem Intervenção`.
- **3.685 violações dentro do universo elegível**, equivalentes a **14,31%**.
- **7.090 violações na base completa**, equivalentes a **5,79%**. Esse número não é usado
  como numerador da taxa sobre elegíveis.
- Previsões recalculadas em execução por ensembles operacionais validados no tempo. A
  Regressão Linear vencedora da Sprint 3 permanece reproduzida como baseline auditável.

O app identifica explicitamente cada elemento como observado, resultado do modelo, cenário
ou recomendação. Não há geração de métricas sintéticas nem chamadas a IA generativa.

## Modelo operacional validado

Os pesos foram escolhidos em três validações móveis de outubro/novembro de 2025. Dezembro
ficou completamente separado como holdout final:

| Horizonte | Ensemble | MAE | RMSE | R² | WAPE | MAE da Linear | Ganho |
|---|---|---:|---:|---:|---:|---:|---:|
| D+1 | 30% Linear Sprint 3 + 70% Ridge operacional | 115,35 | 149,26 | 0,045 | 13,09% | 134,49 | 14,23% |
| Dia +7 | 20% Linear Sprint 3 + 80% Extra Trees pós-setembro | 128,98 | 175,95 | −0,327 | 14,64% | 131,64 | 2,02% |

As features operacionais usam apenas dados conhecidos ao fechar o dia-base: volume atual,
elegíveis, OLA-base, lags, médias móveis, volatilidade e calendário do dia-alvo. O ganho vem
principalmente de incorporar o dia-base e de tratar separadamente o regime pós-setembro.
O critério de seleção é MAE. O R² do dia +7 fica negativo no único mês de holdout — uma
limitação mantida visível — e o ensemble precisa ser revalidado com novos meses.

## Benchmark amplo da Sprint 3 reproduzido

| Horizonte | MAE | RMSE | R² | Viés médio (real − previsto) |
|---|---:|---:|---:|---:|
| D+1 | 187,58 | 275,83 | 0,394 | +165,71 |
| Dia +7 | 181,22 | 267,13 | 0,436 | −88,05 |

O teste usa os últimos 20% da série, de 27/05/2025 a 24/12/2025, sem embaralhamento.
Random Forest, Gradient Boosting e Extra Trees são recalculados como benchmark; todos tiveram
R² negativo nesse corte. O histórico contém uma quebra de regime forte em setembro de 2025,
por isso o app também mostra o viés e faixas empíricas de 80%, não apenas o ponto previsto.

Com o snapshot atual, os componentes finais — reajustados depois da validação com todos os
alvos já conhecidos — estimam:

- **D+1 (01/01/2026): 914**, faixa empírica de **762 a 1.084** incidentes;
- **dia +7 (07/01/2026): 970**, faixa empírica de **799 a 1.233** incidentes.

Essas datas são consequência do limite da base, não previsões ao vivo para a data atual.
`Dia +7` significa o volume daquele dia, e não a soma dos próximos sete dias. O modelo não
possui indicador de feriado, limitação relevante para a estimativa de 01/01.

## Estrutura

```text
aiops-locaweb-dashboard/
├── app.py                    # interface e análises operacionais
├── model_pipeline.py         # features, validação, benchmark e treino final
├── dataset_limpo.parquet     # base tratada e regras auditadas de OLA
├── tests/
│   └── test_pipeline.py      # testes dos resultados centrais
├── requirements.txt
└── README.md
```

Os antigos artefatos isolados de Random Forest foram removidos para não misturar um experimento
posterior de 21 dias com a validação atual. O novo pipeline recalcula baseline, componentes,
pesos, holdout e previsões diretamente da base.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Testar

```bash
python -m unittest discover -s tests -v
```

## Limites de uso

- O dataset é um snapshot e não possui ingestão contínua.
- A previsão é de volume total; não prevê OLA, produto ou categoria individualmente.
- Coeficientes descrevem associação no modelo e não provam causalidade.
- Converter volume em headcount exige produtividade/tempo por analista, ausentes na fonte.
- A cobertura histórica do cenário de priorização não equivale a violações que seriam evitadas.
