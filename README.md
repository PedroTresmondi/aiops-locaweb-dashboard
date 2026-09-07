# visionOps AI — Central de Operações

Aplicação full-stack do Challenge FIAP × Locaweb 2026. O frontend em React + TypeScript
consome uma API FastAPI que reaproveita os pipelines Python validados. A solução transforma
o histórico anonimizado de incidentes em previsão de volume, triagem preditiva de OLA,
diagnóstico de ofensores e dimensionamento de capacidade.

Versão Streamlit publicada: <https://fjhkvpspqbtpzlkhpgscvr.streamlit.app/>. Ela permanece
como demonstração compatível; a interface principal está em `frontend/`.

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

## Fluxos funcionais da Sprint 4

- **Central operacional:** resume volume, faixa prevista, OLA e sinais prioritários.
- **Fila operacional (lote):** carrega os chamados de um dia real do snapshot **ou** um CSV,
  pontua todos com o modelo de risco validado, ordena por probabilidade de violação e exporta
  a fila. Cada chamado abre a contribuição individual de cada fator (delta do próprio modelo +
  taxa histórica). As ações — atribuído, escalado, resolvido, dispensado — ficam registradas
  em um banco operacional (SQLite) separado do snapshot. O acompanhamento mede *risco
  priorizado para intervenção*, não *violações evitadas*.
- **Triagem preditiva:** recebe prioridade, data/hora, produto, categoria e grupo e calcula
  risco calibrado de violação usando apenas informações disponíveis na abertura. A ficha de
  decisão pode ser baixada em CSV.
- **Diagnóstico de OLA:** cruza categoria, produto e grupo; mede escala, taxa, lift, excesso
  de duração e recorrência; abre o histórico mensal da causa selecionada e exporta a fila.
  Inclui a **segmentação de criticidade por K-Means** (Seção 17 do notebook de ML),
  recalculada sobre o snapshot atual.
- **Alocação preventiva:** porta a **Seção 18 do notebook de ML** (programação linear inteira)
  para dentro da API — dada a previsão real de volume D+1, quais produtos revisar amanhã para
  cobrir o máximo de risco de OLA. Capacidade e limite por categoria são parâmetros ajustáveis;
  a tela mostra a curva de sensibilidade e o preço-sombra da capacidade.
- **Capacidade & ação:** converte a faixa D+1 em analistas-equivalentes a partir de premissas
  editáveis de produtividade, ocupação, indisponibilidade e equipe disponível.
- **Monitor de dados:** compara a janela de treino do classificador com os dados recentes via
  PSI (Population Stability Index) e sinaliza quando a revalidação/retreino é recomendada —
  atende à recomendação registrada na Sprint 3 (retreinar periodicamente com janela recente).
- **Modelos & auditoria:** expõe holdouts temporais, benchmarks, calibração, importância das
  features, regras do KPI, cobertura dos campos e registros filtrados.
- **Perfis operacionais:** seletor Analista / Gestor / Administrador na barra lateral. É uma
  visão de trabalho (o perfil Gestor não registra ações), **não** um mecanismo de autenticação.

## Arquitetura e contrato legado

A aplicação é a mesma da arquitetura Azure da Sprint 3: imagem no Azure Container Registry,
execução no Azure Container Instance, banco Azure Database for MySQL (passwordless via Managed
Identity) e telemetria no Application Insights / Log Analytics. Passos em `DEPLOY_AZURE.md`.

- **Fonte de dados:** `VISIONOPS_DATASOURCE=parquet` (padrão, snapshot auditado) ou `mysql`
  (Azure). O resto do código não muda.
- **Endpoints legados da Sprint 3** (usados no vídeo pitch e nas evidências), servidos pela
  mesma aplicação: `GET /health`, `GET /incidentes/total`, `GET /previsao` (previsão real
  D+1/D+7 para os 4 alvos, persistida), `GET /previsao/historico`.
- **Telemetria:** ativa só quando `APPLICATIONINSIGHTS_CONNECTION_STRING` está no ambiente;
  fora do Azure o app funciona igual, sem telemetria.

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

## Modelo de risco de OLA

O segundo modelo atende à triagem de incidentes elegíveis (P1–P3) e não usa duração,
resolução, encerramento ou o próprio alvo como feature. O desenho temporal é:

- treino: histórico anterior a outubro de 2025;
- seleção e calibração: outubro e novembro de 2025;
- holdout final: dezembro de 2025, com 1.438 incidentes e 125 violações.

