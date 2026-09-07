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

