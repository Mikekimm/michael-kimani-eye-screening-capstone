import { beforeEach, describe, expect, it } from "vitest";

import { ApiError, NetworkError } from "@/lib/api/http";
import type { NewScreening } from "@/lib/api/endpoints";
import type { PatientInput, Screening, SyncPullResponse } from "@/lib/api/types";

import { MAX_AUTO_ATTEMPTS } from "./backoff";
import { InMemoryQueueRepository } from "./repository";
import { SyncQueue } from "./syncQueue";

/**
 * A fake server that behaves like the real API: idempotent on client_uuid. It can drop the
 * connection before a request arrives, or *after* saving (the reply is lost on the way back).
 */
class FakeServer {
  screenings = new Map<string, string>();
  patients = new Map<string, string>();
  mode: "ok" | "offline" | "lose-reply" | "reject" | "error500" = "ok";
  calls: { uuid: string; attempt: number; patientId?: string }[] = [];
  pulls: (string | undefined)[] = [];

  api = {
    screenings: {
      create: async (input: NewScreening, attempt = 1) => {
        this.calls.push({ uuid: input.clientUuid, attempt, patientId: input.patientId });
        if (this.mode === "offline") throw new NetworkError();
        if (this.mode === "reject") throw new ApiError(422, "unusable_image", "This photo cannot be screened: Image appears blank or uniform.");
        if (this.mode === "error500") throw new ApiError(500, "error", "Server error");
        if (!this.screenings.has(input.clientUuid)) this.screenings.set(input.clientUuid, `srv-${this.screenings.size + 1}`);
        if (this.mode === "lose-reply") throw new NetworkError();
        return { id: this.screenings.get(input.clientUuid)! } as Screening;
      },
    } as never,
    sync: {
      pushPatients: async (patients: PatientInput[]) => {
        if (this.mode === "offline") throw new NetworkError();
        return {
          results: patients.map((p) => {
            const duplicate = this.patients.has(p.client_uuid!);
            if (!duplicate) this.patients.set(p.client_uuid!, `pat-${this.patients.size + 1}`);
            return { client_uuid: p.client_uuid!, outcome: duplicate ? "duplicate" : "accepted", server_id: this.patients.get(p.client_uuid!)!, error: null } as const;
          }),
        };
      },
      pull: async (since?: string): Promise<SyncPullResponse> => {
        this.pulls.push(since);
        return { server_time: `T${this.pulls.length}`, decisions: [] };
      },
    } as never,
  };
}

const image = new Blob(["fake-jpeg"], { type: "image/jpeg" });

