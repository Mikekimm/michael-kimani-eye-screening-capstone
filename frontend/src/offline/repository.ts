import { openDB, type DBSchema, type IDBPDatabase } from "idb";

import type { Eye, PatientInput } from "@/lib/api/types";

export type QueueStatus = "pending" | "syncing" | "synced" | "failed";

interface QueueItemBase {
  clientUuid: string;
  status: QueueStatus;
  attempts: number;
  nextAttemptAt: number;
  lastError: string | null;
  /** true when retrying unchanged cannot help (e.g. the server rejected the image). */
  permanent: boolean;
  createdAt: string;
  serverId: string | null;
}

export interface PatientQueueItem extends QueueItemBase {
  kind: "patient";
  patient: PatientInput & { client_uuid: string };
}

export interface ScreeningQueueItem extends QueueItemBase {
  kind: "screening";
  /** Either a server patient id, or the client_uuid of a patient that is still queued. */
  patientId: string | null;
  patientClientUuid: string | null;
  patientCode: string;
  eye: Eye;
  capturedAt: string;
  image: Blob;
}

export type QueueItem = PatientQueueItem | ScreeningQueueItem;

/** Storage abstraction for the offline queue; IndexedDB in the app, memory in tests. */
export interface QueueRepository {
  all(): Promise<QueueItem[]>;
  get(clientUuid: string): Promise<QueueItem | undefined>;
  put(item: QueueItem): Promise<void>;
  remove(clientUuid: string): Promise<void>;
  getMeta(key: string): Promise<string | undefined>;
  setMeta(key: string, value: string): Promise<void>;
}

interface OfflineSchema extends DBSchema {
  queue: { key: string; value: QueueItem; indexes: { "by-status": QueueStatus } };
  meta: { key: string; value: string };
}

export class IndexedDbQueueRepository implements QueueRepository {
  private db: Promise<IDBPDatabase<OfflineSchema>>;

  constructor(name = "retina-offline") {
    this.db = openDB<OfflineSchema>(name, 1, {
      upgrade(db) {
        const queue = db.createObjectStore("queue", { keyPath: "clientUuid" });
        queue.createIndex("by-status", "status");
        db.createObjectStore("meta");
      },
    });
  }

  async all(): Promise<QueueItem[]> {
    const items = await (await this.db).getAll("queue");
    return items.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  }

  async get(clientUuid: string): Promise<QueueItem | undefined> {
    return (await this.db).get("queue", clientUuid);
  }

  async put(item: QueueItem): Promise<void> {
    await (await this.db).put("queue", item);
  }

  async remove(clientUuid: string): Promise<void> {
    await (await this.db).delete("queue", clientUuid);
  }

  async getMeta(key: string): Promise<string | undefined> {
    return (await this.db).get("meta", key);
  }

  async setMeta(key: string, value: string): Promise<void> {
    await (await this.db).put("meta", value, key);
  }
}

export class InMemoryQueueRepository implements QueueRepository {
  private items = new Map<string, QueueItem>();
  private meta = new Map<string, string>();

  async all(): Promise<QueueItem[]> {
    return [...this.items.values()].sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  }

  async get(clientUuid: string): Promise<QueueItem | undefined> {
    return this.items.get(clientUuid);
  }

  async put(item: QueueItem): Promise<void> {
    this.items.set(item.clientUuid, { ...item });
  }

  async remove(clientUuid: string): Promise<void> {
    this.items.delete(clientUuid);
  }

  async getMeta(key: string): Promise<string | undefined> {
    return this.meta.get(key);
  }

  async setMeta(key: string, value: string): Promise<void> {
    this.meta.set(key, value);
  }
}
