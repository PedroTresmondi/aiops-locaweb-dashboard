from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from model_pipeline import executar_pipeline


BASE = Path(__file__).parent
ARQUIVO_DADOS = BASE / "dataset_limpo.parquet"
NAVY, ORANGE, TEAL, BLUE = "#10243E", "#F15A29", "#008C95", "#2878B5"
RED, GOLD, MUTED, GRID = "#D63C45", "#D99A16", "#617085", "#E8EDF3"

st.set_page_config(
    page_title="visionOps AI | Central de Operações",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: #F5F7FA; color: #10243E; }
    [data-testid="stHeader"] { background: rgba(245,247,250,.86); }
    [data-testid="stSidebar"] { background: #0E2038; border-right: 0; }
    [data-testid="stSidebar"] * { color: #F7FAFC; }
    [data-testid="stSidebar"] [role="radiogroup"] label {
        padding: .62rem .72rem; border-radius: 10px; margin: .12rem 0;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
        background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.12);
    }
    .block-container { padding-top: 1.8rem; padding-bottom: 3rem; max-width: 1500px; }
    h1, h2, h3 { color: #10243E; letter-spacing: -.025em; }
    h1 { font-weight: 800; font-size: 2rem; }
    h2 { font-weight: 750; font-size: 1.35rem; margin-top: .25rem; }
    .eyebrow { color: #F15A29; font-weight: 800; font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; }
    .page-subtitle { color: #617085; font-size: .94rem; margin-top: -.55rem; margin-bottom: 1.25rem; }
    .context-strip { display: flex; gap: .55rem; flex-wrap: wrap; margin: .3rem 0 1.2rem 0; }
    .pill {
        background: #FFFFFF; color: #33455C; border: 1px solid #DDE4EC;
        border-radius: 999px; padding: .35rem .65rem; font-size: .76rem; font-weight: 650;
    }
    .pill-model { background: #E9F7F7; color: #006B72; border-color: #BFE5E7; }
    .pill-alert { background: #FFF3E8; color: #A84018; border-color: #FFD3BD; }
    [data-testid="stMetric"] {
        background: #FFFFFF; border: 1px solid #E1E7EF; border-radius: 14px;
        padding: 1rem 1.05rem; box-shadow: 0 3px 12px rgba(16,36,62,.045);
    }
    [data-testid="stMetricLabel"] { color: #617085; font-weight: 650; }
    [data-testid="stMetricValue"] { color: #10243E; font-weight: 800; }
    [data-testid="stMetricDelta"] {
        color: #506176; background: #EEF2F6; border-radius: 999px;
        padding: .16rem .42rem; width: fit-content; font-weight: 600;
    }
    .action-card {
        background: #FFFFFF; border: 1px solid #E1E7EF; border-left: 4px solid #F15A29;
        border-radius: 12px; padding: .9rem 1rem; margin-bottom: .7rem;
        box-shadow: 0 3px 12px rgba(16,36,62,.04);
    }
    .action-card.teal { border-left-color: #008C95; }
    .action-card.gold { border-left-color: #D99A16; }
    .action-card.red { border-left-color: #D63C45; }
    .action-label { color: #617085; font-size: .68rem; font-weight: 800; letter-spacing: .09em; text-transform: uppercase; }
    .action-title { color: #10243E; font-size: .98rem; font-weight: 750; margin: .15rem 0 .2rem; }
    .action-copy { color: #506176; font-size: .84rem; line-height: 1.45; }
    .source-box {
        background: #EEF2F6; border-radius: 10px; padding: .75rem .85rem;
        color: #506176; font-size: .78rem; line-height: 1.45;
    }
    div[data-testid="stDataFrame"] { border: 1px solid #E1E7EF; border-radius: 12px; overflow: hidden; }
    .stTabs [data-baseweb="tab-list"] { gap: .35rem; }
    .stTabs [data-baseweb="tab"] { background: #EDF1F5; border-radius: 9px; padding: .35rem .8rem; }
    .stTabs [aria-selected="true"] { background: #10243E !important; color: white !important; }
    footer { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)


def fmt_int(valor: float | int) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def fmt_pct(valor: float, casas: int = 1) -> str:
    return f"{valor * 100:.{casas}f}%".replace(".", ",")


def fmt_num(valor: float, casas: int = 1) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def estilizar_figura(fig: go.Figure, altura: int = 390, legenda: bool = True) -> go.Figure:
    fig.update_layout(
        height=altura, margin=dict(l=10, r=15, t=25, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=NAVY, size=12),
        hoverlabel=dict(bgcolor="white", font_color=NAVY),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        showlegend=legenda,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def cabecalho(titulo: str, subtitulo: str, etiqueta: str) -> None:
    st.markdown(f'<div class="eyebrow">{etiqueta}</div>', unsafe_allow_html=True)
    st.title(titulo)
    st.markdown(f'<div class="page-subtitle">{subtitulo}</div>', unsafe_allow_html=True)


def card_acao(etiqueta: str, titulo: str, texto: str, cor: str = "") -> None:
    st.markdown(
        f"""<div class="action-card {cor}">
        <div class="action-label">{etiqueta}</div>
        <div class="action-title">{titulo}</div>
        <div class="action-copy">{texto}</div>
        </div>""",
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def carregar_dados() -> pd.DataFrame:
    df = pd.read_parquet(ARQUIVO_DADOS)
    df["Aberto"] = pd.to_datetime(df["Aberto"])
    df["Resolvido"] = pd.to_datetime(df["Resolvido"], errors="coerce")
    numero = next((c for c in df.columns if c.endswith("mero")), None)
    if numero and numero != "Número":
        df = df.rename(columns={numero: "Número"})
    mapa_prioridade = {
        1: "1 - Crítica", 2: "2 - Alta", 3: "3 - Média",
        4: "4 - Baixa", 5: "5 - Muito Baixa",
    }
    df["Prioridade"] = df["Prioridade_Cod"].map(mapa_prioridade)
    status = df["Status"].astype("string")
    df["Status_Exibicao"] = np.select(
        [
            status.str.upper().str.startswith("SEM INTERVEN", na=False),
            status.str.upper().eq("ENCERRADO AUTOMATICAMENTE"),
            status.str.upper().eq("ENCERRADO"),
            status.str.upper().eq("AGUARDANDO PROBLEMA"),
        ],
        ["Sem Intervenção", "Encerrado Automaticamente", "Encerrado", "Aguardando Problema"],
        default="Outro",
    )
    if "OLA_Violado_Regra" not in df:
        limites = df["Prioridade_Cod"].map({1: 4, 2: 4, 3: 12, 4: 24, 5: 96})
        df["OLA_Violado_Regra"] = df["Duracao_Horas"].gt(limites)
    if "Elegivel_KPI_Regra" not in df:
        sem_pai = df["Incidente Pai"].isna() | df["Incidente Pai"].astype(str).str.strip().eq("")
        com_intervencao = ~status.str.upper().str.startswith("SEM INTERVEN", na=False)
        df["Elegivel_KPI_Regra"] = df["Prioridade_Cod"].isin([1, 2, 3]) & sem_pai & com_intervencao
    if "OLA_Violado_KPI_Regra" not in df:
        df["OLA_Violado_KPI_Regra"] = (
            df["OLA_Violado_Regra"].astype(bool) & df["Elegivel_KPI_Regra"].astype(bool)
        )
    for coluna in ["OLA_Violado_Regra", "Elegivel_KPI_Regra", "OLA_Violado_KPI_Regra"]:
        df[coluna] = df[coluna].astype(bool)
    return df


@st.cache_resource(show_spinner="Recalculando modelo e validação temporal…")
def carregar_modelagem() -> object:
    return executar_pipeline(carregar_dados())


def ranking_ola(df: pd.DataFrame, coluna: str, minimo: int = 30) -> pd.DataFrame:
    elegiveis = df[df["Elegivel_KPI_Regra"]].copy()
    elegiveis["entidade"] = elegiveis[coluna].fillna("Não informado")
    ranking = (
        elegiveis.groupby("entidade")
        .agg(elegiveis=("Aberto", "size"), violacoes=("OLA_Violado_KPI_Regra", "sum"))
        .reset_index()
    )
    ranking = ranking[ranking["elegiveis"] >= minimo].copy()
    ranking["taxa_violacao"] = ranking["violacoes"] / ranking["elegiveis"]
    if ranking.empty:
        return ranking
    taxa_geral = elegiveis["OLA_Violado_KPI_Regra"].mean()
    mediana_volume = ranking["elegiveis"].median()
    ranking["quadrante"] = np.select(
        [
            (ranking["elegiveis"] >= mediana_volume) & (ranking["taxa_violacao"] >= taxa_geral),
            (ranking["elegiveis"] >= mediana_volume) & (ranking["taxa_violacao"] < taxa_geral),
            (ranking["elegiveis"] < mediana_volume) & (ranking["taxa_violacao"] >= taxa_geral),
        ],
        ["Escala crítica", "Alto volume", "Exceção crítica"],
        default="Monitorar",
    )
    ranking["participacao_violacoes"] = ranking["violacoes"] / max(1, ranking["violacoes"].sum())
    return ranking.sort_values(["violacoes", "taxa_violacao"], ascending=False)


def tendencias_recentes(df: pd.DataFrame) -> pd.DataFrame:
    conhecida = df[df["Categoria"].notna()].copy()
    data_max = conhecida["Aberto"].max().normalize()
    recente = conhecida[conhecida["Aberto"] >= data_max - pd.Timedelta(13, unit="D")]
    anterior = conhecida[
        (conhecida["Aberto"] >= data_max - pd.Timedelta(27, unit="D"))
        & (conhecida["Aberto"] < data_max - pd.Timedelta(13, unit="D"))
    ]
    atual = recente.groupby("Categoria").size().rename("ultimos_14d")
    antes = anterior.groupby("Categoria").size().rename("14d_anteriores")
    tabela = pd.concat([atual, antes], axis=1).fillna(0)
    tabela = tabela[tabela["ultimos_14d"] >= 20].copy()
    tabela["variacao"] = (
        (tabela["ultimos_14d"] - tabela["14d_anteriores"])
        / tabela["14d_anteriores"].replace(0, 1)
    )
    return tabela.sort_values("variacao", ascending=False).reset_index()


df = carregar_dados()
modelo = carregar_modelagem()
serie = modelo.serie
snapshot = df["Aberto"].max()
elegiveis = df[df["Elegivel_KPI_Regra"]]
total_violacoes_kpi = int(elegiveis["OLA_Violado_KPI_Regra"].sum())
taxa_ola = float(elegiveis["OLA_Violado_KPI_Regra"].mean())
violacoes_base = int(df["OLA_Violado_Regra"].sum())
previsao_d1 = modelo.previsoes["D+1"]
previsao_d7 = modelo.previsoes["D+7"]
tendencias = tendencias_recentes(df)
metricas_idx = modelo.metricas.set_index("horizonte")


with st.sidebar:
    st.markdown(
        """<div style="padding:.45rem .2rem 1.1rem">
        <div style="font-size:1.18rem;font-weight:800;letter-spacing:-.03em">◉ visionOps <span style="color:#F15A29">AI</span></div>
        <div style="font-size:.72rem;opacity:.68;margin-top:.2rem">OPERATIONS CONTROL CENTER</div>
        </div>""",
        unsafe_allow_html=True,
    )
    pagina = st.radio(
        "Navegação",
        ["Central operacional", "Modelo & previsão", "Risco de OLA", "Plano de ação", "Auditoria de dados"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("<div style='font-size:.68rem;opacity:.6'>STATUS DOS DADOS</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:.86rem;margin-top:.35rem'>● Snapshot carregado</div>", unsafe_allow_html=True)
    st.caption(f"Até {snapshot:%d/%m/%Y %H:%M}")
    st.caption(f"{fmt_int(len(df))} incidentes · dados anonimizados")
    st.markdown("---")
    st.caption("Challenge FIAP × Locaweb · Sprint 4")


if pagina == "Central operacional":
    cabecalho("Central operacional", "Volume previsto, risco de OLA e decisões prioritárias em uma única visão.", "Visão executiva")
    st.markdown(
        f"""<div class="context-strip">
        <span class="pill">OBSERVADO · base até {snapshot:%d/%m/%Y}</span>
        <span class="pill pill-model">MODELO · Regressão Linear validada no tempo</span>
        <span class="pill pill-alert">ATENÇÃO · não é integração ao vivo</span>
        </div>""",
        unsafe_allow_html=True,
    )
    ultimo = serie.iloc[-1]
    media_7d = serie["incidentes_total"].tail(7).mean()
    delta_ultimo = (ultimo["incidentes_total"] / media_7d - 1) if media_7d else 0
    c1, c2 = st.columns(2)
    c1.metric("Observado em 31/12", fmt_int(ultimo["incidentes_total"]), f"{delta_ultimo * 100:+.1f}".replace(".", ",") + "% vs. média 7d")
    c2.metric(
        f"Modelo D+1 · {previsao_d1['data_alvo']:%d/%m}", fmt_int(previsao_d1["ponto"]),
        f"faixa 80%: {fmt_int(previsao_d1['limite_inferior_80'])}–{fmt_int(previsao_d1['limite_superior_80'])}", delta_color="off",
    )
    c3, c4 = st.columns(2)
    c3.metric(
        f"Modelo dia +7 · {previsao_d7['data_alvo']:%d/%m}", fmt_int(previsao_d7["ponto"]),
        f"faixa 80%: {fmt_int(previsao_d7['limite_inferior_80'])}–{fmt_int(previsao_d7['limite_superior_80'])}", delta_color="off",
    )
    c4.metric("OLA no universo elegível", fmt_pct(taxa_ola, 2), f"{fmt_int(total_violacoes_kpi)} violações", delta_color="off")
    st.caption(
        "D+7 representa o volume esperado especificamente no sétimo dia, não o total dos próximos sete dias. "
        "As faixas usam os resíduos do teste temporal e expressam incerteza histórica, não garantia operacional. "
        "O modelo não possui indicador de feriados, limitação relevante para a previsão de 01/01."
    )

    esquerda, direita = st.columns([1.65, 1])
    with esquerda:
        st.subheader("Pulso de volume")
        cauda = serie.tail(92)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=cauda["data"], y=cauda["incidentes_total"], name="Observado", line=dict(color=NAVY, width=1.5), fill="tozeroy", fillcolor="rgba(16,36,62,.06)"))
        fig.add_trace(go.Scatter(x=cauda["data"], y=cauda["incidentes_total"].rolling(7).mean(), name="Média 7d", line=dict(color=TEAL, width=3)))
        fig.add_trace(go.Scatter(
            x=[previsao_d1["data_alvo"], previsao_d7["data_alvo"]], y=[previsao_d1["ponto"], previsao_d7["ponto"]],
            name="Modelo", mode="markers+text", text=["D+1", "dia +7"], textposition="top center",
            marker=dict(color=ORANGE, size=12, symbol="diamond"),
        ))
        st.plotly_chart(estilizar_figura(fig, 410), width="stretch")
    with direita:
        st.subheader("Próximas decisões")
        card_acao(
            "24 horas · capacidade",
            f"Preparar operação para {fmt_int(previsao_d1['limite_inferior_80'])}–{fmt_int(previsao_d1['limite_superior_80'])} incidentes",
            "Usar a faixa, não apenas o ponto central. Converter volume em pessoas exige taxa de atendimento por analista, ainda não presente na base.", "red",
        )
        top_cat = ranking_ola(df, "Categoria", 30).iloc[0]
        card_acao("24 horas · OLA", f"Abrir fila de revisão para {top_cat['entidade']}", f"A categoria concentra {fmt_int(top_cat['violacoes'])} violações elegíveis e taxa de {fmt_pct(top_cat['taxa_violacao'])}.", "gold")
        card_acao("7 dias · governança", "Tratar o salto de setembro como quebra de regime", "O volume mensal passou de 3.996 em ago/2025 para 21.561 em set/2025. Confirmar mudança de captura/monitoramento antes de promover novo modelo.", "teal")

    st.subheader("Sinais que exigem investigação")
    a, b, c = st.columns(3)
    with a:
        if not tendencias.empty:
            alta = tendencias.iloc[0]
            card_acao("Tendência · 14 dias", f"{alta['Categoria']} em aceleração", f"{fmt_int(alta['ultimos_14d'])} registros; variação de {alta['variacao'] * 100:+.0f}% contra os 14 dias anteriores.")
    with b:
        top_prod = ranking_ola(df, "Produto", 30).iloc[0]
        card_acao("Concentração · produto", top_prod["entidade"], f"{fmt_int(top_prod['violacoes'])} violações entre {fmt_int(top_prod['elegiveis'])} elegíveis ({fmt_pct(top_prod['taxa_violacao'])}).", "gold")
    with c:
        top_grupo = ranking_ola(df, "Grupo designado", 30).iloc[0]
        card_acao("Concentração · equipe", top_grupo["entidade"], f"{fmt_int(top_grupo['violacoes'])} violações elegíveis; investigar causas e distribuição interna antes de atribuir desempenho à equipe.", "teal")


elif pagina == "Modelo & previsão":
    cabecalho("Modelo & previsão", "Validação fora da amostra, comparação de algoritmos e fatores que movem a estimativa.", "Evidência do modelo")
    st.markdown(
        f"""<div class="context-strip">
        <span class="pill">TREINO · até {modelo.corte_treino:%d/%m/%Y}</span>
        <span class="pill">TESTE · {modelo.inicio_teste:%d/%m/%Y}–{modelo.fim_teste:%d/%m/%Y}</span>
        <span class="pill pill-model">18 FEATURES · sem variável futura</span>
        </div>""",
        unsafe_allow_html=True,
    )
    met_d1, met_d7 = metricas_idx.loc["D+1"], metricas_idx.loc["D+7"]
    m1, m2 = st.columns(2)
    m1.metric("D+1 · MAE", fmt_num(met_d1["MAE"], 1), "incidentes/dia", delta_color="off")
    m2.metric("D+1 · R²", fmt_num(met_d1["R2"], 3), "teste temporal", delta_color="off")
    m3, m4 = st.columns(2)
    m3.metric("D+7 · MAE", fmt_num(met_d7["MAE"], 1), "incidentes/dia", delta_color="off")
    m4.metric("D+7 · R²", fmt_num(met_d7["R2"], 3), "teste temporal", delta_color="off")
    st.info("A Regressão Linear venceu no corte temporal amplo da Sprint 3. Modelos de árvore tiveram R² negativo porque o teste contém uma escala de volume muito acima do treino; árvores extrapolam mal fora da faixa já observada.")

    tab_backtest, tab_benchmark, tab_explicacao = st.tabs(["Previsto × observado", "Benchmark", "Explicabilidade"])
    with tab_backtest:
        col_filtro, col_texto = st.columns([1, 2.3])
        with col_filtro:
            horizonte = st.selectbox("Horizonte", ["D+1", "D+7"])
            janela = st.slider("Últimos dias exibidos", 30, 212, 120)
        bt = modelo.backtest[modelo.backtest["horizonte"] == horizonte].tail(janela)
        med = metricas_idx.loc[horizonte]
        with col_texto:
            direcao = "abaixo" if med["vies_real_menos_previsto"] > 0 else "acima"
            st.markdown(
                f"<div class='source-box'><b>Leitura:</b> no teste, o modelo ficou em média <b>{fmt_num(abs(med['vies_real_menos_previsto']), 1)} incidentes {direcao} do observado</b>. O viés é mostrado porque apenas MAE/RMSE não revela a direção do erro.</div>",
                unsafe_allow_html=True,
            )
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=bt["data_alvo"], y=bt["real"], name="Observado", line=dict(color=NAVY, width=2)))
        fig.add_trace(go.Scatter(x=bt["data_alvo"], y=bt["previsto"], name="Previsto", line=dict(color=ORANGE, width=2)))
        st.plotly_chart(estilizar_figura(fig, 430), width="stretch")
    with tab_benchmark:
        bench = modelo.benchmark.copy()
        fig = px.bar(
            bench, x="RMSE", y="modelo", color="horizonte", barmode="group", orientation="h",
            color_discrete_map={"D+1": ORANGE, "D+7": TEAL},
            labels={"modelo": "Modelo", "RMSE": "RMSE (menor é melhor)", "horizonte": "Horizonte"},
        )
        st.plotly_chart(estilizar_figura(fig, 390), width="stretch")
        tabela_bench = bench.copy()
        tabela_bench["MAE"] = tabela_bench["MAE"].map(lambda x: fmt_num(x, 1))
        tabela_bench["RMSE"] = tabela_bench["RMSE"].map(lambda x: fmt_num(x, 1))
        tabela_bench["R2"] = tabela_bench["R2"].map(lambda x: fmt_num(x, 3))
        st.dataframe(tabela_bench, width="stretch", hide_index=True)
    with tab_explicacao:
        horizonte_coef = st.selectbox("Explicar horizonte", ["D+1", "D+7"], key="coef_h")
        coef = modelo.coeficientes[modelo.coeficientes["horizonte"] == horizonte_coef].nlargest(12, "impacto_absoluto").sort_values("coeficiente")
        fig = px.bar(
            coef, x="coeficiente", y="variavel", orientation="h", color="coeficiente",
            color_continuous_scale=[[0, RED], [0.5, "#D9E1EA"], [1, TEAL]],
            labels={"coeficiente": "Coeficiente padronizado", "variavel": ""},
        )
        fig.update_coloraxes(showscale=False)
        st.plotly_chart(estilizar_figura(fig, 440, legenda=False), width="stretch")
        st.caption("Sinal positivo aumenta a previsão; sinal negativo reduz. Coeficientes padronizados permitem comparar magnitudes, mas não provam causalidade.")

    with st.expander("Metodologia auditável"):
        st.markdown(
            """
- Série diária contínua entre 02/01/2023 e 31/12/2025; dias sem incidente recebem zero.
- Features: calendário, defasagens de 1 e 7 dias, médias móveis de 7/14/30 dias e tendência 7d–14d.
- Todas as médias móveis usam `shift(1)`: o dia previsto nunca entra em sua própria explicação.
- Validação: primeiros 80% para treino e últimos 20% para teste, sem embaralhamento.
- Após a validação, o modelo final é reajustado com todos os alvos já conhecidos.
- As previsões apontam para 01/01/2026 e 07/01/2026 porque este é o limite do snapshot fornecido.
"""
        )


elif pagina == "Risco de OLA":
    cabecalho("Risco de OLA", "Priorização combina escala e taxa, sempre dentro do mesmo universo elegível ao KPI.", "Fila dourada")
    k1, k2 = st.columns(2)
    k1.metric("Elegíveis ao KPI", fmt_int(len(elegiveis)))
    k2.metric("Violações elegíveis", fmt_int(total_violacoes_kpi))
    k3, k4 = st.columns(2)
    k3.metric("Taxa de violação", fmt_pct(taxa_ola, 2))
    k4.metric("OLA-base completa", fmt_pct(violacoes_base / len(df), 2), f"{fmt_int(violacoes_base)} casos", delta_color="off")
    st.caption("Os 7.090 casos da base completa não podem ser divididos pelos 25.751 elegíveis. A taxa comparável e auditável é 3.685 ÷ 25.751 = 14,31%.")
    f1, f2 = st.columns([1, 1])
    with f1:
        dimensao_label = st.selectbox("Analisar por", ["Categoria", "Produto", "Grupo designado"])
    with f2:
        amostra_minima = st.slider("Amostra mínima de elegíveis", 10, 300, 30, 10)
    ranking = ranking_ola(df, dimensao_label, amostra_minima)
    if ranking.empty:
        st.warning("Nenhuma entidade atende à amostra mínima escolhida.")
    else:
        cores_quadrante = {"Escala crítica": RED, "Exceção crítica": GOLD, "Alto volume": BLUE, "Monitorar": "#9AA7B6"}
        fig = px.scatter(
            ranking, x="elegiveis", y="taxa_violacao", size="violacoes", color="quadrante",
            hover_name="entidade", size_max=42, log_x=True, color_discrete_map=cores_quadrante,
            labels={"elegiveis": "Incidentes elegíveis (escala log)", "taxa_violacao": "Taxa de violação", "quadrante": "Prioridade", "violacoes": "Violações"},
        )
        fig.add_hline(y=taxa_ola, line_dash="dot", line_color=MUTED, annotation_text="taxa geral 14,31%")
        fig.add_vline(x=ranking["elegiveis"].median(), line_dash="dot", line_color=MUTED, annotation_text="mediana de volume")
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(estilizar_figura(fig, 500), width="stretch")
        st.subheader("Prioridades observadas")
        saida = ranking[["entidade", "quadrante", "elegiveis", "violacoes", "taxa_violacao"]].copy()
        saida.columns = [dimensao_label, "Leitura", "Elegíveis", "Violações", "Taxa de violação"]
        saida["Taxa de violação"] = saida["Taxa de violação"].map(lambda x: fmt_pct(x, 1))
        st.dataframe(saida.head(20), width="stretch", hide_index=True)
        st.caption("Escala crítica = volume acima da mediana do recorte e taxa acima da taxa geral. Exceção crítica = taxa alta com volume abaixo da mediana. O corte de amostra evita destacar taxas extremas baseadas em poucos casos.")


elif pagina == "Plano de ação":
    cabecalho("Plano de ação", "Do sinal analítico à decisão, com horizonte, evidência e limite explícitos.", "Recomendações orientadas por dados")
    prod, cat, grupo = ranking_ola(df, "Produto", 30), ranking_ola(df, "Categoria", 30), ranking_ola(df, "Grupo designado", 30)
    cat_crit = cat[cat["quadrante"] == "Escala crítica"].iloc[0]
    prod_crit = prod[prod["quadrante"] == "Escala crítica"].iloc[0]
    grupo_crit = grupo[grupo["quadrante"] == "Escala crítica"].iloc[0]
    curto, medio, governanca = st.tabs(["Próximas 24h", "Próximos 7–30 dias", "Cenário de cobertura"])
    with curto:
        c1, c2 = st.columns(2)
        with c1:
            card_acao(
                "1 · dimensionar capacidade", f"Planejar para a faixa de {fmt_int(previsao_d1['limite_inferior_80'])}–{fmt_int(previsao_d1['limite_superior_80'])}",
                f"Ponto central do modelo: {fmt_int(previsao_d1['ponto'])} incidentes para {previsao_d1['data_alvo']:%d/%m/%Y}. Manter margem porque o MAE fora da amostra foi {fmt_num(metricas_idx.loc['D+1', 'MAE'], 1)}.", "red",
            )
            card_acao(
                "2 · fila dourada", f"Cruzar {cat_crit['entidade']} com {prod_crit['entidade']}",
                f"São sinais de escala crítica: {cat_crit['entidade']} tem {fmt_int(cat_crit['violacoes'])} violações; {prod_crit['entidade']} tem {fmt_int(prod_crit['violacoes'])}. Validar a interseção e abrir runbook somente depois do drill-down.", "gold",
            )
        with c2:
            card_acao(
                "3 · responsável operacional", f"Revisar carga com {grupo_crit['entidade']}",
                f"O grupo reúne {fmt_int(grupo_crit['violacoes'])} violações elegíveis e taxa de {fmt_pct(grupo_crit['taxa_violacao'])}. O dado aponta onde investigar; não prova que a equipe causou as violações.", "teal",
            )
            if not tendencias.empty:
                alta = tendencias.iloc[0]
                card_acao(
                    "4 · triagem de tendência", f"Investigar aceleração de {alta['Categoria']}",
                    f"O volume conhecido cresceu {alta['variacao'] * 100:+.0f}% entre duas janelas consecutivas de 14 dias. Separar evento real de mudança de monitoramento.",
                )
    with medio:
        st.markdown("#### Roteiro recomendado")
        plano = pd.DataFrame(
            [
                ["7 dias", "Operação", "Criar runbooks para os cruzamentos categoria × produto com maior volume de violações elegíveis.", "Violações e taxa dentro do KPI"],
                ["7 dias", "Dados", "Confirmar com a Locaweb o que mudou em setembro de 2025 e no Team14.", "5,4× de ago para set; 75,7% do volume no Team14"],
                ["30 dias", "Governança", "Tornar Produto e Categoria obrigatórios nos fluxos de monitoramento quando aplicável.", "Cobertura atual de apenas ~36%"],
                ["30 dias", "Modelo", "Implantar ingestão periódica e monitorar erro/viés por janela antes de automatizar alertas.", "Snapshot atual não é feed ao vivo"],
            ], columns=["Horizonte", "Frente", "Ação", "Evidência"],
        )
        st.dataframe(plano, width="stretch", hide_index=True)
        st.warning("A base não contém produtividade por analista, custo por incidente nem tempo médio de atendimento confiável por recurso. Por isso o app não inventa headcount, economia financeira ou probabilidade individual de falha.")
    with governanca:
        capacidade = st.slider("Quantos produtos cabem na revisão preventiva?", 1, 10, 5)
        selecionados = prod.head(capacidade).copy()
        cobertura = selecionados["violacoes"].sum() / max(1, total_violacoes_kpi)
        g1, g2, g3 = st.columns(3)
        g1.metric("Produtos priorizados", capacidade)
        g2.metric("Violações históricas associadas", fmt_int(selecionados["violacoes"].sum()))
        g3.metric("Cobertura histórica da base", fmt_pct(cobertura, 1))
        tabela_cenario = selecionados[["entidade", "elegiveis", "violacoes", "taxa_violacao"]].rename(columns={"entidade": "Produto", "elegiveis": "Elegíveis", "violacoes": "Violações", "taxa_violacao": "Taxa"})
        tabela_cenario["Taxa"] = tabela_cenario["Taxa"].map(lambda v: fmt_pct(v, 1))
        st.dataframe(tabela_cenario, width="stretch", hide_index=True)
        st.caption("CENÁRIO, não previsão: mostra qual parcela das violações elegíveis históricas pertence aos N produtos selecionados. Não significa que todas seriam evitadas.")


else:
    cabecalho("Auditoria de dados", "Cobertura analítica, quebra de regime, regras de KPI e consulta ao nível do incidente.", "Rastreabilidade")
    missing_prod, missing_cat, missing_res = df["Produto"].isna().mean(), df["Categoria"].isna().mean(), df["Resolvido"].isna().mean()
    team14_share = (df["Grupo designado"] == "Team14").mean()
    q1, q2 = st.columns(2)
    q1.metric("Produto preenchido", fmt_pct(1 - missing_prod, 1))
    q2.metric("Categoria preenchida", fmt_pct(1 - missing_cat, 1))
    q3, q4 = st.columns(2)
    q3.metric("Resolvido preenchido", fmt_pct(1 - missing_res, 1))
    q4.metric("Volume no Team14", fmt_pct(team14_share, 1))
    col1, col2 = st.columns([1.45, 1])
    with col1:
        st.subheader("Mudança de regime mensal")
        mensal = df.groupby(df["Aberto"].dt.to_period("M")).size().rename("incidentes").reset_index()
        mensal["mes"] = mensal["Aberto"].dt.to_timestamp()
        fig = px.bar(mensal, x="mes", y="incidentes", color_discrete_sequence=[NAVY])
        fig.add_shape(
            type="line", x0=pd.Timestamp("2025-09-01"), x1=pd.Timestamp("2025-09-01"),
            y0=0, y1=1, yref="paper", line=dict(color=ORANGE, width=3),
        )
        st.plotly_chart(estilizar_figura(fig, 400, legenda=False), width="stretch")
        st.caption("A linha laranja marca setembro de 2025, início da quebra de regime.")
    with col2:
        st.subheader("O que isso muda")
        card_acao("Risco de modelo", "Escala fora da faixa de treino", "55,2% dos alvos D+1 do teste ficaram acima do maior volume visto no treino. Isso explica a dificuldade dos modelos de árvore e amplia a incerteza.", "red")
        card_acao("Cobertura analítica", "Produto e Categoria são opcionais na origem", "A ausência não invalida o incidente, mas limita o diagnóstico de causa raiz e a priorização por domínio.", "gold")
        card_acao("Rastreabilidade", "Duração existe mesmo sem Resolvido", "O dicionário permite usar resolução ou encerramento. A lacuna de Resolvido reduz a distinção entre correção técnica e fechamento, mas não autoriza descartar a duração fornecida.", "teal")

    st.subheader("Definições auditadas")
    definicoes = pd.DataFrame(
        [
            ["Elegível ao KPI", "Prioridades 1–3; sem Incidente Pai; Status diferente de Sem Intervenção", fmt_int(len(elegiveis))],
            ["OLA violado — base", "Duração > 4h (P1/P2), 12h (P3), 24h (P4) ou 96h (P5)", fmt_int(violacoes_base)],
            ["OLA violado — KPI", "OLA violado E incidente elegível ao KPI", fmt_int(total_violacoes_kpi)],
            ["Previsão D+1", "Volume total do próximo dia a partir de sinais históricos até o dia-base", fmt_int(previsao_d1["ponto"])],
            ["Previsão dia +7", "Volume total especificamente sete dias após o dia-base", fmt_int(previsao_d7["ponto"])],
        ], columns=["Métrica", "Regra", "Resultado"],
    )
    st.dataframe(definicoes, width="stretch", hide_index=True)

    st.subheader("Explorador de incidentes")
    f1, f2, f3 = st.columns(3)
    with f1:
        data_inicio = st.date_input("De", df["Aberto"].min().date(), min_value=df["Aberto"].min().date(), max_value=df["Aberto"].max().date())
    with f2:
        data_fim = st.date_input("Até", df["Aberto"].max().date(), min_value=df["Aberto"].min().date(), max_value=df["Aberto"].max().date())
    with f3:
        prioridades = st.multiselect("Prioridade", sorted(df["Prioridade"].dropna().unique()))
    filtrado = df[(df["Aberto"].dt.date >= data_inicio) & (df["Aberto"].dt.date <= data_fim)]
    if prioridades:
        filtrado = filtrado[filtrado["Prioridade"].isin(prioridades)]
    cols = ["Número", "Aberto", "Prioridade", "Produto", "Categoria", "Grupo designado", "Duracao_Horas", "Status_Exibicao", "Elegivel_KPI_Regra", "OLA_Violado_KPI_Regra"]
    st.dataframe(filtrado.sort_values("Aberto", ascending=False)[cols].head(500), width="stretch", hide_index=True)
    st.caption(f"Mostrando até 500 de {fmt_int(len(filtrado))} registros no filtro. A exportação integral permanece no arquivo-fonte do projeto.")
    st.markdown(
        "<div class='source-box'><b>Linhas de evidência:</b> LW-DATASET.xlsx → tratamento determinístico → dataset_limpo.parquet → agregação diária → modelo. As recomendações são derivadas dos resultados exibidos; não há chamadas a IA generativa nem métricas sintéticas em tempo de execução.</div>",
        unsafe_allow_html=True,
    )
