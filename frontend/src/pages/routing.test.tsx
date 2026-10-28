import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ConditionResult, QueueItem, Screening } from "@/lib/api/types";
import { renderWithProviders } from "@/test/render";

import { AskSpecialistForm } from "./ScreeningDetailPage";
import { ReviewQueuePage } from "./specialist";

const result = (condition: string, refer_suggested: boolean): ConditionResult => ({
  condition, display_name: condition === "dr" ? "Diabetic retinopathy" : condition === "glaucoma" ? "Glaucoma" : "Cataract",
  model_available: true, model_version: "v", probability: 0.5, threshold: 0.4, positive: refer_suggested, uncertain: false,
  severity_band: null, risk_level: "low", recommendation: "", refer_suggested,
});

const screening = { id: "s1", referral_advice: "recommended", suggested_priority: "urgent", review_priority: null, referral_conditions: [],
  results: [result("dr", true), result("glaucoma", false), result("cataract", true)] } as unknown as Screening;

describe("Ask a specialist form", () => {
  it("pre-ticks the flagged conditions, suggests urgent and sends conditions, question and priority", async () => {
    const onSubmit = vi.fn();
    render(<AskSpecialistForm screening={screening} busy={false} onSubmit={onSubmit} onCancel={vi.fn()} />);
    expect(screen.getByLabelText("Diabetic retinopathy")).toBeChecked();
    expect(screen.getByLabelText("Glaucoma")).not.toBeChecked();
    expect(screen.getByLabelText("Cataract")).toBeChecked();
    expect(screen.getByLabelText("How soon?")).toHaveValue("urgent");

    await userEvent.click(screen.getByLabelText("Cataract"));
    await userEvent.click(screen.getByLabelText("Glaucoma"));
    await userEvent.type(screen.getByLabelText("Your question for the specialist"), "Is the disc cupped?");
    await userEvent.selectOptions(screen.getByLabelText("How soon?"), "routine");
    await userEvent.click(screen.getByRole("button", { name: "Send to specialist" }));
    expect(onSubmit).toHaveBeenCalledWith({ question: "Is the disc cupped?", conditions: ["dr", "glaucoma"], priority: "routine" });
  });

  it("needs at least one condition and a question", async () => {
    const onSubmit = vi.fn();
    render(<AskSpecialistForm screening={{ ...screening, referral_advice: "none", suggested_priority: "routine", results: [result("dr", false)] }}
      busy={false} onSubmit={onSubmit} onCancel={vi.fn()} />);
    expect(screen.getByLabelText("How soon?")).toHaveValue("routine");
    await userEvent.click(screen.getByRole("button", { name: "Send to specialist" }));
    expect(screen.getByText("Tick at least one condition.")).toBeInTheDocument();
    expect(screen.getByText("Write at least a few words.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

const item = (id: string, overrides: Partial<QueueItem>): QueueItem => ({
  screening_id: id, patient_code: `PHC-${id}`, eye: "left", referral_reason: "positive", flagged_conditions: ["dr"],
  highest_band: null, created_at: "2026-10-28T08:00:00Z", created_by_name: "Amina", created_by_facility: null,
  question: "Please check.", waiting_since: "2026-10-28T08:00:00Z", priority: "urgent", due_at: "2026-10-29T08:00:00Z",
  overdue: false, conditions: ["dr"], matches_my_specialties: true, assigned_to_name: null, assigned_to_me: false, ...overrides,
});

const specialist = { id: "u9", email: "s@example.org", full_name: "Dr Retina", role: "specialist", is_active: true,
  status: "approved", status_reason: null, requested_role: null, facility: null, specialties: ["dr"], created_at: "2026-10-01T00:00:00Z" };

describe("Specialist queue", () => {
  it("shows my specialties first, all cases on the other tab, and lets me take an untaken case", async () => {
    const queue = [item("AAAAAA", {}), item("BBBBBB", { conditions: ["glaucoma"], matches_my_specialties: false, assigned_to_name: "Dr Other" })];
    const take = vi.fn().mockResolvedValue({ id: "AAAAAA" });
    renderWithProviders(<ReviewQueuePage />, { route: "/reviews", signedIn: true,
      api: { auth: { me: vi.fn().mockResolvedValue(specialist) }, reviews: { queue: vi.fn().mockResolvedValue(queue), take } } });

    expect(await screen.findByText("PHC-AAAAAA · Left eye")).toBeInTheDocument();
    expect(screen.queryByText("PHC-BBBBBB · Left eye")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "My specialties (1)" })).toHaveAttribute("aria-selected", "true");

    await userEvent.click(screen.getByRole("tab", { name: "All cases (2)" }));
    expect(screen.getByText("PHC-BBBBBB · Left eye")).toBeInTheDocument();
    expect(screen.getByText("Taken by Dr Other")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Take this case" })).toHaveLength(1); // only the untaken case

    await userEvent.click(screen.getByRole("button", { name: "Take this case" }));
    expect(take).toHaveBeenCalledWith("AAAAAA");
  });
});
