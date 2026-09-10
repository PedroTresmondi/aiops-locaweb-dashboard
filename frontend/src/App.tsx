import { FormEvent, ReactNode, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowRight, BarChart3, CheckCircle2,
  ChevronRight, CircleGauge, Clock3, Database, ListChecks, Menu, Radar, Search,
  ShieldCheck, SlidersHorizontal, Target, TrendingUp, UploadCloud, Users, X,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend,
  Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api, apiUrl } from './api'
import { WorkflowProvider, StartPage, WorkQueue, ProductPlan, TeamPlan, ForecastHealth, Explain, ContextNote, fullDate, parseCsv, type Page } from './Workflow'
import type {
  AdvancedModel, Capacity, Diagnostic, Drift, ItemFila, ModelStatus, Models, Optimization, Overview,
  DataStatus, Perfil, PilotMetrics, RespostaFila, ResumoAcoes, Segmentation, TriageResult,
} from './types'


const nav: { id: Page; label: string; icon: typeof Activity }[] = [
  { id: 'overview', label: 'Início', icon: CircleGauge },
  { id: 'queue', label: 'Revisar chamados', icon: ListChecks },
  { id: 'triage', label: 'Avaliar novo chamado', icon: ShieldCheck },
  { id: 'diagnostics', label: 'Analisar problemas', icon: Target },
  { id: 'optimization', label: 'Revisar produtos', icon: SlidersHorizontal },
  { id: 'capacity', label: 'Planejar equipe', icon: Users },
  { id: 'pilot', label: 'Operação piloto', icon: Activity },
  { id: 'monitor', label: 'Situação dos modelos', icon: Radar },
  { id: 'models', label: 'Validação dos modelos', icon: BarChart3 },
  { id: 'audit', label: 'Qualidade dos dados', icon: Database },
]

const PERFIS: { id: Perfil; label: string }[] = [
  { id: 'analista', label: 'Analista' },
  { id: 'gestor', label: 'Gestor' },
  { id: 'administrador', label: 'Administrador' },
]

function usePerfil(): [Perfil, (p: Perfil) => void] {
  const [perfil, setPerfil] = useState<Perfil>(() => {
    try { return (localStorage.getItem('visionops.perfil') as Perfil) || 'analista' } catch { return 'analista' }
  })
  const trocar = (p: Perfil) => {
    setPerfil(p)
    try { localStorage.setItem('visionops.perfil', p) } catch { /* ambiente sem storage */ }
  }
  return [perfil, trocar]
}

const int = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })
const dec = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const pct = (value: number, digits = 1) => `${(value * 100).toFixed(digits).replace('.', ',')}%`
const date = (value: string) => new Date(`${value}T12:00:00`).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })

function Loading({ label = 'Preparando análise operacional' }: { label?: string }) {
  return <div className="loading"><div className="loader"/><strong>{label}</strong><span>Análise da base histórica. Na primeira abertura, o servidor pode levar até um minuto para iniciar.</span></div>
}

function ErrorState({ message }: { message: string }) {
  return <div className="error-state"><AlertTriangle/><div><strong>Não foi possível carregar esta análise</strong><p>{message}</p></div></div>
}

function PageTitle({ eyebrow, title, copy, actions }: { eyebrow: string; title: string; copy: string; actions?: ReactNode }) {
  return <div className="page-title">
    <div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{copy}</p></div>
    {actions && <div className="page-actions">{actions}</div>}
  </div>
}

function StatCard({ icon, label, value, detail, tone = 'navy' }: { icon: ReactNode; label: string; value: string; detail: string; tone?: string }) {
  return <article className={`stat-card ${tone}`}>
    <div className="stat-head"><span>{label}</span><div className="stat-icon">{icon}</div></div>
    <strong>{value}</strong><p>{detail}</p>
  </article>
}

function Panel({ title, subtitle, children, className = '' }: { title: string; subtitle?: string; children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}><div className="panel-head"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div></div>{children}</section>
}

