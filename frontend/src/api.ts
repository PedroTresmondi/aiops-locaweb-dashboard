const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

/** Resolve a "/api/..." path against the configured backend origin (empty in dev / same-origin). */
export function apiUrl(path: string): string {
  return BASE + path
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `Falha na API (${response.status})`)
  }
  return response.json() as Promise<T>
}
