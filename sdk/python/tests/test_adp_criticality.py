"""Tests for ADP REPLACE-criticality wiring (spec §6 / §7)."""
from __future__ import annotations

import pytest

from osmp import (
    ADPDelta,
    ADPDeltaOp,
    DeltaValidationError,
    FLAG_CRITICAL,
    validate_received_delta,
)


# ── required_overflow_flags ────────────────────────────────────────────


def test_additive_delta_required_flags_is_zero():
    d = ADPDelta(
        from_version="15.0", to_version="15.1",
        operations=[ADPDeltaOp(namespace="H", mode="+", opcode="LACTATE", definition="lactate")],
    )
    assert d.required_overflow_flags == 0


def test_deprecate_delta_required_flags_is_zero():
    d = ADPDelta(
        from_version="15.0", to_version="15.1",
        operations=[ADPDeltaOp(namespace="M", mode="†", opcode="OLDOP")],
    )
    assert d.required_overflow_flags == 0


def test_replace_delta_required_flags_is_critical():
    d = ADPDelta(
        from_version="15.0", to_version="15.1",
        operations=[ADPDeltaOp(namespace="H", mode="←", opcode="HR", definition="heart_rate_v2")],
    )
    assert d.required_overflow_flags == FLAG_CRITICAL


def test_mixed_delta_with_any_replace_is_critical():
    d = ADPDelta(
        from_version="15.0", to_version="15.1",
        operations=[
            ADPDeltaOp(namespace="H", mode="+", opcode="LACTATE"),
            ADPDeltaOp(namespace="H", mode="←", opcode="HR", definition="v2"),
        ],
    )
    assert d.required_overflow_flags == FLAG_CRITICAL


# ── validate_received_delta ────────────────────────────────────────────


def test_validate_replace_without_critical_rejects():
    sal = "A:ASD:DELTA[15.0→15.1:H←[HR]]"
    with pytest.raises(DeltaValidationError):
        validate_received_delta(sal, 0)


def test_validate_replace_with_critical_accepts():
    sal = "A:ASD:DELTA[15.0→15.1:H←[HR]]"
    # Should not raise.
    validate_received_delta(sal, FLAG_CRITICAL)


def test_validate_additive_without_critical_accepts():
    sal = "A:ASD:DELTA[15.0→15.1:H+[LACTATE]]"
    # Non-REPLACE deltas may be transmitted under standing policy.
    validate_received_delta(sal, 0)


def test_validate_non_delta_passthrough():
    # Non-A:ASD:DELTA traffic is out of ADP scope; validator is a no-op.
    validate_received_delta("H:HR@NODE1", 0)
    validate_received_delta("A:ASD[15.1]", 0)
    validate_received_delta("A:ASD?", 0)
