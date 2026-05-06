/**
 * ADP REPLACE-criticality wiring (spec §6 / §7).
 *
 * REPLACE operations on the ASD must be transmitted with FLAG_CRITICAL
 * because a lost REPLACE leaves the receiving node with a stale dictionary
 * entry — a semantic correctness violation. These tests lock in the
 * send-side helper (`deltaRequiredOverflowFlags`) and the receive-side
 * validator (`validateReceivedDelta` + `DeltaValidationError`).
 *
 * License: Apache 2.0
 */
import { describe, it, expect } from "vitest";
import {
  ADPDelta,
  deltaRequiredOverflowFlags,
  validateReceivedDelta,
  DeltaValidationError,
} from "../src/adp.js";
import { FLAG_CRITICAL } from "../src/types.js";

const ADDITIVE_DELTA: ADPDelta = {
  fromVersion: "15.0",
  toVersion: "15.1",
  operations: [
    { namespace: "H", mode: "+", opcode: "LACTATE", definition: "lactate" },
  ],
};

const DEPRECATE_DELTA: ADPDelta = {
  fromVersion: "15.0",
  toVersion: "15.1",
  operations: [{ namespace: "M", mode: "†", opcode: "OLDOP" }],
};

const REPLACE_DELTA: ADPDelta = {
  fromVersion: "15.0",
  toVersion: "15.1",
  operations: [
    { namespace: "H", mode: "←", opcode: "HR", definition: "heart_rate_v2" },
  ],
};

const MIXED_DELTA: ADPDelta = {
  fromVersion: "15.0",
  toVersion: "15.1",
  operations: [
    { namespace: "H", mode: "+", opcode: "LACTATE" },
    { namespace: "H", mode: "←", opcode: "HR", definition: "v2" },
  ],
};

describe("deltaRequiredOverflowFlags", () => {
  it("returns 0 for additive-only delta", () => {
    expect(deltaRequiredOverflowFlags(ADDITIVE_DELTA)).toBe(0);
  });

  it("returns 0 for deprecate-only delta", () => {
    expect(deltaRequiredOverflowFlags(DEPRECATE_DELTA)).toBe(0);
  });

  it("returns FLAG_CRITICAL for REPLACE delta", () => {
    expect(deltaRequiredOverflowFlags(REPLACE_DELTA)).toBe(FLAG_CRITICAL);
  });

  it("returns FLAG_CRITICAL when any operation is REPLACE", () => {
    expect(deltaRequiredOverflowFlags(MIXED_DELTA)).toBe(FLAG_CRITICAL);
  });
});

describe("validateReceivedDelta", () => {
  it("rejects REPLACE delta arriving without FLAG_CRITICAL", () => {
    const sal = "A:ASD:DELTA[15.0→15.1:H←[HR]]";
    expect(() => validateReceivedDelta(sal, 0)).toThrow(DeltaValidationError);
  });

  it("accepts REPLACE delta arriving with FLAG_CRITICAL set", () => {
    const sal = "A:ASD:DELTA[15.0→15.1:H←[HR]]";
    expect(() => validateReceivedDelta(sal, FLAG_CRITICAL)).not.toThrow();
  });

  it("accepts additive delta arriving without FLAG_CRITICAL", () => {
    const sal = "A:ASD:DELTA[15.0→15.1:H+[LACTATE]]";
    expect(() => validateReceivedDelta(sal, 0)).not.toThrow();
  });

  it("passes through non-DELTA SAL", () => {
    expect(() => validateReceivedDelta("H:HR@NODE1", 0)).not.toThrow();
    expect(() => validateReceivedDelta("A:ASD[15.1]", 0)).not.toThrow();
    expect(() => validateReceivedDelta("A:ASD?", 0)).not.toThrow();
  });
});
