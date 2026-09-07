from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from model_pipeline import executar_pipeline
from risk_pipeline import executar_pipeline_risco


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
    [data-testid="stHeader"] { height: 0; background: transparent; }
    [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu { display: none !important; }
    [data-testid="stSidebar"] { background: #0E2038; border-right: 0; }
    [data-testid="stSidebar"] * { color: #F7FAFC; }
    [data-testid="stSidebar"] [role="radiogroup"] label {
        padding: .62rem .72rem; border-radius: 10px; margin: .12rem 0;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
        background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.12);
    }
    .block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1500px; }
    h1, h2, h3 { color: #10243E; letter-spacing: -.025em; }
    h1 { font-weight: 800; font-size: 2rem; }
    h2 { font-weight: 750; font-size: 1.35rem; margin-top: .25rem; }
    .eyebrow { color: #F15A29; font-weight: 800; font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; }
    .page-subtitle { color: #617085; font-size: .94rem; margin-top: -.55rem; margin-bottom: 1.25rem; }
    .app-topbar {
        display:flex; align-items:center; justify-content:space-between; gap:1rem;
        background:#10243E; color:#F7FAFC; border-radius:14px; padding:.65rem .9rem;
        margin:-.45rem 0 1.15rem; box-shadow:0 7px 24px rgba(16,36,62,.12);
        font-size:.75rem; font-weight:700; letter-spacing:.035em;
    }
    .app-topbar .live { color:#7DE2CF; }
    .app-topbar .muted { color:#C5D0DC; font-weight:500; }
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
    .risk-panel {
        background:#10243E; color:#F7FAFC; border-radius:18px; padding:1.25rem 1.35rem;
        box-shadow:0 10px 28px rgba(16,36,62,.16); margin:.4rem 0 1rem;
    }
    .risk-panel .label { color:#A9B8C8; font-size:.7rem; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }
    .risk-panel .value { color:#FFFFFF; font-size:2.35rem; line-height:1.05; font-weight:800; margin:.3rem 0; }
    .risk-panel .copy { color:#D8E1EA; font-size:.86rem; line-height:1.5; }
    .risk-panel.high { border-left:6px solid #F15A29; }
    .risk-panel.medium { border-left:6px solid #D99A16; }
    .risk-panel.low { border-left:6px solid #27A6A8; }
    .section-kicker { color:#617085; font-size:.72rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; margin-bottom:.15rem; }
    div[data-testid="stDownloadButton"] button, div[data-testid="stButton"] button {
        border-radius:10px; border:1px solid #CAD4DF; font-weight:700;
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
    st.markdown(
        "<div class='app-topbar'><span class='live'>● MODELOS OPERACIONAIS ATIVOS</span>"
        "<span class='muted'>snapshot auditável · sem dados sintéticos</span></div>",
        unsafe_allow_html=True,
    )
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
    return executar_pipeline(carregar_dados(), incluir_avancado=False)


@st.cache_resource(show_spinner="Validando modelo de risco de OLA…")
def carregar_modelo_risco() -> object:
    return executar_pipeline_risco(carregar_dados())


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
    recente = conhecida[conhecida["Aberto"] >= data_max - timedelta(days=13)]
    anterior = conhecida[
        (conhecida["Aberto"] >= data_max - timedelta(days=27))
        & (conhecida["Aberto"] < data_max - timedelta(days=13))
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


def ranking_cruzamentos(
    df: pd.DataFrame,
    dimensao_a: str = "Categoria",
    dimensao_b: str = "Produto",
    minimo: int = 20,
    incluir_nao_informado: bool = False,
) -> pd.DataFrame:
    """Prioriza causas combinadas por escala, taxa e recorrência recente."""
    base = df[df["Elegivel_KPI_Regra"]].copy()
    for coluna in [dimensao_a, dimensao_b]:
        base[coluna] = base[coluna].fillna("Não informado").astype(str)
    if not incluir_nao_informado:
        base = base[(base[dimensao_a] != "Não informado") & (base[dimensao_b] != "Não informado")]
    limite = base["Prioridade_Cod"].map({1: 4, 2: 4, 3: 12}).astype(float)
    base["excesso_horas"] = np.where(
        base["OLA_Violado_KPI_Regra"], (base["Duracao_Horas"] - limite).clip(lower=0), np.nan
    )
    corte_recente = base["Aberto"].max().normalize() - timedelta(days=29)
    base["violacao_recente"] = (
        base["OLA_Violado_KPI_Regra"] & (base["Aberto"] >= corte_recente)
    ).astype(int)
    ranking = (
        base.groupby([dimensao_a, dimensao_b], dropna=False)
        .agg(
            elegiveis=("Aberto", "size"),
            violacoes=("OLA_Violado_KPI_Regra", "sum"),
            violacoes_30d=("violacao_recente", "sum"),
            excesso_horas_mediano=("excesso_horas", "median"),
        )
        .reset_index()
    )
    ranking = ranking[ranking["elegiveis"] >= minimo].copy()
    if ranking.empty:
        return ranking
    ranking["taxa_violacao"] = ranking["violacoes"] / ranking["elegiveis"]
    ranking["lift_taxa"] = ranking["taxa_violacao"] / max(1e-9, taxa_ola)
    ranking["score_prioridade"] = 100 * (
        0.50 * ranking["violacoes"].rank(pct=True)
        + 0.30 * ranking["taxa_violacao"].rank(pct=True)
        + 0.20 * ranking["violacoes_30d"].rank(pct=True)
    )
    ranking["causa"] = ranking[dimensao_a].astype(str) + " × " + ranking[dimensao_b].astype(str)
    return ranking.sort_values(["score_prioridade", "violacoes"], ascending=False).reset_index(drop=True)


def evidencia_perfil(df: pd.DataFrame, coluna: str, valor: str | int) -> tuple[int, int, float]:
    base = df[df["Elegivel_KPI_Regra"]].copy()
    serie_coluna = base[coluna].fillna("Não informado").astype(str)
    recorte = base[serie_coluna == str(valor)]
    total = len(recorte)
    violacoes = int(recorte["OLA_Violado_KPI_Regra"].sum())
    return total, violacoes, violacoes / total if total else 0.0


df = carregar_dados()
modelo = carregar_modelagem()
modelo_risco = carregar_modelo_risco()
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
metricas_op_idx = modelo.metricas_operacionais.set_index("horizonte")
metricas_risco = modelo_risco.metricas_holdout


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
        [
            "Central operacional",
            "Fila operacional",
            "Triagem preditiva",
            "Diagnóstico de OLA",
            "Capacidade & ação",
            "Modelo & previsão",
            "Auditoria de dados",
        ],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("<div style='font-size:.68rem;opacity:.6'>STATUS DOS DADOS</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:.86rem;margin-top:.35rem'>● Snapshot carregado</div>", unsafe_allow_html=True)
    st.caption(f"Até {snapshot:%d/%m/%Y %H:%M}")
    st.caption(f"{fmt_int(len(df))} incidentes · dados anonimizados")
    st.markdown("---")
    st.caption("Challenge FIAP × Locaweb · Sprint 4 final")


if pagina == "Central operacional":
    cabecalho("Central operacional", "Volume previsto, risco de OLA e decisões prioritárias em uma única visão.", "Visão executiva")
    st.markdown(
        f"""<div class="context-strip">
        <span class="pill">OBSERVADO · base até {snapshot:%d/%m/%Y}</span>
        <span class="pill pill-model">MODELO · ensemble operacional validado no tempo</span>
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
            "Usar a faixa, não apenas o ponto central. O simulador converte o volume em pessoas a partir das premissas informadas pelo operador.", "red",
        )
        top_cat = ranking_ola(df, "Categoria", 30).iloc[0]
        card_acao("24 horas · OLA", f"Abrir fila de revisão para {top_cat['entidade']}", f"A categoria concentra {fmt_int(top_cat['violacoes'])} violações elegíveis e taxa de {fmt_pct(top_cat['taxa_violacao'])}.", "gold")
        card_acao("7 dias · governança", "Tratar o salto de setembro como quebra de regime", "O volume mensal passou de 3.996 em ago/2025 para 21.561 em set/2025. Confirmar mudança de captura/monitoramento antes de promover novo modelo.", "teal")

    st.subheader("Sinais que exigem investigação")
    a, b, c, d = st.columns(4)
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
    with d:
        card_acao(
            "Modelo de triagem · dezembro",
            f"{fmt_pct(metricas_risco['captura_violacoes'], 1)} das violações capturadas",
            f"A fila alta revisa {fmt_pct(metricas_risco['taxa_revisada'], 1)} dos incidentes e concentra risco {fmt_num(metricas_risco['lift_fila_alta'], 1)}× acima da média.",
            "red",
        )


elif pagina == "Fila operacional":
    cabecalho(
        "Fila operacional em lote",
        "Pontue um lote de chamados, ordene por risco de violação de OLA e exporte a fila priorizada.",
        "Priorização em lote",
    )
    st.markdown(
        """<div class="context-strip">
        <span class="pill pill-model">PREDIÇÃO REAL · ensemble calibrado</span>
        <span class="pill">SEM VAZAMENTO · só dados da abertura</span>
        <span class="pill pill-alert">LOTE · não é um feed ao vivo</span>
        </div>""",
        unsafe_allow_html=True,
    )
    modo = st.radio("Origem", ["Dia real do snapshot", "Importar CSV"], horizontal=True, label_visibility="collapsed")
    entradas = None
    resultado_real = None
    if modo == "Dia real do snapshot":
        colf1, colf2 = st.columns([1, 1])
        with colf1:
            data_lote = st.date_input(
                "Data de abertura", value=pd.Timestamp("2025-11-18").date(),
                min_value=df["Aberto"].min().date(), max_value=snapshot.normalize().date(),
            )
        with colf2:
            janela_dias = st.slider("Janela (dias)", 1, 14, 1)
        inicio = pd.Timestamp(data_lote)
        recorte = elegiveis[(elegiveis["Aberto"] >= inicio) & (elegiveis["Aberto"] < inicio + timedelta(days=janela_dias))]
        if recorte.empty:
            st.warning("Nenhum incidente elegível nessa janela do snapshot.")
        else:
            entradas = pd.DataFrame(
                {
                    "id": recorte["Número"].astype(str).to_numpy(),
                    "prioridade": recorte["Prioridade_Cod"].to_numpy(),
                    "produto": recorte["Produto"].fillna("Não informado").to_numpy(),
                    "categoria": recorte["Categoria"].fillna("Não informado").to_numpy(),
                    "grupo": recorte["Grupo designado"].fillna("Não informado").to_numpy(),
                    "data_hora": recorte["Aberto"].to_numpy(),
                }
            )
            resultado_real = dict(zip(recorte["Número"].astype(str), recorte["OLA_Violado_KPI_Regra"].astype(bool)))
            janela = (
                "holdout (dez/2025, não visto no treino)" if inicio >= pd.Timestamp("2025-12-01")
                else "validação (out/nov 2025)" if inicio >= pd.Timestamp("2025-10-01")
                else "treino (anterior a out/2025)"
            )
            st.caption(f"Janela do modelo para essa data: {janela}. O campo 'violou' é o resultado real — serve só para conferir a ordenação.")
    else:
        arquivo = st.file_uploader("CSV com colunas: id, prioridade, produto, categoria, grupo, dataHora", type="csv")
        modelo_csv = pd.DataFrame(
            [["INC-EXEMPLO-1", 3, "lemn", "cat45", "Team05", "2026-01-05T09:30:00"]],
            columns=["id", "prioridade", "produto", "categoria", "grupo", "dataHora"],
        )
        st.download_button("Baixar modelo (.csv)", modelo_csv.to_csv(index=False).encode("utf-8-sig"), "modelo_fila.csv", "text/csv")
        if arquivo is not None:
            bruto = pd.read_csv(arquivo)
            bruto.columns = [c.strip().lower() for c in bruto.columns]
            entradas = pd.DataFrame(
                {
                    "id": bruto.get("id", pd.Series(range(1, len(bruto) + 1))).astype(str),
                    "prioridade": pd.to_numeric(bruto.get("prioridade"), errors="coerce").fillna(3).astype(int),
                    "produto": bruto.get("produto", "Não informado").fillna("Não informado"),
                    "categoria": bruto.get("categoria", "Não informado").fillna("Não informado"),
                    "grupo": bruto.get("grupo", "Não informado").fillna("Não informado"),
                    "data_hora": bruto.get("datahora", bruto.get("aberto")),
                }
            )

    if entradas is not None and not entradas.empty:
        pontuado = modelo_risco.pontuar_lote(entradas.rename(columns={"data_hora": "data_hora"}))
        fila = entradas.reset_index(drop=True).join(pontuado.reset_index(drop=True))
        fila = fila.sort_values("probabilidade", ascending=False).reset_index(drop=True)
        if resultado_real is not None:
            fila["violou_real"] = fila["id"].map(resultado_real).fillna(False)

        n_alto = int((fila["faixa"] == "Alto").sum())
        esperadas = float(fila["probabilidade"].sum())
        corte_top = max(1, int(np.ceil(len(fila) * 0.2)))
        captura_top = fila["probabilidade"].iloc[:corte_top].sum() / max(esperadas, 1e-9)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Chamados na fila", fmt_int(len(fila)))
        m2.metric("Risco alto", fmt_int(n_alto), f"{fmt_int(int((fila['faixa'] == 'Moderado').sum()))} moderado", delta_color="off")
        m3.metric("Violações esperadas", fmt_num(esperadas, 1), "soma das probabilidades", delta_color="off")
        m4.metric("Captura no topo 20%", fmt_pct(captura_top, 1))
        if resultado_real is not None:
            reais = int(fila["violou_real"].sum())
            no_topo = int(fila["violou_real"].iloc[:corte_top].sum())
            st.info(f"Conferência: neste dia real houve {reais} violação(ões) de OLA; {no_topo} está(ão) nos primeiros 20% da fila ordenada pelo modelo.")

        exibicao = fila.copy()
        exibicao["probabilidade"] = exibicao["probabilidade"].map(lambda v: fmt_pct(v, 1))
        for col in [c for c in exibicao.columns if c.startswith("contribuicao_")]:
            exibicao[col] = exibicao[col].map(lambda v: f"{v * 100:+.1f} pp")
        exibicao = exibicao.rename(
            columns={
                "id": "Chamado", "prioridade": "Prioridade", "produto": "Produto", "categoria": "Categoria",
                "grupo": "Grupo", "data_hora": "Aberto", "probabilidade": "Risco", "faixa": "Faixa",
                "violou_real": "Violou (real)", "contribuicao_Prioridade": "Δ Prioridade",
                "contribuicao_Produto": "Δ Produto", "contribuicao_Categoria": "Δ Categoria", "contribuicao_Grupo": "Δ Grupo",
            }
        )
        st.dataframe(exibicao, width="stretch", hide_index=True)
        st.caption(
            "Δ = quanto cada fator move o risco em relação ao valor mais comum no treino (leitura do próprio modelo, não SHAP). "
            "O registro de ações (atribuído/escalado/resolvido) está na interface React."
        )
        st.download_button(
            "Baixar fila priorizada (.csv)",
            data=fila.to_csv(index=False).encode("utf-8-sig"),
            file_name="fila_priorizada_ola.csv",
            mime="text/csv",
        )


elif pagina == "Triagem preditiva":
    cabecalho(
        "Triagem preditiva de OLA",
        "Estime o risco no momento da abertura e transforme o score em uma decisão operacional verificável.",
        "Modelo de classificação",
    )
    st.markdown(
        """<div class="context-strip">
        <span class="pill pill-model">PREDIÇÃO REAL · ensemble calibrado</span>
        <span class="pill">SEM VAZAMENTO · somente dados da abertura</span>
        <span class="pill pill-alert">DECISÃO ASSISTIDA · não substitui o operador</span>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-kicker">Dados disponíveis na abertura</div>', unsafe_allow_html=True)
    t1, t2, t3 = st.columns([1, 1, 1])
    mapa_prioridades = {"P1 · Crítica": 1, "P2 · Alta": 2, "P3 · Média": 3}
    with t1:
        prioridade_rotulo = st.selectbox("Prioridade", list(mapa_prioridades), index=2)
        data_triagem = st.date_input(
            "Data de abertura",
            value=pd.Timestamp("2026-01-01").date(),
            min_value=df["Aberto"].min().date(),
            max_value=(snapshot.normalize() + timedelta(days=30)).date(),
        )
    with t2:
        produtos = ["Não informado"] + sorted(df["Produto"].dropna().astype(str).unique().tolist())
        categorias = ["Não informado"] + sorted(df["Categoria"].dropna().astype(str).unique().tolist())
        produto_sel = st.selectbox("Produto", produtos, index=produtos.index("lemn") if "lemn" in produtos else 0)
        categoria_sel = st.selectbox("Categoria", categorias, index=categorias.index("cat45") if "cat45" in categorias else 0)
    with t3:
        grupos = sorted(df["Grupo designado"].dropna().astype(str).unique().tolist())
        grupo_sel = st.selectbox("Grupo designado", grupos, index=grupos.index("Team05") if "Team05" in grupos else 0)
        hora_sel = st.slider("Hora de abertura", 0, 23, 9)

    momento_triagem = pd.Timestamp(data_triagem) + timedelta(hours=int(hora_sel))
    st.caption(
        "A tela abre com um perfil histórico de alto risco para demonstração. Altere qualquer campo para simular outra "
        "triagem; datas futuras estão limitadas aos 30 dias após o snapshot."
    )
    resultado_triagem = modelo_risco.prever(
        mapa_prioridades[prioridade_rotulo], produto_sel, categoria_sel, grupo_sel, momento_triagem
    )
    prob = float(resultado_triagem["probabilidade"])
    faixa = str(resultado_triagem["faixa"])
    classe_css = {"Alto": "high", "Moderado": "medium", "Baixo": "low"}[faixa]
    texto_fila = {
        "Alto": "Enviar para a fila dourada e validar capacidade, categoria e runbook antes do primeiro handoff.",
        "Moderado": "Manter monitoramento reforçado e revisar o incidente se houver troca de grupo ou ausência de categorização.",
        "Baixo": "Seguir o fluxo padrão, preservando os guardrails de P1/P2 e o acompanhamento do relógio de OLA.",
    }[faixa]
    st.markdown(
        f"""<div class="risk-panel {classe_css}">
        <div class="label">Risco calibrado de violação · faixa {faixa}</div>
        <div class="value">{fmt_pct(prob, 1)}</div>
        <div class="copy">{texto_fila}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Risco médio no holdout", fmt_pct(metricas_risco["prevalencia"], 1))
    r2.metric("Corte da fila alta", fmt_pct(modelo_risco.limiar_alto, 1))
    r3.metric("Lift da fila alta", f"{fmt_num(metricas_risco['lift_fila_alta'], 2)}×")
    r4.metric("ROC-AUC temporal", fmt_num(metricas_risco["ROC_AUC"], 3))
    st.progress(min(max(prob, 0.0), 1.0), text="Posição do score na escala probabilística")

    st.subheader("Evidências históricas do perfil informado")
    evidencias = []
    for coluna, valor, dimensao_exibida, valor_exibido in [
        ("Prioridade_Cod", mapa_prioridades[prioridade_rotulo], "Prioridade", prioridade_rotulo),
        ("Produto", produto_sel, "Produto", produto_sel),
        ("Categoria", categoria_sel, "Categoria", categoria_sel),
        ("Grupo designado", grupo_sel, "Grupo designado", grupo_sel),
    ]:
        n, v, taxa = evidencia_perfil(df, coluna, valor)
        evidencias.append([dimensao_exibida, valor_exibido, n, v, taxa])
    evidencias_df = pd.DataFrame(
        evidencias, columns=["Dimensão", "Valor", "Elegíveis históricos", "Violações", "Taxa observada"]
    )
    evidencias_df["Taxa observada"] = evidencias_df["Taxa observada"].map(lambda v: fmt_pct(v, 1))
    st.dataframe(evidencias_df, width="stretch", hide_index=True)
    st.caption(
        "As taxas da tabela são descritivas e não são a probabilidade do modelo. O score combina os sinais e foi calibrado "
        "em outubro/novembro de 2025, com teste final apenas em dezembro."
    )

    acao = pd.DataFrame(
        [
            ["Classificação", faixa, f"Risco calibrado de {fmt_pct(prob, 1)}"],
            ["Primeiro passo", texto_fila, "Regra operacional sugerida pelo app"],
            ["Guardrail", "Não usar o score como decisão automática ou atribuição de culpa", "Modelo de apoio à triagem"],
        ],
        columns=["Etapa", "Ação", "Evidência"],
    )
    st.download_button(
        "Baixar ficha de triagem (.csv)",
        data=acao.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"triagem_ola_{momento_triagem:%Y%m%d_%H%M}.csv",
        mime="text/csv",
    )
    with st.expander("Como esta predição foi validada"):
        st.markdown(
            f"""
- Treino: incidentes elegíveis anteriores a outubro de 2025.
- Seleção e calibração: outubro e novembro de 2025.
- Holdout final: {metricas_risco['n_holdout']:.0f} incidentes de dezembro, com {metricas_risco['n_violacoes_holdout']:.0f} violações.
- A fila alta aplicou o corte definido antes do holdout, revisou {fmt_pct(metricas_risco['taxa_revisada'], 1)} dos casos e capturou {fmt_pct(metricas_risco['captura_violacoes'], 1)} das violações.
- Nenhuma feature usa duração, resolução, encerramento ou o próprio indicador de OLA.
"""
        )


elif pagina == "Modelo & previsão":
    cabecalho("Modelo & previsão", "Validação fora da amostra, comparação de algoritmos e fatores que movem a estimativa.", "Evidência do modelo")
    st.markdown(
        """<div class="context-strip">
        <span class="pill">SELEÇÃO · validações móveis em out/nov 2025</span>
        <span class="pill">HOLDOUT FINAL · 01–31/12/2025</span>
        <span class="pill pill-model">ENSEMBLE · pesos escolhidos antes do holdout</span>
        </div>""",
        unsafe_allow_html=True,
    )
    met_d1, met_d7 = metricas_op_idx.loc["D+1"], metricas_op_idx.loc["D+7"]
    m1, m2 = st.columns(2)
    m1.metric("D+1 · MAE no holdout", fmt_num(met_d1["holdout_MAE"], 1), f"{fmt_pct(met_d1['ganho_mae'])} menor que o baseline", delta_color="off")
    m2.metric("D+1 · WAPE", fmt_pct(met_d1["holdout_WAPE"], 1), "dezembro não visto", delta_color="off")
    m3, m4 = st.columns(2)
    m3.metric("Dia +7 · MAE no holdout", fmt_num(met_d7["holdout_MAE"], 1), f"{fmt_pct(met_d7['ganho_mae'])} menor que o baseline", delta_color="off")
    m4.metric("Dia +7 · WAPE", fmt_pct(met_d7["holdout_WAPE"], 1), "dezembro não visto", delta_color="off")
    st.info(
        "O modelo operacional é híbrido: D+1 combina 30% da Linear da Sprint 3 com 70% de Ridge usando o dia-base; "
        "dia +7 combina 20% da Linear com 80% de Extra Trees treinado no regime pós-setembro. Os pesos foram escolhidos "
        "em validações móveis de outubro/novembro; dezembro só foi aberto para o teste final."
    )

    tab_backtest, tab_benchmark, tab_explicacao = st.tabs(["Previsto × observado", "Benchmark", "Explicabilidade"])
    with tab_backtest:
        col_filtro, col_texto = st.columns([1, 2.3])
        with col_filtro:
            horizonte = st.selectbox("Horizonte", ["D+1", "D+7"])
        bt = modelo.backtest_operacional[modelo.backtest_operacional["horizonte"] == horizonte]
        med = metricas_op_idx.loc[horizonte]
        with col_texto:
            direcao = "abaixo" if med["holdout_vies_real_menos_previsto"] > 0 else "acima"
            st.markdown(
                f"<div class='source-box'><b>Holdout de dezembro:</b> o ensemble ficou em média <b>{fmt_num(abs(med['holdout_vies_real_menos_previsto']), 1)} incidentes {direcao} do observado</b>. "
                f"MAE da Linear da Sprint 3 no mesmo período: {fmt_num(med['baseline_holdout_MAE'], 1)}.</div>",
                unsafe_allow_html=True,
            )
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=bt["data_alvo"], y=bt["real"], name="Observado", line=dict(color=NAVY, width=2)))
        fig.add_trace(go.Scatter(x=bt["data_alvo"], y=bt["baseline"], name="Linear Sprint 3", line=dict(color=MUTED, width=1.5, dash="dot")))
        fig.add_trace(go.Scatter(x=bt["data_alvo"], y=bt["previsto"], name="Ensemble operacional", line=dict(color=ORANGE, width=2.5)))
        st.plotly_chart(estilizar_figura(fig, 430), width="stretch")
    with tab_benchmark:
        st.markdown("#### Resultado operacional no holdout final")
        tabela_op = modelo.metricas_operacionais[["horizonte", "modelo", "cv_mae", "holdout_MAE", "holdout_RMSE", "holdout_R2", "holdout_WAPE", "baseline_holdout_MAE", "ganho_mae"]].copy()
        tabela_op.columns = ["Horizonte", "Modelo operacional", "MAE validações", "MAE dezembro", "RMSE dezembro", "R² dezembro", "WAPE dezembro", "MAE baseline", "Ganho vs. baseline"]
        for coluna in ["MAE validações", "MAE dezembro", "RMSE dezembro", "MAE baseline"]:
            tabela_op[coluna] = tabela_op[coluna].map(lambda x: fmt_num(x, 1))
        tabela_op["R² dezembro"] = tabela_op["R² dezembro"].map(lambda x: fmt_num(x, 3))
        for coluna in ["WAPE dezembro", "Ganho vs. baseline"]:
            tabela_op[coluna] = tabela_op[coluna].map(lambda x: fmt_pct(x, 1))
        st.dataframe(tabela_op, width="stretch", hide_index=True)
        st.caption("O critério operacional de seleção foi MAE. Em um único mês com variância limitada, o R² pode ser baixo ou negativo mesmo quando o erro absoluto melhora; por isso todas as métricas permanecem visíveis.")
        st.markdown("#### Benchmark amplo reproduzido da Sprint 3")
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
        st.caption(f"Benchmark amplo: treino até {modelo.corte_treino:%d/%m/%Y}; teste de {modelo.inicio_teste:%d/%m/%Y} a {modelo.fim_teste:%d/%m/%Y}.")
    with tab_explicacao:
        horizonte_coef = st.selectbox("Explicar horizonte", ["D+1", "D+7"], key="coef_h")
        coef = modelo.importancias_operacionais[modelo.importancias_operacionais["horizonte"] == horizonte_coef].nlargest(12, "impacto_absoluto").sort_values("valor")
        fig = px.bar(
            coef, x="valor", y="variavel", orientation="h", color="valor",
            color_continuous_scale=[[0, RED], [0.5, "#D9E1EA"], [1, TEAL]],
            labels={"valor": coef["tipo"].iloc[0], "variavel": ""},
        )
        fig.update_coloraxes(showscale=False)
        st.plotly_chart(estilizar_figura(fig, 440, legenda=False), width="stretch")
        if horizonte_coef == "D+1":
            st.caption("No componente Ridge, o sinal indica direção e a magnitude é comparável após padronização. Isso descreve associação, não causalidade.")
        else:
            st.caption("No Extra Trees, a importância indica quanto uma variável foi usada para reduzir erro; não possui sinal positivo/negativo e não prova causalidade.")

    with st.expander("Metodologia auditável"):
        st.markdown(
            """
- Série diária contínua entre 02/01/2023 e 31/12/2025; dias sem incidente recebem zero.
- A Linear da Sprint 3 e suas 18 features continuam reproduzidas como baseline e benchmark amplo 80/20.
- O componente operacional usa apenas informação disponível ao fechar o dia-base: volume, KPI, OLA-base, lags, médias, volatilidade e calendário do alvo.
- Seleção dos pesos: três janelas móveis em out/nov de 2025. Holdout final: todos os 31 dias de dezembro, nunca usados na seleção.
- A amostra pós-quebra ainda é curta; o ensemble precisa ser revalidado quando chegarem novos meses.
- D+1: 30% Linear + 70% Ridge. Dia +7: 20% Linear + 80% Extra Trees do regime iniciado em setembro.
- Após a avaliação, os componentes finais são reajustados com todos os alvos conhecidos. As faixas vêm somente dos resíduos de out/nov.
- As previsões apontam para 01/01/2026 e 07/01/2026 porque este é o limite do snapshot fornecido.
"""
        )

    st.markdown("---")
    st.subheader("Modelo de risco de OLA na abertura")
    st.caption(
        f"Teste fora da amostra: {modelo_risco.inicio_holdout:%d/%m/%Y} a {modelo_risco.fim_holdout:%d/%m/%Y}. "
        "O alvo é violação dentro do universo elegível; nenhuma variável posterior à abertura entra no modelo."
    )
    mr1, mr2, mr3, mr4 = st.columns(4)
    mr1.metric("ROC-AUC", fmt_num(metricas_risco["ROC_AUC"], 3))
    mr2.metric("PR-AUC", fmt_num(metricas_risco["PR_AUC"], 3), f"base {fmt_num(metricas_risco['prevalencia'], 3)}", delta_color="off")
    mr3.metric("Captura na fila alta", fmt_pct(metricas_risco["captura_violacoes"], 1))
    mr4.metric("Casos revisados", fmt_pct(metricas_risco["taxa_revisada"], 1), f"lift {fmt_num(metricas_risco['lift_fila_alta'], 2)}×", delta_color="off")
    vm1, vm2 = st.columns(2)
    with vm1:
        st.markdown("#### Calibração por faixa de score")
        calibracao = modelo_risco.calibracao
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=calibracao["decil"], y=calibracao["taxa_observada"], name="Taxa observada",
            mode="lines+markers", line=dict(color=NAVY, width=2.5),
        ))
        fig.add_trace(go.Scatter(
            x=calibracao["decil"], y=calibracao["risco_previsto"], name="Risco previsto",
            mode="lines+markers", line=dict(color=ORANGE, width=2, dash="dot"),
        ))
        fig.update_yaxes(tickformat=".0%")
        fig.update_xaxes(dtick=1, title="Faixa crescente de risco")
        st.plotly_chart(estilizar_figura(fig, 370), width="stretch")
    with vm2:
        st.markdown("#### Variáveis com maior poder de separação")
        imp = modelo_risco.importancias.sort_values("queda_pr_auc")
        fig = px.bar(
            imp, x="queda_pr_auc", y="variavel", orientation="h",
            color_discrete_sequence=[TEAL],
            labels={"queda_pr_auc": "Queda de PR-AUC ao embaralhar", "variavel": ""},
        )
        st.plotly_chart(estilizar_figura(fig, 370, legenda=False), width="stretch")
    with st.expander("Benchmark de seleção do classificador"):
        bench_risco = modelo_risco.benchmark_validacao.copy()
        bench_risco["ROC_AUC"] = bench_risco["ROC_AUC"].map(lambda v: fmt_num(v, 3))
        bench_risco["PR_AUC"] = bench_risco["PR_AUC"].map(lambda v: fmt_num(v, 3))
        bench_risco["Brier"] = bench_risco["Brier"].map(lambda v: fmt_num(v, 3))
        bench_risco = bench_risco.drop(columns="peso_extra_trees").rename(
            columns={"modelo": "Candidato", "ROC_AUC": "ROC-AUC", "PR_AUC": "PR-AUC"}
        )
        st.dataframe(bench_risco, width="stretch", hide_index=True)
        st.caption(
            "O peso 50/50 foi escolhido pela maior PR-AUC em outubro/novembro. O Platt scaling foi ajustado nessa mesma "
            "janela e aplicado sem reajuste ao holdout de dezembro."
        )


elif pagina == "Diagnóstico de OLA":
    cabecalho("Diagnóstico de OLA", "Priorização combina escala, taxa e recorrência para indicar onde investigar primeiro.", "Causas e fila dourada")
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

    st.markdown("---")
    st.subheader("Causas combinadas e fila de investigação")
    st.caption(
        "O score transparente combina 50% escala de violações, 30% taxa e 20% recorrência nos 30 dias finais da base. "
        "Ele prioriza investigação; não afirma causalidade."
    )
    combinacoes = {
        "Categoria × Produto": ("Categoria", "Produto"),
        "Categoria × Grupo": ("Categoria", "Grupo designado"),
        "Produto × Grupo": ("Produto", "Grupo designado"),
    }
    cc1, cc2, cc3 = st.columns([1.4, 1, 1])
    with cc1:
        cruzamento_label = st.selectbox("Cruzamento", list(combinacoes))
    with cc2:
        minimo_cruzamento = st.slider("Amostra mínima por combinação", 10, 100, 20, 5)
    with cc3:
        incluir_ausentes = st.toggle("Incluir não informado", value=False)
    dim_a, dim_b = combinacoes[cruzamento_label]
    causas = ranking_cruzamentos(df, dim_a, dim_b, minimo_cruzamento, incluir_ausentes)
    if causas.empty:
        st.warning("Nenhuma combinação atende ao volume mínimo escolhido.")
    else:
        top_causas = causas.head(12).sort_values("score_prioridade")
        fig = px.bar(
            top_causas,
            x="score_prioridade",
            y="causa",
            orientation="h",
            text="violacoes",
            color_discrete_sequence=[ORANGE],
            labels={"score_prioridade": "Score de prioridade (0–100)", "causa": "", "violacoes": "Violações"},
        )
        fig.update_traces(texttemplate="%{text} violações", textposition="outside", cliponaxis=False)
        fig.update_xaxes(range=[0, 108])
        st.plotly_chart(estilizar_figura(fig, 455, legenda=False), width="stretch")

        opcoes_causa = causas.head(30)["causa"].tolist()
        causa_escolhida = st.selectbox("Abrir diagnóstico", opcoes_causa)
        linha = causas[causas["causa"] == causa_escolhida].iloc[0]
        valor_a, valor_b = linha[dim_a], linha[dim_b]
        base_diag = elegiveis.copy()
        filtro_a = base_diag[dim_a].fillna("Não informado").astype(str).eq(str(valor_a))
        filtro_b = base_diag[dim_b].fillna("Não informado").astype(str).eq(str(valor_b))
        detalhe = base_diag[filtro_a & filtro_b].copy()
        mensal_diag = (
            detalhe.groupby(detalhe["Aberto"].dt.to_period("M"))["OLA_Violado_KPI_Regra"]
            .agg(["count", "sum", "mean"])
            .tail(12)
            .reset_index()
        )
        mensal_diag["mes"] = mensal_diag["Aberto"].dt.to_timestamp()
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Elegíveis", fmt_int(linha["elegiveis"]))
        d2.metric("Violações", fmt_int(linha["violacoes"]))
        d3.metric("Taxa", fmt_pct(linha["taxa_violacao"], 1), f"{fmt_num(linha['lift_taxa'], 1)}× a média", delta_color="off")
        d4.metric("Excesso mediano", f"{fmt_num(linha['excesso_horas_mediano'], 1)} h", "entre violações", delta_color="off")
        e1, e2 = st.columns([1.5, 1])
        with e1:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=mensal_diag["mes"], y=mensal_diag["count"], name="Elegíveis", marker_color="#C8D3DF"))
            fig.add_trace(go.Bar(x=mensal_diag["mes"], y=mensal_diag["sum"], name="Violações", marker_color=ORANGE))
            fig.update_layout(barmode="overlay")
            st.plotly_chart(estilizar_figura(fig, 350), width="stretch")
        with e2:
            principal_grupo = detalhe["Grupo designado"].mode().iloc[0] if not detalhe.empty else "—"
            card_acao(
                "Ação sugerida",
                f"Abrir runbook para {causa_escolhida}",
                f"Começar pelo grupo mais recorrente ({principal_grupo}), revisar os {fmt_int(linha['violacoes_30d'])} casos dos 30 dias finais e validar mudança de causa antes de escalar.",
                "red" if linha["lift_taxa"] >= 1.5 else "gold",
            )
            card_acao(
                "Critério de saída",
                "Reavaliar após duas janelas",
                "Fechar a ação somente se a taxa cair sem deslocar violações para outra categoria, produto ou grupo.",
                "teal",
            )

        exportar = causas[[dim_a, dim_b, "score_prioridade", "elegiveis", "violacoes", "taxa_violacao", "violacoes_30d", "excesso_horas_mediano"]].copy()
        st.download_button(
            "Baixar fila priorizada (.csv)",
            data=exportar.to_csv(index=False).encode("utf-8-sig"),
            file_name="fila_investigacao_ola.csv",
            mime="text/csv",
        )


elif pagina == "Capacidade & ação":
    cabecalho("Capacidade & plano de ação", "Converta a faixa prevista em necessidade operacional usando premissas informadas por você.", "Simulador de decisão")
    prod, cat, grupo = ranking_ola(df, "Produto", 30), ranking_ola(df, "Categoria", 30), ranking_ola(df, "Grupo designado", 30)
    cat_crit = cat[cat["quadrante"] == "Escala crítica"].iloc[0]
    prod_crit = prod[prod["quadrante"] == "Escala crítica"].iloc[0]
    grupo_crit = grupo[grupo["quadrante"] == "Escala crítica"].iloc[0]
    capacidade_tab, curto, medio, governanca = st.tabs(
        ["Dimensionamento D+1", "Próximas 24h", "Próximos 7–30 dias", "Cenário de cobertura"]
    )
    with capacidade_tab:
        st.markdown("#### Premissas operacionais")
        st.caption(
            "A previsão de volume vem do modelo. Produtividade, ocupação e equipe disponível são premissas editáveis, "
            "pois esses dados não existem no dataset da Locaweb."
        )
        p1, p2, p3, p4 = st.columns(4)
        with p1:
            produtividade = st.number_input(
                "Incidentes por analista/dia", min_value=1, max_value=100, value=30, step=1
            )
        with p2:
            ocupacao = st.slider("Ocupação planejada", 50, 95, 80, 5)
        with p3:
            indisponibilidade = st.slider("Folga de indisponibilidade", 0, 35, 10, 5)
        with p4:
            equipe_atual = st.number_input("Analistas disponíveis", min_value=1, max_value=200, value=28, step=1)

        capacidade_efetiva = produtividade * (ocupacao / 100) * (1 - indisponibilidade / 100)
        cenarios_volume = {
            "Faixa inferior": previsao_d1["limite_inferior_80"],
            "Ponto central": previsao_d1["ponto"],
            "Faixa superior": previsao_d1["limite_superior_80"],
        }
        dimensionamento = pd.DataFrame(
            [
                [nome, int(round(volume)), int(np.ceil(volume / max(1e-9, capacidade_efetiva)))]
                for nome, volume in cenarios_volume.items()
            ],
            columns=["Cenário", "Volume previsto", "Analistas necessários"],
        )
        dimensionamento["Equipe disponível"] = int(equipe_atual)
        dimensionamento["Gap"] = dimensionamento["Analistas necessários"] - int(equipe_atual)
        centro = dimensionamento.iloc[1]
        alto = dimensionamento.iloc[2]
        dc1, dc2, dc3, dc4 = st.columns(4)
        dc1.metric("Capacidade efetiva", f"{fmt_num(capacidade_efetiva, 1)}", "incidentes/analista", delta_color="off")
        dc2.metric("Necessário · ponto", fmt_int(centro["Analistas necessários"]))
        dc3.metric("Necessário · faixa alta", fmt_int(alto["Analistas necessários"]))
        dc4.metric("Gap · faixa alta", f"{int(alto['Gap']):+d}", "positivo = falta", delta_color="off")

        visual_cap = dimensionamento.melt(
            id_vars="Cenário",
            value_vars=["Analistas necessários", "Equipe disponível"],
            var_name="Série",
            value_name="Analistas",
        )
        fig = px.bar(
            visual_cap,
            x="Cenário",
            y="Analistas",
            color="Série",
            barmode="group",
            text_auto=True,
            color_discrete_map={"Analistas necessários": ORANGE, "Equipe disponível": NAVY},
            labels={"Analistas": "Pessoas por dia"},
        )
        st.plotly_chart(estilizar_figura(fig, 365), width="stretch")

        if alto["Gap"] > 0:
            card_acao(
                "Decisão · faixa superior",
                f"Criar contingência para {int(alto['Gap'])} analistas-equivalentes",
                "Opções: reforço temporário, redistribuição entre grupos ou redução do backlog não crítico. "
                "A decisão final deve considerar habilidades e turnos, ausentes na base.",
                "red",
            )
        else:
            card_acao(
                "Decisão · faixa superior",
                f"Folga estimada de {abs(int(alto['Gap']))} analistas-equivalentes",
                "Preservar parte da folga para P1/P2 e confirmar se a produtividade informada inclui incidentes automáticos.",
                "teal",
            )
        st.download_button(
            "Baixar plano de capacidade (.csv)",
            data=dimensionamento.to_csv(index=False).encode("utf-8-sig"),
            file_name="plano_capacidade_d1.csv",
            mime="text/csv",
        )
        st.info(
            "CENÁRIO, não previsão de headcount: mudar qualquer premissa recalcula a necessidade. "
            "A estimativa de volume permanece fixa no snapshot e no modelo validado."
        )
    with curto:
        c1, c2 = st.columns(2)
        with c1:
            card_acao(
                "1 · dimensionar capacidade", f"Planejar para a faixa de {fmt_int(previsao_d1['limite_inferior_80'])}–{fmt_int(previsao_d1['limite_superior_80'])}",
                f"Ponto central do modelo: {fmt_int(previsao_d1['ponto'])} incidentes para {previsao_d1['data_alvo']:%d/%m/%Y}. Manter margem porque o MAE no holdout foi {fmt_num(metricas_op_idx.loc['D+1', 'holdout_MAE'], 1)}.", "red",
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
        st.download_button(
            "Baixar plano de ação (.csv)",
            data=plano.to_csv(index=False).encode("utf-8-sig"),
            file_name="plano_acao_7_30_dias.csv",
            mime="text/csv",
        )
        st.warning("A base não contém produtividade por analista nem custo por incidente. O dimensionamento usa premissas declaradas pelo operador e não inventa economia financeira.")
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
    f4, f5, f6 = st.columns(3)
    with f4:
        grupos_filtro = st.multiselect("Grupo designado", sorted(df["Grupo designado"].dropna().astype(str).unique()))
    with f5:
        produtos_filtro = st.multiselect("Produto", sorted(df["Produto"].dropna().astype(str).unique()))
    with f6:
        universo_filtro = st.selectbox("Universo", ["Todos", "Elegíveis ao KPI", "Violações elegíveis"])
    filtrado = df[(df["Aberto"].dt.date >= data_inicio) & (df["Aberto"].dt.date <= data_fim)]
    if prioridades:
        filtrado = filtrado[filtrado["Prioridade"].isin(prioridades)]
    if grupos_filtro:
        filtrado = filtrado[filtrado["Grupo designado"].isin(grupos_filtro)]
    if produtos_filtro:
        filtrado = filtrado[filtrado["Produto"].isin(produtos_filtro)]
    if universo_filtro == "Elegíveis ao KPI":
        filtrado = filtrado[filtrado["Elegivel_KPI_Regra"]]
    elif universo_filtro == "Violações elegíveis":
        filtrado = filtrado[filtrado["OLA_Violado_KPI_Regra"]]
    cols = ["Número", "Aberto", "Prioridade", "Produto", "Categoria", "Grupo designado", "Duracao_Horas", "Status_Exibicao", "Elegivel_KPI_Regra", "OLA_Violado_KPI_Regra"]
    st.dataframe(filtrado.sort_values("Aberto", ascending=False)[cols].head(500), width="stretch", hide_index=True)
    st.caption(f"Mostrando até 500 de {fmt_int(len(filtrado))} registros no filtro.")
    st.download_button(
        "Baixar recorte completo (.csv)",
        data=filtrado.sort_values("Aberto", ascending=False)[cols].to_csv(index=False).encode("utf-8-sig"),
        file_name="incidentes_filtrados_visionops.csv",
        mime="text/csv",
    )
    st.markdown(
        "<div class='source-box'><b>Linhas de evidência:</b> LW-DATASET.xlsx → tratamento determinístico → dataset_limpo.parquet → agregação diária → modelo. As recomendações são derivadas dos resultados exibidos; não há chamadas a IA generativa nem métricas sintéticas em tempo de execução.</div>",
        unsafe_allow_html=True,
    )
