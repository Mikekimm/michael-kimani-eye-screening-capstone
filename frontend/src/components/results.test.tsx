import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ConditionResult } from "@/lib/api/types";

import { ScreeningResultCard } from "./ScreeningResultCard";
import { SeverityMeter } from "./SeverityMeter";

const dr = (overrides: Partial<ConditionResult> = {}): ConditionResult => ({
  condition: "dr", display_name: "Diabetic retinopathy", model_available: true, model_version: "mobilenetv2-dr-binary-0.3",
  probability: 0.91, threshold: 0.5, positive: true, uncertain: false, severity_band: 5, risk_level: "high",
  recommendation: "Signs of diabetic retinopathy detected. Refer to an eye specialist.", auto_refer: true, ...overrides,
});

const missing: ConditionResult = {
  condition: "glaucoma", display_name: "Glaucoma", model_available: false, model_version: null, probability: null,
  threshold: null, positive: null, uncertain: null, severity_band: null, risk_level: null,
  recommendation: "Model not available yet. No result is given for this condition.", auto_refer: false,
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
