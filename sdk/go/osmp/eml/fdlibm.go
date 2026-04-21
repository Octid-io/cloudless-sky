// Package eml — Sun fdlibm-derived Exp and Log (Go port).
//
// Reference implementations of exp(x) and log(x) using Sun fdlibm's argument-
// reduction + polynomial-approximation algorithm. All constants are taken
// from Sun's e_exp.c and e_log.c (public domain).
//
// Provides byte-exact cross-language determinism with the Python and
// TypeScript ports when all three languages use their respective fdlibm
// modules. The algorithm uses only IEEE-754-exact basic arithmetic plus
// Frexp/Ldexp, which are identical across IEEE-754-conformant platforms.
//
// SPDX-License-Identifier: Patent-pending
package eml

import "math"

const (
	fdlibmLn2Hi            = 6.93147180369123816490e-01
	fdlibmLn2Lo            = 1.90821492927058770002e-10
	fdlibmInvLn2           = 1.44269504088896338700e+00
	fdlibmP1               = 1.66666666666666019037e-01
	fdlibmP2               = -2.77777777770155933842e-03
	fdlibmP3               = 6.61375632143793436117e-05
	fdlibmP4               = -1.65339022054652515390e-06
	fdlibmP5               = 4.13813679705723846039e-08
	fdlibmExpOverflowThr   = 709.782712893383973096
	fdlibmExpUnderflowThr  = -745.133219101941108420
	fdlibmSqrtHalf         = 0.70710678118654752440

	fdlibmLg1 = 6.666666666666735130e-01
	fdlibmLg2 = 3.999999999940941908e-01
	fdlibmLg3 = 2.857142874366239149e-01
	fdlibmLg4 = 2.222219843214978396e-01
	fdlibmLg5 = 1.818357216161805012e-01
	fdlibmLg6 = 1.531383769920937332e-01
	fdlibmLg7 = 1.479819860511658591e-01
)

// FdlibmExp computes exp(x) using the Sun fdlibm algorithm.
// Byte-exact with FdlibmPyExp and FdlibmTsExp.
func FdlibmExp(x float64) float64 {
	// Special cases
	if x != x { // NaN
		return x
	}
	if math.IsInf(x, 1) {
		return x
	}
	if math.IsInf(x, -1) {
		return 0.0
	}
	if x > fdlibmExpOverflowThr {
		return math.Inf(1)
	}
	if x < fdlibmExpUnderflowThr {
		return 0.0
	}
	if x == 0.0 {
		return 1.0
	}
	// Tiny x: 1 + x
	if x > -twoToNeg28 && x < twoToNeg28 {
		return 1.0 + x
	}

	// Argument reduction: x = k·ln(2) + r, |r| ≤ 0.5·ln(2)
	var k int
	if x >= 0 {
		k = int(x*fdlibmInvLn2 + 0.5)
	} else {
		k = int(x*fdlibmInvLn2 - 0.5)
	}
	fk := float64(k)
	hi := x - fk*fdlibmLn2Hi
	lo := fk * fdlibmLn2Lo
	r := hi - lo

	// Polynomial
	t := r * r
	c := r - t*(fdlibmP1+t*(fdlibmP2+t*(fdlibmP3+t*(fdlibmP4+t*fdlibmP5))))
	var y float64
	if k == 0 {
		y = 1.0 - ((r*c)/(c-2.0) - r)
	} else {
		y = 1.0 - ((lo - (r*c)/(2.0-c)) - hi)
	}
	return math.Ldexp(y, k)
}

// FdlibmLog computes log(x) for x > 0 using the Sun fdlibm algorithm.
// Byte-exact with FdlibmPyLog and FdlibmTsLog.
func FdlibmLog(x float64) float64 {
	if x != x { // NaN
		return x
	}
	if x == 0.0 {
		return math.Inf(-1)
	}
	if x < 0.0 {
		return math.NaN()
	}
	if math.IsInf(x, 1) {
		return x
	}

	// Argument reduction
	m, k := math.Frexp(x)
	if m < fdlibmSqrtHalf {
		m *= 2.0
		k--
	}
	f := m - 1.0

	if f > -twoToNeg20 && f < twoToNeg20 {
		if f == 0.0 {
			if k == 0 {
				return 0.0
			}
			dk := float64(k)
			return dk*fdlibmLn2Hi + dk*fdlibmLn2Lo
		}
		R := f * f * (0.5 - f*(1.0/3.0))
		if k == 0 {
			return f - R
		}
		dk := float64(k)
		return dk*fdlibmLn2Hi - ((R - dk*fdlibmLn2Lo) - f)
	}

	s := f / (2.0 + f)
	z := s * s
	w := z * z
	t1 := w * (fdlibmLg2 + w*(fdlibmLg4+w*fdlibmLg6))
	t2 := z * (fdlibmLg1 + w*(fdlibmLg3+w*(fdlibmLg5+w*fdlibmLg7)))
	R := t2 + t1
	hfsq := 0.5 * f * f
	if k == 0 {
		return f - (hfsq - s*(hfsq+R))
	}
	dk := float64(k)
	return dk*fdlibmLn2Hi - ((hfsq - (s*(hfsq+R) + dk*fdlibmLn2Lo)) - f)
}

// Constants used for argument-reduction thresholds (computed at init time
// rather than as compile-time float literals to guarantee identical bit
// representations across platforms).
var (
	twoToNeg28 = math.Ldexp(1.0, -28)
	twoToNeg20 = math.Ldexp(1.0, -20)
)
