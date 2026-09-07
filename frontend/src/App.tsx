import { FormEvent, ReactNode, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowRight, BarChart3, BrainCircuit, CheckCircle2,
  ChevronRight, CircleGauge, Clock3, Database, ListChecks, Menu, Radar, Search,
  ShieldCheck, SlidersHorizontal, Sparkles, Target, TrendingUp, UploadCloud, Users, X,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend,
  Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from './api'
import type {
  Capacity, Diagnostic, Drift, ItemFila, ModelStatus, Models, Optimization, Overview,
  Perfil, RespostaFila, ResumoAcoes, Segmentation, TriageResult,
} from './types'

type Page = 'overview' | 'queue' | 'triage' | 'diagnostics' | 'optimization' | 'capacity' | 'monitor' | 'models' | 'audit'

const nav: { id: Page; label: string; icon: typeof Activity }[] = [
  { id: 'overview', label: 'Visão operacional', icon: CircleGauge },
  { id: 'queue', label: 'Fila operacional', icon: ListChecks },
  { id: 'triage', label: 'Triagem preditiva', icon: Sparkles },
  { id: 'diagnostics', label: 'Diagnóstico de OLA', icon: Target },
  { id: 'optimization', label: 'Alocação preventiva', icon: SlidersHorizontal },
  { id: 'capacity', label: 'Capacidade & ação', icon: Users },
  { id: 'monitor', label: 'Monitor de dados', icon: Radar },
  { id: 'models', label: 'Modelos & validação', icon: BrainCircuit },
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

function SegmentacaoPanel({ dimension }: { dimension: string }) {
  const [data, setData] = useState<Segmentation>()
  const [error, setError] = useState('')
  useEffect(() => { setData(undefined); api<Segmentation>(`/api/segmentation?dimension=${encodeURIComponent(dimension)}`).then(setData).catch(e => setError(e.message)) }, [dimension])
  if (error) return <ErrorState message={error}/>
  if (!data) return <Panel title="Segmentação de criticidade (K-Means)" subtitle="Carregando"><Loading/></Panel>
  return <Panel title="Segmentação de criticidade (K-Means)" subtitle={`Seção 17 do notebook de ML · K=${data.kEscolhido} escolhido por ${data.criterio}`}>
    <div className="model-table">
      <div className="table-row table-head"><span>Cluster</span><span>Entidades</span><span>Incidentes</span><span>OLA violados</span><span>Taxa média</span></div>
      {data.clusters.map(c => <div className="table-row" key={c.posicao}>
        <strong>{c.rotulo}</strong><span>{int.format(c.entidades)}</span><span>{int.format(c.incidentesTotal)}</span>
        <span>{int.format(c.olaViolados)}</span><span className={c.posicao === 0 ? 'negative' : ''}>{pct(c.taxaMedia)}</span>
      </div>)}
    </div>
    <div className="insight"><Sparkles size={18}/><p><strong>Leitura:</strong> o cluster mais crítico costuma ter volume menor mas taxa de violação bem mais alta — a ordenação simples por soma não separa isso. Método recalculado sobre o snapshot atual.</p></div>
  </Panel>
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
    <SegmentacaoPanel dimension={dimension}/>
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

const FAIXA_CLASSE: Record<string, string> = { Alto: 'alto', Moderado: 'moderado', Baixo: 'baixo' }
const parseCsv = (texto: string): Record<string, string>[] => {
  const linhas = texto.trim().split(/\r?\n/).filter(Boolean)
  if (linhas.length < 2) return []
  const cabecalho = linhas[0].split(',').map(c => c.trim())
  return linhas.slice(1).map(linha => {
    const celulas = linha.split(',')
    return Object.fromEntries(cabecalho.map((coluna, i) => [coluna, (celulas[i] ?? '').trim()]))
  })
}

function FilaRow({ item, perfil, loteId, onAction }: { item: ItemFila; perfil: Perfil; loteId?: string | null; onAction: (t: string) => void }) {
  const [aberto, setAberto] = useState(false)
  const [registrada, setRegistrada] = useState<string>()
  const podeAgir = perfil !== 'gestor'
  async function registrar(acao: string) {
    try {
      await api('/api/actions', { method: 'POST', body: JSON.stringify({ ticketRef: item.id, acao, loteId, prioridade: item.prioridade, faixa: item.faixa, probabilidade: item.probabilidade, perfil }) })
      setRegistrada(acao); onAction(acao)
    } catch { setRegistrada('erro') }
  }
  return <>
    <tr className={`fila-row ${aberto ? 'open' : ''}`} onClick={() => setAberto(v => !v)}>
      <td><span className={`risk-pill ${FAIXA_CLASSE[item.faixa]}`}>{pct(item.probabilidade)}</span></td>
      <td>{item.faixa}</td>
      <td className="mono">{item.id}</td>
      <td>P{item.prioridade}</td>
      <td>{item.produto}</td>
      <td>{item.categoria}</td>
      <td>{item.grupo}</td>
      <td>{item.violouReal === undefined ? '—' : item.violouReal ? <span className="rate bad">violou</span> : 'ok'}</td>
      <td>{registrada && registrada !== 'erro' ? <span className="rate">{registrada}</span> : <ChevronRight className={aberto ? 'chevron open' : 'chevron'}/>}</td>
    </tr>
    {aberto && <tr className="fila-detalhe"><td colSpan={9}>
      <div className="fatores">
        {item.fatores.map(f => <div key={f.fator} className="fator">
          <span>{f.fator}: <b>{f.valor}</b></span>
          <span className={f.contribuicao >= 0 ? 'delta up' : 'delta down'}>{f.contribuicao >= 0 ? '+' : ''}{(f.contribuicao * 100).toFixed(1)} pp no risco</span>
          <small>{f.taxaHistorica == null ? 'sem amostra histórica' : `taxa histórica ${pct(f.taxaHistorica)} · ${int.format(f.amostra)} casos`}</small>
        </div>)}
      </div>
      {podeAgir && <div className="fila-acoes">
        {['atribuido', 'escalado', 'resolvido', 'dispensado'].map(a => <button key={a} onClick={e => { e.stopPropagation(); registrar(a) }}>{a}</button>)}
      </div>}
      {!podeAgir && <p className="fila-nota">Perfil Gestor: visão de acompanhamento, sem registro de ação.</p>}
    </td></tr>}
  </>
}

function QueuePage({ perfil }: { perfil: Perfil }) {
  const [modo, setModo] = useState<'snapshot' | 'csv'>('snapshot')
  const [data, setData] = useState('2025-12-31')
  const [dias, setDias] = useState(1)
  const [resposta, setResposta] = useState<RespostaFila>()
  const [resumoAcoes, setResumoAcoes] = useState<ResumoAcoes>()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const recarregarAcoes = () => { api<ResumoAcoes>('/api/actions/summary').then(setResumoAcoes).catch(() => {}) }
  useEffect(recarregarAcoes, [])

  async function carregarSnapshot() {
    setLoading(true); setError('')
    try { setResposta(await api<RespostaFila>(`/api/queue/sample?data=${data}&dias=${dias}`)) }
    catch (e) { setError((e as Error).message); setResposta(undefined) } finally { setLoading(false) }
  }
  useEffect(() => { if (modo === 'snapshot') carregarSnapshot() }, [modo])

  async function enviarCsv(file: File) {
    setLoading(true); setError('')
    try {
      const linhas = parseCsv(await file.text())
      if (!linhas.length) throw new Error('CSV vazio ou sem linhas de dados.')
      const itens = linhas.map(l => ({
        id: l.id || l.numero || l.Numero, prioridade: Number(l.prioridade || l.Prioridade || 3),
        produto: l.produto || l.Produto || 'Não informado', categoria: l.categoria || l.Categoria || 'Não informado',
        grupo: l.grupo || l.Grupo || 'Não informado', dataHora: l.dataHora || l.data_hora || l.aberto || null,
      }))
      setResposta(await api<RespostaFila>('/api/queue/score', { method: 'POST', body: JSON.stringify({ itens, referencia: file.name, persistir: true }) }))
    } catch (e) { setError((e as Error).message); setResposta(undefined) } finally { setLoading(false) }
  }

  function exportar() {
    if (!resposta) return
    const linhas = [['id', 'faixa', 'probabilidade', 'prioridade', 'produto', 'categoria', 'grupo', 'aberto'].join(',')]
    resposta.fila.forEach(i => linhas.push([i.id, i.faixa, i.probabilidade, i.prioridade, i.produto, i.categoria, i.grupo, i.aberto].join(',')))
    const url = URL.createObjectURL(new Blob([linhas.join('\n')], { type: 'text/csv' }))
    const a = document.createElement('a'); a.href = url; a.download = 'fila_priorizada.csv'; a.click(); URL.revokeObjectURL(url)
  }

  const r = resposta?.resumo
  return <>
    <PageTitle eyebrow="Batch operations" title="Fila operacional" copy="Pontue um lote de chamados, ordene por risco de violação e registre as ações da operação." actions={
      resposta && <button className="ghost-button" onClick={exportar}><ArrowRight size={15}/> Exportar fila (.csv)</button>
    }/>
    <div className="segmented queue-modes">
      <button className={modo === 'snapshot' ? 'active' : ''} onClick={() => setModo('snapshot')}>Do snapshot</button>
      <button className={modo === 'csv' ? 'active' : ''} onClick={() => setModo('csv')}>Importar CSV</button>
    </div>

    {modo === 'snapshot'
      ? <Panel title="Chamados de um dia real da base" subtitle="Incidentes elegíveis abertos na janela escolhida, pontuados com o modelo de risco validado">
          <div className="queue-controls">
            <label><span>Data</span><input type="date" value={data} min="2023-01-02" max="2025-12-31" onChange={e => setData(e.target.value)}/></label>
            <label><span>Janela (dias)</span><input type="number" min={1} max={14} value={dias} onChange={e => setDias(Math.max(1, Math.min(14, +e.target.value)))}/></label>
            <button className="primary-button" onClick={carregarSnapshot} disabled={loading}>{loading ? 'Pontuando…' : 'Carregar fila'}</button>
          </div>
          {resposta?.janelaModelo && <p className="fila-nota">Janela do modelo: {resposta.janelaModelo}. O campo “violou” é o resultado real do incidente — não estava disponível na abertura, serve só para conferir a ordenação.</p>}
        </Panel>
      : <Panel title="Importar CSV de chamados" subtitle="Colunas: id, prioridade, produto, categoria, grupo, dataHora">
          <div className="queue-controls">
            <label className="file-drop"><UploadCloud size={18}/><span>Selecionar arquivo .csv</span>
              <input type="file" accept=".csv,text/csv" onChange={e => { const f = e.target.files?.[0]; if (f) enviarCsv(f) }}/>
            </label>
            <a className="ghost-button" href="/api/queue/template" download="modelo_fila.csv"><ArrowRight size={15}/> Baixar modelo</a>
          </div>
        </Panel>}

    {error && <ErrorState message={error}/>}
    {loading && !resposta && <Loading label="Pontuando o lote"/>}

    {r && <>
      <div className="stats-grid">
        <StatCard icon={<ListChecks/>} label="Chamados na fila" value={int.format(r.total)} detail={`${int.format(r.filaAlta)} em risco alto · ${int.format(r.filaModerada)} moderado`} tone="navy"/>
        <StatCard icon={<AlertTriangle/>} label="Violações esperadas" value={dec.format(r.violacoesEsperadas)} detail="Soma das probabilidades calibradas do lote" tone="red"/>
        <StatCard icon={<Target/>} label="Captura no topo 20%" value={pct(r.capturaTop20Pct)} detail="Do risco total, quanto está nos primeiros 20% da fila" tone="teal"/>
        <StatCard icon={<CheckCircle2/>} label="Risco priorizado" value={resumoAcoes ? dec.format(resumoAcoes.riscoPriorizado) : '—'} detail={resumoAcoes ? `${int.format(resumoAcoes.ticketsComAcao)} chamados com ação registrada` : 'Sem ações ainda'} tone="violet"/>
      </div>
      {r.violacoesReais !== undefined && <div className="insight"><Sparkles size={18}/><p><strong>Conferência:</strong> neste dia real houve {int.format(r.violacoesReais)} violação(ões) de OLA; {int.format(r.violacoesReaisNoTop20 ?? 0)} está(ão) nos primeiros 20% da fila ordenada pelo modelo.</p></div>}

      <Panel title="Fila priorizada" subtitle="Clique numa linha para ver a contribuição de cada fator e registrar ação">
        <div className="data-table-wrap">
          <table className="fila-table">
            <thead><tr><th>Risco</th><th>Faixa</th><th>Chamado</th><th>Pri.</th><th>Produto</th><th>Categoria</th><th>Grupo</th><th>Resultado</th><th></th></tr></thead>
            <tbody>{resposta!.fila.map(item => <FilaRow key={item.id} item={item} perfil={perfil} loteId={resposta!.loteId} onAction={recarregarAcoes}/>)}</tbody>
          </table>
        </div>
      </Panel>

      {resumoAcoes && <Panel title="Registro de ações" subtitle="Estado operacional persistido — não é contagem de violações evitadas, e sim de risco endereçado">
        <div className="scenario-grid">
          {['atribuido', 'escalado', 'resolvido', 'dispensado'].map(a => <article key={a}><span>{a}</span><strong>{int.format(resumoAcoes.porAcao[a] ?? 0)}</strong><p>chamados</p></article>)}
        </div>
      </Panel>}
    </>}
  </>
}

function OptimizationPage() {
  const [capacidade, setCapacidade] = useState(5)
  const [limite, setLimite] = useState(2)
  const [data, setData] = useState<Optimization>()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  async function calcular() {
    setLoading(true); setError('')
    try { setData(await api<Optimization>(`/api/optimization?capacidade=${capacidade}&limitePorCategoria=${limite}`)) }
    catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }
  useEffect(() => { calcular() }, [])
  return <>
    <PageTitle eyebrow="Prescriptive optimization" title="Alocação preventiva D+1" copy="Programação linear inteira (Seção 18 do notebook de ML): quais produtos revisar amanhã para cobrir o máximo de risco de OLA."/>
    <div className="content-grid form-layout">
      <Panel title="Parâmetros do modelo" subtitle="Capacidade e limite por categoria — calibráveis com a operação real">
        <form className="form-grid" onSubmit={e => { e.preventDefault(); calcular() }}>
          <label><span>Capacidade (produtos/dia)</span><input type="number" min={1} max={60} value={capacidade} onChange={e => setCapacidade(+e.target.value)}/></label>
          <label><span>Máx. por categoria dominante</span><input type="number" min={1} max={12} value={limite} onChange={e => setLimite(+e.target.value)}/></label>
          <button className="primary-button span-2" disabled={loading}><SlidersHorizontal size={16}/> {loading ? 'Otimizando…' : 'Recalcular alocação'}</button>
        </form>
        {error && <ErrorState message={error}/>}
        {data && <div className="method-note"><ShieldCheck/><p>Objetivo: previsão real de volume D+1 ({dec.format(data.previsaoD1Total)}) distribuída pelos produtos conforme a participação histórica nas violações. Preço-sombra: <strong>{dec.format(data.precoSombra)}</strong> violações por vaga extra.</p></div>}
      </Panel>
      <Panel title="Cobertura de risco" subtitle={data ? `${pct(data.coberturaPct / 100)} do risco estimado coberto por ${data.selecionados.length} produto(s)` : 'Calculando'}>
        {!data ? <Loading/> : <>
          <div className="chart-md"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.sensibilidade} margin={{ left: -12, right: 10, top: 15 }}>
            <CartesianGrid vertical={false} stroke="#e7edf4"/><XAxis dataKey="capacidade" axisLine={false} tickLine={false}/><YAxis tickFormatter={v => `${Math.round(v)}%`} axisLine={false} tickLine={false}/><Tooltip formatter={(v, n) => n === 'pctDoTotal' ? [`${v}%`, 'Cobertura'] : [dec.format(Number(v)), 'Risco coberto']}/>
            <Bar dataKey="pctDoTotal" name="pctDoTotal" radius={[6, 6, 0, 0]}>{data.sensibilidade.map(s => <Cell key={s.capacidade} fill={s.capacidade === data.capacidade ? '#ef6236' : '#274c77'}/>)}</Bar>
          </BarChart></ResponsiveContainer></div>
          <div className="action-list">{data.selecionados.map((s, i) => <div className="action-item" key={s.produto}><span className="rank">{i + 1}</span><div><strong>{s.produto}</strong><small>categoria {s.categoriaDominante}</small></div><div className="rate">{dec.format(s.cargaEstimadaD1)}</div></div>)}</div>
        </>}
      </Panel>
    </div>
  </>
}

function MonitorPage() {
  const [status, setStatus] = useState<ModelStatus>()
  const [drift, setDrift] = useState<Drift>()
  const [error, setError] = useState('')
  useEffect(() => {
    api<ModelStatus>('/api/model-status').then(setStatus).catch(e => setError(e.message))
    api<Drift>('/api/drift').then(setDrift).catch(e => setError(e.message))
  }, [])
  if (error) return <ErrorState message={error}/>
  if (!status || !drift) return <Loading label="Comparando janelas de dados"/>
  const nivelClasse: Record<string, string> = { 'estável': 'positive', 'atenção': '', 'alto': 'negative' }
  return <>
    <PageTitle eyebrow="Model governance" title="Monitor de dados" copy="Deriva entre a janela de treino e os dados recentes, e quando o modelo precisa ser revalidado."/>
    <div className={`decision-panel panel ${status.revalidacaoRecomendada ? 'alerta' : ''}`}>
      <div className="decision-icon"><Radar/></div>
      <h3>{status.revalidacaoRecomendada ? 'Revalidação recomendada' : 'Modelo dentro do ciclo'}</h3>
      <p>Snapshot de <strong>{status.snapshot}</strong> · {int.format(status.diasDesdeSnapshot)} dias atrás · ciclo alvo de {status.cicloRetreinoDias} dias · origem dos dados: {status.origemDados}.</p>
      {status.motivos.map(m => <div className="decision-rule" key={m}><span>{m}</span></div>)}
    </div>
    <div className="stats-grid">
      <StatCard icon={<BrainCircuit/>} label="ROC-AUC risco (holdout)" value={dec.format(status.risco.rocAuc)} detail={status.risco.holdout} tone="violet"/>
      <StatCard icon={<TrendingUp/>} label="MAE volume D+1" value={dec.format(status.volume.maeD1)} detail={`D+7: ${dec.format(status.volume.maeD7)} · ${status.volume.holdout}`} tone="orange"/>
      <StatCard icon={<Radar/>} label="Pior PSI" value={dec.format(drift.piorPsi)} detail="≥ 0,20 indica mudança relevante" tone="red"/>
      <StatCard icon={<Activity/>} label="Volume recente / treino" value={`${dec.format(drift.volumeMedioDia.razao)}×`} detail={`${dec.format(drift.volumeMedioDia.referencia)} → ${dec.format(drift.volumeMedioDia.recente)} elegíveis/dia`} tone="teal"/>
    </div>
    <Panel title="Deriva por variável (PSI)" subtitle={`Referência: ${drift.janelaReferencia.inicio} a ${drift.janelaReferencia.fim} · recente: ${drift.janelaRecente.inicio} a ${drift.janelaRecente.fim}`}>
      <div className="model-table">
        <div className="table-row table-head"><span>Variável</span><span>PSI</span><span>Nível</span><span>Faixa mais deslocada</span><span></span></div>
        {drift.features.map(f => <div className="table-row" key={f.feature}>
          <strong>{f.feature}</strong><span>{dec.format(f.psi)}</span>
          <span className={nivelClasse[f.nivel]}>{f.nivel}</span>
          <span>{f.detalhe[0] ? `${f.detalhe[0].faixa} (${pct(f.detalhe[0].esperado)} → ${pct(f.detalhe[0].atual)})` : '—'}</span><span></span>
        </div>)}
      </div>
      <div className="method-note"><ShieldCheck/><p>PSI (Population Stability Index) calculado sobre o snapshot real. A quebra de regime de volume em setembro/2025 aparece aqui como PSI alto em “Volume diário” — é a mesma limitação já documentada na Sprint 3, agora quantificada.</p></div>
    </Panel>
  </>
}

export default function App() {
  const [page, setPage] = useState<Page>('overview')
  const [sidebar, setSidebar] = useState(false)
  const [perfil, setPerfil] = usePerfil()
  const current = useMemo(() => nav.find(item => item.id === page)!, [page])

  const workspace = page === 'queue' ? <QueuePage perfil={perfil}/>
    : page === 'overview' ? <OverviewPage/>
    : page === 'triage' ? <TriagePage/>
    : page === 'diagnostics' ? <DiagnosticsPage/>
    : page === 'optimization' ? <OptimizationPage/>
    : page === 'capacity' ? <CapacityPage/>
    : page === 'monitor' ? <MonitorPage/>
    : page === 'models' ? <ModelsPage/>
    : <AuditPage/>

  return <div className="app-shell">
    <aside className={sidebar ? 'sidebar open' : 'sidebar'}>
      <div className="brand"><div className="brand-mark"><Activity/></div><div><strong>visionOps <b>AI</b></strong><span>OPERATIONS INTELLIGENCE</span></div><button className="close-menu" onClick={() => setSidebar(false)}><X/></button></div>
      <nav>{nav.map(item => { const Icon = item.icon; return <button key={item.id} className={page === item.id ? 'active' : ''} onClick={() => { setPage(item.id); setSidebar(false) }}><Icon/><span>{item.label}</span>{page === item.id && <ChevronRight className="chevron"/>}</button> })}</nav>
      <label className="perfil-picker"><span>Perfil operacional</span>
        <select value={perfil} onChange={e => setPerfil(e.target.value as Perfil)}>{PERFIS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}</select>
        <small>Visão de trabalho — não é autenticação</small>
      </label>
      <div className="sidebar-status"><div className="status-dot"/><div><strong>Modelos ativos</strong><span>Snapshot auditável</span></div></div>
      <div className="sidebar-foot"><ShieldCheck/><span>Validação temporal<br/>Dezembro de 2025</span></div>
    </aside>
    <main>
      <header className="topbar"><button className="menu-button" onClick={() => setSidebar(true)}><Menu/></button><div className="breadcrumb"><current.icon/><span>{current.label}</span></div><div className="top-actions"><div className="search"><Search/><span>Buscar análise</span><kbd>⌘ K</kbd></div><div className="avatar">{perfil.slice(0, 2).toUpperCase()}</div></div></header>
      <div className="workspace">{workspace}</div>
    </main>
    {sidebar && <div className="scrim" onClick={() => setSidebar(false)}/>}
  </div>
}
