import { FormEvent, ReactNode, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowRight, BarChart3, BrainCircuit, CheckCircle2,
  ChevronRight, CircleGauge, Clock3, Database, Menu, Search, ShieldCheck,
  Sparkles, Target, TrendingUp, Users, X,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend,
  Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from './api'
import type { Capacity, Diagnostic, Models, Overview, TriageResult } from './types'

type Page = 'overview' | 'triage' | 'diagnostics' | 'capacity' | 'models' | 'audit'

const nav: { id: Page; label: string; icon: typeof Activity }[] = [
  { id: 'overview', label: 'Visão operacional', icon: CircleGauge },
  { id: 'triage', label: 'Triagem preditiva', icon: Sparkles },
  { id: 'diagnostics', label: 'Diagnóstico de OLA', icon: Target },
  { id: 'capacity', label: 'Capacidade & ação', icon: Users },
  { id: 'models', label: 'Modelos & validação', icon: BrainCircuit },
  { id: 'audit', label: 'Qualidade dos dados', icon: Database },
]

const int = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })
const dec = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const pct = (value: number, digits = 1) => `${(value * 100).toFixed(digits).replace('.', ',')}%`
const date = (value: string) => new Date(`${value}T12:00:00`).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })

function Loading({ label = 'Preparando análise operacional' }: { label?: string }) {
  return <div className="loading"><div className="loader"/><strong>{label}</strong><span>Os modelos são calculados com o snapshot real.</span></div>
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

function OverviewPage() {
  const [data, setData] = useState<Overview>()
  const [error, setError] = useState('')
  useEffect(() => { api<Overview>('/api/overview').then(setData).catch(e => setError(e.message)) }, [])
  if (error) return <ErrorState message={error}/>
  if (!data) return <Loading label="Executando previsões e validações"/>
  const d1 = data.forecast[0]
  const d7 = data.forecast[1]
  return <>
    <PageTitle eyebrow="Command center" title="Visão operacional" copy={`Snapshot de ${date(data.snapshot.inicio)} a ${date(data.snapshot.fim)} · decisões com rastreabilidade`} actions={<button className="ghost-button"><Clock3 size={16}/> Atualizado no snapshot</button>}/>
    <div className="stats-grid">
      <StatCard icon={<Activity/>} label="Demanda prevista D+1" value={int.format(d1.ponto)} detail={`Faixa de 80%: ${int.format(d1.inferior)}–${int.format(d1.superior)}`} tone="orange"/>
      <StatCard icon={<TrendingUp/>} label="Demanda prevista D+7" value={int.format(d7.ponto)} detail={`Faixa de 80%: ${int.format(d7.inferior)}–${int.format(d7.superior)}`} tone="teal"/>
      <StatCard icon={<ShieldCheck/>} label="Violação de OLA" value={pct(data.snapshot.taxaOla, 2)} detail={`${int.format(data.snapshot.violacoes)} de ${int.format(data.snapshot.elegiveis)} elegíveis`} tone="red"/>
      <StatCard icon={<Target/>} label="Captura na fila de risco" value={pct(data.risk.captura)} detail={`Revisando ${pct(data.risk.filaAlta)} · lift ${dec.format(data.risk.lift)}×`} tone="violet"/>
    </div>
    <div className="content-grid wide-left">
      <Panel title="Pulso da operação" subtitle="Volume diário observado nos últimos 120 dias">
        <div className="chart-lg"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data.daily} margin={{ top: 15, right: 10, left: -15, bottom: 0 }}>
          <defs><linearGradient id="volumeFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#3b82f6" stopOpacity={.3}/><stop offset="1" stopColor="#3b82f6" stopOpacity={0}/></linearGradient></defs>
          <CartesianGrid vertical={false} stroke="#e7edf4"/><XAxis dataKey="data" tickFormatter={date} minTickGap={38} axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip labelFormatter={label => date(String(label))} formatter={value => [int.format(Number(value)), 'Incidentes']}/><Area type="monotone" dataKey="incidentes" stroke="#2563eb" strokeWidth={2.4} fill="url(#volumeFill)"/>
        </AreaChart></ResponsiveContainer></div>
      </Panel>
      <Panel title="Decisão recomendada" subtitle="Próxima ação baseada nos sinais atuais" className="decision-panel">
        <div className="decision-icon"><Sparkles/></div>
        <h3>Dimensione pela faixa superior</h3>
        <p>Use até <strong>{int.format(d1.superior)} incidentes</strong> no plano de contingência de D+1. O ponto central é {int.format(d1.ponto)}.</p>
        <div className="decision-rule"><span>Confiabilidade D+1</span><strong>WAPE {pct(data.validation['D+1'].wape)}</strong></div>
        <div className="decision-rule"><span>Fila preditiva</span><strong>{dec.format(data.risk.lift)}× mais precisa</strong></div>
      </Panel>
    </div>
    <Panel title="OLA e volume por mês" subtitle="A taxa considera somente incidentes elegíveis ao KPI">
      <div className="chart-md"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={data.monthly} margin={{ top: 15, right: 20, left: -10, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="#223147"/><XAxis dataKey="mes" tickFormatter={date} axisLine={false} tickLine={false}/><YAxis yAxisId="left" axisLine={false} tickLine={false}/><YAxis yAxisId="right" orientation="right" tickFormatter={v => `${Math.round(v * 100)}%`} axisLine={false} tickLine={false}/><Tooltip labelFormatter={label => date(String(label))} formatter={(value, name) => [String(name) === 'Taxa de OLA' ? pct(Number(value)) : int.format(Number(value)), String(name)]}/><Legend/><Bar yAxisId="left" dataKey="incidentes" name="Incidentes" fill="#315a91" radius={[5, 5, 0, 0]}/><Line yAxisId="right" dataKey="taxaOla" name="Taxa de OLA" stroke="#ff7651" strokeWidth={2.5} dot={{ r: 3 }}/>
      </ComposedChart></ResponsiveContainer></div>
    </Panel>
  </>
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
  async function submit(event?: FormEvent) {
    event?.preventDefault(); setLoading(true); setError('')
    try {
      setResult(await api<TriageResult>('/api/triage', { method: 'POST', body: JSON.stringify({ prioridade: form.prioridade, produto: form.produto, categoria: form.categoria, grupo: form.grupo, data_hora: `${form.data}T${form.hora}:00` }) }))
    } catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }
  return <>
    <PageTitle eyebrow="Decision intelligence" title="Triagem preditiva" copy="Estime o risco de violação no momento em que o incidente entra na fila."/>
    <div className="content-grid form-layout">
      <Panel title="Contexto do incidente" subtitle="Somente variáveis conhecidas na abertura">
        {!options ? <Loading label="Carregando valores históricos"/> : <form className="form-grid" onSubmit={submit}>
          <label><span>Prioridade</span><select value={form.prioridade} onChange={e => setForm({ ...form, prioridade: +e.target.value })}>{[1,2,3,4,5].map(v => <option key={v} value={v}>P{v}</option>)}</select></label>
          <label><span>Produto</span><select value={form.produto} onChange={e => setForm({ ...form, produto: e.target.value })}>{options.produtos.map(v => <option key={v}>{v}</option>)}</select></label>
          <label><span>Categoria</span><select value={form.categoria} onChange={e => setForm({ ...form, categoria: e.target.value })}>{options.categorias.map(v => <option key={v}>{v}</option>)}</select></label>
          <label><span>Grupo designado</span><select value={form.grupo} onChange={e => setForm({ ...form, grupo: e.target.value })}>{options.grupos.map(v => <option key={v}>{v}</option>)}</select></label>
          <label><span>Data</span><input type="date" value={form.data} onChange={e => setForm({ ...form, data: e.target.value })}/></label>
          <label><span>Hora</span><input type="time" value={form.hora} onChange={e => setForm({ ...form, hora: e.target.value })}/></label>
          <button className="primary-button span-2" disabled={loading}>{loading ? 'Calculando risco…' : <><BrainCircuit size={18}/> Calcular risco real</>}</button>
        </form>}
        {error && <ErrorState message={error}/>} 
      </Panel>
      <section className={`risk-result ${result ? result.faixa.toLowerCase() : ''}`}>
        {!result ? <div className="empty-result"><BrainCircuit/><h2>Modelo pronto para analisar</h2><p>Preencha o contexto e execute a triagem. Nenhuma duração ou resultado futuro é usado.</p></div> : <>
          <div className="risk-top"><span>Risco calibrado de violação</span><span className="risk-badge">{result.faixa}</span></div>
          <div className="risk-value">{pct(result.probabilidade)}</div>
          <div className="risk-track"><span style={{ width: `${Math.min(100, result.probabilidade * 100)}%` }}/></div>
          <p>{result.acao}</p>
          <div className="risk-meta"><div><span>Taxa-base</span><strong>{pct(result.taxaBase)}</strong></div><div><span>Risco relativo</span><strong>{dec.format(result.multiplicadorBase)}×</strong></div><div><span>Limiar alto</span><strong>{pct(result.limiarAlto)}</strong></div></div>
        </>}
      </section>
    </div>
    {result && <Panel title="Evidência histórica do contexto" subtitle="Taxas observadas por fator na base elegível">
      <div className="evidence-grid">{result.evidencias.map(item => <div className="evidence" key={item.fator}><span>{item.fator}</span><strong>{item.taxa == null ? 'Sem amostra' : pct(item.taxa)}</strong><small>{int.format(item.amostra)} incidentes</small></div>)}</div>
    </Panel>}
  </>
}

function DiagnosticsPage() {
  const [dimension, setDimension] = useState('Categoria')
  const [data, setData] = useState<Diagnostic>()
  const [error, setError] = useState('')
  useEffect(() => { setData(undefined); api<Diagnostic>(`/api/diagnostics?dimension=${encodeURIComponent(dimension)}&min_sample=30`).then(setData).catch(e => setError(e.message)) }, [dimension])
  return <>
    <PageTitle eyebrow="Root cause explorer" title="Diagnóstico de OLA" copy="Priorize onde o volume de violações e a taxa de risco realmente se concentram." actions={<div className="segmented">{['Categoria','Produto','Grupo designado'].map(v => <button className={dimension === v ? 'active' : ''} onClick={() => setDimension(v)} key={v}>{v === 'Grupo designado' ? 'Grupo' : v}</button>)}</div>}/>
    {error ? <ErrorState message={error}/> : !data ? <Loading/> : <div className="content-grid wide-left">
      <Panel title={`Maiores ofensores por ${dimension.toLowerCase()}`} subtitle="Barras = violações · linha de referência = taxa geral">
        <div className="chart-xl"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.items.slice(0, 10)} layout="vertical" margin={{ left: 5, right: 20, top: 5, bottom: 5 }}>
          <CartesianGrid horizontal={false} stroke="#e7edf4"/><XAxis type="number" axisLine={false} tickLine={false}/><YAxis type="category" dataKey="nome" width={90} tick={{ fontSize: 11 }} axisLine={false} tickLine={false}/><Tooltip formatter={value => int.format(Number(value))}/><Bar dataKey="violacoes" name="Violações" radius={[0, 6, 6, 0]}>{data.items.slice(0,10).map((_, i) => <Cell key={i} fill={i < 3 ? '#ef6236' : '#274c77'}/>)}</Bar>
        </BarChart></ResponsiveContainer></div>
      </Panel>
      <Panel title="Fila de ação" subtitle={`Taxa geral: ${pct(data.taxaGeral)}`}>
        <div className="action-list">{data.items.slice(0, 6).map((item, index) => <div className="action-item" key={item.nome}><span className="rank">{index + 1}</span><div><strong>{item.nome}</strong><small>{int.format(item.violacoes)} violações de {int.format(item.elegiveis)}</small></div><div className={item.taxa > data.taxaGeral ? 'rate bad' : 'rate'}>{pct(item.taxa)}</div></div>)}</div>
        <div className="insight"><Sparkles size={18}/><p><strong>Prioridade sugerida:</strong> atuar primeiro nos itens com maior número absoluto; use a taxa para diferenciar concentração de volume de risco estrutural.</p></div>
      </Panel>
    </div>}
  </>
}

function CapacityPage() {
  const [form, setForm] = useState({ produtividade: 25, ocupacao: 80, indisponibilidade: 10, analistas_atuais: 40, horizonte: 'D+1' })
  const [data, setData] = useState<Capacity>()
  const [error, setError] = useState('')
  async function submit(event?: FormEvent) {
    event?.preventDefault(); setError('')
    try { setData(await api<Capacity>('/api/capacity', { method: 'POST', body: JSON.stringify({ ...form, ocupacao: form.ocupacao / 100, indisponibilidade: form.indisponibilidade / 100 }) })) } catch (e) { setError((e as Error).message) }
  }
  useEffect(() => { submit() }, [])
  return <>
    <PageTitle eyebrow="What-if simulator" title="Capacidade & ação" copy="Converta a previsão de demanda em uma decisão de escala operacional."/>
    <div className="content-grid form-layout">
      <Panel title="Premissas operacionais" subtitle="Parâmetros ajustáveis e explicitamente separados do modelo">
        <form className="form-grid" onSubmit={submit}>
          <label><span>Horizonte</span><select value={form.horizonte} onChange={e => setForm({ ...form, horizonte: e.target.value })}><option>D+1</option><option>D+7</option></select></label>
          <label><span>Analistas atuais</span><input type="number" min="0" value={form.analistas_atuais} onChange={e => setForm({ ...form, analistas_atuais: +e.target.value })}/></label>
          <label><span>Incidentes / analista / dia</span><input type="number" min="1" value={form.produtividade} onChange={e => setForm({ ...form, produtividade: +e.target.value })}/></label>
          <label><span>Ocupação planejada (%)</span><input type="number" min="10" max="100" value={form.ocupacao} onChange={e => setForm({ ...form, ocupacao: +e.target.value })}/></label>
          <label><span>Margem de indisponibilidade (%)</span><input type="number" min="0" max="89" value={form.indisponibilidade} onChange={e => setForm({ ...form, indisponibilidade: +e.target.value })}/></label>
          <button className="primary-button span-2"><Users size={18}/> Recalcular capacidade</button>
        </form>{error && <ErrorState message={error}/>} 
      </Panel>
      <Panel title="Cobertura por cenário" subtitle={data ? `Capacidade efetiva: ${dec.format(data.capacidadeEfetiva)} incidentes/analista` : 'Calculando'}>
        {!data ? <Loading/> : <><div className="chart-md"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.cenarios} margin={{ left: -10, right: 10, top: 20 }}><CartesianGrid vertical={false} stroke="#e7edf4"/><XAxis dataKey="cenario" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip/><Bar dataKey="necessarios" name="Analistas necessários" radius={[7,7,0,0]}>{data.cenarios.map((s, i) => <Cell key={s.cenario} fill={i === 2 ? '#ef6236' : i === 1 ? '#2563eb' : '#93b4e9'}/>)}</Bar><ReferenceLine y={form.analistas_atuais} stroke="#0f9f91" strokeDasharray="5 5" label="Equipe atual"/></BarChart></ResponsiveContainer></div><div className="capacity-callout"><CheckCircle2/><div><strong>{data.acao}</strong><p>{data.nota}</p></div></div></>}
      </Panel>
    </div>
    {data && <div className="scenario-grid">{data.cenarios.map(s => <article key={s.cenario}><span>{s.cenario}</span><strong>{int.format(s.demanda)} chamados</strong><p>{s.necessarios} analistas · <b className={s.gap > 0 ? 'negative' : 'positive'}>{s.gap > 0 ? `déficit ${s.gap}` : `reserva ${Math.abs(s.gap)}`}</b></p></article>)}</div>}
  </>
}

