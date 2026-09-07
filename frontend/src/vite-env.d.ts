/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Origin of the FastAPI backend. Empty in dev (Vite proxies /api) and on the combined container. */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
