import { ApiError, NetworkError } from "@/lib/api/http";
import type { Api } from "@/lib/api/endpoints";
import type { Eye, PatientInput, SyncDecision } from "@/lib/api/types";

import { DEFAULT_BACKOFF, MAX_AUTO_ATTEMPTS, nextRetryDelay, type BackoffOptions } from "./backoff";
import type { PatientQueueItem, QueueItem, QueueRepository, ScreeningQueueItem } from "./repository";

export interface SyncReport {
  synced: number;
  failed: number;
  stillPending: number;
  offline: boolean;
  decisions: SyncDecision[];
}

type SyncApi = Pick<Api, "screenings" | "sync">;
const LAST_PULL = "lastPullAt";

/**
 * Offline-first queue. Captures are stored on the device first, then pushed in creation order.
 *
 * Correctness rests on the server being idempotent on client_uuid: if the connection drops after
 * the server saved a record but before the reply arrived, the retry returns the same record
 * instead of creating a duplicate. Patients created offline are pushed before the screenings
 * that refer to them.
 */
export class SyncQueue {
  private running: Promise<SyncReport> | null = null;

  constructor(
    private readonly repo: QueueRepository,
    private readonly api: SyncApi,
    private readonly now: () => number = Date.now,
    private readonly backoff: BackoffOptions = DEFAULT_BACKOFF,
    private readonly newUuid: () => string = () => crypto.randomUUID(),
  ) {}

  async enqueuePatient(patient: PatientInput): Promise<PatientQueueItem> {
    const clientUuid = patient.client_uuid ?? this.newUuid();
    const item: PatientQueueItem = {
      ...this.base(clientUuid), kind: "patient", patient: { ...patient, client_uuid: clientUuid },
    };
    await this.repo.put(item);
    return item;
  }

  async enqueueScreening(input: {
    patientId?: string; patientClientUuid?: string; patientCode: string; eye: Eye; image: Blob; capturedAt?: string;
  }): Promise<ScreeningQueueItem> {
    if (!input.patientId && !input.patientClientUuid) throw new Error("A patient is required.");
    const item: ScreeningQueueItem = {
      ...this.base(this.newUuid()), kind: "screening",
      patientId: input.patientId ?? null, patientClientUuid: input.patientClientUuid ?? null,
      patientCode: input.patientCode, eye: input.eye, image: input.image,
      capturedAt: input.capturedAt ?? new Date(this.now()).toISOString(),
    };
    await this.repo.put(item);
    return item;
  }

  list(): Promise<QueueItem[]> {
    return this.repo.all();
  }

  /** Manual retry: clears the backoff and the permanent flag, then syncs. */
  async retry(clientUuid: string): Promise<SyncReport> {
    const item = await this.repo.get(clientUuid);
    if (item && item.status !== "synced") {
      await this.repo.put({ ...item, status: "pending", nextAttemptAt: 0, permanent: false });
    }
    return this.syncNow();
  }

  async discard(clientUuid: string): Promise<void> {
    await this.repo.remove(clientUuid);
  }

  /** Runs one sync cycle; concurrent callers share the same run. */
  syncNow(): Promise<SyncReport> {
    this.running ??= this.cycle().finally(() => {
      this.running = null;
    });
    return this.running;
  }

  private async cycle(): Promise<SyncReport> {
    const report: SyncReport = { synced: 0, failed: 0, stillPending: 0, offline: false, decisions: [] };
    const items = await this.repo.all();
    const due = items.filter((i) => this.isDue(i));
    // Patients first so screenings can resolve their server patient id.
    const ordered = [...due.filter((i) => i.kind === "patient"), ...due.filter((i) => i.kind === "screening")];

    for (const item of ordered) {
      const outcome = await this.push(item);
      if (outcome === "synced") report.synced += 1;
      if (outcome === "failed") report.failed += 1;
      if (outcome === "offline") {
        report.offline = true;
        break; // no connection: stop here, the rest keep their place in the queue
      }
    }
    report.stillPending = (await this.repo.all()).filter((i) => i.status === "pending").length;
    if (!report.offline) report.decisions = await this.pullDecisions(report);
    return report;
  }

  private isDue(item: QueueItem): boolean {
    return (item.status === "pending" || item.status === "syncing") && !item.permanent && item.nextAttemptAt <= this.now();
  }

  private async push(item: QueueItem): Promise<"synced" | "failed" | "offline" | "waiting"> {
    const attempt = item.attempts + 1;
    await this.repo.put({ ...item, status: "syncing" });
    try {
      const serverId = item.kind === "patient" ? await this.pushPatient(item, attempt) : await this.pushScreening(item, attempt);
      if (serverId === null) {
        await this.repo.put({ ...item, status: "pending" }); // waiting for its patient to sync
        return "waiting";
      }
      await this.repo.put({ ...item, status: "synced", attempts: attempt, serverId, lastError: null });
      return "synced";
    } catch (error) {
      return this.recordFailure(item, attempt, error);
    }
  }

  private async pushPatient(item: PatientQueueItem, attempt: number): Promise<string> {
    const { results } = await this.api.sync.pushPatients([item.patient], attempt);
    const result = results[0];
    if (!result || result.outcome === "rejected" || !result.server_id) {
      throw new ApiError(422, "rejected", result?.error ?? "The server rejected this patient.");
    }
    return result.server_id;
  }

  private async pushScreening(item: ScreeningQueueItem, attempt: number): Promise<string | null> {
    let patientId = item.patientId;
    if (!patientId && item.patientClientUuid) {
      const parent = await this.repo.get(item.patientClientUuid);
      patientId = parent?.status === "synced" ? parent.serverId : null;
      if (!patientId) return null;
    }
    const screening = await this.api.screenings.create(
      { patientId: patientId!, eye: item.eye, clientUuid: item.clientUuid, capturedAt: item.capturedAt, image: item.image },
      attempt,
    );
    return screening.id;
  }

  private async recordFailure(item: QueueItem, attempt: number, error: unknown): Promise<"failed" | "offline"> {
    const retryable = error instanceof NetworkError || (error instanceof ApiError && (error.status >= 500 || error.status === 401));
    const message = error instanceof Error ? error.message : "Unknown error.";
    if (retryable && attempt < MAX_AUTO_ATTEMPTS) {
      await this.repo.put({
        ...item, status: "pending", attempts: attempt, lastError: message,
        nextAttemptAt: this.now() + nextRetryDelay(attempt, this.backoff),
      });
      return "offline";
    }
    await this.repo.put({ ...item, status: "failed", attempts: attempt, lastError: message, permanent: !retryable });
    return "failed";
  }

  private async pullDecisions(report: SyncReport): Promise<SyncDecision[]> {
    try {
      const since = await this.repo.getMeta(LAST_PULL);
      const response = await this.api.sync.pull(since);
      await this.repo.setMeta(LAST_PULL, response.server_time);
      return response.decisions;
    } catch (error) {
      if (error instanceof NetworkError) report.offline = true;
      return [];
    }
  }

  private base(clientUuid: string) {
    return {
      clientUuid, status: "pending" as const, attempts: 0, nextAttemptAt: 0, lastError: null, permanent: false,
      createdAt: new Date(this.now()).toISOString(), serverId: null,
    };
  }
}
