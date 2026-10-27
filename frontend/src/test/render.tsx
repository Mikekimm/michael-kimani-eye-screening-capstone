import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { AuthProvider } from "@/hooks/useAuth";
import { SyncProvider } from "@/hooks/useSync";
import { TokenStore } from "@/lib/auth/tokenStore";
import type { Api } from "@/lib/api/endpoints";
import { ServicesProvider, type Services } from "@/lib/services";
import { InMemoryQueueRepository } from "@/offline/repository";
import { SyncQueue } from "@/offline/syncQueue";

/** Renders UI with every provider, a fake API (only the methods a test supplies) and an in-memory queue. */
export function renderWithProviders(ui: ReactElement, { api = {}, route = "/", signedIn = false } = {} as {
  api?: Partial<Record<keyof Api, Record<string, unknown>>>; route?: string; signedIn?: boolean;
}) {
  const tokens = new TokenStore(localStorage);
  if (signedIn) tokens.save({ access_token: "a", refresh_token: "r", token_type: "bearer", expires_in: 900 });
  const fullApi = {
    auth: { me: vi.fn(), login: vi.fn(), register: vi.fn(), logout: vi.fn().mockResolvedValue(undefined), ...api.auth },
    patients: { search: vi.fn().mockResolvedValue([]), ...api.patients },
    screenings: { list: vi.fn().mockResolvedValue([]),
      dailyCounts: vi.fn().mockResolvedValue({ time_zone: "Africa/Kigali", today: "2026-10-28", days: [] }), ...api.screenings },
    reviews: { ...api.reviews },
    sync: { pull: vi.fn().mockResolvedValue({ server_time: "t", decisions: [] }), pushPatients: vi.fn(), ...api.sync },
    admin: { ...api.admin },
    models: { list: vi.fn().mockResolvedValue([]), ...api.models },
  } as unknown as Api;
  const services: Services = { api: fullApi, tokens, queue: new SyncQueue(new InMemoryQueueRepository(), fullApi) };
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    api: fullApi,
    ...render(
      <ServicesProvider services={services}>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={[route]}>
            <ToastProvider>
              <AuthProvider>
                <SyncProvider>{ui}</SyncProvider>
              </AuthProvider>
            </ToastProvider>
          </MemoryRouter>
        </QueryClientProvider>
      </ServicesProvider>,
    ),
  };
}
