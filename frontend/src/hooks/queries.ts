import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { AccountStatus, PatientInput, ReviewInput, Role } from "@/lib/api/types";
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

export const useScreenings = (limit = 50) => {
  const api = useApi();
  return useQuery({ queryKey: ["screenings", "mine", limit], queryFn: () => api.screenings.list(limit) });
};

export const useScreening = (id: string) => {
  const api = useApi();
  return useQuery({ queryKey: ["screenings", "detail", id], queryFn: () => api.screenings.get(id) });
};

export const useReferScreening = (id: string) => {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.screenings.refer(id),
    onSuccess: (screening) => {
      client.setQueryData(["screenings", "detail", id], screening);
      return client.invalidateQueries({ queryKey: ["screenings"] });
    },
  });
};

export const useScreeningImage = (id: string) => {
  const api = useApi();
  return useQuery({ queryKey: ["screenings", "image", id], queryFn: () => api.screenings.image(id), staleTime: Infinity });
};

export const useReviewQueue = () => {
  const api = useApi();
  return useQuery({ queryKey: ["reviews", "queue"], queryFn: () => api.reviews.queue() });
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
    mutationFn: ({ id, ...body }: { id: string; role?: Role; is_active?: boolean; status?: AccountStatus }) =>
      api.admin.updateUser(id, body),
    onSuccess: () => client.invalidateQueries({ queryKey: ["admin"] }),
  });
};

export const useAnalytics = () => {
  const api = useApi();
  return useQuery({ queryKey: ["admin", "analytics"], queryFn: () => api.admin.analytics() });
};