describe("SyncQueue", () => {
  let server: FakeServer;
  let repo: InMemoryQueueRepository;
  let clock: number;
  let queue: SyncQueue;
  let n: number;

  beforeEach(() => {
    server = new FakeServer();
    repo = new InMemoryQueueRepository();
    clock = 1_000_000;
    n = 0;
    queue = new SyncQueue(repo, server.api, () => clock, { baseMs: 1000, maxMs: 60_000, random: () => 0.5 }, () => `uuid-${++n}`);
  });

  it("sends queued screenings and marks them synced", async () => {
    await queue.enqueueScreening({ patientId: "p1", patientCode: "PHC-1", eye: "left", image, patientConsent: true });
    const report = await queue.syncNow();
    expect(report).toMatchObject({ synced: 1, failed: 0, offline: false });
    const [item] = await queue.list();
    expect(item).toMatchObject({ status: "synced", serverId: "srv-1", attempts: 1 });
  });

  it("does not create a duplicate when the reply is lost after the server saved the record", async () => {
    const item = await queue.enqueueScreening({ patientId: "p1", patientCode: "PHC-1", eye: "right", image, patientConsent: true });
    server.mode = "lose-reply";
    await queue.syncNow();
    expect((await queue.list())[0]).toMatchObject({ status: "pending", attempts: 1 });

    server.mode = "ok";
    clock += 60_000; // past the backoff delay
    await queue.syncNow();
    expect(server.screenings.size).toBe(1);
    expect(server.calls.map((c) => [c.uuid, c.attempt])).toEqual([[item.clientUuid, 1], [item.clientUuid, 2]]);
    expect((await queue.list())[0]).toMatchObject({ status: "synced", serverId: "srv-1" });
  });

  it("stops at the first network failure, keeps order, and schedules a backoff", async () => {
    await queue.enqueueScreening({ patientId: "p1", patientCode: "A", eye: "left", image, patientConsent: true });
    clock += 1;
    await queue.enqueueScreening({ patientId: "p1", patientCode: "B", eye: "left", image, patientConsent: true });
    server.mode = "offline";
    const report = await queue.syncNow();
    expect(report.offline).toBe(true);
    expect(server.calls).toHaveLength(1); // the second item was not attempted
    const [first, second] = await queue.list();
    expect(first).toMatchObject({ status: "pending", attempts: 1, nextAttemptAt: clock + 500 }); // 0.5 * 1000ms
    expect(second).toMatchObject({ status: "pending", attempts: 0 });
    expect(server.pulls).toHaveLength(0); // no pull while offline
  });

  it("respects the backoff: items are not retried before their next attempt time", async () => {
    await queue.enqueueScreening({ patientId: "p1", patientCode: "A", eye: "left", image, patientConsent: true });
    server.mode = "offline";
    await queue.syncNow();
    server.mode = "ok";
    await queue.syncNow(); // too early
    expect(server.calls).toHaveLength(1);
    clock += 10_000;
    await queue.syncNow();
    expect(server.calls).toHaveLength(2);
  });

  it("marks an item failed permanently when the server rejects it (no endless retries)", async () => {
    await queue.enqueueScreening({ patientId: "p1", patientCode: "A", eye: "left", image, patientConsent: true });
    server.mode = "reject";
    const report = await queue.syncNow();
    expect(report.failed).toBe(1);
    const [item] = await queue.list();
    expect(item).toMatchObject({ status: "failed", permanent: true });
    expect(item!.lastError).toContain("blank");
    clock += 1_000_000;
    await queue.syncNow();
    expect(server.calls).toHaveLength(1);
  });

  it("gives up automatic retries after the attempt limit but allows a manual retry", async () => {
    await queue.enqueueScreening({ patientId: "p1", patientCode: "A", eye: "left", image, patientConsent: true });
    server.mode = "error500";
    for (let i = 0; i < MAX_AUTO_ATTEMPTS + 2; i++) {
      clock += 10 * 60_000;
      await queue.syncNow();
    }
    expect(server.calls).toHaveLength(MAX_AUTO_ATTEMPTS);
    const [item] = await queue.list();
    expect(item).toMatchObject({ status: "failed", permanent: false });

    server.mode = "ok";
    await queue.retry(item!.clientUuid);
    expect((await queue.list())[0]).toMatchObject({ status: "synced" });
  });

  it("pushes an offline-registered patient before its screening and links them", async () => {
    const patient = await queue.enqueuePatient({ code: "OFF-1" });
    clock += 1;
    await queue.enqueueScreening({ patientClientUuid: patient.clientUuid, patientCode: "OFF-1", eye: "left", image, patientConsent: true });
    await queue.syncNow();
    expect(server.patients.get(patient.clientUuid)).toBe("pat-1");
    expect(server.calls[0]!.patientId).toBe("pat-1");
    expect((await queue.list()).every((i) => i.status === "synced")).toBe(true);
  });

  it("holds a screening whose patient has not synced yet", async () => {
    await queue.enqueueScreening({ patientClientUuid: "missing", patientCode: "X", eye: "left", image, patientConsent: true });
    await queue.syncNow();
    expect(server.calls).toHaveLength(0);
    expect((await queue.list())[0]).toMatchObject({ status: "pending" });
  });

  it("pulls specialist decisions since the last pull", async () => {
    await queue.syncNow();
    await queue.syncNow();
    expect(server.pulls).toEqual([undefined, "T1"]);
  });

  it("shares one run between concurrent sync calls", async () => {
    await queue.enqueueScreening({ patientId: "p1", patientCode: "A", eye: "left", image, patientConsent: true });
    await Promise.all([queue.syncNow(), queue.syncNow(), queue.syncNow()]);
    expect(server.calls).toHaveLength(1);
  });
});