function ModelsPage() {
  const [data, setData] = useState<Models>()
  const [error, setError] = useState('')
  useEffect(() => { api<Models>('/api/models').then(setData).catch(e => setError(e.message)) }, [])
  if (error) return <ErrorState message={error}/>
  if (!data) return <Loading label="Carregando validação temporal"/>
  return <>
    <PageTitle eyebrow="Model governance" title="Modelos & validação" copy="Desempenho fora da amostra, calibração e sinais usados na decisão."/>
    <div className="stats-grid">
      <StatCard icon={<BrainCircuit/>} label="ROC-AUC risco" value={dec.format(data.risk.rocAuc)} detail="Discriminação no holdout" tone="violet"/>
      <StatCard icon={<Target/>} label="PR-AUC risco" value={dec.format(data.risk.prAuc)} detail={`Base positiva: ${pct(data.risk.prevalencia)}`} tone="orange"/>
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
    <PageTitle eyebrow="Data observability" title="Qualidade dos dados" copy="Transparência sobre completude, universo analítico e registros que sustentam as decisões."/>
    <div className="quality-grid">{data.missing.map(item => <article key={item.campo}><div><span>{item.campo}</span><strong>{pct(1-item.taxa)} completos</strong></div><div className="quality-track"><span style={{ width: `${(1-item.taxa)*100}%` }}/></div><small>{int.format(item.faltantes)} ausentes</small></article>)}</div>
    <Panel title="Amostra auditável" subtitle="50 registros mais recentes do snapshot — nenhuma linha sintética">
      <div className="data-table-wrap"><table><thead><tr>{columns.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{data.sample.map((row, index) => <tr key={index}>{columns.map(c => <td key={c}>{typeof row[c] === 'boolean' ? (row[c] ? 'Sim' : 'Não') : String(row[c] ?? '—')}</td>)}</tr>)}</tbody></table></div>
    </Panel>
  </>
}

export default function App() {
  const [page, setPage] = useState<Page>('overview')
  const [sidebar, setSidebar] = useState(false)
  const current = useMemo(() => nav.find(item => item.id === page)!, [page])
  const PageComponent = { overview: OverviewPage, triage: TriagePage, diagnostics: DiagnosticsPage, capacity: CapacityPage, models: ModelsPage, audit: AuditPage }[page]
  return <div className="app-shell">
    <aside className={sidebar ? 'sidebar open' : 'sidebar'}>
      <div className="brand"><div className="brand-mark"><Activity/></div><div><strong>visionOps <b>AI</b></strong><span>OPERATIONS INTELLIGENCE</span></div><button className="close-menu" onClick={() => setSidebar(false)}><X/></button></div>
      <nav>{nav.map(item => { const Icon = item.icon; return <button key={item.id} className={page === item.id ? 'active' : ''} onClick={() => { setPage(item.id); setSidebar(false) }}><Icon/><span>{item.label}</span>{page === item.id && <ChevronRight className="chevron"/>}</button> })}</nav>
      <div className="sidebar-status"><div className="status-dot"/><div><strong>Modelos ativos</strong><span>Snapshot auditável</span></div></div>
      <div className="sidebar-foot"><ShieldCheck/><span>Validação temporal<br/>Dezembro de 2025</span></div>
    </aside>
    <main>
      <header className="topbar"><button className="menu-button" onClick={() => setSidebar(true)}><Menu/></button><div className="breadcrumb"><current.icon/><span>{current.label}</span></div><div className="top-actions"><div className="search"><Search/><span>Buscar análise</span><kbd>⌘ K</kbd></div><div className="avatar">VT</div></div></header>
      <div className="workspace"><PageComponent/></div>
    </main>
    {sidebar && <div className="scrim" onClick={() => setSidebar(false)}/>} 
  </div>
}
