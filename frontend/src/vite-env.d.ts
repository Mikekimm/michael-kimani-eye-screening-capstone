/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API base URL; defaults to "/api" (proxied to the backend in dev and preview). */
  readonly VITE_API_URL?: string;
  /** API host name on the hosted deployment (render.yaml), e.g. retina-screening-api.onrender.com */
  readonly VITE_API_HOST?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
