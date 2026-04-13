/**
 * OSMP Wire Modes — Semantic Assembly Isomorphic Language (SAIL) and Security Envelope (SEC)
 *
 * TypeScript implementation matching osmp_wire.py (Python reference).
 *
 * Modes:
 *   OSMP          — Mnemonic SAL (UTF-8 text, human-readable)
 *   OSMP-SAIL     — Semantic Assembly Isomorphic Language (compact binary, table-decoded)
 *   OSMP-SEC      — Mnemonic SAL + security envelope
 *   OSMP-SAIL-SEC — SAIL + security envelope (hardened mode)
 *
 * Dictionary: OSMP-semantic-dictionary-v15.csv
 */
export declare enum WireMode {
    MNEMONIC = 0,
    SAIL = 1,
    SEC = 2,
    SAIL_SEC = 3
}
export declare function wireModeLabel(m: WireMode): string;
export interface CorpusEntry {
    /** Stable UTF-8 identifier (1-255 bytes), e.g. "asd-v15" */
    corpusId: string;
    /** Full 32-byte SHA-256 over the corpus file bytes verbatim */
    corpusHash: Buffer;
}
export declare class DictionaryBasis {
    private readonly _entries;
    private _fingerprint;
    constructor(entries: CorpusEntry[]);
    get entries(): readonly CorpusEntry[];
    get length(): number;
    isBaseOnly(): boolean;
    /**
     * Canonical wire form per spec §9.3.
     * For each entry in basis order:
     *   corpus_id_length (1 byte) || corpus_id (UTF-8 bytes) || corpus_hash (32 bytes)
     */
    canonicalSerialization(): Buffer;
    /**
     * 8-byte basis fingerprint per spec §9.3.
     * First 8 bytes of SHA-256 over the canonical serialization.
     */
    fingerprint(): Buffer;
    equals(other: DictionaryBasis): boolean;
    /**
     * Construct a basis from corpus files on disk.
     */
    static fromPaths(asdPath: string, asdId?: string, mdrCorpora?: Array<{
        corpusId: string;
        path: string;
    }>): DictionaryBasis;
    /**
     * Construct the default base-ASD-only basis from canonical default locations.
     */
    static default(dictPath?: string): DictionaryBasis;
    private static _hashFile;
    private static _deriveAsdId;
}
export declare class SAILCodec {
    private opToIdx;
    private idxToOp;
    private strToRef;
    private refToStr;
    readonly basis: DictionaryBasis;
    constructor(dictPath?: string, basis?: DictionaryBasis);
    /** 8-byte basis fingerprint for FNP capability negotiation (spec §9.3). */
    basisFingerprint(): Buffer;
    private tryNamespaceOpcode;
    private encodeToken;
    encode(sal: string): Uint8Array;
    decode(data: Uint8Array): string;
}
export interface SecEnvelope {
    mode: WireMode;
    nodeId: Buffer;
    seqCounter: number;
    payload: Buffer;
    authTag: Buffer;
    signature: Buffer;
}
export declare class SecCodec {
    /**
     * Security envelope encoder/decoder.
     *
     * Uses real cryptographic primitives via Node.js stdlib crypto:
     *   - Ed25519 (RFC 8032) for sender authentication via 64-byte signatures
     *   - ChaCha20-Poly1305 (RFC 7539, RFC 8439) for AEAD payload integrity
     *     with a 16-byte authentication tag
     *   - 12-byte nonces derived deterministically from the envelope header
     *     padded with the canonical OSMP nonce salt
     *
     * The wire format is byte-identical to the Python and Go SecCodec
     * implementations so cross-SDK envelopes interoperate natively.
     *
     * Key management is external (MDR node identity service). For ephemeral
     * sessions or local testing, omit the key arguments and the constructor
     * will generate fresh keys via crypto.randomBytes.
     */
    private static readonly NONCE_SALT;
    private nodeId;
    private signingKeySeed;
    private symmetricKey;
    private ed25519PrivateKey;
    private ed25519PublicKey;
    private verifyPublicKeyDefault;
    private seqCounter;
    constructor(nodeId: Buffer, signingKey?: Buffer, symmetricKey?: Buffer, verifyKey?: Buffer);
    /** Wrap a 32-byte raw Ed25519 seed in the PKCS#8 DER prefix Node expects. */
    private static ed25519PrivateFromSeed;
    /** Wrap a 32-byte raw Ed25519 public key in the SPKI DER prefix Node expects. */
    private static ed25519PublicFromBytes;
    /** Return the 32-byte raw Ed25519 public key for distributing to peers. */
    get publicSigningKey(): Buffer;
    private nextSeq;
    /** Derive a 12-byte ChaCha20-Poly1305 nonce from the envelope header. */
    private deriveNonce;
    private seal;
    private open;
    private sign;
    private verify;
    pack(payload: Buffer, wireMode?: WireMode): Buffer;
    unpack(data: Buffer): SecEnvelope | null;
}
export declare class OSMPWireCodec {
    private sail;
    private sec;
    constructor(opts?: {
        dictPath?: string;
        basis?: DictionaryBasis;
        nodeId?: Buffer;
        signingKey?: Buffer;
        symmetricKey?: Buffer;
    });
    /** The Dictionary Basis bound to this codec (ADR-004). */
    get basis(): DictionaryBasis;
    /** 8-byte basis fingerprint for FNP capability negotiation (spec §9.3). */
    basisFingerprint(): Buffer;
    encode(sal: string, mode?: WireMode): Buffer;
    decode(data: Buffer, mode?: WireMode): string;
    measure(sal: string): Record<string, any>;
}
export default OSMPWireCodec;
