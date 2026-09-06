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
- Previsões recalculadas em execução pela Regressão Linear vencedora da Sprint 3, com
  18 features temporais sem vazamento de alvo.

O app identifica explicitamente cada elemento como observado, resultado do modelo, cenário
ou recomendação. Não há geração de métricas sintéticas nem chamadas a IA generativa.

## Validação temporal reproduzida

| Horizonte | MAE | RMSE | R² | Viés médio (real − previsto) |
|---|---:|---:|---:|---:|
| D+1 | 187,58 | 275,83 | 0,394 | +165,71 |
| Dia +7 | 181,22 | 267,13 | 0,436 | −88,05 |

O teste usa os últimos 20% da série, de 27/05/2025 a 24/12/2025, sem embaralhamento.
Random Forest, Gradient Boosting e Extra Trees são recalculados como benchmark; todos tiveram
R² negativo nesse corte. O histórico contém uma quebra de regime forte em setembro de 2025,
por isso o app também mostra o viés e faixas empíricas de 80%, não apenas o ponto previsto.

Com o snapshot atual, o modelo final — reajustado depois da validação com todos os alvos já
conhecidos — estima:

- **D+1 (01/01/2026): 962**, faixa empírica de **914 a 1.424** incidentes;
- **dia +7 (07/01/2026): 1.313**, faixa empírica de **929 a 1.398** incidentes.

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

Os antigos artefatos de Random Forest foram removidos da versão ativa para não misturar um
experimento posterior de 21 dias com o modelo e a janela definidos na Sprint 3.

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
