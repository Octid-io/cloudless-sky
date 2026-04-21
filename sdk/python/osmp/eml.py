"""
EML — Universal Binary Operator Evaluator

Evaluator and tree data structure for EML expressions.

Based on Odrzywołek (2026), arXiv:2603.21852: a single binary operator
eml(x, y) = exp(x) − ln(y), together with constant 1, generates the
standard calculator function basis.

This module ships the public evaluator:
  - The eml operator (real and complex)
  - EMLNode tree representation with evaluate() and evaluate_complex()
  - Manual tree-builder primitives (leaf, var_x, node)

Not included in this release:
  - Chain construction toolchain (how to author a new tree for a target function)
  - Binary wire format for transmission
  - Shallow-tree approximation optimizer

Attribution
-----------
Built on the universal binary operator eml(x, y) = exp(x) − ln(y)
introduced by Andrzej Odrzywołek (Jagiellonian University,
arXiv:2603.21852, March 2026). The operator itself is not claimed by
any patent; the present work claims the transmission, encoding, and
apparatus layer distinct from the operator. This release ships the
evaluator and tree data structure; the chain-construction toolchain
is proprietary and not included in this release.

Patent pending | License: Apache 2.0
"""
from __future__ import annotations

import math
from dataclasses import dataclass


# ── Core Operator ────────────────────────────────────────────────────────────

def eml(x: complex, y: complex) -> complex:
    """The universal binary operator: eml(x, y) = exp(x) − ln(y)."""
    return complex(math.e ** x - (math.log(y) if y != 0 else float('inf')))


def eml_real(x: float, y: float) -> float:
    """Real-valued eml with complex fallback for negative y.

    When y is negative, ln(y) is computed in the complex plane and the
    real part of the result is returned. This follows the paper's use
    of complex128 arithmetic for intermediate values.
    """
    try:
        if y > 0:
            return math.exp(x) - math.log(y)
        else:
            # Complex fallback: ln(negative) = ln(|y|) + i*pi
            import cmath
            result = cmath.exp(x) - cmath.log(complex(y))
            return result.real
    except (ValueError, OverflowError):
        return float('nan')


# ── Tree Representation ─────────────────────────────────────────────────────

# Sentinel value for the variable x in tree leaves.
# A leaf whose .value equals _X_SENTINEL is treated as the variable x
# during evaluation (injected at call time).
_X_SENTINEL = float('inf')


@dataclass
class EMLNode:
    """A node in an EML expression tree.

    Grammar: S → constant | eml(S, S)
    Leaf nodes hold a constant value (default 1.0).
    Branch nodes apply eml(left, right).
    """
    left: 'EMLNode | None' = None
    right: 'EMLNode | None' = None
    value: float = 1.0  # leaf constant (only used when left is None)

    @property
    def is_leaf(self) -> bool:
        return self.left is None

    @property
    def depth(self) -> int:
        if self.is_leaf:
            return 0
        return 1 + max(self.left.depth, self.right.depth)

    @property
    def node_count(self) -> int:
        if self.is_leaf:
            return 1
        return 1 + self.left.node_count + self.right.node_count

    def evaluate(self, x: float = 0.0) -> float:
        """Evaluate the tree. Leaf nodes return their constant.
        The variable x is injected at var_x() leaves."""
        if self.is_leaf:
            return x if self.value == _X_SENTINEL else self.value
        left_val = self.left.evaluate(x)
        right_val = self.right.evaluate(x)
        return eml_real(left_val, right_val)

    def evaluate_complex(self, x: complex = 0.0) -> complex:
        """Complex-valued evaluation for functions requiring imaginary intermediate values."""
        if self.is_leaf:
            return complex(x) if self.value == _X_SENTINEL else complex(self.value)
        left_val = self.left.evaluate_complex(x)
        right_val = self.right.evaluate_complex(x)
        return eml(left_val, right_val)


def leaf(value: float = 1.0) -> EMLNode:
    """Create a leaf node with a constant value."""
    return EMLNode(value=value)


def var_x() -> EMLNode:
    """Create a leaf node representing the variable x."""
    return EMLNode(value=_X_SENTINEL)


def node(left: EMLNode, right: EMLNode) -> EMLNode:
    """Create a branch node: eml(left, right)."""
    return EMLNode(left=left, right=right)
