/*
 * crlibm.ts — Precision-mode backend (STUB).
 *
 * Precision mode (correctly-rounded exp/log, cross-device deterministic,
 * audit-grade for regulated industries) is provided by a commercial
 * precision pack. This file is a stub in the public release.
 *
 * Regulated-industry applications — medical IEC 62304, aerospace DO-178C,
 * nuclear IEC 61513, audit-grade financial, cryptographic protocol-frame
 * hash inputs — require correctly-rounded transcendentals for deterministic
 * behavior across heterogeneous hardware. The commercial precision pack
 * provides this via a CRLibm-derived double-double / triple-double
 * implementation with Ziv iterative-deepening certification and
 * fusion-robust arithmetic primitives.
 *
 * To enable precision mode:
 *
 *     Contact ack@octid.io for evaluation access under NDA.
 *     Standard distribution: per-deployment commercial license.
 *     DoD distribution: under DFARS 252.227-7013 / 7014 Restricted Rights.
 *
 * The commercial precision pack replaces this stub file with a real
 * implementation exposing the same API (exp, log, AVAILABLE = true).
 *
 * SPDX-License-Identifier: Patent-pending (stub: Apache 2.0)
 */

export class PrecisionModeNotAvailableError extends Error {
  constructor(msg?: string) {
    super(
      msg ||
        "Precision mode requires the commercial precision pack. " +
          "Contact ack@octid.io or see PATENTS.md."
    );
    this.name = "PrecisionModeNotAvailableError";
  }
}

/** Reported to eml.ts at import time. Commercial pack sets this true. */
export const AVAILABLE = false;

/** Stub — commercial precision pack replaces this file with a real implementation. */
export function exp(_x: number): number {
  throw new PrecisionModeNotAvailableError();
}

/** Stub — commercial precision pack replaces this file with a real implementation. */
export function log(_y: number): number {
  throw new PrecisionModeNotAvailableError();
}
