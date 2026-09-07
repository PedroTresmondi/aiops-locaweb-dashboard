# Evidências do sistema — visionOps AI / AIOps SLA Monitor

Material de apoio para o PPTX e o vídeo pitch da Sprint 4. Todos os números vêm de
execução real sobre o snapshot `dataset_limpo.parquet` (sem dado sintético) e são
reproduzíveis com `python -m unittest discover -s tests` (30 testes, todos passando).

Última atualização: 2026-09-07.

---

## 1. O que é o sistema

Aplicação full-stack que transforma o histórico anonimizado de incidentes da Locaweb em:

- **previsão de volume** de incidentes para D+1 e D+7;
- **triagem preditiva de risco de violação de OLA** no momento da abertura;
- **fila operacional em lote** — pontua um dia de chamados e ordena por risco;
- **alocação preventiva** (otimização matemática) e **segmentação de criticidade**;
- **monitor de deriva de dados** com recomendação de retreino.

Frontend React + TypeScript · Backend FastAPI · pipelines em scikit-learn. A mesma API
serve o contrato legado da Sprint 3 (`/health`, `/incidentes/total`, `/previsao`,
`/previsao/historico`).

### Onde está no ar

| Interface | URL | Estado |
|---|---|---|
| Streamlit (contingência) | https://fjhkvpspqbtpzlkhpgscvr.streamlit.app/ | no ar (deploy automático a cada push) |
| React + FastAPI (Azure Web App) | https://visionops-ai-fiap-esdshub2ceexe2er.eastus-01.azurewebsites.net/ | **parado** — religar antes da banca (`Stop`/`Start` no portal) |

---

## 2. Base de dados (números auditados)

| Métrica | Valor |
|---|---|
| Incidentes no snapshot | **122.543** |
| Período | 02/01/2023 a 31/12/2025 |
| Elegíveis ao KPI (prioridade 1–3, sem incidente pai, com intervenção) | **25.751** |
| Violações de OLA na base completa | 7.090 (5,79%) |
| Violações de OLA no universo elegível | **3.685 → taxa de 14,31%** |

**Quebra de regime:** o volume mensal saltou de ~3.996 (ago/2025) para ~21.561 (set/2025).
Mais da metade dos dias de teste ficam acima do maior valor visto no treino — por isso
modelos de árvore puros (Random Forest, Gradient Boosting, Extra Trees) dão R² negativo:
é limitação estrutural de extrapolação, não erro de implementação.

---

## 3. Arquitetura (Azure — mesma da Sprint 3)

```
dataset real ──► Azure Container Registry ──► Azure Web App (Container, FastAPI) ──► Azure Database for MySQL
 (LW-DATASET)     acraiopsvisionopsai          visionops-ai-fiap (Linux, B1)          mysql-aiops-visionopsai
                                                      │                                (Chile Central, Entra-only)
                                       Managed Identity id-aiops-visionopsai (sem senha)
                                                      │
                                        Application Insights ──► Log Analytics Workspace
```

- **Resource Group:** `rg-aiops-sprint3-visionopsai` (East US)
- **Imagem:** `acraiopsvisionopsai.azurecr.io/visionops-ai:v1`, construída com
  `az acr build --registry acraiopsvisionopsai --image visionops-ai:v1 <URL do repo GitHub>`
  (commit da imagem: `26033c0`)
- **Plano:** App Service B1 (1,75 GB / 1 vCPU) — ~US$ 12,41/mês no crédito Azure for Students
- **Fonte de dados:** `VISIONOPS_DATASOURCE=parquet` (padrão) ou `mysql` (passwordless)
- Runbook completo em `DEPLOY_AZURE.md`.

---

## 4. Modelos e validação

### 4.1 Previsão de volume — benchmark amplo da Sprint 3 (reproduzido, não mudou)

Teste: últimos 20% da série (27/05/2025 a 24/12/2025), sem embaralhamento.

| Horizonte | MAE | RMSE | R² |
|---|---:|---:|---:|
| D+1 | 187,58 | **275,83** | 0,394 |
| Dia +7 | 181,22 | **267,13** | 0,436 |

### 4.2 Previsão de volume — ensemble operacional (Sprint 4, publicado)

Pesos escolhidos em 3 validações móveis de out/nov 2025; **dezembro/2025 como holdout final**.

| Horizonte | Modelo | MAE holdout | RMSE holdout | R² holdout | WAPE | Ganho vs. baseline |
|---|---|---:|---:|---:|---:|---:|
| D+1 | 30% Linear Sprint 3 + 70% Ridge (sinais do dia-base) | **115,35** | 149,26 | 0,045 | 13,09% | **14,23%** |
| Dia +7 | 20% Linear Sprint 3 + 80% Extra Trees (regime pós-set) | **128,98** | 175,95 | −0,327 | 14,64% | 2,02% |

Previsões finais (limite do snapshot): **D+1 (01/01/2026) = 914** [762–1.084] ·
**dia +7 (07/01/2026) = 970** [799–1.233].

### 4.3 Previsão de volume — modelo avançado (extensão Sprint 4)

