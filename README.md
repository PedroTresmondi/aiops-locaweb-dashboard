# AIOps Locaweb — Painel Operacional de Incidentes

Painel interativo (Streamlit) com previsão de volume de incidentes (D+1/D+7), risco de
violação de OLA e recomendações operacionais. Desenvolvido para o Challenge FIAP x Locaweb 2026.

Aplicação publicada: <https://fjhkvpspqbtpzlkhpgscvr.streamlit.app/>

## Decisões de modelagem

- **Benchmark histórico da Sprint 3:** a Regressão Linear foi o modelo que melhor generalizou no
  corte temporal amplo (D+1: MAE 187,58; RMSE 275,83; R² 0,394. D+7: MAE 181,22; RMSE 267,13;
  R² 0,436).
- **Modelo operacional do painel:** Random Forest retreinada no regime recente e avaliada nos
  últimos 21 dias (D+1: MAE 197,8; MAPE 19,8%. D+7: MAE 168,6; MAPE 16,8%). A distinção evita
  comparar resultados produzidos com janelas temporais diferentes como se fossem o mesmo teste.
- **OLA:** regra determinística e auditável conforme o Dicionário de Dados v2: 4 horas para P1/P2,
  12 horas para P3, 24 horas para P4 e 96 horas para P5. No recorte de KPI, entram prioridades
  1–3, sem incidente pai e com intervenção. São 7.090 violações na base completa (5,79%) e 3.685
  entre 25.751 incidentes elegíveis (14,31%). As flags originais permanecem no parquet apenas para
  rastreabilidade.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`.

## Publicar de graça (Streamlit Community Cloud) — ~10 minutos

1. Crie uma conta gratuita em **share.streamlit.io** (pode entrar direto com sua conta GitHub).
2. Crie um repositório no **GitHub** e envie os arquivos listados na estrutura abaixo.
3. No Streamlit Community Cloud, clique em **"New app"**, escolha o repositório que você
   acabou de criar, selecione o arquivo `app.py` como arquivo principal, e clique em **Deploy**.
4. Após o deploy, use a URL pública no slide de demonstração e na planilha final.

## Estrutura

```
aiops-locaweb-dashboard/
├── app.py                          # aplicação Streamlit
├── requirements.txt
├── dataset_limpo.parquet           # base tratada, com regras oficiais de OLA
├── serie_features.csv              # série diária agregada + features
├── teste_previsao_d1.csv
├── teste_previsao_d7.csv
├── ranking_categorias_risco.csv
├── metricas.json
├── rf_d1.joblib                    # Random Forest operacional D+1
├── rf_d7.joblib                    # Random Forest operacional D+7
└── features_list.joblib
```

## O que o painel mostra

- **🏠 Painel do Dia**: previsão automática real de D+1 e D+7 — calculada ao vivo aplicando os
  modelos sobre o último dia efetivamente registrado na base (não é hipotética) — mais alertas
  de categorias em alta (últimos 14 dias vs. 14 dias anteriores), calculados por consulta direta
  à base de dados a cada carregamento.
- **🔍 Explorar Dados**: consulta interativa à base completa (122 mil incidentes) com filtros por
  período, prioridade, categoria e equipe — gráfico e tabela recalculados na hora.
- **📊 Tendências**: sazonalidade por dia da semana, volume por prioridade (P2/P3).
- **🔮 Previsão & Simulador**: previsto vs. real no período de teste + simulador manual de cenários
  hipotéticos, rodando os modelos treinados ao vivo.
- **⚠️ Risco de OLA**: ranking de categorias mais críticas e indicadores recalculados pelas regras
  oficiais de elegibilidade e duração.
- **✅ Recomendações**: síntese acionável combinando achados fixos com alertas calculados na hora.