function TriagePage() {
  const [options, setOptions] = useState<{ produtos: string[]; categorias: string[]; grupos: string[]; ultimaData: string }>()
  const [form, setForm] = useState({ prioridade: 3, produto: '', categoria: '', grupo: '', data: '2026-01-01', hora: '09:00' })
  const [result, setResult] = useState<TriageResult>()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    api<typeof options>('/api/options').then(o => {
      if (!o) return
      setOptions(o)
      setForm(f => ({ ...f, produto: o.produtos.includes('lemn') ? 'lemn' : o.produtos[0], categoria: o.categorias.includes('cat45') ? 'cat45' : o.categorias[0], grupo: o.grupos.includes('Team05') ? 'Team05' : o.grupos[0] }))
    }).catch(e => setError(e.message))
  }, [])
  useEffect(() => { setResult(undefined) }, [form])
  async function submit(event?: FormEvent) {
    event?.preventDefault(); setLoading(true); setError('')
    try {
      setResult(await api<TriageResult>('/api/triage', { method: 'POST', body: JSON.stringify({ prioridade: form.prioridade, produto: form.produto, categoria: form.categoria, grupo: form.grupo, data_hora: `${form.data}T${form.hora}:00` }) }))
    } catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }
  return <>
    <PageTitle eyebrow="Operação diária" title="Qual é o risco deste chamado?" copy="Informe os dados de abertura para apoiar a revisão de prioridade e encaminhamento."/>
    <ContextNote>Estimativa individual com o modelo histórico. Alterar os campos limpa a estimativa anterior; clique em Avaliar risco para calcular novamente.</ContextNote>
    <div className="content-grid form-layout">
      <Panel title="Contexto do incidente" subtitle="Somente variáveis conhecidas na abertura">
        {!options ? <Loading label="Carregando valores históricos"/> : <form className="form-grid" onSubmit={submit}>
          <label><span>Prioridade</span><select disabled={loading} aria-label="Prioridade" value={form.prioridade} onChange={e => setForm({ ...form, prioridade: +e.target.value })}>{[1,2,3,4,5].map(v => <option key={v} value={v}>P{v}</option>)}</select></label>
          <label><span>Produto</span><select disabled={loading} value={form.produto} onChange={e => setForm({ ...form, produto: e.target.value })}>{options.produtos.map(v => <option key={v}>{v}</option>)}</select></label>
          <label><span>Categoria</span><select disabled={loading} value={form.categoria} onChange={e => setForm({ ...form, categoria: e.target.value })}>{options.categorias.map(v => <option key={v}>{v}</option>)}</select></label>
          <label><span>Grupo designado</span><select disabled={loading} value={form.grupo} onChange={e => setForm({ ...form, grupo: e.target.value })}>{options.grupos.map(v => <option key={v}>{v}</option>)}</select></label>
          <label><span>Data</span><input disabled={loading} type="date" value={form.data} onChange={e => setForm({ ...form, data: e.target.value })}/></label>
          <label><span>Hora</span><input disabled={loading} type="time" value={form.hora} onChange={e => setForm({ ...form, hora: e.target.value })}/></label>
          <button className="primary-button span-2" disabled={loading}>{loading ? 'Calculando risco…' : <><ShieldCheck size={18}/> Avaliar risco</>}</button>
        </form>}
        {error && <ErrorState message={error}/>} 
      </Panel>
      <section className={`risk-result ${result ? result.faixa.toLowerCase() : ''}`}>
        {!result ? <div className="empty-result"><ShieldCheck/><h2>Aguardando os dados do chamado</h2><p>Preencha o contexto para calcular o risco. A análise usa somente informações disponíveis na abertura.</p></div> : <>
          <div className="risk-top"><span>Risco estimado de descumprir o prazo</span><span className="risk-badge">{result.faixa}</span></div>
          <div className="risk-value">{pct(result.probabilidade)}</div>
          <div className="risk-track"><span style={{ width: `${Math.min(100, result.probabilidade * 100)}%` }}/></div>
          <p>{result.acao}</p>
          <div className="risk-meta"><div><span>Taxa-base</span><strong>{pct(result.taxaBase)}</strong></div><div><span>Risco relativo</span><strong>{dec.format(result.multiplicadorBase)}×</strong></div><div><span>Limiar alto</span><strong>{pct(result.limiarAlto)}</strong></div></div>
        </>}
      </section>
    </div>
    {result && <Explain title="Consultar as taxas históricas do contexto"><Panel title="Evidência histórica" subtitle="Associação histórica; não comprova a causa do atraso.">
      <div className="evidence-grid">{result.evidencias.map(item => <div className="evidence" key={item.fator}><span>{item.fator}</span><strong>{item.taxa == null ? 'Sem amostra' : pct(item.taxa)}</strong><small>{int.format(item.amostra)} incidentes</small></div>)}</div>
    </Panel></Explain>}
  </>
}

