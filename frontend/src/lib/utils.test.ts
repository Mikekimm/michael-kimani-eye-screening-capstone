import { describe, expect, it } from "vitest";

import { waitingFor } from "./utils";

describe("waitingFor", () => {
  const since = "2026-10-27T00:00:00Z"; // a case referred at midnight
  const at = (hours: number) => new Date(since).getTime() + hours * 3_600_000;

  it.each([[0.5, "30 min"], [5, "5 h"], [47, "47 h"], [72, "3 days"]])("after %s hours shows %s", (hours, text) => {
    expect(waitingFor(since, at(hours))).toBe(text);
  });
});
