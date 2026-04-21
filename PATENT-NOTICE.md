# PATENT NOTICE

## Patent Status

The software in this repository is the subject of pending United States patent applications. Inventor: Clay Holberg, Texas, United States of America.

---

## Patent Grant Under Apache 2.0

This software is licensed under the Apache License, Version 2.0. Section 3 of the Apache License provides an express patent grant:

> Each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable patent license to make, have made, use, offer to sell, sell, import, and otherwise transfer the Work, where such license applies only to those patent claims licensable by such Contributor that are necessarily infringed by their Contribution(s) alone or by combination of their Contribution(s) with the Work.

This means: if you implement OSMP or UBOT according to the published specification, you receive a license to the relevant patent claims under the terms of Apache 2.0. You do not need a separate patent license agreement to build a conformant implementation.

---

## Patent Termination Clause

If you initiate patent litigation against any entity (including a cross-claim or counterclaim) alleging that this Work constitutes patent infringement, your patent licenses granted under the Apache 2.0 License terminate as of the date such litigation is filed.

---

## Commercial Services — Request-Gated

Three commercial services require a direct request. Gating is intentional: each service requires a conversation to ensure informational integrity, deployment quality, and appropriate use. Contact `ack@octid.io` for all three (subject line triage is appreciated — see each section below).

### Omega Namespace Extensions

The OSMP grammar reserves extension namespaces for domain-specific opcodes beyond the 352-opcode public ASD. Organizations deploying OSMP in specialized domains — clinical specialties, defense-vertical taxonomies, industrial-control vocabularies, proprietary agent frameworks, multi-tenant enterprise platforms — can register custom namespace opcodes under the Omega extension protocol. Registered Omega namespaces sit outside the core patent claim scope (third-party sovereign extensions are the intellectual property of their respective authors) while retaining wire-level compatibility with the public grammar.

**Request Omega namespace registration:** `ack@octid.io` — subject: *Omega namespace request*

### MDR Certification (Managed Dictionary Registry)

The MDR is a certification layer for compliant enterprise namespace implementations where authoritative domain-code mapping is operationally required. Relevant deployments include regulated industries (healthcare, financial services, defense), multi-tenant platforms requiring attestation, and audit-grade contexts where the namespace-to-semantics binding must be formally certified. MDR certification is separate from the Apache 2.0 patent grant; use of the public OSMP protocol does not require MDR certification.

**Request MDR certification inquiry:** `ack@octid.io` — subject: *MDR certification*

### UBOT Precision Mode

The UBOT evaluator ships in this repository with two precision modes:

- **Fast mode (fdlibm-derived, 1-ULP accurate):** included publicly under Apache 2.0. Correct for LoRa / BLE / edge-ML, drone swarm coordination, constrained-channel transmission, and general scientific computation.
- **Precision mode (crlibm-derived, correctly-rounded, cross-device byte-exact):** NOT included in the public release. Available under **commercial license** for regulated-industry applications — medical (IEC 62304), aerospace (DO-178C), nuclear (IEC 61513), audit-grade financial, cryptographic protocol-frame hash inputs, and DoD / defense-aerospace deployments.

Calling `set_precision_mode("precision")` / `SetPrecisionMode(Precision)` without the commercial precision pack installed raises `PrecisionModeNotAvailable` / returns `ErrPrecisionPackNotInstalled`.

**DoD / defense-aerospace distribution:** The commercial precision pack is available under DFARS 252.227-7013 ("Rights in Technical Data — Noncommercial Items") and DFARS 252.227-7014 ("Rights in Noncommercial Computer Software") Restricted Rights framework.

**Request precision-mode access:** `ack@octid.io` — subject: *UBOT precision mode*

The precision pack is separate from the Apache 2.0 patent grant above. Use of the fast-mode public release does not require a commercial precision-pack license.

---

## Questions

Commercial services (Omega / MDR / precision mode) and general licensing: `ack@octid.io` or [octid.io](https://octid.io)

General protocol / software questions: open an issue at [github.com/octid-io/cloudless-sky](https://github.com/octid-io/cloudless-sky)