function SegmentacaoPanel({ dimension }: { dimension: string }) {
  const [data, setData] = useState<Segmentation>()
  const [error, setError] = useState('')
  useEffect(() => { let active = true; setData(undefined); setError(''); api<Segmentation>(`/api/segmentation?dimension=${encodeURIComponent(dimension)}`).then(d => { if (active) setData(d) }).catch(e => { if (active) setError(e.message) }); return () => { active = false } }, [dimension])
  if (error) return <ErrorState message={error}/>
  if (!data) return <Panel title="Grupos de criticidade" subtitle="Carregando"><Loading/></Panel>
  return <Panel title="Grupos de criticidade" subtitle={`Agrupamento estatístico com K=${data.kEscolhido}, selecionado por ${data.criterio}`}>
    <div className="model-table">
      <div className="table-row table-head"><span>Cluster</span><span>Entidades</span><span>Incidentes</span><span>OLA violados</span><span>Taxa média</span></div>
      {data.clusters.map(c => <div className="table-row" key={c.posicao}>
        <strong>{c.rotulo}</strong><span>{int.format(c.entidades)}</span><span>{int.format(c.incidentesTotal)}</span>
        <span>{int.format(c.olaViolados)}</span><span className={c.posicao === 0 ? 'negative' : ''}>{pct(c.taxaMedia)}</span>
      </div>)}
    </div>
    <div className="insight"><BarChart3 size={18}/><p><strong>Leitura:</strong> compare a quantidade de casos e a taxa de violação de cada grupo. Uma taxa alta em poucos casos tem significado diferente de um grande volume de atrasos.</p></div>
  </Panel>
}

function DiagnosticsPage() {
  const [dimension, setDimension] = useState('Categoria')
  const [data, setData] = useState<Diagnostic>()
  const [error, setError] = useState('')
  useEffect(() => { let active = true; setData(undefined); setError(''); api<Diagnostic>(`/api/diagnostics?dimension=${encodeURIComponent(dimension)}&min_sample=30`).then(d => { if (active) setData(d) }).catch(e => { if (active) setError(e.message) }); return () => { active = false } }, [dimension])
  return <>
    <PageTitle eyebrow="Análise operacional" title="Onde os atrasos se concentram?" copy="Compare os grupos com mais descumprimentos do prazo interno de atendimento (OLA)." actions={<div className="segmented">{['Categoria','Produto','Grupo designado'].map(v => <button className={dimension === v ? 'active' : ''} onClick={() => setDimension(v)} key={v}>{v === 'Grupo designado' ? 'Grupo' : v}</button>)}</div>}/>
    <ContextNote>Análise do histórico completo, de 02/01/2023 a 31/12/2025. Não segue o filtro da fila. Os códigos são os identificadores fornecidos na base.</ContextNote>
    {data?.items[0] && <section className="decision-hero compact"><span className="eyebrow">Ponto de partida para investigação</span><h2>Investigue {data.items[0].nome}</h2><p>Este item concentra {int.format(data.items[0].violacoes)} descumprimentos em {int.format(data.items[0].elegiveis)} chamados elegíveis ({pct(data.items[0].taxa)}). Confira os casos recorrentes com o grupo responsável e identifique impedimentos no atendimento.</p></section>}
    {error ? <ErrorState message={error}/> : !data ? <Loading/> : <div className="content-grid wide-left">
      <Panel title={`Mais atrasos por ${dimension.toLowerCase()}`} subtitle="Quantidade de descumprimentos. Compare a taxa no quadro ao lado para considerar o tamanho de cada grupo.">
        <div className="chart-xl"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.items.slice(0, 10)} layout="vertical" margin={{ left: 5, right: 20, top: 5, bottom: 5 }}>
          <CartesianGrid horizontal={false} stroke="#e7edf4"/><XAxis type="number" axisLine={false} tickLine={false}/><YAxis type="category" dataKey="nome" width={90} tick={{ fontSize: 11 }} axisLine={false} tickLine={false}/><Tooltip formatter={value => int.format(Number(value))}/><Bar dataKey="violacoes" name="Violações" radius={[0, 6, 6, 0]}>{data.items.slice(0,10).map((_, i) => <Cell key={i} fill={i < 3 ? '#ef6236' : '#274c77'}/>)}</Bar>
        </BarChart></ResponsiveContainer></div>
      </Panel>
      <Panel title="Fila de ação" subtitle={`Taxa geral: ${pct(data.taxaGeral)}`}>
        <div className="action-list">{data.items.slice(0, 6).map((item, index) => <div className="action-item" key={item.nome}><span className="rank">{index + 1}</span><div><strong>{item.nome}</strong><small>{int.format(item.violacoes)} violações de {int.format(item.elegiveis)}</small></div><div className={item.taxa > data.taxaGeral ? 'rate bad' : 'rate'}>{pct(item.taxa)}</div></div>)}</div>
        <div className="insight"><BarChart3 size={18}/><p><strong>Prioridade sugerida:</strong> comece pelos itens com mais violações. Use a taxa para identificar casos em que o risco permanece alto mesmo com menor volume.</p></div>
      </Panel>
    </div>}
    <Explain title="Explorar agrupamentos estatísticos"><SegmentacaoPanel dimension={dimension}/></Explain>
  </>
}

