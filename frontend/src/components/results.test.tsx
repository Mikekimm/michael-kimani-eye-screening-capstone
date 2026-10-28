import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MemoryRouter } from "react-router-dom";

import type { ConditionResult, ModelInfo, Screening } from "@/lib/api/types";

import { statusLabel } from "./feedback";
import { ScreeningResultCard } from "./ScreeningResultCard";
import { OutdatedModelNotice } from "./ScreeningView";
import { SeverityMeter } from "./SeverityMeter";

const dr = (overrides: Partial<ConditionResult> = {}): ConditionResult => ({
  condition: "dr", display_name: "Diabetic retinopathy", model_available: true, model_version: "mobilenetv2-dr-binary-0.3",
  probability: 0.91, threshold: 0.5, positive: true, uncertain: false, severity_band: 5, risk_level: "high",
  recommendation: "Signs of diabetic retinopathy detected. Refer to an eye specialist.", refer_suggested: true, ...overrides,
});

const missing: ConditionResult = {
  condition: "glaucoma", display_name: "Glaucoma", model_available: false, model_version: null, probability: null,
  threshold: null, positive: null, uncertain: null, severity_band: null, risk_level: null,
  recommendation: "Model not available yet. No result is given for this condition.", refer_suggested: false,
};

describe("SeverityMeter", () => {
  it.each([1, 2, 3, 4, 5])("labels band %i as an estimate", (band) => {
    render(<SeverityMeter band={band} />);
    expect(screen.getByRole("img", { name: new RegExp(`Estimated severity band ${band} of 5`) })).toBeInTheDocument();
    expect(screen.getByText(/not a clinical grade/)).toBeInTheDocument();
  });

  it("has a distinct unavailable state", () => {
    render(<SeverityMeter band={null} />);
    expect(screen.getByRole("img", { name: "Estimated severity band: unavailable" })).toBeInTheDocument();
  });
});

describe("ScreeningResultCard", () => {
  it("shows a positive result with its model version, score explanation and action", () => {
    render(<ScreeningResultCard result={dr()} />);
    expect(screen.getByText("Signs detected: refer")).toBeInTheDocument();
    expect(screen.getByText(/model mobilenetv2-dr-binary-0.3/)).toBeInTheDocument();
    expect(screen.getByText(/Model score 91%/)).toBeInTheDocument();
    expect(screen.getByText(/not a probability that the patient has the disease/)).toBeInTheDocument();
    expect(screen.getByText(/Refer to an eye specialist/)).toBeInTheDocument();
  });

  it("presents a borderline score as needing review, not as negative", () => {
    render(<ScreeningResultCard result={dr({ probability: 0.45, positive: false, uncertain: true, severity_band: 3, risk_level: "medium" })} />);
    expect(screen.getByText("Borderline: specialist review")).toBeInTheDocument();
    expect(screen.queryByText("No signs detected")).not.toBeInTheDocument();
  });

  it("never shows a score or band for a condition without a model", () => {
    render(<ScreeningResultCard result={missing} />);
    expect(screen.getByText("Model not available yet")).toBeInTheDocument();
    expect(screen.getByText(/Do not treat this as a normal result/)).toBeInTheDocument();
    expect(screen.queryByText(/Model score/)).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: /unavailable/ })).toBeInTheDocument();
  });

  it("shows a binary-only result without inventing a severity band", () => {
    render(<ScreeningResultCard result={dr({ condition: "cataract", display_name: "Cataract", severity_band: null,
      probability: 0.8, threshold: 0.4, positive: true, uncertain: false, risk_level: "high", recommendation: "Refer." })} />);
    expect(screen.getByText("Signs detected: refer")).toBeInTheDocument();
    expect(screen.getByText(/Binary result only/)).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /severity band/ })).not.toBeInTheDocument();
  });
});

describe("model reliability on the result card", () => {
  // Figures from models/glaucoma/model_card.json (patient-separated test split)
  const glaucomaModel: ModelInfo = {
    condition: "glaucoma", display_name: "Glaucoma", available: true, status_reason: "ok",
    version: "mobilenetv2-glaucoma-binary-odir5k-0.1", threshold: 0.3198, threshold_source: "validation", uncertainty_margin: 0.1,
    input: null, labels: null, architecture: null, training: null,
    metrics: { sensitivity: 0.7619, specificity: 0.7214, precision: 0.1032, f1: 0.1818, accuracy: 0.7231, auc: 0.8183, test_images: 1040 },
    metrics_status: "below the 85% sensitivity / 80% specificity targets", limitations: [],
  };
  const glaucoma = dr({ condition: "glaucoma", display_name: "Glaucoma", model_version: glaucomaModel.version,
    severity_band: null, threshold: 0.3198, probability: 0.39 });

  it("tells the reader how often a positive flag was a false alarm", () => {
    render(<ScreeningResultCard result={glaucoma} model={glaucomaModel} />);
    expect(screen.getByTestId("reliability-glaucoma")).toHaveTextContent("about 9 in 10 of its positive flags were false alarms");
    expect(screen.getByText(/below the 85% sensitivity/)).toBeInTheDocument();
  });

  it("hides the figures when the result came from a different model version", () => {
    render(<ScreeningResultCard result={{ ...glaucoma, model_version: "older-model" }} model={glaucomaModel} />);
    expect(screen.queryByTestId("reliability-glaucoma")).not.toBeInTheDocument();
  });
});

