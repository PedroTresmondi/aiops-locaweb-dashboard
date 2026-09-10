import { createContext, useContext, useEffect, useState, type ReactNode, type Dispatch, type SetStateAction } from 'react'
import { ArrowRight, AlertTriangle, CheckCircle2, ListChecks, TrendingUp, Users, ShieldCheck, Download } from 'lucide-react'
import { AreaChart, Area, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { api, apiUrl } from './api'
import type { Overview, RespostaFila, ItemFila, Perfil, Optimization, Capacity, ModelStatus, Drift, PriorityForecast } from './types'

export type Page = 'overview' | 'queue' | 'triage' | 'diagnostics' | 'optimization' | 'capacity' | 'monitor' | 'models' | 'audit'
export type Navigate = (page: Page) => void
type Filter = 'Todos' | 'Alto' | 'Moderado' | 'Baixo'
const integer = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })
const decimal = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 })
export const percent = (n: number) => `${decimal.format(n * 100)}%`
export const fullDate = (s: string) => new Date(`${s.slice(0, 10)}T12:00:00`).toLocaleDateString('pt-BR')
const cache = new Map<string, unknown>()
const pending = new Map<string, Promise<unknown>>()
function read<T>(path: string): Promise<T> {
  if (cache.has(path)) return Promise.resolve(cache.get(path) as T)
  if (!pending.has(path)) pending.set(path, api<T>(path).then(value => { cache.set(path, value); return value }).finally(() => pending.delete(path)))
  return pending.get(path) as Promise<T>
}
export function useRead<T>(path: string, enabled = true) {
  const [result, setResult] = useState<{ path: string; data?: T; error?: string }>({ path, data: cache.get(path) as T })
  const [attempt, retry] = useState(0)
  useEffect(() => {
    if (!enabled) return
    let active = true
    setResult({ path, data: cache.get(path) as T })
    read<T>(path).then(data => { if (active) setResult({ path, data }) }).catch(e => { if (active) setResult({ path, error: e.message }) })
    return () => { active = false }
  }, [path, attempt, enabled])
  return { data: enabled && result.path === path ? result.data : undefined, error: enabled && result.path === path ? result.error : undefined, retry: () => retry(n => n + 1) }
}
type Session = { day: string; days: number; filter: Filter; imported?: RespostaFila; mode: 'history' | 'csv'; actions: Record<string, string> }
const SessionContext = createContext<{ session: Session; update: Dispatch<SetStateAction<Session>> } | null>(null)
export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [session, update] = useState<Session>({ day: '2025-12-01', days: 1, filter: 'Todos', mode: 'history', actions: {} })
  return <SessionContext.Provider value={{ session, update }}>{children}</SessionContext.Provider>
}
function useSession() { return useContext(SessionContext)! }
function useQueue() {
  const { session } = useSession()
  return useRead<RespostaFila>(`/api/queue/sample?data=${session.day}&dias=${session.days}`)
}
function range(day: string, days: number) {
  const end = new Date(`${day}T12:00:00`); end.setDate(end.getDate() + days - 1)
  return days === 1 ? fullDate(day) : `${fullDate(day)} a ${end.toLocaleDateString('pt-BR')}`
}
export function Wait({ error, retry }: { error?: string; retry?: () => void }) {
  return error ? <div className="error-state" role="alert"><AlertTriangle/><div><strong>Não foi possível carregar os dados</strong><p>{error}</p>{retry && <button className="ghost-button" onClick={retry}>Tentar novamente</button>}</div></div> : <div className="loading" role="status"><div className="loader"/><strong>Carregando a análise</strong><span>Na primeira abertura, o servidor pode levar até um minuto para iniciar.</span></div>
}
export function Heading({ title, children }: { title: string; children: ReactNode }) {
  return <div className="page-title"><div><h1>{title}</h1><p>{children}</p></div></div>
}
export function Box({ title, children, subtitle }: { title: string; subtitle?: string; children: ReactNode }) {
  return <section className="panel"><div className="panel-head"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div></div>{children}</section>
}
export function Explain({ title = 'Como interpretar estes números', children, onOpen }: { title?: string; children: ReactNode; onOpen?: (open: boolean) => void }) {
  return <details className="explain" onToggle={e => onOpen?.(e.currentTarget.open)}><summary>{title}</summary><div>{children}</div></details>
}
function Metric({ label, value, children }: { label: string; value: string; children: ReactNode }) {
  return <article className="metric"><span>{label}</span><strong>{value}</strong><p>{children}</p></article>
}
export function ContextNote({ children }: { children: ReactNode }) {
  return <div className="context-note"><ShieldCheck size={17}/><span>{children}</span></div>
}
export function StartPage({ navigate }: { navigate: Navigate }) {
  const { session, update } = useSession()
  const [historyOpen, setHistoryOpen] = useState(false)
  const queue = useQueue()
  const overview = useRead<Overview>('/api/overview', historyOpen)
  const status = useRead<ModelStatus>('/api/model-status', Boolean(queue.data))
  if (!queue.data) return <><Heading title="Por onde começar?">Revise os chamados de maior risco e decida o encaminhamento.</Heading><Wait error={queue.error} retry={queue.retry}/></>
  const q = queue.data.resumo
  const start = () => { update(s => ({ ...s, mode: 'history', filter: q.filaAlta ? 'Alto' : 'Todos' })); navigate('queue') }
  return <>
    <Heading title="Por onde começar?">Uma visão do período escolhido, com o próximo passo para o atendimento.</Heading>
    <ContextNote><strong>Exercício com dados históricos · {range(session.day, session.days)}</strong> · Chamados elegíveis ao prazo interno de atendimento (OLA). Não é uma fila ao vivo.</ContextNote>
    <section className="decision-hero">
      <span className="eyebrow">Atendimento · primeiro passo</span>
      <h2>{q.filaAlta ? `${q.filaAlta} chamados merecem revisão prioritária` : 'Revise a fila na ordem de risco estimado'}</h2>
      <p>{q.filaAlta ? `São os chamados classificados com maior risco de descumprir o prazo entre os ${q.total} analisados. Abra um chamado, confira os fatores e registre seu encaminhamento.` : `Nenhum dos ${q.total} chamados ultrapassou o limiar de alto risco. Isso não elimina a possibilidade de atrasos: mantenha o acompanhamento.`}</p>
      <button className="primary-button" onClick={start}>Revisar {q.filaAlta ? `${q.filaAlta} chamados prioritários` : 'chamados'}<ArrowRight size={18}/></button>
    </section>
    <div className="metric-strip">
      <Metric label="Chamados analisados" value={integer.format(q.total)}>Abertos no período selecionado</Metric>
      <Metric label="Risco alto" value={integer.format(q.filaAlta)}>Revisar prioridade e encaminhamento</Metric>
      <Metric label="Risco moderado" value={integer.format(q.filaModerada)}>Conferir atendimento e acompanhar prazo</Metric>
    </div>
    <div className="task-grid">
      <button className="task-card" onClick={() => navigate('capacity')}><Users/><strong>A equipe será suficiente?</strong><p>Simule o número de analistas com a previsão de demanda e as suas premissas.</p><span>Planejar equipe <ArrowRight size={16}/></span></button>
      <button className="task-card" onClick={() => navigate('diagnostics')}><TrendingUp/><strong>Onde os atrasos se concentram?</strong><p>Compare produtos, categorias e grupos para orientar uma investigação.</p><span>Analisar problemas <ArrowRight size={16}/></span></button>
    </div>
    {status.data?.revalidacaoRecomendada && <div className="review-banner"><AlertTriangle/><div><strong>As previsões precisam de revisão antes de uso operacional.</strong><p>Os dados mudaram desde o treinamento. Use os resultados como apoio à análise humana.</p></div><button className="ghost-button" onClick={() => navigate('monitor')}>Entender o alerta</button></div>}
    {status.error && <ContextNote>Não foi possível verificar a situação dos modelos. <button className="text-button" onClick={status.retry}>Tentar novamente</button></ContextNote>}
    <Explain title="Ver a base histórica e a previsão de demanda" onOpen={setHistoryOpen}>
      {!overview.data ? <Wait error={overview.error} retry={overview.retry}/> : <>
        <p>Base de {fullDate(overview.data.snapshot.inicio)} a {fullDate(overview.data.snapshot.fim)}: {integer.format(overview.data.snapshot.incidentes)} incidentes. A previsão de volume usa essa base completa; não é uma projeção da fila selecionada acima.</p>
        <div className="metric-strip">{overview.data.forecast.map(f => <Metric key={f.horizonte} label={`Volume previsto · ${fullDate(f.dataAlvo)}`} value={integer.format(f.ponto)}>Faixa estimada: {integer.format(f.inferior)} a {integer.format(f.superior)} chamados</Metric>)}</div>
        <div className="chart-md"><ResponsiveContainer width="100%" height="100%"><AreaChart data={overview.data.daily}><CartesianGrid vertical={false}/><XAxis dataKey="data" tickFormatter={fullDate} minTickGap={65}/><YAxis/><Tooltip labelFormatter={x => fullDate(String(x))}/><Area isAnimationActive={false} dataKey="incidentes" name="Chamados observados" stroke="#7fa9d7" fill="#24425f"/></AreaChart></ResponsiveContainer></div>
      </>}
    </Explain>
  </>
}

