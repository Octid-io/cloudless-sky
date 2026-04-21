"""
fdlibm.py — Sun fdlibm-derived exp and log, pure Python, byte-exact.
======================================================================

Reference implementations of exp(x) and log(x) using Sun fdlibm's argument-
reduction + polynomial-approximation algorithm. All constants are taken
directly from Sun's e_exp.c and e_log.c (public domain).

Why this exists: Python's math.exp and math.log use libm (correctly-rounded),
while Go's math.Exp/Log and V8's Math.exp/log are 1-ULP-accurate. Using a
common fdlibm-derived reference in all three languages gives byte-exact
exp/log results across Python, Go, and TypeScript — satisfying the
cross-language determinism requirement for UBOT's cross-device evaluation
claim.

Algorithm:
    exp(x):
        Argument reduction:   x = k·ln(2) + r,  |r| ≤ 0.5·ln(2)
        Polynomial:           c = r - r²·(P1 + r²·P2 + ... + r^10·P5)
        Primary eval:         y = 1 - ((lo - (r·c)/(2 - c)) - hi)
        Scale:                exp(x) = y · 2^k

    log(x):
        Argument reduction:   x = m · 2^k  via frexp, adjusted to m ∈ [√2/2, √2)
        Let f = m - 1, s = f/(m + 1)
        Polynomial:           R = s²·(Lg1 + s²·Lg3 + ...)  +  s⁴·(Lg2 + s²·Lg4 + ...)
        Result:               log(x) = k·ln(2) + f - hfsq + s·(hfsq + R)

The implementation uses only IEEE-754-exact basic arithmetic (+, -, *, /)
and the frexp/ldexp primitives.

Patent pending | License: Apache 2.0
"""
import math

# =============================================================================
# CONSTANTS (from Sun fdlibm e_exp.c and e_log.c — public domain)
# =============================================================================

# exp()
_LN2_HI   = 6.93147180369123816490e-01
_LN2_LO   = 1.90821492927058770002e-10
_INV_LN2  = 1.44269504088896338700e+00
_P1 = 1.66666666666666019037e-01
_P2 = -2.77777777770155933842e-03
_P3 = 6.61375632143793436117e-05
_P4 = -1.65339022054652515390e-06
_P5 = 4.13813679705723846039e-08
_EXP_OVERFLOW_THRESHOLD  =  709.782712893383973096
_EXP_UNDERFLOW_THRESHOLD = -745.133219101941108420

# log()
_LG1 = 6.666666666666735130e-01
_LG2 = 3.999999999940941908e-01
_LG3 = 2.857142874366239149e-01
_LG4 = 2.222219843214978396e-01
_LG5 = 1.818357216161805012e-01
_LG6 = 1.531383769920937332e-01
_LG7 = 1.479819860511658591e-01

_SQRT_HALF = 0.70710678118654752440  # √2/2


# =============================================================================
# exp(x) — Sun fdlibm algorithm
# =============================================================================

def exp(x: float) -> float:
    """fdlibm-derived exp(x). Byte-exact with the Go and TypeScript ports."""
    if x != x:
        return x
    if x == float("inf"):
        return x
    if x == float("-inf"):
        return 0.0
    if x > _EXP_OVERFLOW_THRESHOLD:
        return float("inf")
    if x < _EXP_UNDERFLOW_THRESHOLD:
        return 0.0
    if x == 0.0:
        return 1.0

    if -2**-28 < x < 2**-28:
        return 1.0 + x

    if x >= 0:
        k = int(x * _INV_LN2 + 0.5)
    else:
        k = int(x * _INV_LN2 - 0.5)

    hi = x - k * _LN2_HI
    lo = k * _LN2_LO
    r = hi - lo

    t = r * r
    c = r - t * (_P1 + t * (_P2 + t * (_P3 + t * (_P4 + t * _P5))))
    if k == 0:
        y = 1.0 - ((r * c) / (c - 2.0) - r)
    else:
        y = 1.0 - ((lo - (r * c) / (2.0 - c)) - hi)

    return math.ldexp(y, k)


# =============================================================================
# log(x) — Sun fdlibm algorithm
# =============================================================================

def log(x: float) -> float:
    """fdlibm-derived log(x) for x > 0. Byte-exact with the Go and TS ports."""
    if x != x:
        return x
    if x == 0.0:
        return float("-inf")
    if x < 0.0:
        return float("nan")
    if x == float("inf"):
        return x

    m, k = math.frexp(x)
    if m < _SQRT_HALF:
        m *= 2.0
        k -= 1

    f = m - 1.0

    if abs(f) < 2**-20:
        if f == 0.0:
            if k == 0:
                return 0.0
            dk = float(k)
            return dk * _LN2_HI + dk * _LN2_LO
        R = f * f * (0.5 - f * (1.0 / 3.0))
        if k == 0:
            return f - R
        dk = float(k)
        return dk * _LN2_HI - ((R - dk * _LN2_LO) - f)

    s = f / (2.0 + f)
    z = s * s
    w = z * z
    t1 = w * (_LG2 + w * (_LG4 + w * _LG6))
    t2 = z * (_LG1 + w * (_LG3 + w * (_LG5 + w * _LG7)))
    R = t2 + t1
    hfsq = 0.5 * f * f
    if k == 0:
        return f - (hfsq - s * (hfsq + R))
    dk = float(k)
    return dk * _LN2_HI - ((hfsq - (s * (hfsq + R) + dk * _LN2_LO)) - f)


if __name__ == "__main__":
    # Quick self-check against math.*
    probes = [0.1, 0.5, 1.0, 1.5, 2.0, 2.71828, 3.14159, 5.0, 10.0, -1.0, -10.0]
    print("fdlibm.py exp/log self-check")
    for x in probes:
        if -50 <= x <= 50:
            a = exp(x); b = math.exp(x)
            print(f"  exp({x}): fdlibm={a!r}  math={b!r}")
    for x in [0.5, 1.0, 1.5, 2.0, 2.71828, 10.0, 100.0]:
        a = log(x); b = math.log(x)
        print(f"  log({x}): fdlibm={a!r}  math={b!r}")
