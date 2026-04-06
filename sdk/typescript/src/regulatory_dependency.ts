/**
 * OSMP Regulatory Dependency Grammar — Rule 8 for validateComposition
 * Validates instruction chains against REQUIRES rules loaded from MDR corpora.
 * Dependency rules are SAL expressions using the same glyph operators as
 * the instructions they govern.
 *
 * Patent ref: OSMP-001-UTIL Claim 40 (pending)
 * License: Apache 2.0
 */

import { readFileSync, existsSync } from "fs";
import type { CompositionIssue } from "./validate.js";

// ─── Data Structures ────────────────────────────────────────────────────────

export interface DependencyRule {
  entry: string;        // e.g. "F:BVLOS[P]"
  namespace: string;    // e.g. "F"
  opcode: string;       // e.g. "BVLOS"
  slotValue: string;    // e.g. "P" or "" if no slot
  requiresRaw: string;  // e.g. "REQUIRES:F:REMID[S]∨F:REMID[M]"
  alternatives: string[][];  // parsed: [[prereq_pattern, ...], ...]
}

// ─── Parser ─────────────────────────────────────────────────────────────────

const PREREQ_RE = /([A-Z]{1,2}):([A-Z][A-Z0-9]*)(?:\[([^\]]+)\])?/;

export function parseRequiresExpression(requires: string): string[][] {
  let expr = requires;
  if (expr.startsWith("REQUIRES:")) expr = expr.slice(9);
  // Split on ∨ (OR), then split each alternative on ∧ (AND) for conjunctive prerequisites.
  // Result: [[conjunct, ...], ...] — at least ONE group where ALL conjuncts satisfied.
  return expr.split("\u2228")  // ∨
    .map(p => p.trim())
    .filter(p => p.length > 0)
    .map(p => p.split("\u2227").map(c => c.trim()).filter(c => c.length > 0));
}

// ─── MDR Loader ─────────────────────────────────────────────────────────────

export function loadMDRDependencyRules(mdrPath: string): DependencyRule[] {
  if (!existsSync(mdrPath)) return [];

  const lines = readFileSync(mdrPath, "utf-8").split("\n");
  const rules: DependencyRule[] = [];
  let inSectionB = false;

  for (const line of lines) {
    const stripped = line.trim();
    if (stripped.includes("SECTION B")) { inSectionB = true; continue; }
    if (stripped.startsWith("SECTION ") && !stripped.includes("SECTION B")) {
      if (inSectionB) break;
    }
    if (!inSectionB) continue;
    if (!stripped || stripped.startsWith("Format:") ||
        stripped.startsWith("===") || stripped.startsWith("---") ||
        stripped.startsWith("Note:") || stripped.startsWith("Dependency rules")) {
      continue;
    }

    const parts = stripped.split(",");
    if (parts.length < 5 || !parts[0].includes(":")) continue;

    const depRule = (parts[4] || "").trim();
    if (!depRule.startsWith("REQUIRES:")) continue;

    const nsOp = parts[0].trim();
    const slotValue = parts[1].trim();
    const nsParts = nsOp.split(":");
    if (nsParts.length < 2) continue;

    const ns = nsParts[0];
    const opcode = nsParts[1];
    const entry = slotValue ? `${ns}:${opcode}[${slotValue}]` : `${ns}:${opcode}`;

    rules.push({
      entry,
      namespace: ns,
      opcode,
      slotValue,
      requiresRaw: depRule,
      alternatives: parseRequiresExpression(depRule),
    });
  }
  return rules;
}

// ─── Chain Frame Extraction ─────────────────────────────────────────────────

const CHAIN_FRAME_RE = /([A-Z]{1,2}):([A-Z][A-Z0-9]*)(?:\[([^\]]+)\]|:([A-Z0-9][A-Z0-9_.]+))?/g;

export function extractChainFrames(sal: string): { frames: Set<string>; opcodes: Set<string> } {
  const frames = new Set<string>();
  const opcodes = new Set<string>();
  const re = new RegExp(CHAIN_FRAME_RE.source, "g");
  let m: RegExpExecArray | null;

  while ((m = re.exec(sal)) !== null) {
    const [, ns, opcode, bracketVal, colonVal] = m;
    opcodes.add(`${ns}:${opcode}`);
    const val = bracketVal || colonVal;
    if (val) frames.add(`${ns}:${opcode}[${val}]`);
  }
  return { frames, opcodes };
}

// ─── Prerequisite Matching ──────────────────────────────────────────────────

function prereqSatisfied(pattern: string, frames: Set<string>, opcodes: Set<string>): boolean {
  const m = PREREQ_RE.exec(pattern);
  if (!m) return false;
  const [, ns, opcode, slot] = m;
  if (slot) return frames.has(`${ns}:${opcode}[${slot}]`);
  return opcodes.has(`${ns}:${opcode}`);
}

function checkAlternatives(alts: string[][], frames: Set<string>, opcodes: Set<string>): boolean {
  for (const group of alts) {
    if (group.every(prereq => prereqSatisfied(prereq, frames, opcodes))) {
      return true;
    }
  }
  return false;
}

// ─── Rule 8: Regulatory Dependency Validation ───────────────────────────────

export function validateRegulatoryDependencies(
  sal: string,
  rules: DependencyRule[],
): CompositionIssue[] {
  if (rules.length === 0) return [];

  const { frames, opcodes } = extractChainFrames(sal);

  // Build lookup
  const lookup = new Map<string, DependencyRule>();
  for (const rule of rules) {
    lookup.set(rule.entry, rule);
    if (!rule.slotValue) {
      lookup.set(`${rule.namespace}:${rule.opcode}`, rule);
    }
  }

  const issues: CompositionIssue[] = [];

  for (const frame of frames) {
    const rule = lookup.get(frame);
    if (rule && !checkAlternatives(rule.alternatives, frames, opcodes)) {
      const reqDisplay = rule.requiresRaw.replace("REQUIRES:", "");
      issues.push({
        rule: "REGULATORY_DEPENDENCY",
        severity: "error",
        message: `${rule.entry} requires ${reqDisplay} as a regulatory prerequisite. The prerequisite is absent from the instruction chain.`,
        frame: rule.entry,
      });
    }
  }

  for (const bare of opcodes) {
    if (frames.has(bare)) continue;
    const rule = lookup.get(bare);
    if (rule && !rule.slotValue && !checkAlternatives(rule.alternatives, frames, opcodes)) {
      const reqDisplay = rule.requiresRaw.replace("REQUIRES:", "");
      issues.push({
        rule: "REGULATORY_DEPENDENCY",
        severity: "error",
        message: `${rule.entry} requires ${reqDisplay} as a regulatory prerequisite. The prerequisite is absent from the instruction chain.`,
        frame: rule.entry,
      });
    }
  }

  return issues;
}
