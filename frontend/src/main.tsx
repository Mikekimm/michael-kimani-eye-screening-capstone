import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { ToastProvider } from "./components/ui/toast";
import { AuthProvider } from "./hooks/useAuth";
import { SyncProvider } from "./hooks/useSync";
import { ApiError, NetworkError } from "./lib/api/http";
import { createServices, ServicesProvider } from "./lib/services";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Retry only failures that might succeed later; 4xx answers will not change.
      retry: (count, error) => count < 2 && (error instanceof NetworkError || (error instanceof ApiError && error.status >= 500)),
    },
  },
});

const services = createServices(() => {
  queryClient.clear();
  window.location.assign("/login");
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ServicesProvider services={services}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ToastProvider>
            <AuthProvider>
              <SyncProvider>
                <App />
              </SyncProvider>
            </AuthProvider>
          </ToastProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ServicesProvider>
  </StrictMode>,
);
