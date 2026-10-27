import { describe, expect, it } from "vitest";

import { ALPHABET, PREFIX, checkCharacter, generatePatientCode, isValidPatientCode } from "./patientCode";

describe("patient codes", () => {
  it("match the server implementation on pinned values", () => {
    // Same values as backend/tests/ml/test_patient_codes.py.
    expect([checkCharacter("7K3Q9"), checkCharacter("22222"), checkCharacter("ZZZZZ")]).toEqual(["W", "2", "7"]);
  });

  it("generates valid, varied codes", () => {
    const codes = Array.from({ length: 300 }, () => generatePatientCode());
    expect(codes.every(isValidPatientCode)).toBe(true);
    expect(new Set(codes).size).toBeGreaterThan(290);
  });

  it("catches every single mistyped character", () => {
    const code = generatePatientCode();
    for (let i = PREFIX.length; i < code.length; i += 1) {
      for (const c of ALPHABET) {
        if (c !== code[i]) expect(isValidPatientCode(code.slice(0, i) + c + code.slice(i + 1))).toBe(false);
      }
    }
  });

  it("accepts lower case and spaces, rejects names and old-style codes", () => {
    const code = generatePatientCode();
    expect(isValidPatientCode(` ${code.toLowerCase()} `)).toBe(true);
    for (const bad of ["Jane Doe", "PHC-0042", "", "PHC-ABCDE0"]) expect(isValidPatientCode(bad)).toBe(false);
  });
});
