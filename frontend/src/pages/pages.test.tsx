import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppShell, ProtectedRoute, recordConsent } from "@/components/AppShell";
import { ApiError, NetworkError } from "@/lib/api/http";
import type { User } from "@/lib/api/types";
import { renderWithProviders } from "@/test/render";

import { ForgotPasswordPage, LoginPage, ResetPasswordPage, SignupPage, signupSchema } from "./auth";
import { AboutPage } from "./AboutPage";
import { HomePage } from "./HomePage";
import { patientSchema } from "./patients";
import { reviewSchema } from "./specialist";

const nurse: User = { id: "u1", email: "n@example.org", full_name: "Amina Nurse", role: "health_worker", is_active: true,
  status: "approved", status_reason: null, requested_role: null, facility: "Demo Health Centre A", specialties: [],
  created_at: "2026-10-01T00:00:00Z" };

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

describe("AppShell", () => {
  // Regression: opening "/" while signed out showed a blank page because the shell rendered nothing.
  it("sends a signed-out visitor of the home page to login", async () => {
    renderWithProviders(
      <Routes>
        <Route path="/login" element={<p>login page</p>} />
        <Route element={<AppShell />}>
          <Route element={<ProtectedRoute roles={["health_worker"]} />}>
            <Route index element={<p>health worker home</p>} />
          </Route>
        </Route>
      </Routes>,
      { route: "/" },
    );
    expect(await screen.findByText("login page")).toBeInTheDocument();
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
  const valid = { full_name: "Amina", email: "a@example.org", password: "long-enough-1",
    requested_role: "specialist" };

  it("explains that a sign-up is a request an administrator approves", () => {
    renderWithProviders(<SignupPage />, { route: "/signup" });
    expect(screen.getByText(/the role you ask for grants nothing until then/)).toBeInTheDocument();
  });

  it("asks only for name, email, password and requested role", () => {
    renderWithProviders(<SignupPage />, { route: "/signup" });
    for (const label of ["Full name", "Email", "Password", "I am requesting access as"]) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
    expect(screen.queryByLabelText(/facility/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/registration/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Administrator" })).not.toBeInTheDocument();
  });

  it("rejects weak passwords and the admin role", () => {
    expect(signupSchema.safeParse({ ...valid, password: "onlyletters" }).success).toBe(false);
    expect(signupSchema.safeParse({ ...valid, requested_role: "admin" }).success).toBe(false);
    expect(signupSchema.safeParse(valid).success).toBe(true);
  });

  it("says the request is waiting for approval instead of signing in", async () => {
    const { api } = renderWithProviders(<SignupPage />, { route: "/signup",
      api: { auth: { register: vi.fn().mockResolvedValue({}) } } });
    await userEvent.type(screen.getByLabelText("Full name"), valid.full_name);
    await userEvent.type(screen.getByLabelText("Email"), valid.email);
    await userEvent.type(screen.getByLabelText("Password"), valid.password);
    await userEvent.selectOptions(screen.getByLabelText("I am requesting access as"), "specialist");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Waiting for administrator approval")).toBeInTheDocument();
    expect(api.auth.register).toHaveBeenCalledWith(valid);
    expect(api.auth.login).not.toHaveBeenCalled();
  });
});

describe("password reset", () => {
  it("shows the same confirmation whatever email is entered", async () => {
    const { api } = renderWithProviders(<ForgotPasswordPage />, { route: "/forgot-password",
      api: { auth: { forgotPassword: vi.fn().mockResolvedValue({ message: "ok" }) } } });
    await userEvent.type(screen.getByLabelText("Email"), "someone@example.org");
    await userEvent.click(screen.getByRole("button", { name: "Send reset link" }));
    expect(await screen.findByText("Check your email")).toBeInTheDocument();
    expect(api.auth.forgotPassword).toHaveBeenCalledWith("someone@example.org");
  });

  it("requires the new password twice before calling the API", async () => {
    const { api } = renderWithProviders(<ResetPasswordPage />, { route: "/reset-password?token=abc",
      api: { auth: { resetPassword: vi.fn().mockResolvedValue(undefined) } } });
    await userEvent.type(screen.getByLabelText("New password"), "brand-new-pass-1");
    await userEvent.type(screen.getByLabelText("Repeat new password"), "different-pass-2");
    await userEvent.click(screen.getByRole("button", { name: "Save new password" }));
    expect(await screen.findByText("The passwords do not match.")).toBeInTheDocument();
    expect(api.auth.resetPassword).not.toHaveBeenCalled();
  });

  it("explains an incomplete link instead of showing the form", () => {
    renderWithProviders(<ResetPasswordPage />, { route: "/reset-password" });
    expect(screen.getByRole("alert")).toHaveTextContent("This link is incomplete");
  });
});

describe("form schemas", () => {
  it("validates patient details; the code itself is generated by the app", () => {
    expect(patientSchema.safeParse({ year_of_birth: "", sex: "unknown", has_diabetes: "unknown" }).success).toBe(true);
    expect(patientSchema.safeParse({ year_of_birth: "1970", sex: "female", has_diabetes: "yes" }).success).toBe(true);
    expect(patientSchema.safeParse({ year_of_birth: String(new Date().getFullYear() + 1), sex: "female", has_diabetes: "yes" }).success).toBe(false);
  });

  it("requires a corrected result and a reason for an override", () => {
    const override = { action: "override", condition: "glaucoma" };
    expect(reviewSchema.safeParse({ ...override, override_positive: "", note: "" }).success).toBe(false);
    expect(reviewSchema.safeParse({ ...override, override_positive: "false", note: "" }).success).toBe(false);
    expect(reviewSchema.safeParse({ ...override, condition: "", override_positive: "false", note: "Artefact" }).success).toBe(false);
    expect(reviewSchema.safeParse({ ...override, override_positive: "false", note: "Artefact" }).success).toBe(true);
    expect(reviewSchema.safeParse({ action: "approve", condition: "", override_positive: "", note: "" }).success).toBe(true);
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

  it("labels validation metrics as not an independent hold-out", async () => {
    renderWithProviders(<AboutPage />, { signedIn: true, api: {
      auth: { me: vi.fn().mockResolvedValue(nurse) },
      models: { list: vi.fn().mockResolvedValue([{ condition: "dr", display_name: "Diabetic retinopathy", available: true,
        status_reason: "ok", version: "v1", threshold: 0.5, threshold_source: "default", uncertainty_margin: 0.1, input: null,
        labels: null, architecture: null, training: null, limitations: [],
        metrics_status: "validation results from the training notebook, not an independent hold-out",
        metrics: { sensitivity: 0.542, specificity: 0.97, precision: 0.92, f1: 0.682, accuracy: 0.79, auc: null, test_images: 47234,
          evaluation_set: "validation fold from the training notebook (not an independent hold-out)" } }]) } } });
    expect(await screen.findByText(/validation fold from the training notebook \(not an independent hold-out\), 47,234 images/)).toBeInTheDocument();
    expect(screen.getByText("54.2%")).toBeInTheDocument();
    expect(screen.getByText("not computed")).toBeInTheDocument();
    expect(screen.queryByText(/test set/)).not.toBeInTheDocument();
  });
});
