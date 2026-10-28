import { act, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { refreshIntervalMs } from "@/lib/refresh";
import { renderWithProviders } from "@/test/render";

import { HomePage } from "./HomePage";
import { ReviewQueuePage } from "./specialist";

const user = (role: string) => ({ id: "u1", email: "u@example.org", full_name: "Amina Nurse", role, is_active: true,
  status: "approved", status_reason: null, requested_role: null, facility: null, specialties: ["general"],
  created_at: "2026-10-01T00:00:00Z" });

describe("automatic refresh", () => {
  afterEach(() => vi.useRealTimers());

  it("defaults to 30 seconds, is configurable and can be turned off", () => {
    expect(refreshIntervalMs(undefined)).toBe(30_000);
    expect(refreshIntervalMs("10")).toBe(10_000);
    expect(refreshIntervalMs("0")).toBe(false);
    expect(refreshIntervalMs("nonsense")).toBe(false);
  });

  it("the specialist queue asks the server again after 30 seconds without a reload", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const queue = vi.fn().mockResolvedValue([]);
    renderWithProviders(<ReviewQueuePage />, { route: "/reviews", signedIn: true,
      api: { auth: { me: vi.fn().mockResolvedValue(user("specialist")) }, reviews: { queue } } });
    await screen.findByText("No cases waiting");
    expect(queue).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
    expect(queue).toHaveBeenCalledTimes(2);
  });
});

describe("new decisions on the health worker's home", () => {
  it("shows how many specialist decisions have not been opened and marks them in the list", async () => {
    const reviewed = { id: "s1", patient_code: "PHC-AAAAAA", eye: "left", status: "reviewed", referral_advice: "consider",
      created_at: "2026-10-28T08:00:00Z", results: [], new_decision: true };
    renderWithProviders(<HomePage />, { route: "/", signedIn: true, api: {
      auth: { me: vi.fn().mockResolvedValue(user("health_worker")) },
      screenings: { list: vi.fn().mockResolvedValue([reviewed]),
        newDecisions: vi.fn().mockResolvedValue({ count: 1, screening_ids: ["s1"] }),
        dailyCounts: vi.fn().mockResolvedValue({ time_zone: "Africa/Kigali", today: "2026-10-28", days: [{ day: "2026-10-28", count: 1 }] }) },
    } });
    expect(await screen.findByTestId("new-decision")).toHaveTextContent("New decision");
    await waitFor(() => expect(screen.getByTestId("new-decisions")).toHaveTextContent("1New decisions"));
    expect(screen.getByTestId("status-label")).toHaveTextContent("Reviewed");
  });
});
