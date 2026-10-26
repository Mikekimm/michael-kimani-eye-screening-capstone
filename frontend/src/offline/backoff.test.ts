import { describe, expect, it } from "vitest";

import { nextRetryDelay } from "./backoff";

const opts = (r: number) => ({ baseMs: 1000, maxMs: 60_000, random: () => r });

describe("nextRetryDelay", () => {
  it("grows exponentially before the cap", () => {
    // random -> 0.999... gives (almost) the ceiling: 1s, 2s, 4s, 8s
    expect([1, 2, 3, 4].map((a) => nextRetryDelay(a, opts(0.9999)))).toEqual([999, 1999, 3999, 7999]);
  });

  it("never exceeds the cap however many attempts were made", () => {
    expect(nextRetryDelay(50, opts(0.9999))).toBeLessThan(60_000);
    expect(nextRetryDelay(1_000, opts(0.9999))).toBeLessThan(60_000);
  });

  it("applies full jitter between 0 and the ceiling", () => {
    expect(nextRetryDelay(3, opts(0))).toBe(0);
    expect(nextRetryDelay(3, opts(0.5))).toBe(2000);
  });

  it("spreads many devices apart with real randomness", () => {
    const delays = new Set(Array.from({ length: 50 }, () => nextRetryDelay(5, { baseMs: 1000, maxMs: 60_000 })));
    expect(delays.size).toBeGreaterThan(40);
  });

  it("rejects invalid attempt numbers", () => {
    expect(() => nextRetryDelay(0)).toThrow(RangeError);
    expect(() => nextRetryDelay(1.5)).toThrow(RangeError);
  });
});
