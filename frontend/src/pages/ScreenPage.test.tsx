import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/http";
import { renderWithProviders } from "@/test/render";

import { ScreenPage } from "./ScreenPage";

const patient = { id: "p1", code: "PHC-7A8MRX" };
const nurse = { id: "u1", email: "n@example.org", full_name: "Amina Nurse", role: "health_worker", is_active: true,
  status: "approved", status_reason: null, requested_role: null, facility: null, created_at: "2026-10-01T00:00:00Z" };
const photo = () => new File([new Uint8Array([1, 2, 3])], "eye.jpg", { type: "image/jpeg" });

async function reachPhotoStep(create = vi.fn()) {
  const view = renderWithProviders(<ScreenPage />, {
    route: "/screen?patient=p1", signedIn: true,
    api: { auth: { me: vi.fn().mockResolvedValue(nurse) }, patients: { get: vi.fn().mockResolvedValue(patient) },
      screenings: { create } },
  });
  await userEvent.click(await screen.findByRole("button", { name: `Continue with ${patient.code}` }));
  await userEvent.click(screen.getByRole("button", { name: "Left eye" }));
  return view;
}

const choosePhoto = () => userEvent.upload(screen.getByLabelText("Choose a fundus photo from the gallery"), photo());

describe("capture flow", () => {
  beforeAll(() => {
    // jsdom has no object URLs; the preview only needs a string.
    URL.createObjectURL = vi.fn(() => "blob:preview");
    URL.revokeObjectURL = vi.fn();
  });

  it("previews the photo with Cancel and Analyse; Cancel throws it away without uploading", async () => {
    const create = vi.fn();
    await reachPhotoStep(create);
    await choosePhoto();
    expect(screen.getByAltText("Captured fundus photo preview")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyse" })).toBeDisabled(); // consent first
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByAltText("Captured fundus photo preview")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "From gallery" })).toBeVisible();
    expect(create).not.toHaveBeenCalled();
  });

  it("a photo the server refuses shows no result and offers Retake / Upload another", async () => {
    const create = vi.fn().mockRejectedValue(new ApiError(422, "unusable_image",
      "This photo cannot be screened: This does not look like a retinal fundus photograph."));
    await reachPhotoStep(create);
    await choosePhoto();
    await userEvent.click(screen.getByLabelText(/The patient agreed/));
    await userEvent.click(screen.getByRole("button", { name: "Analyse" }));
    expect(await screen.findByTestId("photo-rejected")).toHaveTextContent("does not look like a retinal fundus photograph");
    expect(screen.getByTestId("photo-rejected")).toHaveTextContent("Nothing was saved");
    expect(screen.getByRole("button", { name: "Retake" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Upload another" })).toBeVisible();
    expect(screen.queryByAltText("Captured fundus photo preview")).not.toBeInTheDocument();

    await choosePhoto(); // choosing another photo clears the message
    expect(screen.queryByTestId("photo-rejected")).not.toBeInTheDocument();
    expect(create).toHaveBeenCalledTimes(1);
  });
});
