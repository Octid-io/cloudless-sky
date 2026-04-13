import { DictUpdateMode, DeltaLogEntry } from "./types.js";
export declare class AdaptiveSharedDictionary {
    readonly floorVersion: string;
    private _data;
    private _tombstones;
    private _versionLog;
    constructor(floorVersion?: string);
    lookup(namespace: string, opcode: string): string | null;
    applyDelta(namespace: string, opcode: string, definition: string, mode: DictUpdateMode, versionPointer: string): void;
    fingerprint(): string;
    /** Canonical JSON matching Python json.dumps(data, sort_keys=True, ensure_ascii=True).
     *  Uses ", " and ": " separators; escapes non-ASCII to \\uXXXX.
     *  Required for cross-SDK FNP fingerprint wire compatibility. */
    canonicalJSON(): string;
    namespaces(): string[];
    versionLog(): DeltaLogEntry[];
}
