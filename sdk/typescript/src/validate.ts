/**
 * OSMP Composition Validator
 * Validates composed SAL instructions against the seven deterministic rules
 * (Section 12.5 of OSMP-SPEC-v1).
 * Patent: OSMP-001-UTIL (pending) — inventor Clay Holberg
 * License: Apache 2.0
 */
import { AdaptiveSharedDictionary } from "./asd.js";
import { validateRegulatoryDependencies, DependencyRule } from "./regulatory_dependency.js";

export interface CompositionIssue {
  rule: string;        // e.g. "HALLUCINATED_OPCODE", "NAMESPACE_AS_TARGET"
  severity: "error" | "warning";
  message: string;
  frame?: string;      // the offending frame or substring
}

export interface CompositionResult {
  valid: boolean;
  issues: CompositionIssue[];
  sal: string;
  nl: string;
  errors: CompositionIssue[];
  warnings: CompositionIssue[];
}

const FRAME_SPLIT_RE = /([→∧∨↔∥;])/;
const NS_TARGET_RE = /@([A-Z]{1,2}):([A-Z][A-Z0-9]+)/g;
const FRAME_NS_OP_RE = /^([A-Z]{1,2}):([A-Z§][A-Z0-9§]*)/;

/**
 * Validate a composed SAL instruction against composition rules.
 *
 * Rules enforced:
 *   1. Hallucination check — every opcode must exist in the ASD
 *   2. Namespace-as-target — @ must not be followed by NS:OPCODE
 *   3. R namespace consequence class — mandatory except R:ESTOP
 *   4. I:§ precondition — ⚠ and ⊘ require I:§ in the chain
 *   5. Byte check — SAL bytes must not exceed NL bytes (exception: R safety chains)
 *   6. Slash rejection — / is not a SAL operator
 *   7. Mixed-mode check — no natural language text embedded in SAL frames
 *   8. Regulatory dependency — REQUIRES rules from MDR corpora
 */
export function validateComposition(
  sal: string,
  nl: string = "",
  asd?: AdaptiveSharedDictionary,
  rSafetyExempt: boolean = true,
  dependencyRules?: DependencyRule[],
): CompositionResult {
  if (!asd) {
    asd = new AdaptiveSharedDictionary();
  }

  const issues: CompositionIssue[] = [];

  // ── Rule 6: Slash rejection ──────────────────────────────────────────
  if (sal.includes("/")) {
    issues.push({
      rule: "SLASH_OPERATOR",
      severity: "error",
      message: "/ is not a SAL operator. Use → for THEN, ∧ for AND, ∨ for OR.",
      frame: sal,
    });
  }

  // ── Rule 2: Namespace-as-target ──────────────────────────────────────
  let nsTargetMatch: RegExpExecArray | null;
  const nsTargetRe = new RegExp(NS_TARGET_RE.source, "g");
  while ((nsTargetMatch = nsTargetRe.exec(sal)) !== null) {
    const [full, ns, op] = nsTargetMatch;
    issues.push({
      rule: "NAMESPACE_AS_TARGET",
      severity: "error",
      message: `@ target must be a node_id or *, not a namespace:opcode. Found @${ns}:${op}`,
      frame: `@${ns}:${op}`,
    });
  }

  // ── Split into frames and validate each ──────────────────────────────
  const parts = sal.split(FRAME_SPLIT_RE);
  const operators = new Set(["→", "∧", "∨", "↔", "∥", ";"]);
  const frames = parts
    .map(p => p.trim())
    .filter(p => p && !operators.has(p));

  let hasRNamespace = false;
  let hasRHazardousOrIrreversible = false;
  let hasISection = false;

  for (const frame of frames) {
    const m = FRAME_NS_OP_RE.exec(frame);
    if (!m) {
      // Frame doesn't start with NS:OP pattern
      if (frame.length > 20 && frame.includes(" ")) {
        issues.push({
          rule: "MIXED_MODE",
          severity: "warning",
          message: `Frame appears to contain embedded natural language: '${frame.slice(0, 40)}...'`,
          frame,
        });
      }
      continue;
    }

    const ns = m[1];
    const op = m[2];

    // ── Rule 1: Hallucination check ──────────────────────────────────
    if (!(ns === "I" && op === "§")) {
      const definition = asd.lookup(ns, op);
      if (definition === null || definition === undefined) {
        issues.push({
          rule: "HALLUCINATED_OPCODE",
          severity: "error",
          message: `${ns}:${op} does not exist in the Adaptive Shared Dictionary.`,
          frame,
        });
      }
    }

    // ── Rules 3 & 4: R namespace consequence class and I:§ ───────────
    if (ns === "R") {
      hasRNamespace = true;
      if (op !== "ESTOP") {
        const hasCc = ["⚠", "↺", "⊘"].some(cc => frame.includes(cc));
        if (!hasCc) {
          issues.push({
            rule: "CONSEQUENCE_CLASS_OMISSION",
            severity: "error",
            message: `R:${op} requires a consequence class designator (⚠/↺/⊘). R:ESTOP is the sole exception.`,
            frame,
          });
        }
        if (frame.includes("⚠") || frame.includes("⊘")) {
          hasRHazardousOrIrreversible = true;
        }
      }
    }

    if (ns === "I" && op === "§") {
      hasISection = true;
    }
  }

  // ── Rule 4 (chain-level): I:§ must precede ⚠/⊘ ──────────────────────
  if (hasRHazardousOrIrreversible && !hasISection) {
    issues.push({
      rule: "AUTHORIZATION_OMISSION",
      severity: "error",
      message: "R namespace instructions with ⚠ (HAZARDOUS) or ⊘ (IRREVERSIBLE) require I:§ as a structural precondition in the instruction chain.",
    });
  }

  // ── Rule 5: Byte check ───────────────────────────────────────────────
  if (nl) {
    const salBytes = new TextEncoder().encode(sal).length;
    const nlBytes = new TextEncoder().encode(nl).length;
    if (salBytes >= nlBytes) {
      if (rSafetyExempt && hasRNamespace) {
        issues.push({
          rule: "BYTE_CHECK_EXEMPT",
          severity: "warning",
          message: `SAL (${salBytes}B) >= NL (${nlBytes}B). Exempt: safety-complete R namespace chain.`,
        });
      } else {
        issues.push({
          rule: "BYTE_INFLATION",
          severity: "error",
          message: `SAL (${salBytes}B) >= NL (${nlBytes}B). Use NL_PASSTHROUGH. BAEL compression floor guarantee violated.`,
        });
      }
    }
  }

  // ── Rule 8: Regulatory dependency grammar ─────────────────────────────
  if (dependencyRules && dependencyRules.length > 0) {
    const depIssues = validateRegulatoryDependencies(sal, dependencyRules);
    issues.push(...depIssues);
  }

  const errors = issues.filter(i => i.severity === "error");
  const warnings = issues.filter(i => i.severity === "warning");

  return {
    valid: errors.length === 0,
    issues,
    sal,
    nl,
    errors,
    warnings,
  };
}
