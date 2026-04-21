// Package eml — Precision-mode backend (STUB).
//
// Precision mode (correctly-rounded exp/log, cross-device deterministic,
// audit-grade for regulated industries) is provided by a commercial
// precision pack. This file is a stub in the public release.
//
// Regulated-industry applications — medical IEC 62304, aerospace DO-178C,
// nuclear IEC 61513, audit-grade financial, cryptographic protocol-frame
// hash inputs — require correctly-rounded transcendentals for deterministic
// behavior across heterogeneous hardware. The commercial precision pack
// provides this via a CRLibm-derived double-double / triple-double
// implementation with Ziv iterative-deepening certification and
// fusion-robust arithmetic primitives.
//
// To enable precision mode:
//
//	Contact ack@octid.io for evaluation access under NDA.
//	Standard distribution: per-deployment commercial license.
//	DoD distribution: under DFARS 252.227-7013 / 7014 Restricted Rights.
//
// The commercial precision pack replaces this stub file with a real
// implementation exposing the same API (CrlibmExp, CrlibmLog,
// CrlibmAvailable = true).
//
// SPDX-License-Identifier: Patent-pending (stub: Apache 2.0)
package eml

import "errors"

// ErrPrecisionPackNotInstalled is returned / panicked when precision mode
// is requested without the commercial precision pack.
//
// Contact ack@octid.io for commercial evaluation under NDA.
// See PATENTS.md at the repository root for license-inquiry details.
var ErrPrecisionPackNotInstalled = errors.New(
	"precision mode requires the commercial precision pack; contact ack@octid.io or see PATENTS.md",
)

// CrlibmAvailable reports whether the precision-mode backend is installed.
// Public release: false. Commercial precision pack: replaces this file
// with one that sets this to true and provides real CrlibmExp / CrlibmLog.
const CrlibmAvailable = false

// CrlibmExp is a stub in the public release. SetPrecisionMode returns
// ErrPrecisionPackNotInstalled before reaching here, so this panic path
// is defense-in-depth only.
func CrlibmExp(x float64) float64 {
	panic(ErrPrecisionPackNotInstalled)
}

// CrlibmLog is a stub in the public release. See CrlibmExp.
func CrlibmLog(y float64) float64 {
	panic(ErrPrecisionPackNotInstalled)
}