const recommendations: Record<Filter, string> = { Todos: 'Revisar chamado', Alto: 'Revisar encaminhamento', Moderado: 'Conferir atendimento', Baixo: 'Manter acompanhamento' }
const actionNames: Record<string, string> = { atribuido: 'Atribuição registrada', escalado: 'Escalonamento registrado', resolvido: 'Resolução registrada', dispensado: 'Revisão dispensada' }
const actionKey = (response: RespostaFila, id: string) => `${response.origem}:${response.loteId ?? response.referencia}:${id}`

// CSV com aspas, quebras de linha e separador comum em exportações brasileiras.
export function parseQueueCsv(text: string): Record<string, string>[] {
  const input = text.replace(/^\uFEFF/, '')
  const first = input.split(/\r?\n/)[0]
  const delimiter = first.includes(';') ? ';' : ','
  const rows: string[][] = []; let row: string[] = []; let cell = ''; let quoted = false
  for (let i = 0; i < input.length; i++) {
    const c = input[i]
    if (c === '"') { if (quoted && input[i + 1] === '"') { cell += '"'; i++ } else quoted = !quoted }
    else if (c === delimiter && !quoted) { row.push(cell.trim()); cell = '' }
    else if ((c === '\n' || c === '\r') && !quoted) { if (c === '\r' && input[i + 1] === '\n') i++; row.push(cell.trim()); if (row.some(Boolean)) rows.push(row); row = []; cell = '' }
    else cell += c
  }
  if (quoted) throw new Error('Há aspas sem fechamento no CSV.')
  row.push(cell.trim()); if (row.some(Boolean)) rows.push(row)
  const header = rows.shift()
  if (!header || !rows.length) throw new Error('O CSV precisa de cabeçalho e ao menos um chamado.')
  if (rows.length > 5000) throw new Error('Importe até 5.000 chamados por arquivo.')
  const records = rows.map((cells, index) => {
    if (cells.length !== header.length) throw new Error(`Linha ${index + 2}: quantidade de colunas diferente do cabeçalho.`)
    return Object.fromEntries(header.map((key, i) => [key.toLowerCase(), cells[i]]))
  })
  const ids = new Set<string>()
  records.forEach((r, index) => {
    const id = r.id || r.numero || r['número']
    if (!id || !r.prioridade || !r.produto || !r.categoria || !(r.grupo || r['grupo designado'])) throw new Error(`Linha ${index + 2}: preencha id, prioridade, produto, categoria e grupo.`)
    if (![1, 2, 3, 4, 5].includes(Number(r.prioridade))) throw new Error(`Linha ${index + 2}: prioridade deve ser de 1 a 5.`)
    if (ids.has(id)) throw new Error(`Chamado duplicado no arquivo: ${id}.`)
    ids.add(id)
  })
  return records
}