function AdvancedModelPanel() {
  const [data, setData] = useState<AdvancedModel>()
  const [horizonte, setHorizonte] = useState('D+1')
  const [error, setError] = useState('')
  useEffect(() => { api<AdvancedModel>('/api/models/advanced').then(setData).catch(e => setError(e.message)) }, [])
  if (error) return <Panel title="Modelo avançado de previsão (extensão)" subtitle="Erro"><ErrorState message={error}/></Panel>
  if (!data) return <Panel title="Modelo avançado de previsão (extensão)" subtitle="Rodando backtest rolling-origin"><Loading/></Panel>
  const m = data.metricas.find(x => x.horizonte === horizonte)!
  const bt = data.backtest.filter(x => x.horizonte === horizonte)
  const imp = data.importancias.filter(x => x.horizonte === horizonte)
  const prev = data.previsoes.find(x => x.horizonte === horizonte)!
  return <Panel title="Modelo avançado de previsão (extensão Sprint 4)" subtitle={`${data.janelaBacktest.descricao} · ${data.janelaBacktest.inicio} a ${data.janelaBacktest.fim} · ${m.nPontos} previsões diárias`}
    className="advanced-panel">
    <div className="segmented" style={{ marginBottom: 14 }}>{['D+1', 'D+7'].map(h => <button key={h} className={horizonte === h ? 'active' : ''} onClick={() => setHorizonte(h)}>{h}</button>)}</div>
    <div className="stats-grid">
      <StatCard icon={<BarChart3/>} label={`MAE ${horizonte} · backtest`} value={dec.format(m.mae)} detail={`${m.nPontos} previsões · WAPE ${pct(m.wape)}`} tone="navy"/>
      <StatCard icon={<TrendingUp/>} label="vs. baseline linear" value={pct(m.ganhoVsBaseline)} detail={`MAE baseline: ${dec.format(m.maeBaseline)}`} tone="teal"/>
      <StatCard icon={<Target/>} label="vs. ensemble operacional" value={pct(m.ganhoVsOperacional)} detail={`MAE operacional: ${dec.format(m.maeOperacional)}`} tone={m.ganhoVsOperacional >= 0 ? 'teal' : 'orange'}/>
      <StatCard icon={<Clock3/>} label={`Previsão ${horizonte} · ${date(prev.dataAlvo)}`} value={int.format(prev.ponto)} detail={`${int.format(prev.inferior)}–${int.format(prev.superior)}${prev.alvoFeriado ? ' · alvo é feriado' : ''}`} tone="orange"/>
    </div>
    <div className="content-grid equal">
      <div className="chart-md"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={bt} margin={{ top: 15, right: 15, left: -8 }}>
        <CartesianGrid vertical={false} stroke="#223147"/><XAxis dataKey="dataAlvo" tickFormatter={date} minTickGap={30} tick={{ fontSize: 10 }}/><YAxis tick={{ fontSize: 10 }}/><Tooltip labelFormatter={l => date(String(l))} formatter={v => int.format(Number(v))}/><Legend/>
        <Line dataKey="real" name="Observado" stroke="#e6e9ef" strokeWidth={2} dot={false}/>
        <Line dataKey="baseline" name="Baseline linear" stroke="#8a97a8" strokeWidth={1.5} strokeDasharray="4 3" dot={false}/>
        <Line dataKey="avancado" name="Avançado" stroke="#a993ff" strokeWidth={2.5} dot={false}/>
      </ComposedChart></ResponsiveContainer></div>
      <div className="chart-md"><ResponsiveContainer width="100%" height="100%"><BarChart data={imp} layout="vertical" margin={{ left: 10, right: 15 }}>
        <CartesianGrid horizontal={false} stroke="#223147"/><XAxis type="number" tick={{ fontSize: 10 }}/><YAxis type="category" dataKey="variavel" width={140} tick={{ fontSize: 10 }}/><Tooltip formatter={v => dec.format(Number(v))}/>
        <Bar dataKey="importancia" name="Impacto no MAE (permutação)" radius={[0, 6, 6, 0]}>{imp.map(i => <Cell key={i.variavel} fill={i.eFeriado ? '#ef6236' : '#274c77'}/>)}</Bar>
      </BarChart></ResponsiveContainer></div>
    </div>
    <div className="method-note"><ShieldCheck/><p>
      <strong>Extensão em validação — não substitui o ensemble operacional publicado.</strong> Adiciona: feriados nacionais do Brasil (fatos de calendário; {data.feriados.length} no período), perda de Poisson (respeita contagem), pesos por recência e um backtest de origem móvel com {m.nPontos} previsões diárias em vez do holdout único de dezembro. Compare os ganhos medidos nos cartões acima. A previsão considera o calendário de feriados — a estimativa para 01/01 é {int.format(data.previsoes.find(x => x.horizonte === 'D+1')!.ponto)} (alvo é feriado).
    </p></div>
  </Panel>
}

