import json
from pathlib import Path
from datetime import timedelta

import joblib
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

BASE = Path(__file__).parent


def _resolver_pasta(nome: str, arquivo_referencia: str) -> Path:
    """Encontra a pasta 'dados' ou 'modelos' testando vários layouts possíveis de
    deploy: subpasta normal, dentro de app/, ou tudo solto junto do app.py."""
    candidatos = [
        BASE / nome,
        BASE / "app" / nome,
        BASE.parent / nome,
        BASE,
        Path.cwd() / nome,
        Path.cwd() / "app" / nome,
        Path.cwd(),
    ]
    for candidato in candidatos:
        if (candidato / arquivo_referencia).exists():
            return candidato
    raise FileNotFoundError(
        f"Não encontrei '{arquivo_referencia}' em nenhum destes locais: "
        + ", ".join(str(c) for c in candidatos)
    )


DADOS = _resolver_pasta("dados", "dataset_limpo.parquet")
MODELOS = _resolver_pasta("modelos", "rf_d1.joblib")

st.set_page_config(page_title="AIOps Locaweb — Painel Operacional", page_icon="📈", layout="wide")

DIAS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

# ---------------------------------------------------------------
# Carregamento (cacheado) — consulta direta à base tratada
# ---------------------------------------------------------------
@st.cache_data
def carregar_base_bruta():
    df = pd.read_parquet(DADOS / "dataset_limpo.parquet")
    df["Aberto"] = pd.to_datetime(df["Aberto"])
    return df

@st.cache_data
def carregar_serie():
    serie = pd.read_csv(DADOS / "serie_features.csv", parse_dates=["Aberto"]).rename(columns={"Aberto": "Data"})
    return serie

@st.cache_data
def carregar_auxiliares():
    teste_d1 = pd.read_csv(DADOS / "teste_previsao_d1.csv", index_col=0, parse_dates=True)
    teste_d7 = pd.read_csv(DADOS / "teste_previsao_d7.csv", index_col=0, parse_dates=True)
    ranking = pd.read_csv(DADOS / "ranking_categorias_risco.csv")
    with open(DADOS / "metricas.json") as f:
        metricas = json.load(f)
    return teste_d1, teste_d7, ranking, metricas

@st.cache_resource
def carregar_modelos():
    rf_d1 = joblib.load(MODELOS / "rf_d1.joblib")
    rf_d7 = joblib.load(MODELOS / "rf_d7.joblib")
    features = joblib.load(MODELOS / "features_list.joblib")
    return rf_d1, rf_d7, features

df_raw = carregar_base_bruta()
serie = carregar_serie()
teste_d1, teste_d7, ranking, metricas = carregar_auxiliares()
rf_d1, rf_d7, FEATURES = carregar_modelos()

# ---------------------------------------------------------------
# Previsão automática real (a partir do último dia efetivamente registrado)
# ---------------------------------------------------------------
@st.cache_data
def prever_proximo_periodo():
    ultima_linha_valida = serie.dropna(subset=FEATURES).iloc[[-1]]
    data_base = ultima_linha_valida["Data"].iloc[0]
    x = ultima_linha_valida[FEATURES]
    pred_d1 = float(rf_d1.predict(x)[0])
    pred_d7 = float(rf_d7.predict(x)[0])
    return data_base, pred_d1, pred_d7

data_base, prev_d1_auto, prev_d7_auto = prever_proximo_periodo()

# ---------------------------------------------------------------
# Tendências dinâmicas por categoria (consulta ao vivo na base bruta)
# ---------------------------------------------------------------
@st.cache_data
def calcular_categorias_em_alta(min_incidentes=20):
    base = df_raw[df_raw["Categoria"].notna()]
    data_max = base["Aberto"].max()
    janela_recente = base[base["Aberto"] > data_max - timedelta(days=14)]
    janela_anterior = base[
        (base["Aberto"] <= data_max - timedelta(days=14)) &
        (base["Aberto"] > data_max - timedelta(days=28))
    ]
    recente = janela_recente.groupby("Categoria").size().rename("recente")
    anterior = janela_anterior.groupby("Categoria").size().rename("anterior")
    comp = pd.concat([recente, anterior], axis=1).fillna(0)
    comp = comp[comp["recente"] >= min_incidentes]
    comp["variacao_%"] = ((comp["recente"] - comp["anterior"]) / comp["anterior"].replace(0, 1) * 100).round(1)
    return comp.sort_values("variacao_%", ascending=False)

tendencias = calcular_categorias_em_alta()

