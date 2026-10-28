import type { HttpClient } from "./http";
import type {
  AccountStatus, Analytics, AskSpecialistInput, DailyCounts, Eye, ModelInfo, Patient, PatientInput, QueueItem, ReviewInput, Role,
  Screening, Specialty, SyncItemResult,
  SyncPullResponse, TokenPair, User,
} from "./types";

export interface NewScreening {
  patientId: string;
  eye: Eye;
  clientUuid: string;
  capturedAt: string;
  image: Blob;
  fileName?: string;
  /** The health worker confirmed the patient agreed; the server refuses screenings without it. */
  patientConsent: boolean;
}

export interface SignUpInput {
  email: string;
  full_name: string;
  password: string;
  /** Grants nothing until an administrator approves the account. */
  requested_role: "health_worker" | "specialist";
}

/** Typed wrappers for every backend endpoint, grouped by feature. Components use these via hooks. */
export function createApi(http: HttpClient) {
  return {
    auth: {
      register: (body: SignUpInput) =>
        http.request<User>("/auth/register", { method: "POST", json: body, anonymous: true }),
      forgotPassword: (email: string) =>
        http.request<{ message: string }>("/auth/password/forgot", { method: "POST", json: { email }, anonymous: true }),
      resetPassword: (token: string, password: string) =>
        http.request<void>("/auth/password/reset", { method: "POST", json: { token, password }, anonymous: true }),
      login: (email: string, password: string) =>
        http.request<TokenPair>("/auth/login", { method: "POST", json: { email, password }, anonymous: true }),
      logout: (refreshToken: string) =>
        http.request<void>("/auth/logout", { method: "POST", json: { refresh_token: refreshToken }, anonymous: true }),
      me: () => http.request<User>("/auth/me"),
    },
    patients: {
      search: (q?: string) => http.request<Patient[]>("/patients", { query: { q } }),
      get: (id: string) => http.request<Patient>(`/patients/${id}`),
      create: (body: PatientInput) => http.request<Patient>("/patients", { method: "POST", json: body }),
      screenings: (id: string) => http.request<Screening[]>(`/patients/${id}/screenings`),
    },
    screenings: {
      list: (limit = 50, day?: string) => http.request<Screening[]>("/screenings", { query: { limit, day } }),
      dailyCounts: (days = 14) => http.request<DailyCounts>("/screenings/daily-counts", { query: { days } }),
      newDecisions: () => http.request<{ count: number; screening_ids: string[] }>("/screenings/new-decisions"),
      get: (id: string) => http.request<Screening>(`/screenings/${id}`),
      askSpecialist: (id: string, body: AskSpecialistInput) =>
        http.request<Screening>(`/screenings/${id}/ask-specialist`, { method: "POST", json: body }),
      discard: (id: string, reason: string) =>
        http.request<void>(`/screenings/${id}/discard`, { method: "POST", json: { reason } }),
      image: (id: string) => http.request<Blob>(`/screenings/${id}/image`, { responseType: "blob" }),
      create: (input: NewScreening, attempt = 1) => {
        const form = new FormData();
        form.append("image", input.image, input.fileName ?? "fundus.jpg");
        form.append("patient_id", input.patientId);
        form.append("eye", input.eye);
        form.append("client_uuid", input.clientUuid);
        form.append("captured_at", input.capturedAt);
        form.append("patient_consent", String(input.patientConsent));
        return http.request<Screening>("/screenings", {
          method: "POST", form, headers: { "X-Sync-Attempt": String(attempt) },
        });
      },
    },
    reviews: {
      queue: () => http.request<QueueItem[]>("/reviews/queue"),
      take: (screeningId: string) => http.request<Screening>(`/reviews/${screeningId}/take`, { method: "POST" }),
      submit: (screeningId: string, body: ReviewInput) =>
        http.request<Screening>(`/reviews/${screeningId}`, { method: "POST", json: body }),
    },
    sync: {
      pushPatients: (patients: PatientInput[], attempt = 1) =>
        http.request<{ results: SyncItemResult[] }>("/sync/push", {
          method: "POST", json: { patients }, headers: { "X-Sync-Attempt": String(attempt) },
        }),
      pull: (since?: string) => http.request<SyncPullResponse>("/sync/pull", { query: { since } }),
    },
    admin: {
      users: () => http.request<User[]>("/admin/users"),
      createUser: (body: { email: string; full_name: string; password: string; role: Role }) =>
        http.request<User>("/admin/users", { method: "POST", json: body }),
      updateUser: (id: string, body: { role?: Role; is_active?: boolean; status?: AccountStatus; status_reason?: string; facility?: string; specialties?: Specialty[] }) =>
        http.request<User>(`/admin/users/${id}`, { method: "PATCH", json: body }),
      analytics: () => http.request<Analytics>("/admin/analytics"),
    },
    models: {
      list: () => http.request<ModelInfo[]>("/models"),
    },
  };
}

export type Api = ReturnType<typeof createApi>;