function TicketDetail({ item, response, perfil }: { item: ItemFila; response: RespostaFila; perfil: Perfil }) {
  const { session, update } = useSession()
  const [action, setAction] = useState('atribuido')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const recorded = session.actions[actionKey(response, item.id)]
  async function save() {
    if (saving) return
    setSaving(true); setError('')
    try {
      await api('/api/actions', { method: 'POST', body: JSON.stringify({ ticketRef: item.id, acao: action, loteId: response.loteId, prioridade: item.prioridade, faixa: item.faixa, probabilidade: item.probabilidade, perfil, nota: `${response.origem === 'snapshot' ? 'Exercício histórico' : 'Revisão de CSV'} · ${response.referencia ?? ''} · ${note}` }) })
      update(s => ({ ...s, actions: { ...s.actions, [actionKey(response, item.id)]: action } }))
    } catch (e) { setError((e as Error).message) } finally { setSaving(false) }
  }
  const factors = item.fatores.filter(f => f.contribuicao > 0).slice(0, 2)
  return <aside className="ticket-detail" aria-label={`Detalhes do chamado ${item.id}`}>
    <span className="eyebrow">Chamado selecionado</span><h2>{item.id}</h2>
    <div className={`ticket-risk ${item.faixa.toLowerCase()}`}><strong>{percent(item.probabilidade)}</strong><span>Risco estimado de descumprir o prazo · {item.faixa.toLowerCase()}</span></div>
    <h3>1. Entenda o contexto</h3><p>Produto <strong>{item.produto}</strong> · categoria <strong>{item.categoria}</strong><br/>Grupo: <strong>{item.grupo}</strong> · prioridade original P{item.prioridade}</p>
    <h3>2. Confira a recomendação</h3><p>{item.faixa === 'Alto' ? 'Revise a prioridade e confirme se o grupo atual pode atender. Se necessário, encaminhe para atendimento especializado.' : item.faixa === 'Moderado' ? 'Confira se existe responsável pelo atendimento e acompanhe o prazo. Reavalie o encaminhamento se houver impedimentos.' : 'Mantenha o acompanhamento habitual. Um risco baixo não garante que o prazo será cumprido.'}</p>
    <p className="subtle">{factors.length ? `Nesta estimativa, ${factors.map(f => `${f.fator.toLowerCase()} (${f.valor})`).join(' e ')} elevaram o risco em comparação ao contexto de referência do modelo.` : 'Os fatores exibidos não elevaram o risco em comparação ao contexto de referência do modelo.'}</p>
    <Explain title="Ver os fatores usados na estimativa"><p>Variação ao comparar cada fator com uma referência do modelo. Não representa uma causa comprovada; as parcelas não devem ser somadas.</p>{item.fatores.map(f => <div className="factor-line" key={f.fator}><span>{f.fator}: {f.valor}</span><strong>{f.contribuicao >= 0 ? '+' : ''}{decimal.format(f.contribuicao * 100)} pontos percentuais</strong></div>)}</Explain>
    <h3>3. Registre sua decisão</h3>
    <p className="subtle">{response.origem === 'snapshot' ? 'Registro de exercício histórico no VisionOps. Não envia o chamado para outro sistema.' : 'Registro no VisionOps. O encaminhamento no sistema de atendimento deve ser realizado pela equipe.'}</p>
    {perfil === 'gestor' ? <p>O perfil Gestor permite acompanhamento. Use Analista para registrar decisões.</p> : <form className="decision-form" onSubmit={e => { e.preventDefault(); save() }}>
      <label>Decisão<select aria-label="Decisão" value={action} onChange={e => setAction(e.target.value)}><option value="atribuido">Registrar atribuição</option><option value="escalado">Registrar escalonamento</option><option value="resolvido">Registrar resolução</option><option value="dispensado">Dispensar revisão prioritária</option></select></label>
      <label>Justificativa (opcional)<textarea maxLength={500} value={note} onChange={e => setNote(e.target.value)} placeholder="Descreva o encaminhamento escolhido."/></label>
      <button className="primary-button" disabled={saving}>{saving ? 'Salvando…' : 'Salvar decisão'}</button>
    </form>}
    {error && <div role="alert" className="error-state">{error}</div>}
    {recorded && <p role="status" className="save-success"><CheckCircle2 size={17}/>{actionNames[recorded]} nesta sessão.</p>}
  </aside>
}