# ---------------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------------
st.title("📈 AIOps Locaweb — Painel Operacional de Incidentes")
st.caption("Challenge FIAP x Locaweb 2026 · Consulta em tempo real à base de incidentes + modelos preditivos")

tab_home, tab_explorar, tab_tend, tab_prev, tab_ola, tab_rec = st.tabs([
    "🏠 Painel do Dia", "🔍 Explorar Dados", "📊 Tendências", "🔮 Previsão & Simulador",
    "⚠️ Risco de OLA", "✅ Recomendações",
])

# ---------------------------------------------------------------
# TAB — Painel do Dia (previsão automática real + alertas)
# ---------------------------------------------------------------
with tab_home:
    st.subheader(f"Previsão automática — base atualizada até {data_base:%d/%m/%Y}")
    st.caption("Calculada agora, ao vivo, aplicando os modelos treinados sobre o último dia real registrado na base.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Previsto para {(data_base + timedelta(days=1)):%d/%m}", f"{prev_d1_auto:.0f} incidentes")
    c2.metric(f"Previsto para {(data_base + timedelta(days=7)):%d/%m}", f"{prev_d7_auto:.0f} incidentes")
    c3.metric("Erro médio do modelo (D+1)", f"{metricas['mape_d1']}%")
    c4.metric("Erro médio do modelo (D+7)", f"{metricas['mape_d7']}%")

    st.divider()
    col1, col2 = st.columns([1.4, 1])
    with col1:
        st.markdown("**Volume real — últimos 30 dias + previsão**")
        cauda = serie.tail(30)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=cauda["Data"], y=cauda["Total"], name="Real", line=dict(color="#1a1a1a", width=2)))
        fig.add_trace(go.Scatter(
            x=[data_base + timedelta(days=1), data_base + timedelta(days=7)],
            y=[prev_d1_auto, prev_d7_auto],
            mode="markers+text", name="Previsão",
            marker=dict(color="#C8102E", size=12, symbol="star"),
            text=["D+1", "D+7"], textposition="top center",
        ))
        fig.update_layout(height=380, hovermode="x unified", margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")
    with col2:
        st.markdown("**🚨 Categorias em alta (14 dias vs. 14 dias anteriores)**")
        if len(tendencias) > 0:
            for cat, row in tendencias.head(5).iterrows():
                seta = "🔺" if row["variacao_%"] > 0 else "🔻"
                st.write(f"{seta} **{cat}** — {row['recente']:.0f} incidentes ({row['variacao_%']:+.0f}%)")
        else:
            st.write("Sem categorias com volume suficiente para comparação no período.")

    st.info(
        f"**Ruído de monitoramento:** {metricas['pct_ruido_monitoramento']}% dos incidentes são abertos "
        f"automaticamente, e {metricas['pct_sem_intervencao_monitoramento']}% destes fecham sem intervenção "
        "humana — oportunidade de triagem automática para reduzir carga operacional."
    )

# ---------------------------------------------------------------
# TAB — Explorar Dados (consulta ao vivo na base)
# ---------------------------------------------------------------
with tab_explorar:
    st.subheader("Consulta interativa à base de incidentes")
    st.caption(f"{len(df_raw):,} incidentes carregados diretamente da base tratada".replace(",", "."))

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        periodo = st.date_input(
            "Período", value=(df_raw["Aberto"].min().date(), df_raw["Aberto"].max().date()),
            min_value=df_raw["Aberto"].min().date(), max_value=df_raw["Aberto"].max().date(),
        )
    with f2:
        prioridades = st.multiselect("Prioridade", sorted(df_raw["Prioridade"].dropna().unique()))
    with f3:
        categorias_disp = sorted(df_raw["Categoria"].dropna().unique())
        categorias_sel = st.multiselect("Categoria", categorias_disp)
    with f4:
        equipes = st.multiselect("Equipe", sorted(df_raw["Grupo designado"].dropna().unique()))

    filtrado = df_raw.copy()
    if isinstance(periodo, tuple) and len(periodo) == 2:
        filtrado = filtrado[
            (filtrado["Aberto"].dt.date >= periodo[0]) & (filtrado["Aberto"].dt.date <= periodo[1])
        ]
    if prioridades:
        filtrado = filtrado[filtrado["Prioridade"].isin(prioridades)]
    if categorias_sel:
        filtrado = filtrado[filtrado["Categoria"].isin(categorias_sel)]
    if equipes:
        filtrado = filtrado[filtrado["Grupo designado"].isin(equipes)]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Incidentes no filtro", f"{len(filtrado):,}".replace(",", "."))
    m2.metric("Duração média", f"{filtrado['Duracao_Horas'].mean():.1f} h" if len(filtrado) else "—")
    m3.metric("% sem intervenção", f"{(filtrado['Status'] == 'Sem Intervenção').mean()*100:.1f}%" if len(filtrado) else "—")
    m4.metric("% violaram OLA", f"{filtrado['KPI_Violado'].mean()*100:.2f}%" if len(filtrado) else "—")

    if len(filtrado) > 0:
        diario_filtro = filtrado.groupby(filtrado["Aberto"].dt.date).size()
        fig = px.bar(x=diario_filtro.index, y=diario_filtro.values, labels={"x": "Data", "y": "Nº de incidentes"})
        fig.update_traces(marker_color="#C8102E")
        fig.update_layout(height=320, margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")

        st.markdown("**Amostra dos incidentes filtrados**")
        st.dataframe(
            filtrado.sort_values("Aberto", ascending=False)
            [["Número", "Aberto", "Prioridade", "Categoria", "Produto", "Grupo designado", "Duracao_Horas", "Status"]]
            .head(500),
            width="stretch", hide_index=True,
        )
    else:
        st.warning("Nenhum incidente encontrado para os filtros selecionados.")

# ---------------------------------------------------------------
# TAB — Tendências (histórico e sazonalidade)
# ---------------------------------------------------------------
with tab_tend:
    st.subheader("Tendência diária de incidentes (regime atual, pós 02/09/2025)")
    janela = st.slider("Janela de dias exibida", 30, len(serie), min(90, len(serie)))
    s = serie.tail(janela)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s["Data"], y=s["Total"], name="Total diário", line=dict(color="#C8102E", width=1.3)))
    fig.add_trace(go.Scatter(x=s["Data"], y=s["Total"].rolling(7).mean(), name="Média móvel 7d", line=dict(color="#1a1a1a", width=2.5)))
    fig.update_layout(height=420, hovermode="x unified", margin=dict(t=20))
    st.plotly_chart(fig, width="stretch")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Volume médio por dia da semana**")
        by_dow = serie.groupby("dow")["Total"].mean().reindex(range(7))
        fig2 = go.Figure(go.Bar(x=DIAS_PT, y=by_dow.values, marker_color="#C8102E"))
        fig2.update_layout(height=330, margin=dict(t=10))
        st.plotly_chart(fig2, width="stretch")
    with col2:
        st.markdown("**Volume diário: P2 (Alta) vs P3 (Média)**")
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=s["Data"], y=s["P2"], name="P2 - Alta", line=dict(color="#C8102E")))
        fig3.add_trace(go.Scatter(x=s["Data"], y=s["P3"], name="P3 - Média", line=dict(color="#1a1a1a")))
        fig3.update_layout(height=330, margin=dict(t=10), hovermode="x unified")
        st.plotly_chart(fig3, width="stretch")

