import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const dateOnly = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });

export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso));
}

export function formatDate(iso: string): string {
  return dateOnly.format(new Date(iso));
}

export function percent(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export const EYE_LABEL = { left: "Left eye", right: "Right eye" } as const;

export const CONDITION_LABEL: Record<string, string> = { dr: "Diabetic retinopathy", glaucoma: "Glaucoma", cataract: "Cataract" };
/** Specialist specialties; "general" matches every case. */
export const SPECIALTY_LABEL: Record<string, string> = { ...CONDITION_LABEL, general: "General (all cases)" };

export const ROLE_LABEL = { health_worker: "Health worker", specialist: "Specialist", admin: "Administrator" } as const;

/** "45 min", "5 h" or "3 days": how long something has been waiting, for queues and status lines. */
export function waitingFor(sinceIso: string, now: number = Date.now()): string {
  const minutes = Math.max(0, Math.floor((now - new Date(sinceIso).getTime()) / 60_000));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours} h`;
  return `${Math.floor(hours / 24)} days`;
}
