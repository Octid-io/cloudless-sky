/**
 * OSMP Composition Validator
 * Validates composed SAL instructions against the seven deterministic rules
 * (Section 12.5 of OSMP-SPEC-v1).
 * Patent pending — inventor Clay Holberg
 * License: Apache 2.0
 */
import { AdaptiveSharedDictionary } from "./asd.js";
import { DependencyRule } from "./regulatory_dependency.js";
export interface CompositionIssue {
    rule: string;
    severity: "error" | "warning";
    message: string;
    frame?: string;
}
export interface CompositionResult {
    valid: boolean;
    issues: CompositionIssue[];
    sal: string;
    nl: string;
    errors: CompositionIssue[];
    warnings: CompositionIssue[];
}
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
export declare function validateComposition(sal: string, nl?: string, asd?: AdaptiveSharedDictionary, rSafetyExempt?: boolean, dependencyRules?: DependencyRule[]): CompositionResult;