# ---------------------------------------------------------------
# TAB — Previsão & Simulador
# ---------------------------------------------------------------
with tab_prev:
    st.subheader("Previsto vs. Real — período de teste (últimos 21 dias do histórico)")
    colA, colB = st.columns(2)
    with colA:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=teste_d1.index, y=teste_d1["target_d1"], name="Real", mode="lines+markers", line=dict(color="#1a1a1a")))
        fig.add_trace(go.Scatter(x=teste_d1.index, y=teste_d1["previsto"], name="Previsto D+1", mode="lines+markers", line=dict(color="#C8102E")))
        fig.update_layout(title=f"D+1 (MAE {metricas['mae_d1']} · MAPE {metricas['mape_d1']}%)", height=380, hovermode="x unified", margin=dict(t=40))
        st.plotly_chart(fig, width="stretch")
    with colB:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=teste_d7.index, y=teste_d7["target_d7"], name="Real", mode="lines+markers", line=dict(color="#1a1a1a")))
        fig.add_trace(go.Scatter(x=teste_d7.index, y=teste_d7["previsto"], name="Previsto D+7", mode="lines+markers", line=dict(color="#C8102E")))
        fig.update_layout(title=f"D+7 (MAE {metricas['mae_d7']} · MAPE {metricas['mape_d7']}%)", height=380, hovermode="x unified", margin=dict(t=40))
        st.plotly_chart(fig, width="stretch")

    st.divider()
    st.subheader("🎛️ Simulador manual — 'e se o volume de ontem fosse X?'")
    st.caption("Ajuste os parâmetros abaixo para testar cenários hipotéticos, além da previsão automática do Painel do Dia.")

    ultimo = serie.dropna(subset=FEATURES).iloc[-1]
    col1, col2, col3 = st.columns(3)
    with col1:
        lag1_sim = st.slider("Incidentes registrados ontem", 0, int(serie["Total"].max()), int(ultimo["lag1"]))
    with col2:
        dow_sim = st.selectbox("Dia da semana de amanhã", DIAS_PT, index=int(ultimo["dow"]))
    with col3:
        st.metric("Últimos valores reais usados", f"lag7={int(ultimo['lag7'])}, mm7={ultimo['mm7']:.0f}")

    entrada = pd.DataFrame([{
        "dow": DIAS_PT.index(dow_sim),
        "is_weekend": int(DIAS_PT.index(dow_sim) >= 5),
        "lag1": lag1_sim,
        "lag2": ultimo["lag2"],
        "lag7": ultimo["lag7"],
        "mm3": (lag1_sim + ultimo["lag2"] + ultimo["lag7"]) / 3,
        "mm7": ultimo["mm7"],
        "p2_lag1": ultimo["p2_lag1"],
        "p3_lag1": ultimo["p3_lag1"],
    }])[FEATURES]

    pred_d1_sim = rf_d1.predict(entrada)[0]
    pred_d7_sim = rf_d7.predict(entrada)[0]
    r1, r2 = st.columns(2)
    r1.metric("📅 Cenário — amanhã (D+1)", f"{pred_d1_sim:.0f} incidentes")
    r2.metric("📅 Cenário — daqui 7 dias (D+7)", f"{pred_d7_sim:.0f} incidentes")

