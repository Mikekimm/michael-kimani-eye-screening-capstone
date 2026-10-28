/** How often lists that other people change (specialist queue, health worker home and history) refresh by
 * themselves, so a case sent in one window appears in the other without a reload. Set VITE_REFRESH_SECONDS to
 * change it (0 turns it off). TanStack Query pauses the polling while the tab is hidden, which keeps it light. */
export function refreshIntervalMs(seconds: string | undefined = import.meta.env.VITE_REFRESH_SECONDS): number | false {
  const value = seconds === undefined || seconds === "" ? 30 : Number(seconds);
  return Number.isFinite(value) && value > 0 ? value * 1000 : false;
}

export const REFRESH_MS = refreshIntervalMs();
