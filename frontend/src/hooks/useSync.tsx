import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import type { QueueItem } from "@/offline/repository";
import type { SyncReport } from "@/offline/syncQueue";
import { useServices } from "@/lib/services";

import { useAuth } from "./useAuth";
import { useOnline } from "./useOnline";

const AUTO_SYNC_MS = 30_000;

interface SyncState {
  items: QueueItem[];
  counts: Record<QueueItem["status"], number>;
  syncing: boolean;
  lastReport: SyncReport | null;
  syncNow: () => Promise<void>;
  retry: (clientUuid: string) => Promise<void>;
  discard: (clientUuid: string) => Promise<void>;
  refresh: () => Promise<void>;
}

const SyncContext = createContext<SyncState | null>(null);

/** Runs the offline queue: on start, when the device comes back online, and every 30 s. */
export function SyncProvider({ children }: { children: ReactNode }) {
  const { queue } = useServices();
  const { user } = useAuth();
  const online = useOnline();
  const queryClient = useQueryClient();
  const [items, setItems] = useState<QueueItem[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [lastReport, setLastReport] = useState<SyncReport | null>(null);

  const refresh = useCallback(async () => setItems(await queue.list()), [queue]);

  const syncNow = useCallback(async () => {
    if (user?.role !== "health_worker") return;
    setSyncing(true);
    try {
      const report = await queue.syncNow();
      setLastReport(report);
      if (report.synced || report.decisions.length) {
        await queryClient.invalidateQueries({ queryKey: ["screenings"] });
        await queryClient.invalidateQueries({ queryKey: ["patients"] });
      }
    } finally {
      setSyncing(false);
      await refresh();
    }
  }, [queue, user, queryClient, refresh]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!online || user?.role !== "health_worker") return;
    void syncNow();
    const timer = window.setInterval(() => void syncNow(), AUTO_SYNC_MS);
    return () => window.clearInterval(timer);
  }, [online, user, syncNow]);

  const retry = useCallback(async (clientUuid: string) => {
    setSyncing(true);
    try {
      setLastReport(await queue.retry(clientUuid));
    } finally {
      setSyncing(false);
      await refresh();
    }
  }, [queue, refresh]);

  const discard = useCallback(async (clientUuid: string) => {
    await queue.discard(clientUuid);
    await refresh();
  }, [queue, refresh]);

  const value = useMemo<SyncState>(() => {
    const counts = { pending: 0, syncing: 0, synced: 0, failed: 0 };
    for (const item of items) counts[item.status] += 1;
    return { items, counts, syncing, lastReport, syncNow, retry, discard, refresh };
  }, [items, syncing, lastReport, syncNow, retry, discard, refresh]);

  return <SyncContext.Provider value={value}>{children}</SyncContext.Provider>;
}

export function useSync(): SyncState {
  const state = useContext(SyncContext);
  if (!state) throw new Error("useSync must be used inside SyncProvider");
  return state;
}
