# AIOps Locaweb — Painel de Previsão de Incidentes

Painel interativo (Streamlit) com previsão de volume de incidentes (D+1/D+7), risco de
violação de OLA e recomendações operacionais. Desenvolvido para o Challenge FIAP x Locaweb 2026.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`.

## Publicar de graça (Streamlit Community Cloud) — ~10 minutos

1. Crie uma conta gratuita em **share.streamlit.io** (pode entrar direto com sua conta GitHub).
2. Crie um repositório novo no **GitHub** (pode ser público) e suba TODO o conteúdo desta
   pasta `app/` (app.py, requirements.txt, a pasta `dados/` e a pasta `modelos/`) — pelo site
   do GitHub mesmo, arrastando os arquivos, sem precisar usar linha de comando se não quiser.
3. No Streamlit Community Cloud, clique em **"New app"**, escolha o repositório que você
   acabou de criar, selecione o arquivo `app.py` como arquivo principal, e clique em **Deploy**.
4. Em alguns minutos o app estará no ar com uma URL pública tipo
   `https://seu-usuario-seu-projeto.streamlit.app` — esse é o link que vai no slide de
   "Demonstração da Solução" e na planilha final.

## Estrutura

```
app/
├── app.py                 # aplicação Streamlit
├── requirements.txt
├── dados/
│   ├── dataset_limpo.parquet     # base completa tratada (122.543 incidentes), para consulta ao vivo
│   ├── serie_features.csv        # série diária agregada + features
│   ├── teste_previsao_d1.csv
│   ├── teste_previsao_d7.csv
│   ├── ranking_categorias_risco.csv
│   └── metricas.json
└── modelos/                # modelos treinados (Random Forest, scikit-learn)
    ├── rf_d1.joblib
    ├── rf_d7.joblib
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
- **⚠️ Risco de OLA**: ranking de categorias mais críticas + métricas do modelo de classificação.
- **✅ Recomendações**: síntese acionável combinando achados fixos com alertas calculados na hora.