O ensemble escolhido antes do holdout combina 50% Extra Trees e 50%
HistGradientBoosting, com Platt scaling para converter o score balanceado em probabilidade.
No holdout, obteve ROC-AUC **0,775**, PR-AUC **0,280** e Brier **0,074**. Aplicando o corte
da fila alta definido na validação, revisa **15,8%** dos incidentes e captura **39,2%** das
violações, com lift de **2,48×** sobre a prevalência do mês. O score apoia a decisão; não
deve automatizar atribuição de culpa ou bloqueio de atendimento.

## Estrutura

```text
aiops-locaweb-dashboard/
├── frontend/                 # aplicação React + TypeScript responsiva
├── backend/
│   ├── main.py               # API FastAPI e servidor do build React
│   ├── datasource.py         # fonte de incidentes: Parquet (padrão) ou Azure MySQL
│   ├── store.py              # estado operacional (SQLite): fila, ações, histórico legado
│   ├── monitoring.py         # deriva de dados (PSI) janela recente vs. treino
│   ├── optimization.py       # alocação preventiva D+1 (MILP — Seção 18 do notebook)
│   ├── segmentation.py       # segmentação de criticidade K-Means (Seção 17 do notebook)
│   ├── legacy_forecast.py    # contrato /previsao da Sprint 3 (4 alvos × D+1/D+7)
│   ├── telemetry.py          # Application Insights (opcional, só no Azure)
│   ├── requirements.txt      # dependências da API
│   └── requirements-azure.txt # extras só para o deploy no Azure (MySQL + telemetria)
├── app.py                    # versão Streamlit de contingência
├── model_pipeline.py         # features, validação, benchmark e treino final
├── risk_pipeline.py          # classificação e calibração temporal de risco de OLA
├── dataset_limpo.parquet     # base tratada e regras auditadas de OLA
├── tests/
│   ├── test_pipeline.py      # testes da previsão de volume
│   ├── test_risk_pipeline.py # testes da triagem preditiva
│   ├── test_api.py           # contrato e métricas da API
│   └── test_sprint4.py       # fila em lote, ações, deriva, otimização, segmentação, legado
├── Dockerfile                # build único de frontend + backend (ACR/ACI)
├── DEPLOY_AZURE.md           # runbook de publicação no Azure
├── render.yaml               # deploy alternativo como Web Service
├── requirements.txt
└── README.md
```

Os antigos artefatos isolados de Random Forest foram removidos para não misturar um experimento
posterior de 21 dias com a validação atual. O novo pipeline recalcula baseline, componentes,
pesos, holdout e previsões diretamente da base.

## Rodar a aplicação React + FastAPI localmente

Terminal 1:

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Terminal 2:

```bash
cd frontend
npm install
npm run dev
```

Abra `http://localhost:5173`. Para simular produção, execute `npm run build` dentro de
`frontend/` e acesse `http://localhost:8000`; o FastAPI servirá o build estático.

## Rodar a versão Streamlit

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy full-stack

O `Dockerfile` gera o frontend e publica React + API no mesmo serviço. No Render, importe
o repositório como Blueprint usando `render.yaml`. A versão React não roda no Streamlit
Community Cloud porque essa plataforma espera um processo Streamlit, não uma API ASGI.

## Testar

```bash
python -m unittest discover -s tests -v
```

## Limites de uso

- O dataset é um snapshot; a leitura via MySQL usa a mesma carga de 122.543 incidentes. Não há
  ingestão contínua — o Monitor de dados existe justamente para sinalizar quando o snapshot
  ficou velho demais ou a distribuição mudou.
- O forecast prevê volume total; o classificador de OLA estima risco de incidentes elegíveis.
  A fila operacional pontua um lote (dia real do snapshot ou CSV), não um feed ao vivo.
- Na fila do snapshot, o campo "violou" é o resultado real do incidente — serve só para
  conferir a ordenação; não estava disponível na abertura e não entra no modelo.
- Coeficientes e contribuições por fator descrevem o comportamento do modelo, não causalidade.
- Converter volume em headcount exige produtividade/tempo por analista, ausentes na fonte;
  por isso o simulador torna essas premissas explícitas e editáveis.
- O registro de ações mede risco endereçado (soma das probabilidades dos chamados com ação),
  **não** violações evitadas. A cobertura histórica do cenário de priorização também não.
- A alocação preventiva (MILP) usa capacidade e custo por produto como parâmetros ilustrativos
  — precisam ser calibrados com a operação real da Locaweb.
- O perfil operacional é uma visão de trabalho, não autenticação.
