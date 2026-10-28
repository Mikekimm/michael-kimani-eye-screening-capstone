import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import { AnalyticsPage } from "./admin";

const admin = { id: "a1", email: "admin@example.org", full_name: "Admin", role: "admin", is_active: true, status: "approved",
  status_reason: null, requested_role: null, facility: null, specialties: [], created_at: "2026-10-01T00:00:00Z" };

const analytics = {
  total_screenings: 4, screenings_per_day: [], positives_per_condition: {}, referral_rate: 0.5, time_zone: "Africa/Kigali",
  open_referrals: 1, overdue_referrals: 0, overdue_by_priority: { urgent: 0, routine: 0 },
  review_targets_hours: { urgent: 24, routine: 72 }, median_review_turnaround_hours: null, model_versions_in_use: {},
  users_by_role: { health_worker: 3, specialist: 1, admin: 1 }, pending_requests: 2,
};

describe("admin overview", () => {
  it("shows approved people per role and the requests waiting for approval, without names", async () => {
    renderWithProviders(<AnalyticsPage />, { route: "/admin/analytics", signedIn: true, api: {
      auth: { me: vi.fn().mockResolvedValue(admin) },
      admin: { analytics: vi.fn().mockResolvedValue(analytics), users: vi.fn().mockResolvedValue([]) },
    } });
    const people = await screen.findByTestId("people-overview");
    const expected: [string, string][] = [["Health workers", "3"], ["Specialists", "1"], ["Administrators", "1"], ["Waiting for approval", "2"]];
    for (const [label, value] of expected) {
      expect(within(people).getByText(label).parentElement).toHaveTextContent(value);
    }
    expect(within(people).getByRole("link")).toHaveAttribute("href", "/admin/users");
  });
});