describe("notice on results made with earlier models", () => {
  const models: ModelInfo[] = ["dr", "glaucoma", "cataract"].map((condition) => ({
    condition, display_name: condition, available: true, status_reason: "ok",
    version: condition === "dr" ? "mobilenetv2-dr-binary-2.0" : `mobilenetv2-${condition}-binary-odir5k-0.1`,
    threshold: 0.4, threshold_source: "", uncertainty_margin: 0.1, input: null, labels: null, architecture: null,
    training: null, metrics: null, metrics_status: "", limitations: [],
  }));
  const screening = (results: ConditionResult[]): Screening => ({
    id: "s1", client_uuid: "c1", patient_id: "p1", patient_code: "PHC-7A8MRX", eye: "left", status: "completed",
    captured_at: "2026-10-27T12:47:00Z", patient_consent: true, created_at: "2026-10-27T12:47:00Z",
    updated_at: "2026-10-27T12:47:00Z", created_by_name: "Mike",
    quality: { usable: true, warnings: [], sharpness: 1, brightness: 1, contrast: 1 }, results,
    referral_advice: "none", referral_reason: null, referral_question: null, referred_at: null, review_priority: null, review_due_at: null, review_overdue: false,
    referral_conditions: [], assigned_to_name: null, assigned_to_id: null, queued_automatically: false,
    suggested_priority: "routine", new_decision: false,
    reviews: [], disclaimer: "",
  });
  const old = screening([dr(), { ...missing }, { ...missing, condition: "cataract", display_name: "Cataract" }]);

  it("names the earlier model, the current ones, and offers a new screening to the health worker", () => {
    render(<MemoryRouter><OutdatedModelNotice screening={old} models={models} canRescreen /></MemoryRouter>);
    const notice = screen.getByTestId("outdated-model-notice");
    expect(notice).toHaveTextContent("This result was made by an earlier model (Diabetic retinopathy mobilenetv2-dr-binary-0.3)");
    expect(notice).toHaveTextContent("No model was installed for Glaucoma and Cataract at the time");
    expect(notice).toHaveTextContent("Current models: Diabetic retinopathy mobilenetv2-dr-binary-2.0");
    expect(notice).toHaveTextContent("This result is kept as it was");
    expect(screen.getByRole("link", { name: "Screen this patient again" })).toHaveAttribute("href", "/screen?patient=p1");
  });

  it("tells the specialist to ask for a new screening instead of offering one", () => {
    render(<MemoryRouter><OutdatedModelNotice screening={old} models={models} canRescreen={false} /></MemoryRouter>);
    expect(screen.getByTestId("outdated-model-notice")).toHaveTextContent("Ask the health worker to screen again");
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("stays hidden when every result came from the installed models", () => {
    const current = screening(models.map((m) => dr({ condition: m.condition, model_version: m.version })));
    render(<MemoryRouter><OutdatedModelNotice screening={current} models={models} canRescreen /></MemoryRouter>);
    expect(screen.queryByTestId("outdated-model-notice")).not.toBeInTheDocument();
  });
});

describe("status label", () => {
  it.each([
    ["completed", "none", "No referral needed"],
    ["completed", "consider", "Uncertain, consider asking a specialist"],
    ["completed", "recommended", "Refer recommended"],
    ["referred", "recommended", "Awaiting specialist"],
    ["reviewed", "none", "Reviewed"],
    ["retake_requested", "consider", "Retake needed"],
  ] as const)("%s + %s shows %s", (status, referral_advice, label) => {
    expect(statusLabel({ status, referral_advice }).label).toBe(label);
  });

  it("never says 'Awaiting specialist' for a case that was not sent", () => {
    for (const advice of ["none", "consider", "recommended"] as const) {
      expect(statusLabel({ status: "completed", referral_advice: advice }).label).not.toBe("Awaiting specialist");
    }
  });
});