function ModelsPage() {
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [data, setData] = useState<Models>()
  const [error, setError] = useState('')
  useEffect(() => { api<Models>('/api/models').then(setData).catch(e => setError(e.message)) }, [])
  if (error) return <ErrorState message={error}/>
  if (!data) return <Loading label="Carregando validação temporal"/>
  return <>
    <PageTitle eyebrow="Validação das previsões" title="Validação dos modelos" copy="Resultados em período separado, calibração do risco e variáveis usadas no cálculo."/>
    <div className="stats-grid">
      <StatCard icon={<BarChart3/>} label="ROC-AUC risco" value={data.risk.rocAuc.toFixed(3)} detail="Discriminação no período de teste" tone="navy"/>
      <StatCard icon={<Target/>} label="PR-AUC risco" value={data.risk.prAuc.toFixed(3)} detail={`Base positiva: ${pct(data.risk.prevalencia)}`} tone="orange"/>
      <StatCard icon={<ShieldCheck/>} label="Captura de violações" value={pct(data.risk.captura)} detail={`Com ${pct(data.risk.filaAlta)} dos casos`} tone="teal"/>
      <StatCard icon={<TrendingUp/>} label="Lift da fila" value={`${dec.format(data.risk.lift)}×`} detail={`Precisão: ${pct(data.risk.precisaoFila)}`} tone="red"/>
    </div>
    <div className="content-grid equal">
      <Panel title="Calibração do risco" subtitle="Probabilidade prevista versus taxa realmente observada">
        <div className="chart-md"><ResponsiveContainer width="100%" height="100%"><LineChart data={data.calibration} margin={{ top: 15, right: 15, left: -5 }}><CartesianGrid stroke="#e7edf4"/><XAxis dataKey="decil" label={{ value: 'Decil', position: 'insideBottom', offset: -3 }}/><YAxis tickFormatter={v => `${Math.round(v*100)}%`}/><Tooltip formatter={value => pct(Number(value))}/><Line dataKey="previsto" name="Previsto" stroke="#2563eb" strokeWidth={2.5}/><Line dataKey="observado" name="Observado" stroke="#ef6236" strokeWidth={2.5}/><Legend/></LineChart></ResponsiveContainer></div>
      </Panel>
      <Panel title="Importância operacional" subtitle="Queda de PR-AUC ao remover o sinal">
        <div className="chart-md"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.importance} layout="vertical" margin={{ left: 10, right: 15 }}><CartesianGrid horizontal={false} stroke="#e7edf4"/><XAxis type="number"/><YAxis type="category" dataKey="variavel" width={112} tick={{ fontSize: 11 }}/><Tooltip/><Bar dataKey="valor" name="Queda de PR-AUC" fill="#274c77" radius={[0,6,6,0]}/></BarChart></ResponsiveContainer></div>
      </Panel>
    </div>
    <Panel title="Previsão de volume" subtitle="Holdout temporal de dezembro de 2025">
      <div className="model-table"><div className="table-row table-head"><span>Horizonte</span><span>Modelo selecionado</span><span>MAE</span><span>WAPE</span><span>Ganho</span></div>{data.volume.map(row => <div className="table-row" key={row.horizonte}><strong>{row.horizonte}</strong><span>{row.modelo}</span><span>{dec.format(row.mae)}</span><span>{pct(row.wape)}</span><span className={row.ganho >= 0 ? 'positive' : 'negative'}>{pct(row.ganho)}</span></div>)}</div>
      <div className="method-note"><ShieldCheck/><p><strong>Sem vazamento de alvo.</strong> O classificador utiliza apenas prioridade, produto, categoria, grupo e contexto temporal disponíveis na abertura. Dezembro permaneceu intocado até o teste final.</p></div>
    </Panel>
    <Explain title="Consultar a extensão com feriados e validação por origem móvel" onOpen={setAdvancedOpen}>{advancedOpen && <AdvancedModelPanel/>}</Explain>
  </>
}

