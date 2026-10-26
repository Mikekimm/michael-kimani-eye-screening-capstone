import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ProtectedRoute, recordConsent } from "@/components/AppShell";
import { ApiError, NetworkError } from "@/lib/api/http";
import type { User } from "@/lib/api/types";
import { renderWithProviders } from "@/test/render";

import { LoginPage, SignupPage, signupSchema } from "./auth";
import { AboutPage } from "./AboutPage";
import { HomePage } from "./HomePage";
import { patientSchema } from "./patients";
import { reviewSchema } from "./specialist";

const nurse: User = { id: "u1", email: "n@example.org", full_name: "Amina Nurse", role: "health_worker", is_active: true, created_at: "2026-10-01T00:00:00Z" };

function guarded(role: "health_worker" | "admin") {
  return (
    <Routes>
      <Route path="/login" element={<p>login page</p>} />
      <Route path="/consent" element={<p>consent page</p>} />
      <Route path="/" element={<p>health worker home</p>} />
      <Route element={<ProtectedRoute roles={[role]} />}>
        <Route path="/secret" element={<p>secret page</p>} />
      </Route>
    </Routes>
  );
}

describe("ProtectedRoute", () => {
  it("sends signed-out users to login", async () => {
    renderWithProviders(guarded("health_worker"), { route: "/secret" });
    expect(await screen.findByText("login page")).toBeInTheDocument();
  });

  it("asks for consent before the first use", async () => {
    renderWithProviders(guarded("health_worker"), { route: "/secret", signedIn: true, api: { auth: { me: vi.fn().mockResolvedValue(nurse) } } });
    expect(await screen.findByText("consent page")).toBeInTheDocument();
  });

  it("redirects a user whose role is not allowed", async () => {
    recordConsent();
    renderWithProviders(guarded("admin"), { route: "/secret", signedIn: true, api: { auth: { me: vi.fn().mockResolvedValue(nurse) } } });
    expect(await screen.findByText("health worker home")).toBeInTheDocument();
  });

  it("lets the right role in", async () => {
    recordConsent();
    renderWithProviders(guarded("health_worker"), { route: "/secret", signedIn: true, api: { auth: { me: vi.fn().mockResolvedValue(nurse) } } });
    expect(await screen.findByText("secret page")).toBeInTheDocument();
  });
});

describe("LoginPage", () => {
  it("validates before calling the API", async () => {
    const { api } = renderWithProviders(<LoginPage />, { route: "/login" });
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(api.auth.login).not.toHaveBeenCalled();
  });

  it("shows the server error for wrong credentials", async () => {
    renderWithProviders(<LoginPage />, { route: "/login",
      api: { auth: { login: vi.fn().mockRejectedValue(new ApiError(401, "not_authenticated", "Incorrect email or password.")) } } });
    await userEvent.type(screen.getByLabelText("Email"), "n@example.org");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
  });

  it("toggles password visibility", async () => {
    renderWithProviders(<LoginPage />, { route: "/login" });
    const input = screen.getByLabelText("Password");
    expect(input).toHaveAttribute("type", "password");
    await userEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(input).toHaveAttribute("type", "text");
  });
});

describe("SignupPage", () => {
  it("explains that sign-up creates a health worker account", () => {
    renderWithProviders(<SignupPage />, { route: "/signup" });
    expect(screen.getByText(/New accounts are health worker accounts/)).toBeInTheDocument();
  });

  it("rejects short passwords", () => {
    const result = signupSchema.safeParse({ full_name: "Amina", email: "a@example.org", password: "short" });
    expect(result.success).toBe(false);
  });
});

describe("form schemas", () => {
  it("rejects patient codes that look like names", () => {
    expect(patientSchema.safeParse({ code: "Jane Doe", year_of_birth: "", sex: "unknown", has_diabetes: "unknown" }).success).toBe(false);
    expect(patientSchema.safeParse({ code: "PHC-0042", year_of_birth: "1970", sex: "female", has_diabetes: "yes" }).success).toBe(true);
  });

  it("requires a corrected result and a reason for an override", () => {
    expect(reviewSchema.safeParse({ action: "override", override_positive: "", note: "" }).success).toBe(false);
    expect(reviewSchema.safeParse({ action: "override", override_positive: "false", note: "" }).success).toBe(false);
    expect(reviewSchema.safeParse({ action: "override", override_positive: "false", note: "Artefact" }).success).toBe(true);
    expect(reviewSchema.safeParse({ action: "approve", override_positive: "", note: "" }).success).toBe(true);
  });
});

describe("loading, empty and error states", () => {
  it("shows an empty state when there are no screenings", async () => {
    recordConsent();
    renderWithProviders(<HomePage />, { signedIn: true, api: { auth: { me: vi.fn().mockResolvedValue(nurse) } } });
    expect(await screen.findByText("No screenings yet")).toBeInTheDocument();
  });

  it("shows a plain-language offline error", async () => {
    renderWithProviders(<HomePage />, { signedIn: true, api: {
      auth: { me: vi.fn().mockResolvedValue(nurse) }, screenings: { list: vi.fn().mockRejectedValue(new NetworkError()) } } });
    expect(await screen.findByText(/You appear to be offline/)).toBeInTheDocument();
  });

  it("shows unmeasured metrics honestly on the About screen", async () => {
    renderWithProviders(<AboutPage />, { signedIn: true, api: {
      auth: { me: vi.fn().mockResolvedValue(nurse) },
      models: { list: vi.fn().mockResolvedValue([
        { condition: "dr", display_name: "Diabetic retinopathy", available: true, status_reason: "ok", version: "v1", threshold: 0.5,
          threshold_source: "default", uncertainty_margin: 0.1, input: null, labels: null, architecture: "MobileNetV2", training: null,
          metrics: null, metrics_status: "not yet measured", limitations: ["Not clinically validated."] },
        { condition: "glaucoma", display_name: "Glaucoma", available: false, status_reason: "Model not available yet (no trained model has been added).",
          version: null, threshold: null, threshold_source: null, uncertainty_margin: null, input: null, labels: null, architecture: null,
          training: null, metrics: null, metrics_status: "not yet measured", limitations: [] },
      ]) } } });
    await waitFor(() => expect(screen.getByText(/not yet measured\. No accuracy figures/)).toBeInTheDocument());
    expect(screen.getByText("Model not available yet")).toBeInTheDocument();
    expect(screen.queryByText(/Sensitivity/)).not.toBeInTheDocument();
  });
});
