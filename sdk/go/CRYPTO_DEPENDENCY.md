# Go SDK Cryptographic Dependencies

## Why this file exists

The Go SDK declares one external dependency in `go.mod`:

```
require golang.org/x/crypto v0.31.0
```

This file explains why that single dependency is necessary, what it
provides, and why it is the only safe choice for the OSMP SEC envelope
implementation in Go.

## What `golang.org/x/crypto` provides

`golang.org/x/crypto` is the canonical Go cryptography extended library.
It is maintained by the Go team at Google and lives under the official
`golang.org/x/` import namespace alongside `golang.org/x/sys`,
`golang.org/x/net`, and other Go-team-maintained packages that supplement
the standard library.

The Go SDK uses one specific subpackage:

```go
import "golang.org/x/crypto/chacha20poly1305"
```

This subpackage implements the **ChaCha20-Poly1305** AEAD cipher
specified in RFC 7539 and RFC 8439. It is used by the OSMP SEC envelope
codec (`sdk/go/osmp/wire.go`) to encrypt instruction payloads with
authenticated encryption.

## Why the Go standard library is not sufficient

The Go standard library `crypto` package includes:

| Algorithm | Standard library | Used by OSMP SEC? |
|---|---|---|
| Ed25519 signatures (RFC 8032) | `crypto/ed25519` | Yes — for sender authentication |
| SHA-256 / SHA-512 | `crypto/sha256`, `crypto/sha512` | Yes — used in nonce derivation |
| HMAC | `crypto/hmac` | No |
| AES-GCM | `crypto/aes`, `crypto/cipher` | No |
| **ChaCha20-Poly1305** | **NOT in stdlib** | **Yes — required for AEAD** |

ChaCha20-Poly1305 is the only cryptographic primitive the SEC envelope
needs that is not in the Go standard library. It lives in
`golang.org/x/crypto/chacha20poly1305` and has lived there since 2016.
There is no path to implementing the SEC envelope wire format in pure
Go stdlib without writing a ChaCha20-Poly1305 implementation from
scratch, which would be roughly 800 lines of cryptographic code that
would require its own audit and fuzz testing.

## Why ChaCha20-Poly1305 specifically

The OSMP SEC envelope uses ChaCha20-Poly1305 (not AES-GCM) for three
reasons:

1. **Constant-time on all hardware**: ChaCha20 is a software stream
   cipher that runs in constant time on every CPU architecture. AES-GCM
   requires hardware AES instructions (AES-NI) for both performance and
   constant-time execution; on hardware without AES-NI it is slow and
   potentially vulnerable to cache-timing attacks. The OSMP target
   platform list includes LoRa edge devices, embedded controllers, and
   ARM microcontrollers where AES-NI is not available.

2. **Cross-SDK byte compatibility**: the Python SDK uses
   `cryptography.hazmat.primitives.ciphers.aead.ChaCha20Poly1305` and
   the TypeScript SDK uses Node's built-in `crypto.createCipheriv` with
   `chacha20-poly1305`. All three SDKs must produce byte-identical
   envelope output for the same inputs so a Python-signed envelope
   decodes in Go and a Go-signed envelope decodes in TypeScript. Using
   the same algorithm across all three SDKs is the only way to
   guarantee this.

3. **Smaller code surface**: AES-GCM has known footguns around nonce
   reuse and tag truncation. ChaCha20-Poly1305 has a simpler API with
   fewer ways to misuse it.

The selection of ChaCha20-Poly1305 happened during Sprint 3 of the
audit (Findings 4 and 31, "real cryptography"), when the SecCodec was
migrated from an HMAC placeholder to real AEAD encryption + Ed25519
signing.

## Why this dependency is trustworthy

`golang.org/x/crypto` is as close to "standard library" as a Go
dependency gets without literally being in the standard library:

- **Maintained by**: the Go team at Google. The same engineers who
  maintain `crypto/ed25519` in the standard library also maintain
  `golang.org/x/crypto/chacha20poly1305`.
- **Versioning**: follows Go's semver-incompatible `golang.org/x/`
  versioning scheme. The version pinned here is `v0.31.0`, released
  December 2024.
- **Audit history**: the package has been in active production use
  across the Go ecosystem since 2016. It is used by every major Go
  TLS implementation, every major Go SSH library, and every major Go
  cryptography wrapper. It has been audited by the Go security team
  and external researchers multiple times.
- **Reverse dependency count**: tens of thousands of Go modules
  depend on it, including major projects like `golang.org/x/net`,
  `gopkg.in/square/go-jose`, and the `kubernetes/kubernetes`
  control plane.
- **Supply chain**: published through `proxy.golang.org`, the
  Google-operated Go module proxy. Module hashes are recorded in
  `go.sum` and verified on every build.

## Why no other dependencies are needed

The Sprint 3 real-cryptography migration was deliberately designed to
minimize external dependencies in the Go SDK. Specifically:

| OSMP need | Source | Dependency? |
|---|---|---|
| Ed25519 signing | `crypto/ed25519` | stdlib, no dependency |
| SHA-256 hashing | `crypto/sha256` | stdlib, no dependency |
| Random key generation | `crypto/rand` | stdlib, no dependency |
| Constant-time comparison | `crypto/subtle` | stdlib, no dependency |
| ChaCha20-Poly1305 AEAD | `golang.org/x/crypto/chacha20poly1305` | one dependency |
| zstd block decompression | `github.com/klauspost/compress/zstd` | one dependency |

The other declared dependency, `github.com/klauspost/compress`, is the
canonical Go zstd implementation. It is required by the dpack consumer
code (`sdk/go/osmp/dpack.go`) for reading MDR corpora compressed with
zstd. There is no zstd implementation in the Go standard library.

## What happens on `go mod tidy`

When a developer or CI runs `go mod tidy` against this module, the Go
toolchain does three things:

1. Reads every `import` statement in every `.go` file under the module
2. Cross-references those imports against `go.mod`
3. Downloads any missing packages from `proxy.golang.org`, writes their
   hashes to `go.sum`, and removes any declared dependencies that
   nothing imports

The dependencies declared in this module are:

- `golang.org/x/crypto v0.31.0` — direct dependency for ChaCha20-Poly1305
- `github.com/klauspost/compress v1.17.6` — direct dependency for zstd
- `golang.org/x/sys v0.28.0` (indirect) — pulled by `golang.org/x/crypto`
  for platform-specific syscalls

No additional dependencies are added at runtime. No native code
extensions. No dynamic library loading. The Go SDK builds to a single
static binary on every supported platform.

## Why this matters for patent and audit review

Reviewers examining the OSMP Go SDK for the patent prosecution and the
YC application will see exactly two non-stdlib imports. Both are
necessary, both are well-established, and both have clear architectural
justifications documented above. The Go SDK is otherwise self-contained
in the standard library.

This is the smallest possible cryptographic surface area for a
production-grade authenticated mesh protocol implementation in Go.
