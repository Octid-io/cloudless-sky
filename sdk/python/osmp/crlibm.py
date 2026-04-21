"""
crlibm.py — Precision-mode backend (STUB).
==========================================

Precision mode (correctly-rounded exp/log, cross-device deterministic,
audit-grade for regulated industries) is provided by a commercial
precision pack. This file is a stub in the public release.

Regulated-industry applications — medical IEC 62304, aerospace DO-178C,
nuclear IEC 61513, audit-grade financial, cryptographic protocol-frame
hash inputs — require correctly-rounded transcendentals for deterministic
behavior across heterogeneous hardware. The commercial precision pack
provides this via a CRLibm-derived double-double / triple-double
implementation with Ziv iterative-deepening certification and
fusion-robust arithmetic primitives.

To enable precision mode:

    Contact ack@octid.io for evaluation access under NDA.
    Standard distribution: per-deployment commercial license.
    DoD distribution: under DFARS 252.227-7013 / 7014 Restricted Rights.

The commercial precision pack replaces this stub file with a real
implementation exposing the same API (exp, log, AVAILABLE = True).

Patent pending | Stub: Apache 2.0 | Precision pack: commercial license
"""
from __future__ import annotations


class PrecisionModeNotAvailable(RuntimeError):
    """Raised when precision mode is requested without the commercial precision pack.

    Contact ack@octid.io for commercial evaluation under NDA.
    See PATENTS.md at repo root for license-inquiry details.
    """

    def __init__(self, msg: str | None = None):
        super().__init__(
            msg
            or (
                "Precision mode requires the commercial precision pack. "
                "Contact ack@octid.io or see PATENTS.md."
            )
        )


# Reported to eml.py at import time. Commercial pack sets this True.
AVAILABLE: bool = False


def exp(x: float) -> float:
    """Stub — commercial precision pack replaces this file with a real implementation."""
    raise PrecisionModeNotAvailable()


def log(y: float) -> float:
    """Stub — commercial precision pack replaces this file with a real implementation."""
    raise PrecisionModeNotAvailable()