function AuditPage() {
  const [data, setData] = useState<{ missing: { campo: string; faltantes: number; taxa: number }[]; sample: Record<string, unknown>[] }>()
  const [error, setError] = useState('')
  useEffect(() => { api<typeof data>('/api/audit?limit=50').then(d => d && setData(d)).catch(e => setError(e.message)) }, [])
  if (error) return <ErrorState message={error}/>
  if (!data) return <Loading/>
  const columns = data.sample.length ? Object.keys(data.sample[0]) : []
  return <>
    <PageTitle eyebrow="Qualidade da base" title="Qualidade dos dados" copy="Completude, universo analisado e registros que sustentam as decisões."/>
    <div className="quality-grid">{data.missing.map(item => <article key={item.campo}><div><span>{item.campo}</span><strong>{pct(1-item.taxa)} completos</strong></div><div className="quality-track"><span style={{ width: `${(1-item.taxa)*100}%` }}/></div><small>{int.format(item.faltantes)} ausentes</small></article>)}</div>
    <Panel title="Amostra auditável" subtitle="50 registros mais recentes do snapshot — nenhuma linha sintética">
      <div className="data-table-wrap"><table><thead><tr>{columns.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{data.sample.map((row, index) => <tr key={index}>{columns.map(c => <td key={c}>{typeof row[c] === 'boolean' ? (row[c] ? 'Sim' : 'Não') : String(row[c] ?? '—')}</td>)}</tr>)}</tbody></table></div>
    </Panel>
  </>
}

function PilotPage() {
  const [metrics, setMetrics] = useState<PilotMetrics>()
  const [status, setStatus] = useState<DataStatus>()
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [token, setToken] = useState('')
  const [outcome, setOutcome] = useState({ ticketRef: '', olaViolado: 'false', resolvidoEm: '', esforcoMinutos: 0 })
  const load = () => Promise.all([api<PilotMetrics>('/api/pilot/metrics'), api<DataStatus>('/api/data/status')]).then(([m, s]) => { setMetrics(m); setStatus(s) }).catch(e => setError(e.message))
  useEffect(() => { load() }, [])
  async function saveOutcome(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(''); setMessage('')
    try {
      await api('/api/pilot/outcomes', { method: 'POST', body: JSON.stringify({ ...outcome, olaViolado: outcome.olaViolado === 'true', resolvidoEm: outcome.resolvidoEm || null }) })
      setMessage('Desfecho salvo. As métricas do piloto foram recalculadas.'); await load()
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }
  async function importHistory(file: File) {
    setBusy(true); setError(''); setMessage('')
    try {
      const records = parseCsv(await file.text())
      if (records.length > 100000) throw new Error('Importe até 100.000 incidentes por arquivo.')
      const result = await api<{ importacao: { recebidos: number; novos: number; atualizados: number; snapshotDepois: string }; retreino: { status: string } }>('/api/data/import', { method: 'POST', headers: { 'X-VisionOps-Admin': token }, body: JSON.stringify({ itens: records, retreinar: true }) })
      setMessage(`${result.importacao.recebidos} registros processados: ${result.importacao.novos} novos e ${result.importacao.atualizados} atualizados. Retreino ${result.retreino.status}.`); await load()
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }
  if (!metrics || !status) return error ? <ErrorState message={error}/> : <Loading label="Carregando operação piloto"/>
  return <>
    <PageTitle eyebrow="Próximos passos implementados" title="Operação piloto e atualização" copy="Meça o uso, informe desfechos e revalide os modelos com uma nova exportação de incidentes."/>
    <ContextNote>Fonte atual: {status.origem} · {int.format(status.incidentes)} incidentes · dados até {fullDate(status.snapshot)}.</ContextNote>
    <div className="stats-grid pilot-stats">
      <StatCard icon={<ListChecks/>} label="Chamados com decisão" value={int.format(metrics.chamadosComDecisao)} detail={`${int.format(metrics.chamadosComDesfecho)} com desfecho informado`} tone="navy"/>
      <StatCard icon={<Clock3/>} label="Tempo médio de reação" value={metrics.tempoReacaoMedioHoras === null ? 'Sem medição' : `${dec.format(metrics.tempoReacaoMedioHoras)} h`} detail={`${metrics.reacoesMedidas} reações calculadas`} tone="orange"/>
      <StatCard icon={<Activity/>} label="Esforço registrado" value={`${dec.format(metrics.esforcoTotalMinutos)} min`} detail="Decisão e fechamento do piloto" tone="teal"/>
      <StatCard icon={<ShieldCheck/>} label="Violação de OLA" value={metrics.taxaViolacaoOla === null ? 'Sem desfecho' : pct(metrics.taxaViolacaoOla)} detail={`${metrics.violacoes} violações observadas`} tone="red"/>
    </div>
    <div className="content-grid equal">
      <Panel title="1. Informar o resultado do piloto" subtitle="Use um chamado importado por CSV que já tenha uma decisão registrada.">
        <form className="form-grid" onSubmit={saveOutcome}>
          <label><span>Número do chamado</span><input required value={outcome.ticketRef} onChange={e => setOutcome(s => ({ ...s, ticketRef: e.target.value }))}/></label>
          <label><span>Resultado de OLA</span><select value={outcome.olaViolado} onChange={e => setOutcome(s => ({ ...s, olaViolado: e.target.value }))}><option value="false">Cumpriu o OLA</option><option value="true">Violou o OLA</option></select></label>
          <label><span>Data e hora da resolução</span><input type="datetime-local" value={outcome.resolvidoEm} onChange={e => setOutcome(s => ({ ...s, resolvidoEm: e.target.value }))}/></label>
          <label><span>Esforço no fechamento (minutos)</span><input type="number" min="0" max="10080" value={outcome.esforcoMinutos} onChange={e => setOutcome(s => ({ ...s, esforcoMinutos: +e.target.value }))}/></label>
          <button className="primary-button span-2" disabled={busy}>Salvar desfecho e recalcular</button>
        </form>
        <p className="subtle">Tempo de reação: abertura do chamado até a primeira decisão no VisionOps. Esforço: soma dos minutos informados na decisão e no desfecho.</p>
      </Panel>
      <Panel title="2. Atualizar a base e retreinar" subtitle="Importação protegida por chave administrativa. O arquivo substitui chamados com o mesmo número.">
        <div className="form-grid">
          <label className="span-2"><span>Chave administrativa do backend</span><input type="password" value={token} onChange={e => setToken(e.target.value)} autoComplete="off"/></label>
          <label className="span-2"><span>Exportação CSV de incidentes recentes</span><input type="file" accept=".csv" disabled={busy || !token} onChange={e => { const f = e.target.files?.[0]; if (f) importHistory(f); e.target.value = '' }}/></label>
          <a className="ghost-button span-2" href={apiUrl('/api/data/template')}>Baixar modelo de atualização</a>
        </div>
        <p>{status.adminConfigurado ? 'O backend está preparado para receber uma atualização autenticada.' : 'A atualização está bloqueada até configurar VISIONOPS_ADMIN_TOKEN no backend.'}</p>
        <p className="subtle">O retreino recalcula volume, risco e P2/P3. Registros sem duração ou resolução entram no volume, mas não no treino do risco até terem desfecho conhecido.</p>
      </Panel>
    </div>
    {error && <div role="alert" className="error-state">{error}</div>}
    {message && <p role="status" className="save-success"><CheckCircle2 size={17}/>{message}</p>}
    <div className="method-note"><ShieldCheck/><p><strong>Interpretação.</strong> {metrics.nota} {status.notaPersistencia}</p></div>
  </>
}

function AppShell() {
  const route = (): Page => nav.some(n => n.id === window.location.hash.slice(1)) ? window.location.hash.slice(1) as Page : 'overview'
  const [page, setPage] = useState<Page>(route)
  const [sidebar, setSidebar] = useState(false)
  const [perfil, setPerfil] = usePerfil()
  const [help, setHelp] = useState(false)
  const current = nav.find(item => item.id === page)!
  const navigate = (target: Page) => {
    window.location.hash = target
    setPage(target); setSidebar(false); setHelp(false)
    window.scrollTo({ top: 0, behavior: 'instant' })
  }
  useEffect(() => {
    const changed = () => { setPage(route()); setSidebar(false); setHelp(false); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', changed)
    return () => window.removeEventListener('hashchange', changed)
  }, [])
  const workspace = page === 'queue' ? <WorkQueue perfil={perfil} navigate={navigate}/>
    : page === 'overview' ? <StartPage navigate={navigate}/>
    : page === 'triage' ? <TriagePage/>
    : page === 'diagnostics' ? <DiagnosticsPage/>
    : page === 'optimization' ? <ProductPlan navigate={navigate}/>
    : page === 'capacity' ? <TeamPlan navigate={navigate}/>
    : page === 'pilot' ? <PilotPage/>
    : page === 'monitor' ? <ForecastHealth/>
    : page === 'models' ? <ModelsPage/>
    : <AuditPage/>
  const navButton = (id: Page) => {
    const item = nav.find(n => n.id === id)!; const Icon = item.icon
    return <button key={id} aria-current={page === id ? 'page' : undefined} className={page === id ? 'active' : ''} onClick={() => navigate(id)}><Icon/><span>{item.label}</span>{page === id && <ChevronRight className="chevron"/>}</button>
  }
  return <div className="app-shell">
    <a className="skip-link" href="#main-content" onClick={e => { e.preventDefault(); document.getElementById('main-content')?.focus() }}>Ir para o conteúdo</a>
    <aside className={sidebar ? 'sidebar open' : 'sidebar'}>
      <div className="brand"><div className="brand-mark"><Activity/></div><div><strong>VisionOps</strong><span>GESTÃO OPERACIONAL</span></div><button className="close-menu" aria-label="Fechar menu" onClick={() => setSidebar(false)}><X/></button></div>
      <nav aria-label="Navegação principal">
        {navButton('overview')}
        <span className="nav-section">Atendimento</span>{navButton('queue')}
        <span className="nav-section">Planejamento</span>{navButton('capacity')}{navButton('optimization')}
        <span className="nav-section">Operação</span>{navButton('pilot')}
        <span className="nav-section">Investigação</span>{navButton('diagnostics')}
        <details className="technical-nav" open={['monitor', 'models', 'audit'].includes(page) || undefined}><summary>Dados e modelos</summary>{navButton('monitor')}{navButton('models')}{navButton('audit')}</details>
      </nav>
      <label className="perfil-picker"><span>Perfil de demonstração</span><select value={perfil} onChange={e => setPerfil(e.target.value as Perfil)}>{PERFIS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}</select><small>Visão de trabalho, sem autenticação.</small></label>
      <div className="sidebar-status"><Database size={18}/><div><strong>Base histórica</strong><span>Jan/2023 a dez/2025</span></div></div>
    </aside>
    <main id="main-content" tabIndex={-1}>
      <header className="topbar"><button className="menu-button" aria-label="Abrir menu" onClick={() => setSidebar(true)}><Menu/></button><div className="breadcrumb"><current.icon/><span>{current.label}</span></div><div className="top-actions"><span className="history-badge">Histórico e piloto controlado</span><button className="ghost-button" aria-expanded={help} onClick={() => setHelp(v => !v)}>Como usar</button></div></header>
      <div className="workspace">
        {help && <section className="usage-guide"><h2>Do risco ao encaminhamento</h2><ol><li>Abra <strong>Revisar chamados</strong> e escolha o período.</li><li>Filtre o risco e selecione um chamado na lista.</li><li>Confira a recomendação e registre sua decisão no painel ao lado.</li></ol><p><strong>OLA</strong> é o prazo interno de atendimento definido na base. <strong>Risco</strong> é uma estimativa de descumprimento, não um atraso confirmado. O registro fica no VisionOps e não aciona um sistema externo.</p><button className="text-button" onClick={() => setHelp(false)}>Fechar orientações</button></section>}
        {workspace}
      </div>
    </main>
    {sidebar && <div className="scrim" onClick={() => setSidebar(false)}/>}
  </div>
}
export default function App() {
  return <WorkflowProvider><AppShell/></WorkflowProvider>
}