# ---------------------------------------------------------------
# TAB — Risco de OLA
# ---------------------------------------------------------------
with tab_ola:
    st.subheader("Ranking de categorias por risco de violação de OLA")
    st.caption("Base: incidentes elegíveis a KPI (prioridades 2 e 3), mínimo de 30 ocorrências por categoria")

    ranking_top = ranking.sort_values("violacoes", ascending=False).head(10)
    fig = go.Figure(go.Bar(
        x=ranking_top["violacoes"], y=ranking_top["Categoria"], orientation="h", marker_color="#C8102E",
        text=[f"{t}% de taxa" for t in ranking_top["taxa_violacao_%"]], textposition="outside",
    ))
    fig.update_layout(height=420, margin=dict(t=20), yaxis=dict(autorange="reversed"), xaxis_title="Nº de violações")
    st.plotly_chart(fig, width="stretch")

    col1, col2 = st.columns(2)
    col1.metric("Recall do modelo (violações capturadas)", f"{metricas['recall_viola_ola']*100:.0f}%")
    col2.metric("Precisão do modelo", f"{metricas['precision_viola_ola']*100:.1f}%")
    st.warning(
        "**Leitura honesta:** violação de OLA é um evento raro (~1% dos casos). O modelo foi calibrado "
        "para priorizar recall (captura a maioria das violações reais) ao custo de mais falsos positivos."
    )
    st.dataframe(ranking.sort_values("violacoes", ascending=False), width="stretch", hide_index=True)

# ---------------------------------------------------------------
# TAB — Recomendações (dinâmicas + síntese)
# ---------------------------------------------------------------
with tab_rec:
    st.subheader("Recomendações — calculadas a partir dos dados atuais")

    if len(tendencias) > 0:
        top_alta = tendencias.head(3)
        st.markdown("**🚨 Prioridade imediata (categorias em alta nos últimos 14 dias):**")
        for cat, row in top_alta.iterrows():
            st.write(f"- **{cat}**: {row['recente']:.0f} incidentes recentes, variação de {row['variacao_%']:+.0f}% — investigar causa raiz esta semana.")

    st.markdown(f"""
**Síntese estrutural:**
1. **Reduzir ruído de monitoramento** — {metricas['pct_ruido_monitoramento']}% dos incidentes são abertos por
   monitoramento; {metricas['pct_sem_intervencao_monitoramento']}% destes fecham sem intervenção humana.
2. **Antecipação de volume** — modelo D+1/D+7 supera a previsão ingênua em 9–12%, com previsão automática
   disponível na aba "Painel do Dia".
3. **Atenção preventiva por categoria** — cat31, cat85 e cat71 concentram o maior volume de violações; cat48
   tem taxa de violação de 7,8% (quase 8x a média) — possível causa raiz isolada.
4. **Capacidade do Team14** — concentra 76% do volume total e é a variável mais associada ao risco de OLA.
5. **Próximos passos** — ampliar o histórico do regime atual e incorporar dados externos (deploys, janelas
   de manutenção) como features adicionais.
""")
    st.caption("Painel construído com Streamlit · Random Forest (scikit-learn) · Challenge FIAP x Locaweb 2026")
