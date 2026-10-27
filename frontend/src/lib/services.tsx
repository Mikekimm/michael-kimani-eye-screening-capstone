import { createContext, useContext, type ReactNode } from "react";

import { IndexedDbQueueRepository } from "@/offline/repository";
import { SyncQueue } from "@/offline/syncQueue";

import { createApi, type Api } from "./api/endpoints";
import { HttpClient } from "./api/http";
import { TokenStore } from "./auth/tokenStore";

/** Application-wide services, created once and injected through context (swappable in tests). */
export interface Services {
  api: Api;
  tokens: TokenStore;
  queue: SyncQueue;
}

export function createServices(onSessionExpired: () => void): Services {
  const tokens = new TokenStore();
  const api = createApi(new HttpClient(apiBaseUrl(), tokens, onSessionExpired));
  return { api, tokens, queue: new SyncQueue(new IndexedDbQueueRepository(), api) };
}

/** Same origin ("/api") locally; on the hosted deployment the API lives on its own host (render.yaml). */
function apiBaseUrl(): string {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  if (import.meta.env.VITE_API_HOST) return `https://${import.meta.env.VITE_API_HOST}/api`;
  return "/api";
}

const ServicesContext = createContext<Services | null>(null);

export function ServicesProvider({ services, children }: { services: Services; children: ReactNode }) {
  return <ServicesContext.Provider value={services}>{children}</ServicesContext.Provider>;
}

export function useServices(): Services {
  const services = useContext(ServicesContext);
  if (!services) throw new Error("useServices must be used inside ServicesProvider");
  return services;
}

export const useApi = (): Api => useServices().api;
