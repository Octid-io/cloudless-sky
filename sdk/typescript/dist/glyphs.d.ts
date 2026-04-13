/**
 * OSMP Glyph Tables and ASD Basis Set
 * AUTO-GENERATED from sdk/python/osmp/protocol.py (dictionary v15)
 *
 * DO NOT EDIT — regenerate via: python3 tools/gen_asd.py
 * Edits to this file will be silently overwritten on the next generation run.
 *
 * Patent: OSMP-001-UTIL (pending) — inventor Clay Holberg
 * License: Apache 2.0
 */
export declare const ASD_FLOOR_VERSION = "1.0";
export declare const GLYPH_OPERATORS: Record<string, {
    unicode: string;
    name: string;
    nl: string[];
}>;
export declare const COMPOUND_OPERATORS: Record<string, {
    unicode: string;
    name: string;
    nl: string[];
}>;
export declare const CONSEQUENCE_CLASSES: Record<string, {
    unicode: string;
    name: string;
    hitlRequired: boolean;
}>;
export declare const OUTCOME_STATES: Record<string, string>;
export declare const PARAMETER_DESIGNATORS: Record<string, {
    unicode: string;
    name: string;
    bytes: number;
}>;
export declare const LOSS_POLICIES: Record<string, {
    unicode: string;
    name: string;
    bytes: number;
    legacy: string;
}>;
export declare const DICT_UPDATE_MODES: Record<string, {
    unicode: string;
    name: string;
    bytes: number;
}>;
export declare const ASD_BASIS: Record<string, Record<string, string>>;
