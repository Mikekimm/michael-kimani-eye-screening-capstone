/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API base URL; defaults to "/api" (proxied to the backend in dev and preview). */
  readonly VITE_API_URL?: string;
  /** API host name on the hosted deployment (render.yaml), e.g. retina-screening-api.onrender.com */
  readonly VITE_API_HOST?: string;
  /** Seconds between automatic refreshes of the queue, home and history (default 30; 0 = off). */
  readonly VITE_REFRESH_SECONDS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
