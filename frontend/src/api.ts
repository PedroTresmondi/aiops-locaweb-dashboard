const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

/** Resolve a "/api/..." path against the configured backend origin (empty in dev / same-origin). */
export function apiUrl(path: string): string {
  return BASE + path
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: { ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    const message = Array.isArray(detail)
      ? detail.map((item: { loc?: (string | number)[]; msg?: string }) => `${item.loc?.slice(1).join('.') || 'Dados'}: ${item.msg || 'valor inválido'}`).join('; ')
      : typeof detail === 'string' ? detail : `Falha na API (${response.status})`
    throw new Error(message)
  }
  return response.json() as Promise<T>
}
