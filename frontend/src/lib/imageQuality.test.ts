import { describe, expect, it } from "vitest";

import { assessGray, hintsFor } from "./imageQuality";

describe("assessGray", () => {
  it("gives zero sharpness for a flat image", () => {
    const flat = new Float32Array(16 * 16).fill(100);
    expect(assessGray(flat, 16, 16)).toEqual({ brightness: 100, sharpness: 0 });
  });

  it("scores a checkerboard as much sharper than a smooth gradient", () => {
    const size = 32;
    const checker = new Float32Array(size * size).map((_, i) => ((i % size) + Math.floor(i / size)) % 2 ? 255 : 0);
    const gradient = new Float32Array(size * size).map((_, i) => (i % size) * 8);
    expect(assessGray(checker, size, size).sharpness).toBeGreaterThan(assessGray(gradient, size, size).sharpness * 100);
  });
});

describe("hintsFor", () => {
  it("is silent for a good photo", () => {
    expect(hintsFor(1024, 1024, 120, 300)).toEqual([]);
  });

  it("flags small, dark, bright and blurry photos", () => {
    expect(hintsFor(100, 100, 120, 300)[0]).toMatch(/small/);
    expect(hintsFor(1024, 1024, 5, 300)[0]).toMatch(/dark/);
    expect(hintsFor(1024, 1024, 250, 300)[0]).toMatch(/bright/);
    expect(hintsFor(1024, 1024, 120, 2)[0]).toMatch(/blurry/);
  });
});
