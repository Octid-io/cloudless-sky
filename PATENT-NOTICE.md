# PATENT NOTICE

## Patent Status

The software in this repository is the subject of pending United States patent applications. Inventor: Clay Holberg, Texas, United States of America.

---

## Patent Grant Under Apache 2.0

This software is licensed under the Apache License, Version 2.0. Section 3 of the Apache License provides an express patent grant:

> Each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable patent license to make, have made, use, offer to sell, sell, import, and otherwise transfer the Work, where such license applies only to those patent claims licensable by such Contributor that are necessarily infringed by their Contribution(s) alone or by combination of their Contribution(s) with the Work.

This means: if you implement OSMP according to this specification, you receive a license to the relevant patent claims under the terms of Apache 2.0. You do not need a separate patent license agreement to build a conformant OSMP implementation.

---

## Patent Termination Clause

If you initiate patent litigation against any entity (including a cross-claim or counterclaim) alleging that this Work constitutes patent infringement, your patent licenses granted under the Apache 2.0 License terminate as of the date such litigation is filed.

---

## Sovereign Extension Namespace Scope

The patent grant covers implementations of the published OSMP specification. Sovereign namespace extensions defined by third parties under the reserved extension prefix are outside the scope of the patent grant and are neither covered by nor restricted by the OSMP patent claims, provided they do not practice the claimed OSMP architecture itself. Third-party sovereign extensions are the intellectual property of their respective authors.

---

## MDR Certification (Separate from Patent)

The Managed Dictionary Registry (MDR) is a certification layer for compliant enterprise namespace implementations. MDR certification is a commercial service and is separate from the Apache 2.0 patent grant. Use of the OSMP protocol does not require MDR certification. MDR certification may be required for specific regulated-industry deployments where authoritative namespace mapping is operationally required.

---

## UBOT Precision Pack (Separate from Patent Grant)

The UBOT evaluator ships in this repository with two precision modes:

- **Fast mode (fdlibm-derived, 1-ULP accurate):** included with this public release under Apache 2.0. Covers the vast majority of UBOT applications — LoRa / BLE / edge-ML deployments, drone swarm coordination, constrained-channel transmission, and general scientific computation.
- **Precision mode (crlibm-derived, correctly-rounded, cross-device byte-exact):** NOT included in the public release. Available under **commercial license** for regulated-industry applications — medical (IEC 62304), aerospace (DO-178C), nuclear (IEC 61513), audit-grade financial, cryptographic protocol-frame hash inputs, and DoD / defense-aerospace deployments.

Calling `set_precision_mode("precision")` / `SetPrecisionMode(Precision)` without the commercial precision pack installed raises `PrecisionModeNotAvailable` / returns `ErrPrecisionPackNotInstalled`.

**DoD / defense-aerospace distribution:** The commercial precision pack is available under DFARS 252.227-7013 ("Rights in Technical Data — Noncommercial Items") and DFARS 252.227-7014 ("Rights in Noncommercial Computer Software") Restricted Rights framework.

**Licensing inquiries:** `licensing@octid.io`

The precision pack is separate from the Apache 2.0 patent grant above. Use of the fast-mode public release does not require a commercial precision-pack license.

---

## Questions

Patent and commercial licensing inquiries: `licensing@octid.io` or [octid.io](https://octid.io)

General protocol / software questions: open an issue at [github.com/octid-io/cloudless-sky](https://github.com/octid-io/cloudless-sky)