Adiciona **feriados nacionais do Brasil** (fixos + móveis via cálculo da Páscoa — fatos de
calendário, 38 no período), **perda de Poisson** (respeita contagem, nunca gera negativo),
**pesos por recência** (meia-vida 90 dias) e **validação por origem móvel (rolling-origin)**:
refit a cada 14 dias, **59 previsões diárias por horizonte** em vez do holdout único.

| Horizonte | MAE avançado | MAE baseline linear | MAE ensemble operacional | Ganho vs. baseline |
|---|---:|---:|---:|---:|
| D+1 | 121,9 | 125,2 | 115,7 | **+2,6%** |
| Dia +7 | 133,7 | 138,4 | 135,3 | **+3,3%** |

**Leitura honesta:** o modelo avançado **ganha do baseline linear e empata com o ensemble
operacional** (que foi calibrado exatamente nessa janela). O diferencial real: é o único que
antecipa a queda em feriados — previsão para **01/01/2026 (feriado) = 885** contra 914 do
ensemble. Era exatamente a data que a Sprint 3 errava por não ter calendário. Fica documentado
como próxima evolução, validado da mesma forma auditável. Endpoint: `GET /api/models/advanced`.

### 4.4 Modelo de risco de OLA (classificador)

Treino: elegíveis anteriores a out/2025 · seleção/calibração: out–nov/2025 ·
**holdout: dezembro/2025 (1.438 incidentes, 125 violações)**. Ensemble 50% Extra Trees +
50% HistGradientBoosting, Platt scaling. Nenhuma feature usa duração/resolução/encerramento.

| Métrica (holdout) | Valor |
|---|---:|
| ROC-AUC | **0,775** |
| PR-AUC | 0,280 (prevalência 8,7%) |
| Brier | 0,074 |
| Corte da fila alta — casos revisados | 15,8% |
| Violações capturadas na fila alta | **39,2%** |
| Lift da fila alta | **2,48×** |

---

## 5. Fluxos funcionais (com números reais)

### Fila operacional em lote
Carrega os chamados elegíveis de um dia real do snapshot (ou um CSV), pontua todos com o
modelo de risco validado e ordena por probabilidade. Cada chamado abre a contribuição de
cada fator (delta do próprio modelo + taxa histórica). Ações (atribuído/escalado/resolvido/
dispensado) persistem em SQLite.

Exemplo — **18/11/2025** (janela de validação): 61 chamados · 8 em risco alto · 6,2 violações
esperadas (soma das probabilidades) · **63,4% do risco no top 20% da fila** · das 5 violações
reais do dia, 3 caem nos primeiros 20%.

### Alocação preventiva — MILP (Seção 18 do notebook de ML)
Programação linear inteira via `scipy.optimize.milp`. Com capacidade de 5 produtos/dia:
**cobre 66,0% do risco estimado de OLA em D+1**, seleciona `lsin, lhco, lcem, lhvp, lcsi`.
Preço-sombra: ~54,7 violações cobertas por vaga adicional na margem.

### Segmentação de criticidade — K-Means (Seção 17 do notebook de ML)
K escolhido por Coeficiente de Silhueta. Por produto: **K=4**. O cluster mais crítico tem só
3 produtos mas **taxa média de violação de 50,8%** — contra 1,6% do cluster menos crítico.
A ordenação simples por soma não separa isso.

### Monitor de deriva de dados (PSI)
Compara a janela de treino do classificador com os últimos 30 dias do snapshot.
**Pior PSI = 7,67** no volume diário de elegíveis (limite de alerta: 0,20) — reflexo da
quebra de regime de setembro. Snapshot com **249 dias**, acima do ciclo alvo de 45 dias.
Conclusão do monitor: **revalidação/retreino recomendado**.

---

## 6. Testes automatizados

`python -m unittest discover -s tests -v` → **30 testes, todos passando** (~28 s):

- `test_pipeline.py` — métricas de OLA auditadas, RMSE Sprint 3 (275,83 / 267,13), ensemble operacional (115,35 / 128,98)
- `test_risk_pipeline.py` — holdout temporal de dezembro, sem vazamento de alvo, ROC-AUC > 0,75
- `test_api.py` — contrato da API, 122.543 / 25.751 / 3.685
- `test_sprint4.py` — fila em lote, ações, deriva, otimização, segmentação, endpoints legados
- `test_advanced_model.py` — feriados nacionais, backtest rolling-origin (≥ 40 pontos), ganho vs. baseline

---

## 7. Como capturar prints para o PPTX

App local: `uvicorn backend.main:app --port 8000` (a partir da raiz do repo, com o
`frontend/dist` já buildado) → `http://localhost:8000`. Primeira carga ~60–90 s (treina os
modelos). Páginas que valem print:

1. **Visão operacional** — cards 914 / 970 / 14,31% / 39,2% + "Pulso da operação"
2. **Fila operacional** — data 18/11/2025, tabela ordenada por risco + linha de conferência
3. **Alocação preventiva** — cobertura 66% + curva de sensibilidade
4. **Monitor de dados** — alerta de revalidação + tabela de PSI
5. **Modelos & validação** — tabela do holdout + painel "Modelo avançado" (backtest rolling-origin)

Para a demo ao vivo: religar o Azure Web App (`Start`) uns minutos antes e abrir a URL para
aquecer os modelos.