export function WorkQueue({ perfil, navigate }: { perfil: Perfil; navigate: Navigate }) {
  const { session, update } = useSession()
  const history = useQueue()
  const [draftDay, setDraftDay] = useState(session.day)
  const [draftDays, setDraftDays] = useState(session.days)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const response = session.mode === 'history' ? history.data : session.imported
  const filtered = response?.fila.filter(i => (session.filter === 'Todos' || i.faixa === session.filter) && `${i.id} ${i.produto} ${i.categoria} ${i.grupo}`.toLowerCase().includes(search.toLowerCase())) ?? []
  const pages = Math.max(1, Math.ceil(filtered.length / 10))
  const currentPage = Math.min(page, pages - 1)
  const visible = filtered.slice(currentPage * 10, currentPage * 10 + 10)
  const item = visible.find(i => i.id === selected) ?? visible[0]
  const r = response?.resumo
  const actionCount = response?.fila.filter(i => session.actions[actionKey(response, i.id)]).length ?? 0
  async function upload(file: File) {
    setBusy(true); setError(''); update(s => ({ ...s, imported: undefined }))
    try {
      const records = parseQueueCsv(await file.text())
      const itens = records.map(r => ({ id: r.id || r.numero || r['número'], prioridade: Number(r.prioridade), produto: r.produto, categoria: r.categoria, grupo: r.grupo || r['grupo designado'], dataHora: r.datahora || r.data_hora || r.aberto || null }))
      const imported = await api<RespostaFila>('/api/queue/score', { method: 'POST', body: JSON.stringify({ itens, referencia: file.name, persistir: true }) })
      update(s => ({ ...s, imported, filter: 'Todos' })); setPage(0); setSelected(undefined)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  function download() {
    if (!response) return
    const safe = (value: unknown) => `"${String(value ?? '').replace(/^[=+@-]/, "'$&").replace(/"/g, '""')}"`
    const rows = [['chamado', 'risco_estimado', 'faixa', 'produto', 'categoria', 'grupo'], ...filtered.map(i => [i.id, i.probabilidade, i.faixa, i.produto, i.categoria, i.grupo])]
    const url = URL.createObjectURL(new Blob(['\uFEFF' + rows.map(row => row.map(safe).join(';')).join('\r\n')], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a'); link.href = url; link.download = `fila-${session.filter.toLowerCase()}.csv`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return <>
    <Heading title="Quais chamados revisar primeiro?">Filtre o risco, selecione um chamado e registre o encaminhamento.</Heading>
    <div className="segmented"><button className={session.mode === 'history' ? 'active' : ''} onClick={() => { update(s => ({ ...s, mode: 'history' })); setError(''); setPage(0) }}>Base histórica</button><button className={session.mode === 'csv' ? 'active' : ''} onClick={() => { update(s => ({ ...s, mode: 'csv' })); setError(''); setPage(0) }}>Importar chamados</button></div>
    {session.mode === 'history' ? <form className="period-controls" onSubmit={e => { e.preventDefault(); update(s => ({ ...s, day: draftDay, days: draftDays, filter: 'Todos' })); setPage(0); setSelected(undefined) }}>
      <label>Data de abertura<input type="date" min="2023-01-02" max="2025-12-31" required value={draftDay} onChange={e => setDraftDay(e.target.value)}/></label><label>Período<select value={draftDays} onChange={e => setDraftDays(Number(e.target.value))}>{[1, 3, 7, 14].map(n => <option key={n} value={n}>{n} {n === 1 ? 'dia' : 'dias'}</option>)}</select></label><button className="ghost-button">Aplicar período</button>
      {(draftDay !== session.day || draftDays !== session.days) && <span className="subtle">Clique em Aplicar para atualizar os resultados.</span>}
    </form> : <div className="period-controls"><label>Arquivo CSV<input type="file" accept=".csv" disabled={busy} onChange={e => { const file = e.target.files?.[0]; if (file) upload(file); e.target.value = '' }}/></label><a className="ghost-button" href={apiUrl('/api/queue/template')}>Baixar modelo CSV</a><span className="subtle">Preencha os valores reais do seu lote antes de importar.</span></div>}
    {error && <Wait error={error}/>} {busy && <Wait/>}
    {session.mode === 'history' && !response && <Wait error={history.error} retry={history.retry}/>}
    {session.mode === 'csv' && !response && !busy && !error && <Box title="Selecione um arquivo para começar"><p>Informe id, prioridade (1 a 5), produto, categoria e grupo. A data de abertura pode ser enviada em dataHora. Os exemplos do modelo CSV são apenas instruções de preenchimento.</p></Box>}
    {response && r && <>
      <ContextNote>{session.mode === 'history' ? <><strong>Período carregado: {range(session.day, session.days)}</strong> · Exercício histórico. As ações não alteram o resultado original dos chamados.</> : <><strong>Lote: {response.referencia}</strong> · Dados enviados pelo usuário; sem confirmação do resultado real.</>}</ContextNote>
      <div className="metric-strip"><Metric label="Chamados neste lote" value={integer.format(r.total)}>O resumo considera o lote completo</Metric><Metric label="Risco alto" value={integer.format(r.filaAlta)}>Revisar prioridade e encaminhamento</Metric><Metric label="Decisões nesta sessão" value={integer.format(actionCount)}>Chamados deste lote com registro salvo agora</Metric></div>
      <div className="queue-toolbar"><div className="filter-tabs">{(['Todos', 'Alto', 'Moderado', 'Baixo'] as Filter[]).map(f => <button aria-pressed={session.filter === f} className={session.filter === f ? 'active' : ''} key={f} onClick={() => { update(s => ({ ...s, filter: f })); setPage(0); setSelected(undefined) }}>{f === 'Todos' ? 'Todos' : `Risco ${f.toLowerCase()}`} <b>{f === 'Todos' ? r.total : response.fila.filter(i => i.faixa === f).length}</b></button>)}</div><label className="queue-search">Buscar chamado, produto ou grupo<input type="search" value={search} onChange={e => { setSearch(e.target.value); setPage(0) }} placeholder="Buscar na fila…"/></label></div>
      <div className="workbench"><section className="panel queue-list"><div className="panel-head"><div><h2>{filtered.length} chamados encontrados</h2><p>Maior risco primeiro. Selecione um chamado para revisar.</p></div><button className="ghost-button" disabled={!filtered.length} onClick={download}><Download size={15}/>Exportar filtro</button></div>
        {visible.length ? <><div className="data-table-wrap"><table><thead><tr><th>Chamado / produto</th><th>Risco de atraso</th><th>Revisão</th></tr></thead><tbody>{visible.map(i => <tr key={i.id} className={item?.id === i.id ? 'selected-ticket' : ''}><td><button className="ticket-link" aria-pressed={item?.id === i.id} onClick={() => { setSelected(i.id); if (window.innerWidth <= 1200) requestAnimationFrame(() => document.querySelector('.ticket-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' })) }}>{i.id}</button><small className="table-secondary">{i.produto} · {i.grupo}</small></td><td><strong className={`risk-label ${i.faixa.toLowerCase()}`}>{percent(i.probabilidade)} · {i.faixa.toLowerCase()}</strong><small className="table-secondary">{recommendations[i.faixa]}</small></td><td>{session.actions[actionKey(response, i.id)] ? <span className="save-success">Registrada</span> : <span className="subtle">A revisar</span>}</td></tr>)}</tbody></table></div><div className="pagination"><button className="ghost-button" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Anterior</button><span>Página {currentPage + 1} de {pages}</span><button className="ghost-button" disabled={currentPage + 1 >= pages} onClick={() => setPage(currentPage + 1)}>Próxima</button></div></> : <p className="empty-state">Nenhum chamado corresponde ao filtro. Escolha outro nível de risco ou limpe a busca.</p>}
      </section>{item && <TicketDetail key={actionKey(response, item.id)} item={item} response={response} perfil={perfil}/>}</div>
      <Explain title="Conferir estimativas e resultados históricos"><p>{response.janelaModelo}</p><p>O modelo estima {decimal.format(r.violacoesEsperadas)} descumprimentos no lote, pela soma das probabilidades. É uma estimativa agregada, não uma contagem de casos confirmados.</p><p>Os primeiros {Math.ceil(r.total * .2)} chamados concentram {percent(r.capturaTop20Pct)} do risco previsto no lote. Este percentual não é a taxa de acerto do modelo.</p>{r.violacoesReais !== undefined && <p>No histórico, ocorreram {r.violacoesReais} descumprimentos; {r.violacoesReaisNoTop20 ?? 0} estavam nos primeiros 20% da fila. Esse resultado era desconhecido na abertura.</p>}<p>“Decisões nesta sessão” conta somente os chamados deste lote registrados durante esta abertura da aplicação. Não mede atrasos evitados.</p></Explain>
    </>}
    <div className="next-step"><span>Precisa avaliar um chamado individual?</span><button className="ghost-button" onClick={() => navigate('triage')}>Avaliar novo chamado <ArrowRight size={16}/></button></div>
  </>
}

export function ProductPlan({ navigate }: { navigate: Navigate }) {
  const [draft, setDraft] = useState({ capacity: 5, limit: 2 })
  const [applied, setApplied] = useState(draft)
  const result = useRead<Optimization>(`/api/optimization?capacidade=${applied.capacity}&limitePorCategoria=${applied.limit}`)
  const overview = useRead<Overview>('/api/overview')
  const d = result.data
  return <>
    <Heading title="Quais produtos revisar com a equipe disponível?">Defina quantas revisões cabem no dia. O plano seleciona os produtos com maior peso no histórico de atrasos.</Heading>
    <ContextNote>Planejamento separado da fila de chamados. {overview.data && `Base até ${fullDate(overview.data.snapshot.fim)} · previsão usada: ${fullDate(overview.data.forecast[0].dataAlvo)}.`} A capacidade abaixo é uma premissa sua.</ContextNote>
    <form className="period-controls" onSubmit={e => { e.preventDefault(); setApplied({ ...draft }) }}><label>Produtos que cabem na revisão diária<input required type="number" min={1} max={60} value={draft.capacity} onChange={e => setDraft(s => ({ ...s, capacity: +e.target.value }))}/></label><label>Limite de produtos da mesma categoria<input required type="number" min={1} max={12} value={draft.limit} onChange={e => setDraft(s => ({ ...s, limit: +e.target.value }))}/></label><button className="primary-button">Atualizar plano</button></form>
    {(draft.capacity !== applied.capacity || draft.limit !== applied.limit) && <ContextNote>Há alterações ainda não aplicadas. O resultado abaixo usa a última capacidade confirmada.</ContextNote>}
    {!d ? <Wait error={result.error} retry={result.retry}/> : <>
      <section className="decision-hero compact"><span className="eyebrow">Plano de revisão</span><h2>Revise {d.selecionados.length} produtos, começando por {d.selecionados[0]?.produto ?? 'nenhum produto'}</h2><p>Os produtos selecionados representam {decimal.format(d.coberturaPct)}% do peso histórico de atrasos usado na alocação. Isso indica onde concentrar a revisão, não quantos atrasos serão evitados.</p></section>
      <div className="content-grid equal"><Box title="Ordem de revisão" subtitle={`Capacidade aplicada: ${d.capacidade} produtos · limite de ${d.limitePorCategoria} por categoria`}><ol className="product-plan">{d.selecionados.map(p => <li key={p.produto}><div><strong>{p.produto}</strong><span>Categoria {p.categoriaDominante}</span></div><span>{d.riscoTotal ? percent(p.cargaEstimadaD1 / d.riscoTotal) : '—'} do peso</span></li>)}</ol><p className="subtle">Confira os chamados recorrentes e combine o plano com os responsáveis por cada produto.</p></Box><Box title="O que muda com mais capacidade?" subtitle="Participação do peso histórico incluída no plano, para cada limite de revisão"><div className="chart-md"><ResponsiveContainer width="100%" height="100%"><BarChart data={[...d.sensibilidade.filter(s => s.capacidade !== d.capacidade), { capacidade: d.capacidade, pctDoTotal: d.coberturaPct }].sort((a, b) => a.capacidade - b.capacidade)}><CartesianGrid vertical={false}/><XAxis dataKey="capacidade"/><YAxis unit="%" domain={[0, 100]}/><Tooltip labelFormatter={v => `${v} produtos por dia`} formatter={v => [`${decimal.format(Number(v))}%`, 'Peso incluído no plano']}/><Bar isAnimationActive={false} dataKey="pctDoTotal" fill="#739fce" radius={[4, 4, 0, 0]}/></BarChart></ResponsiveContainer></div></Box></div>
      <Explain title="Premissas e método do planejamento"><p>A otimização distribui a previsão total de volume pelo peso de cada produto nas violações históricas. Essa carga ponderada serve para ordenar a revisão; não é uma previsão calibrada de violações por produto.</p><p>Cada produto usa uma vaga de revisão. A duração real e os custos de atendimento não estão disponíveis na base. O limite por categoria evita concentrar todas as revisões em uma só categoria.</p><p>Os códigos de produto e categoria são os identificadores fornecidos na base; seus nomes comerciais não foram inventados.</p></Explain>
    </>}
    <div className="next-step"><span>Para dimensionar pessoas, use as premissas de produtividade.</span><button className="ghost-button" onClick={() => navigate('capacity')}>Planejar equipe <ArrowRight size={16}/></button></div>
  </>
}

export function TeamPlan({ navigate }: { navigate: Navigate }) {
  const initial = { produtividade: 25, ocupacao: 80, indisponibilidade: 10, analistas_atuais: 40, horizonte: 'D+1' }
  const [draft, setDraft] = useState(initial)
  const [applied, setApplied] = useState(initial)
  const [data, setData] = useState<Capacity>()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const overview = useRead<Overview>('/api/overview')
  useEffect(() => {
    let active = true; setBusy(true); setError(''); setData(undefined)
    api<Capacity>('/api/capacity', { method: 'POST', body: JSON.stringify({ ...applied, ocupacao: applied.ocupacao / 100, indisponibilidade: applied.indisponibilidade / 100 }) }).then(d => { if (active) setData(d) }).catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [applied])
  const target = overview.data?.forecast.find(f => f.horizonte === applied.horizonte)
  const base = data?.cenarios[1]
  return <>
    <Heading title="A equipe será suficiente?">Transforme o volume previsto em necessidade de pessoas. Os valores de produtividade são premissas ajustáveis.</Heading>
    <ContextNote>{target ? `Simulação para ${fullDate(target.dataAlvo)} · base histórica até ${fullDate(overview.data!.snapshot.fim)}.` : 'Simulação baseada no último período da base histórica.'} Não representa a demanda de hoje.</ContextNote>
    <div className="content-grid equal"><Box title="1. Informe as condições da equipe" subtitle="Valores iniciais ilustrativos; ajuste à realidade antes de decidir."><form className="form-grid" onSubmit={e => { e.preventDefault(); setApplied({ ...draft }) }}>
      <label><span>Data do planejamento</span><select value={draft.horizonte} onChange={e => setDraft(s => ({ ...s, horizonte: e.target.value }))}>{['D+1', 'D+7'].map(h => <option key={h} value={h}>{overview.data?.forecast.find(f => f.horizonte === h) ? fullDate(overview.data.forecast.find(f => f.horizonte === h)!.dataAlvo) : h === 'D+1' ? 'Dia seguinte ao fim da base' : 'Sete dias após o fim da base'}</option>)}</select></label>
      {([{ key: 'analistas_atuais', label: 'Analistas disponíveis', min: 0, max: 10000 }, { key: 'produtividade', label: 'Chamados por analista por dia', min: 1, max: 1000 }, { key: 'ocupacao', label: 'Tempo dedicado ao atendimento (%)', min: 10, max: 100 }, { key: 'indisponibilidade', label: 'Reserva para ausências (%)', min: 0, max: 89 }] as const).map(f => <label key={f.key}><span>{f.label}</span><input required type="number" min={f.min} max={f.max} value={draft[f.key]} onChange={e => setDraft(s => ({ ...s, [f.key]: +e.target.value }))}/></label>)}
      <button className="primary-button span-2" disabled={busy}>{busy ? 'Calculando…' : 'Calcular necessidade de equipe'}</button>
    </form>{JSON.stringify(draft) !== JSON.stringify(applied) && <p className="subtle">Alterações pendentes: clique em Calcular para atualizar a recomendação.</p>}</Box>
    <Box title="2. Confira a necessidade estimada" subtitle={target ? `Planejamento para ${fullDate(target.dataAlvo)}` : undefined}>{!data ? <Wait error={error} retry={() => setApplied(s => ({ ...s }))}/> : <>
      {base && <div className="team-answer"><strong>{base.gap > 0 ? `Faltariam ${base.gap} analistas` : `A equipe cobriria o cenário-base`}</strong><p>{base.necessarios} necessários para {integer.format(base.demanda)} chamados, considerando {applied.analistas_atuais} disponíveis.</p></div>}
      <div className="scenario-list">{data.cenarios.map((s, i) => <article key={s.cenario}><span>{['Menor volume', 'Cenário-base', 'Maior volume'][i] ?? s.cenario}</span><strong>{s.necessarios} analistas</strong><p>{integer.format(s.demanda)} chamados · {s.gap > 0 ? `${s.gap === 1 ? 'faltaria' : 'faltariam'} ${s.gap}` : `reserva de ${Math.abs(s.gap)}`}</p></article>)}</div>
      <p>Se a equipe não cobrir o cenário escolhido, revise a escala, a produtividade esperada e a possibilidade de apoio antes de assumir novos compromissos.</p>
      <Explain title="Como a necessidade foi calculada"><p>Capacidade por analista: {applied.produtividade} × {percent(applied.ocupacao / 100)} × {percent(1 - applied.indisponibilidade / 100)} = {decimal.format(data.capacidadeEfetiva)} chamados por dia. A demanda de cada cenário é dividida por essa capacidade e arredondada para cima.</p><p>A faixa da previsão representa incerteza. A base não informa produtividade, escala ou ausências reais da equipe.</p></Explain>
    </>}</Box></div>
    <PriorityDemand horizon={applied.horizonte}/>
    <div className="next-step"><span>Já definiu a equipe? Escolha os produtos para revisão.</span><button className="ghost-button" onClick={() => navigate('optimization')}>Planejar revisão de produtos <ArrowRight size={16}/></button></div>
  </>
}

function PriorityDemand({ horizon }: { horizon: string }) {
  const result = useRead<PriorityForecast>('/api/forecast/priorities')
  const forecasts = result.data?.previsoes.filter(f => f.horizonte === horizon)
  return <Box title="3. Confira a demanda P2 e P3" subtitle="Estimativas diárias por prioridade original para a data aplicada acima.">
    {!result.data ? <Wait error={result.error} retry={result.retry}/> : <>
      <div className="metric-strip">{forecasts?.map(f => <Metric key={f.prioridade} label={`P${f.prioridade} · ${fullDate(f.dataAlvo)}`} value={`${integer.format(f.ponto)} chamados`}>Faixa estimada: {integer.format(f.inferior)} a {integer.format(f.superior)} chamados</Metric>)}</div>
      {forecasts?.some(f => f.validacao.ganho !== null && f.validacao.ganho < 0) && <div className="review-banner"><AlertTriangle/><div><strong>Estimativas que exigem revisão: {forecasts.filter(f => f.validacao.ganho !== null && f.validacao.ganho < 0).map(f => `P${f.prioridade}`).join(', ')}.</strong><p>Nesses recortes, o modelo teve mais erro no teste que repetir a semana anterior. Confira a comparação abaixo e não use essas estimativas sozinhas para definir a escala.</p></div></div>}
      <p>Confira se a escala tem pessoas habilitadas para atender cada prioridade. Os volumes abaixo já fazem parte do contexto da demanda total: não os some novamente ao cálculo de equipe.</p>
      <p className="subtle">Base até {fullDate(result.data.snapshot)}. {horizon === 'D+7' ? 'D+7 estima o volume do sétimo dia, não a soma da semana.' : 'D+1 estima o dia seguinte ao fim da base.'} As estimativas por prioridade são independentes do modelo de volume total.</p>
      <Explain title="Conferir a qualidade da previsão por prioridade">
        <p>{result.data.metodo}</p>
        {forecasts?.map(f => <div key={f.prioridade}>
          <h3>P{f.prioridade}: {f.modelo}</h3>
          <p>Teste de {fullDate(f.validacao.inicio)} a {fullDate(f.validacao.fim)}, com {f.validacao.dias} dias. Erro médio absoluto: {decimal.format(f.validacao.mae)} chamados por dia. Repetir a semana anterior teria erro de {decimal.format(f.validacao.maeBaseline)} chamados por dia.</p>
          <p>{f.validacao.ganho === null ? 'A comparação percentual não se aplica porque a referência teve erro zero.' : f.validacao.ganho > 0 ? `O erro no teste foi ${percent(f.validacao.ganho)} menor que o da referência semanal.` : f.validacao.ganho < 0 ? `O erro no teste foi ${percent(-f.validacao.ganho)} maior que o da referência semanal. Revise esta previsão antes de usá-la operacionalmente.` : 'O método selecionado equivale à referência semanal; não houve ganho frente a ela.'} A faixa cobriu {percent(f.validacao.coberturaFaixa)} dos dias de teste.</p>
          <div className="chart-md"><ResponsiveContainer width="100%" height="100%"><AreaChart data={f.backtest}><CartesianGrid vertical={false}/><XAxis dataKey="data" tickFormatter={fullDate} minTickGap={65}/><YAxis/><Tooltip labelFormatter={x => fullDate(String(x))}/><Area isAnimationActive={false} dataKey="real" name="Volume observado" stroke="#7fa9d7" fill="#24425f"/><Area isAnimationActive={false} dataKey="previsto" name="Previsão no teste" stroke="#ff804a" fill="transparent"/></AreaChart></ResponsiveContainer></div>
        </div>)}
        <p>{result.data.nota}</p>
      </Explain>
    </>}
  </Box>
}

export function ForecastHealth() {
  const status = useRead<ModelStatus>('/api/model-status')
  const drift = useRead<Drift>('/api/drift')
  if (!status.data || !drift.data) return <Wait error={status.error || drift.error} retry={() => { status.retry(); drift.retry() }}/>
  const s = status.data; const d = drift.data
  return <>
    <Heading title="As previsões precisam de revisão?">Verifique se os dados ainda se parecem com aqueles usados para treinar os modelos.</Heading>
    <section className="decision-hero compact"><span className="eyebrow">Situação dos modelos</span><h2>{s.revalidacaoRecomendada ? 'Revisar os modelos antes de automatizar decisões' : 'Nenhum alerta nos critérios monitorados'}</h2><p>{s.revalidacaoRecomendada ? 'Há sinais de mudança nos dados ou de base desatualizada. As estimativas ajudam a investigar, mas precisam de avaliação com dados recentes antes do uso operacional.' : 'Os critérios monitorados não acionaram revisão. Continue conferindo as previsões contra os resultados observados.'}</p></section>
    <div className="content-grid equal"><Box title="O que mudou?"><p>O volume médio de incidentes elegíveis passou de <strong>{decimal.format(d.volumeMedioDia.referencia)}</strong> para <strong>{decimal.format(d.volumeMedioDia.recente)}</strong> por dia entre os períodos comparados.</p><p>Base de referência: {fullDate(d.janelaReferencia.inicio)} a {fullDate(d.janelaReferencia.fim)}.<br/>Período comparado: {fullDate(d.janelaRecente.inicio)} a {fullDate(d.janelaRecente.fim)}.</p><p className="subtle">“Recente” significa o último período da base histórica, não o dia de hoje.</p></Box><Box title="Qual é o próximo passo?"><ol className="plain-steps"><li>Conferir se a mudança vem da operação ou da coleta de dados.</li><li>Atualizar a base e avaliar o erro em um período novo.</li><li>Se o desempenho piorou, retreinar e comparar os modelos antes de publicar.</li></ol><p className="subtle">Este painel sinaliza a necessidade de revisão; não executa o retreinamento.</p></Box></div>
    <Explain title="Ver critérios e métricas técnicas"><p>Última base: {s.snapshot} · {s.diasDesdeSnapshot} dias desde o fechamento.</p><ul>{s.motivos.map(m => <li key={m}>{m}</li>)}</ul><p>ROC-AUC no teste: {s.risco.rocAuc.toFixed(3)} · erro médio absoluto de volume: {decimal.format(s.volume.maeD1)} chamados no dia seguinte.</p><p>PSI compara distribuições. Valor a partir de 0,20 aciona atenção nesta aplicação; não é uma taxa de acerto.</p><div className="data-table-wrap"><table><thead><tr><th>Variável</th><th>PSI</th><th>Situação</th></tr></thead><tbody>{d.features.map(f => <tr key={f.feature}><td>{f.feature}</td><td>{f.psi.toFixed(2)}</td><td>{f.nivel}</td></tr>)}</tbody></table></div></Explain>
  </>
}
