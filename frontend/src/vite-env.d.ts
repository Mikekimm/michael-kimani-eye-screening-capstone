/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API base URL; defaults to "/api" (proxied to the backend in dev and preview). */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
