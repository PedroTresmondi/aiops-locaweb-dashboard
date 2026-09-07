export type Forecast = { horizonte: string; dataAlvo: string; ponto: number; inferior: number; superior: number }

export type Overview = {
  snapshot: { inicio: string; fim: string; incidentes: number; elegiveis: number; violacoes: number; taxaOla: number }
  forecast: Forecast[]
  risk: { rocAuc: number; prAuc: number; captura: number; filaAlta: number; lift: number }
  daily: { data: string; incidentes: number }[]
  monthly: { mes: string; incidentes: number; elegiveis: number; violacoes: number; taxaOla: number | null }[]
  validation: Record<string, { mae: number; wape: number; ganho: number }>
}

export type TriageResult = {
  probabilidade: number
  faixa: 'Alto' | 'Moderado' | 'Baixo'
  limiarMedio: number
  limiarAlto: number
  taxaBase: number
  multiplicadorBase: number
  acao: string
  evidencias: { fator: string; amostra: number; taxa: number | null }[]
}

export type Diagnostic = {
  dimensao: string
  taxaGeral: number
  items: { nome: string; elegiveis: number; violacoes: number; taxa: number; participacao: number }[]
}

export type Capacity = {
  horizonte: string
  capacidadeEfetiva: number
  cenarios: { cenario: string; demanda: number; necessarios: number; gap: number }[]
  acao: string
  nota: string
}

export type Models = {
  volume: { horizonte: string; modelo: string; mae: number; rmse: number; r2: number; wape: number; ganho: number }[]
  risk: { rocAuc: number; prAuc: number; brier: number; prevalencia: number; filaAlta: number; precisaoFila: number; captura: number; lift: number; amostra: number; violacoes: number }
  importance: { variavel: string; valor: number }[]
  calibration: { decil: number; previsto: number; observado: number; incidentes: number }[]
}

export type Perfil = 'analista' | 'gestor' | 'administrador'

export type FatorRisco = {
  fator: string
  valor: string
  contribuicao: number
  taxaHistorica: number | null
  amostra: number
}

export type ItemFila = {
  id: string
  prioridade: number
  produto: string
  categoria: string
  grupo: string
  aberto: string
  probabilidade: number
  faixa: 'Alto' | 'Moderado' | 'Baixo'
  fatores: FatorRisco[]
  violouReal?: boolean
}

export type ResumoFila = {
  total: number
  filaAlta: number
  filaModerada: number
  violacoesEsperadas: number
  corteFilaAlta: number
  capturaTop20Pct: number
  violacoesReais?: number
  violacoesReaisNoTop20?: number
}

export type RespostaFila = {
  origem: string
  loteId?: string | null
  referencia?: string | null
  janelaModelo?: string
  resumo: ResumoFila
  fila: ItemFila[]
}

export type ResumoAcoes = {
  ticketsComAcao: number
  totalEventos: number
  totalLotes: number
  porAcao: Record<string, number>
  riscoPriorizado: number
}

export type AcaoRegistro = {
  id: number
  ticketRef: string
  acao: string
  faixa: string | null
  probabilidade: number | null
  nota: string | null
  perfil: string | null
  criadoEm: string
}

export type Drift = {
  janelaReferencia: { inicio: string; fim: string; incidentes: number; descricao: string }
  janelaRecente: { inicio: string; fim: string; incidentes: number; descricao: string }
  features: { feature: string; psi: number; nivel: string; detalhe: { faixa: string; esperado: number; atual: number; psi: number }[] }[]
  volumeMedioDia: { referencia: number; recente: number; razao: number }
  taxaViolacao: { referencia: number; recente: number; variacaoPP: number }
  piorPsi: number
  revalidacaoRecomendada: boolean
}

export type ModelStatus = {
  snapshot: string
  diasDesdeSnapshot: number
  cicloRetreinoDias: number
  origemDados: string
  risco: { treino: string; validacao: string; holdout: string; rocAuc: number; prAuc: number }
  volume: { holdout: string; maeD1: number; maeD7: number }
  deriva: { piorPsi: number; volumeRazao: number; revalidacaoRecomendada: boolean }
  revalidacaoRecomendada: boolean
  motivos: string[]
}

export type Optimization = {
  previsaoD1Total: number
  capacidade: number
  limitePorCategoria: number
  custoUniforme: boolean
  riscoCoberto: number
  riscoTotal: number
  coberturaPct: number
  precoSombra: number
  selecionados: { produto: string; categoriaDominante: string; cargaEstimadaD1: number; custo: number }[]
  fila: { produto: string; categoriaDominante: string; incidentesTotal: number; olaViolados: number; cargaEstimadaD1: number; selecionado: boolean }[]
  sensibilidade: { capacidade: number; riscoCoberto: number; pctDoTotal: number }[]
}

export type Segmentation = {
  dimensao: string
  kEscolhido: number
  criterio: string
  escolhaK: { k: number; silhouette: number; inertia: number }[]
  clusters: { posicao: number; rotulo: string; entidades: number; incidentesTotal: number; olaViolados: number; taxaMedia: number; duracaoMediaH: number }[]
  entidades: { entidade: string; cluster: number; rotulo: string; incidentesTotal: number; incidentesKpi: number; olaViolados: number; taxaViolacao: number; duracaoMediaH: number }[]
}

export type AdvancedModel = {
  janelaBacktest: { inicio: string; fim: string; descricao: string }
  metricas: {
    horizonte: string; modelo: string; nPontos: number; mae: number; rmse: number; wape: number; r2: number
    maeBaseline: number; maeOperacional: number; ganhoVsBaseline: number; ganhoVsOperacional: number
  }[]
  previsoes: { horizonte: string; dataAlvo: string; ponto: number; inferior: number; superior: number; linear: number; gbmPoisson: number; alvoFeriado: boolean }[]
  backtest: { dataAlvo: string; horizonte: string; real: number; baseline: number; operacional: number; avancado: number }[]
  importancias: { horizonte: string; variavel: string; importancia: number; eFeriado: boolean }[]
  feriados: { data: string; nome: string }[]
}

