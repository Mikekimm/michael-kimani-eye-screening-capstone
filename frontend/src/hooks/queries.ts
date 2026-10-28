import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { AccountStatus, AskSpecialistInput, PatientInput, ReviewInput, Role, Specialty } from "@/lib/api/types";
import { REFRESH_MS } from "@/lib/refresh";
import { useApi } from "@/lib/services";

/** Data hooks: components read server state only through these (no fetch calls in components). */

export const usePatients = (q?: string) => {
  const api = useApi();
  return useQuery({ queryKey: ["patients", q ?? ""], queryFn: () => api.patients.search(q) });
};

export const usePatient = (id: string) => {
  const api = useApi();
  return useQuery({ queryKey: ["patients", "detail", id], queryFn: () => api.patients.get(id) });
};

export const usePatientScreenings = (id: string) => {
  const api = useApi();
  return useQuery({ queryKey: ["screenings", "patient", id], queryFn: () => api.patients.screenings(id) });
};

export const useCreatePatient = () => {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: PatientInput) => api.patients.create(body),
    onSuccess: () => client.invalidateQueries({ queryKey: ["patients"] }),
  });
};

export const useScreenings = (limit = 50, day?: string) => {
  const api = useApi();
  return useQuery({ queryKey: ["screenings", "mine", limit, day ?? ""], queryFn: () => api.screenings.list(limit, day),
    refetchInterval: REFRESH_MS });
};

/** Screenings per day in the clinic's time zone (server setting), for "Screened today" and History. */
export const useDailyCounts = (days = 14) => {
  const api = useApi();
  return useQuery({ queryKey: ["screenings", "daily", days], queryFn: () => api.screenings.dailyCounts(days),
    refetchInterval: REFRESH_MS });
};

/** Specialist decisions not opened yet ("New decisions" on the health worker's home). */
export const useNewDecisions = () => {
  const api = useApi();
  return useQuery({ queryKey: ["screenings", "new-decisions"], queryFn: () => api.screenings.newDecisions(),
    refetchInterval: REFRESH_MS });
};

export const useScreening = (id: string) => {
  const api = useApi();
  const client = useQueryClient();
  return useQuery({
    queryKey: ["screenings", "detail", id],
    queryFn: async () => {
      const screening = await api.screenings.get(id);
      // Opening a screening marks a new specialist decision as seen on the server; refresh the home count.
      void client.invalidateQueries({ queryKey: ["screenings", "new-decisions"] });
      return screening;
    },
  });
};

export const useAskSpecialist = (id: string) => {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: AskSpecialistInput) => api.screenings.askSpecialist(id, body),
    onSuccess: (screening) => {
      client.setQueryData(["screenings", "detail", id], screening);
      return client.invalidateQueries({ queryKey: ["screenings"] });
    },
  });
};

export const useDiscardScreening = (id: string) => {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (reason: string) => api.screenings.discard(id, reason),
    onSuccess: () => client.invalidateQueries({ queryKey: ["screenings"] }),
  });
};

export const useScreeningImage = (id: string) => {
  const api = useApi();
  return useQuery({ queryKey: ["screenings", "image", id], queryFn: () => api.screenings.image(id), staleTime: Infinity });
};

export const useReviewQueue = () => {
  const api = useApi();
  return useQuery({ queryKey: ["reviews", "queue"], queryFn: () => api.reviews.queue(), refetchInterval: REFRESH_MS });
};

export const useTakeCase = (screeningId: string) => {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.reviews.take(screeningId),
    onSuccess: (screening) => {
      client.setQueryData(["screenings", "detail", screeningId], screening);
      return client.invalidateQueries({ queryKey: ["reviews"] });
    },
  });
};

export const useSubmitReview = (screeningId: string) => {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ReviewInput) => api.reviews.submit(screeningId, body),
    onSuccess: (screening) => {
      client.setQueryData(["screenings", "detail", screeningId], screening);
      return client.invalidateQueries({ queryKey: ["reviews"] });
    },
  });
};

export const useModels = () => {
  const api = useApi();
  return useQuery({ queryKey: ["models"], queryFn: () => api.models.list(), staleTime: 5 * 60_000 });
};

export const useUsers = () => {
  const api = useApi();
  return useQuery({ queryKey: ["admin", "users"], queryFn: () => api.admin.users() });
};

export const useUpdateUser = () => {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; role?: Role; is_active?: boolean; status?: AccountStatus; status_reason?: string; facility?: string; specialties?: Specialty[] }) =>
      api.admin.updateUser(id, body),
    onSuccess: () => client.invalidateQueries({ queryKey: ["admin"] }),
  });
};

export const useCreateUser = () => {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; full_name: string; password: string; role: Role }) => api.admin.createUser(body),
    onSuccess: () => client.invalidateQueries({ queryKey: ["admin"] }),
  });
};

export const useAnalytics = () => {
  const api = useApi();
  return useQuery({ queryKey: ["admin", "analytics"], queryFn: () => api.admin.analytics() });
};
