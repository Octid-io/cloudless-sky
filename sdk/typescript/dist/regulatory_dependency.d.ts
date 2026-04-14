/**
 * OSMP Regulatory Dependency Grammar — Rule 8 for validateComposition
 * Validates instruction chains against REQUIRES rules loaded from MDR corpora.
 * Dependency rules are SAL expressions using the same glyph operators as
 * the instructions they govern.
 *
 * License: Apache 2.0
 */
import type { CompositionIssue } from "./validate.js";
export interface DependencyRule {
    entry: string;
    namespace: string;
    opcode: string;
    slotValue: string;
    requiresRaw: string;
    alternatives: string[][];
}
export declare function parseRequiresExpression(requires: string): string[][];
export declare function loadMDRDependencyRules(mdrPath: string): DependencyRule[];
export declare function extractChainFrames(sal: string): {
    frames: Set<string>;
    opcodes: Set<string>;
};
export declare function validateRegulatoryDependencies(sal: string, rules: DependencyRule[]): CompositionIssue[];
