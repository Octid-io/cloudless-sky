// Package eml — Universal Binary Operator Evaluator (UBOT public reference).
//
// Reference implementation of the Universal Binary Operator for mathematical
// instruction encoding, under the UBOT-001-UTIL patent application (pending).
//
// Based on Odrzywołek (2026, arXiv:2603.21852):
//
//	eml(x, y) = exp(x) − ln(y)
//
// This package is the PUBLIC library-free evaluator. It uses only the Go
// standard library (math, encoding/binary, crypto/sha256). It does not
// depend on cgo, assembly, or any external package.
//
// Dual-mode precision:
//
//	Fast mode      — fdlibm-derived (1-ULP accurate, ships publicly)
//	Precision mode — crlibm-derived (correctly-rounded, audit-grade)
//	                 AVAILABLE UNDER COMMERCIAL LICENSE.
//
// Precision mode (correctly-rounded, cross-device deterministic, audit-grade
// for regulated industries — medical IEC 62304, aerospace DO-178C, nuclear
// IEC 61513, audit-grade finance) is available under commercial license.
// Contact licensing@octid.io for evaluation.
//
// Calling SetPrecisionMode(Precision) without the commercial precision
// pack installed returns ErrPrecisionPackNotInstalled (see crlibm.go stub).
//
// Attribution: built on the universal binary operator eml(x, y) =
// exp(x) − ln(y) introduced by Andrzej Odrzywołek (Jagiellonian
// University, arXiv:2603.21852, March 2026). The operator itself is
// not claimed by any patent; the present work claims the transmission,
// encoding, and apparatus layer distinct from the operator.
//
// License: Apache 2.0 (public module). Precision pack: separate
// commercial license — see PATENTS.md at repository root.
//
// SPDX-License-Identifier: Apache-2.0
package eml

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"fmt"
	"math"
	"sort"
)

// =============================================================================
// CORE OPERATOR
// =============================================================================

// ExpClamp is the safe_exp argument clamp magnitude. Load-bearing: matches
// the Python reference, part of the patent claims (Category M envelope).
const ExpClamp float64 = 50.0

// LogEps is the safe_log input magnitude floor. Load-bearing.
const LogEps float64 = 1e-30

// PrecisionMode selects between fdlibm (fast, 1-ULP) and crlibm (slower, 0-ULP typical).
type PrecisionMode int

const (
	// Fast mode: fdlibm-derived primitives (~1-ULP accurate, fast).
	// Default mode, sufficient for nearly all UBOT applications.
	Fast PrecisionMode = iota
	// Precision mode: DD-based primitives (~0-ULP accurate on typical inputs,
	// ~3× slower than Fast). Opt-in for audit-grade / regulated applications.
	Precision
)

var currentMode PrecisionMode = Fast

// SetPrecisionMode sets the evaluator precision mode.
//
// Precision mode requires the commercial precision pack. If the pack is
// not installed (CrlibmAvailable == false), SetPrecisionMode(Precision)
// returns ErrPrecisionPackNotInstalled without changing the current mode.
// Fast mode always succeeds. Contact licensing@octid.io for evaluation.
func SetPrecisionMode(m PrecisionMode) error {
	if m == Precision && !CrlibmAvailable {
		return ErrPrecisionPackNotInstalled
	}
	currentMode = m
	return nil
}

// GetPrecisionMode returns the current evaluator precision mode.
func GetPrecisionMode() PrecisionMode { return currentMode }

// PrecisionModeAvailable reports whether the commercial precision-mode
// backend is installed.
func PrecisionModeAvailable() bool { return CrlibmAvailable }

func activeExp(x float64) float64 {
	if currentMode == Precision {
		// Defense-in-depth: SetPrecisionMode refuses to switch to Precision
		// without the precision pack, so this path should only fire if
		// currentMode was set by some other means.
		if !CrlibmAvailable {
			panic(ErrPrecisionPackNotInstalled)
		}
		return CrlibmExp(x)
	}
	return FdlibmExp(x)
}

func activeLog(y float64) float64 {
	if currentMode == Precision {
		if !CrlibmAvailable {
			panic(ErrPrecisionPackNotInstalled)
		}
		return CrlibmLog(y)
	}
	return FdlibmLog(y)
}

// SafeExp computes exp(x) with argument clamped to [-ExpClamp, +ExpClamp].
// Uses the current PrecisionMode.
func SafeExp(x float64) float64 {
	if x > ExpClamp {
		return activeExp(ExpClamp)
	}
	if x < -ExpClamp {
		return activeExp(-ExpClamp)
	}
	return activeExp(x)
}

// SafeLog computes log(|y|) with |y| floored at LogEps. Uses current PrecisionMode.
func SafeLog(y float64) float64 {
	mag := math.Abs(y)
	if mag < LogEps {
		mag = LogEps
	}
	return activeLog(mag)
}

// Eml computes the universal binary operator eml(x, y) = SafeExp(x) − SafeLog(y).
func Eml(x, y float64) float64 {
	return SafeExp(x) - SafeLog(y)
}

// =============================================================================
// PAPER TREE REPRESENTATION
// =============================================================================

// Node in an EML expression tree. Grammar: S → constant | var_x | eml(S, S).
type Node struct {
	Left  *Node
	Right *Node
	Value float64 // leaf value (meaningful only when IsLeaf)
	IsX   bool    // true when leaf represents the variable x
}

// IsLeaf reports whether n is a leaf.
func (n *Node) IsLeaf() bool {
	return n.Left == nil
}

// Depth returns the tree depth (leaf = 0, branch = 1 + max(child depths)).
func (n *Node) Depth() int {
	if n.IsLeaf() {
		return 0
	}
	dl := n.Left.Depth()
	dr := n.Right.Depth()
	if dl > dr {
		return dl + 1
	}
	return dr + 1
}

// Evaluate evaluates the tree at variable value x.
func (n *Node) Evaluate(x float64) float64 {
	if n.IsLeaf() {
		if n.IsX {
			return x
		}
		return n.Value
	}
	return Eml(n.Left.Evaluate(x), n.Right.Evaluate(x))
}

// Leaf constructs a constant-leaf node.
func Leaf(v float64) *Node { return &Node{Value: v} }

// VarX constructs a variable-x leaf.
func VarX() *Node { return &Node{IsX: true} }

// Branch constructs an eml(left, right) branch.
func Branch(left, right *Node) *Node { return &Node{Left: left, Right: right} }

// One is the canonical constant-1 leaf.
var One = Leaf(1.0)

// =============================================================================
// PAPER TREE WIRE FORMAT
// =============================================================================

const (
	tagLeafF32 byte = 0x00 // 1 tag + 4-byte float32 = 5 bytes
	tagBranch  byte = 0x01
	tagVarX    byte = 0x02
	tagLeafF64 byte = 0x03 // 1 tag + 8-byte float64 = 9 bytes
)

// EncodeTree serializes a tree to the paper wire format.
//
// useF64 = false: emits 4-byte float32 leaves (5 bytes per leaf-with-float).
// useF64 = true:  emits 8-byte float64 leaves (9 bytes per leaf-with-float).
func EncodeTree(tree *Node, useF64 bool) []byte {
	var buf bytes.Buffer
	encodeNode(&buf, tree, useF64)
	return buf.Bytes()
}

func encodeNode(buf *bytes.Buffer, n *Node, useF64 bool) {
	if n.IsLeaf() {
		if n.IsX {
			buf.WriteByte(tagVarX)
			return
		}
		if useF64 {
			buf.WriteByte(tagLeafF64)
			binary.Write(buf, binary.LittleEndian, n.Value)
		} else {
			buf.WriteByte(tagLeafF32)
			binary.Write(buf, binary.LittleEndian, float32(n.Value))
		}
		return
	}
	buf.WriteByte(tagBranch)
	encodeNode(buf, n.Left, useF64)
	encodeNode(buf, n.Right, useF64)
}

// DecodeTree deserializes a tree from the paper wire format.
func DecodeTree(data []byte) (*Node, error) {
	node, off, err := decodeNode(data, 0)
	if err != nil {
		return nil, err
	}
	if off != len(data) {
		return nil, fmt.Errorf("trailing bytes after tree: %d", len(data)-off)
	}
	return node, nil
}

func decodeNode(data []byte, offset int) (*Node, int, error) {
	if offset >= len(data) {
		return nil, 0, errors.New("unexpected end of tree data")
	}
	tag := data[offset]
	offset++
	switch tag {
	case tagVarX:
		return VarX(), offset, nil
	case tagLeafF32:
		if offset+4 > len(data) {
			return nil, 0, errors.New("truncated float32 leaf")
		}
		var f float32
		binary.Read(bytes.NewReader(data[offset:offset+4]), binary.LittleEndian, &f)
		return Leaf(float64(f)), offset + 4, nil
	case tagLeafF64:
		if offset+8 > len(data) {
			return nil, 0, errors.New("truncated float64 leaf")
		}
		var f float64
		binary.Read(bytes.NewReader(data[offset:offset+8]), binary.LittleEndian, &f)
		return Leaf(f), offset + 8, nil
	case tagBranch:
		l, off2, err := decodeNode(data, offset)
		if err != nil {
			return nil, 0, err
		}
		r, off3, err := decodeNode(data, off2)
		if err != nil {
			return nil, 0, err
		}
		return Branch(l, r), off3, nil
	}
	return nil, 0, fmt.Errorf("invalid tree tag: 0x%02x", tag)
}

// =============================================================================
// CHAIN REPRESENTATION
// =============================================================================

// ChainLevel is a single chain level with two operand codes.
//
// Operand codes:
//
//	"1"            -> constant 1.0
//	<var name>     -> variable (e.g., "x", "y", "a")
//	"f"            -> f_{k-1} (restricted-chain shorthand)
//	"fN"           -> f_N (wide-chain explicit, N in 1..k-1)
type ChainLevel struct {
	Left  string
	Right string
}

// ChainVariant selects the wire-format grammar for a chain.
type ChainVariant int

const (
	Restricted ChainVariant = iota
	WideMultivar
)

// Chain is an ordered list of levels plus variables + grammar variant.
type Chain struct {
	Levels    []ChainLevel
	Variables []string
	Variant   ChainVariant
}

// NLevels returns the number of levels.
func (c *Chain) NLevels() int { return len(c.Levels) }

// NVariables returns the number of named variables.
func (c *Chain) NVariables() int { return len(c.Variables) }

// Evaluate evaluates the chain at the given variable values (positional).
func (c *Chain) Evaluate(values []float64) (float64, error) {
	if len(values) != len(c.Variables) {
		return 0, fmt.Errorf("got %d values, expected %d", len(values), len(c.Variables))
	}
	varMap := map[string]float64{"1": 1.0}
	for i, nm := range c.Variables {
		varMap[nm] = values[i]
	}
	f := make([]float64, 0, len(c.Levels))
	for k, lvl := range c.Levels {
		a, err := resolveOperand(lvl.Left, varMap, f, k+1)
		if err != nil {
			return 0, err
		}
		b, err := resolveOperand(lvl.Right, varMap, f, k+1)
		if err != nil {
			return 0, err
		}
		f = append(f, Eml(a, b))
	}
	if len(f) == 0 {
		return 0, nil
	}
	return f[len(f)-1], nil
}

func resolveOperand(op string, varMap map[string]float64, f []float64, k int) (float64, error) {
	if op == "1" {
		return 1.0, nil
	}
	if op == "f" {
		if k < 2 {
			return 0, errors.New("'f' referenced at L1")
		}
		return f[k-2], nil
	}
	if len(op) > 1 && op[0] == 'f' {
		idx := 0
		for _, c := range op[1:] {
			if c < '0' || c > '9' {
				idx = -1
				break
			}
			idx = idx*10 + int(c-'0')
		}
		if idx >= 1 && idx < k {
			return f[idx-1], nil
		}
		if idx >= k {
			return 0, fmt.Errorf("f%d out of range at L%d", idx, k)
		}
	}
	if v, ok := varMap[op]; ok {
		return v, nil
	}
	return 0, fmt.Errorf("unknown operand %q", op)
}

// =============================================================================
// RESTRICTED-CHAIN WIRE FORMAT
// =============================================================================

// EncodeChainRestricted bit-packs a restricted chain to bytes.
// selfDescribing=true prefixes a 4-bit length nibble (supports N ≤ 15).
func EncodeChainRestricted(c *Chain, selfDescribing bool) ([]byte, error) {
	if c.Variant != Restricted {
		return nil, fmt.Errorf("not a restricted chain")
	}
	if len(c.Variables) != 1 {
		return nil, fmt.Errorf("restricted chain must be single-variable")
	}
	varName := c.Variables[0]
	l1Code := map[string]uint8{"1": 0, "x": 1}
	lkCode := map[string]uint8{"1": 0b00, "x": 0b01, "f": 0b10}

	var bits []uint8
	if selfDescribing {
		if c.NLevels() > 15 {
			return nil, fmt.Errorf("self-describing supports N≤15")
		}
		for i := 3; i >= 0; i-- {
			bits = append(bits, uint8((c.NLevels()>>i)&1))
		}
	}
	for k, lvl := range c.Levels {
		bitsPerInput := 1
		codebook := l1Code
		if k+1 > 1 {
			bitsPerInput = 2
			codebook = lkCode
		}
		for _, operand := range []string{lvl.Left, lvl.Right} {
			op := operand
			if op == varName {
				op = "x"
			}
			code, ok := codebook[op]
			if !ok {
				return nil, fmt.Errorf("operand %q not encodable at L%d", operand, k+1)
			}
			for i := bitsPerInput - 1; i >= 0; i-- {
				bits = append(bits, (code>>uint(i))&1)
			}
		}
	}
	return packBits(bits), nil
}

// DecodeChainRestricted decodes a restricted-chain wire payload.
func DecodeChainRestricted(data []byte, selfDescribing bool, nLevels int, variableName string) (*Chain, error) {
	bits := unpackBits(data)
	off := 0
	if selfDescribing {
		if nLevels != 0 {
			return nil, errors.New("cannot pass nLevels with selfDescribing")
		}
		if len(bits) < 4 {
			return nil, errors.New("truncated header")
		}
		for i := 0; i < 4; i++ {
			nLevels = (nLevels << 1) | int(bits[off])
			off++
		}
	}
	if nLevels == 0 {
		return nil, errors.New("nLevels required when not self-describing")
	}
	l1Dec := map[uint8]string{0: "1", 1: "x"}
	lkDec := map[uint8]string{0b00: "1", 0b01: "x", 0b10: "f"}

	levels := make([]ChainLevel, 0, nLevels)
	for k := 1; k <= nLevels; k++ {
		bitsPerInput := 1
		decoder := l1Dec
		if k > 1 {
			bitsPerInput = 2
			decoder = lkDec
		}
		ops := make([]string, 0, 2)
		for i := 0; i < 2; i++ {
			if off+bitsPerInput > len(bits) {
				return nil, fmt.Errorf("truncated at L%d", k)
			}
			var code uint8
			for j := 0; j < bitsPerInput; j++ {
				code = (code << 1) | bits[off]
				off++
			}
			op, ok := decoder[code]
			if !ok {
				return nil, fmt.Errorf("reserved code %d at L%d", code, k)
			}
			if op == "x" {
				op = variableName
			}
			ops = append(ops, op)
		}
		levels = append(levels, ChainLevel{Left: ops[0], Right: ops[1]})
	}
	return &Chain{Levels: levels, Variables: []string{variableName}, Variant: Restricted}, nil
}

// =============================================================================
// WIDE MULTI-VARIABLE CHAIN WIRE FORMAT
// =============================================================================

func bitsPerInputAtLevel(V, k int) int {
	options := V + k
	b := 0
	for (1 << uint(b)) < options {
		b++
	}
	if b < 1 {
		return 1
	}
	return b
}

// EncodeChainWide bit-packs a wide (multi-variable) chain to bytes.
func EncodeChainWide(c *Chain) ([]byte, error) {
	if c.Variant != WideMultivar {
		return nil, errors.New("not a wide-multivar chain")
	}
	V := c.NVariables()
	N := c.NLevels()
	if V < 1 || V > 255 || N < 1 || N > 255 {
		return nil, fmt.Errorf("V=%d, N=%d out of supported range (1..255)", V, N)
	}
	varIndex := map[string]int{}
	for i, v := range c.Variables {
		varIndex[v] = i + 1
	}

	var bits []uint8
	if V <= 15 && N <= 15 {
		header := uint8((V << 4) | N)
		pushByte(&bits, header)
	} else {
		pushByte(&bits, 0xFF)
		pushByte(&bits, uint8(N))
		pushByte(&bits, uint8(V))
	}

	for k, lvl := range c.Levels {
		bpi := bitsPerInputAtLevel(V, k+1)
		for _, operand := range []string{lvl.Left, lvl.Right} {
			idx, err := wideOperandIndex(operand, varIndex, V, k+1)
			if err != nil {
				return nil, err
			}
			for i := bpi - 1; i >= 0; i-- {
				bits = append(bits, uint8((idx>>uint(i))&1))
			}
		}
	}
	return packBits(bits), nil
}

func wideOperandIndex(op string, varIndex map[string]int, V, k int) (int, error) {
	if op == "1" {
		return 0, nil
	}
	if idx, ok := varIndex[op]; ok {
		return idx, nil
	}
	if op == "f" {
		if k < 2 {
			return 0, errors.New("'f' at L1")
		}
		return V + (k - 1), nil
	}
	if len(op) > 1 && op[0] == 'f' {
		fi := 0
		for _, c := range op[1:] {
			if c < '0' || c > '9' {
				fi = -1
				break
			}
			fi = fi*10 + int(c-'0')
		}
		if fi < 1 || fi >= k {
			return 0, fmt.Errorf("f%d out of range at L%d", fi, k)
		}
		return V + fi, nil
	}
	return 0, fmt.Errorf("unknown operand %q", op)
}

// DecodeChainWide decodes a wide multi-variable chain wire payload.
// If variables is nil, defaults to ["x1", "x2", ..., "xV"].
func DecodeChainWide(data []byte, variables []string) (*Chain, error) {
	bits := unpackBits(data)
	off := 0
	// Parse header
	var header int
	for i := 0; i < 8; i++ {
		header = (header << 1) | int(bits[off])
		off++
	}
	var V, N int
	if header == 0xFF {
		for i := 0; i < 8; i++ {
			N = (N << 1) | int(bits[off])
			off++
		}
		for i := 0; i < 8; i++ {
			V = (V << 1) | int(bits[off])
			off++
		}
	} else {
		V = (header >> 4) & 0x0F
		N = header & 0x0F
	}

	if variables == nil {
		variables = make([]string, V)
		for i := 0; i < V; i++ {
			variables[i] = fmt.Sprintf("x%d", i+1)
		}
	} else if len(variables) != V {
		return nil, fmt.Errorf("got %d variable names, header says V=%d", len(variables), V)
	}
	idxToVar := map[int]string{}
	for i, v := range variables {
		idxToVar[i+1] = v
	}

	levels := make([]ChainLevel, 0, N)
	for k := 1; k <= N; k++ {
		bpi := bitsPerInputAtLevel(V, k)
		ops := make([]string, 0, 2)
		for i := 0; i < 2; i++ {
			if off+bpi > len(bits) {
				return nil, fmt.Errorf("truncated at L%d", k)
			}
			idx := 0
			for j := 0; j < bpi; j++ {
				idx = (idx << 1) | int(bits[off])
				off++
			}
			var op string
			switch {
			case idx == 0:
				op = "1"
			case idx <= V:
				op = idxToVar[idx]
			case idx < V+k:
				op = fmt.Sprintf("f%d", idx-V)
			default:
				return nil, fmt.Errorf("operand idx %d out of range at L%d", idx, k)
			}
			ops = append(ops, op)
		}
		levels = append(levels, ChainLevel{Left: ops[0], Right: ops[1]})
	}
	return &Chain{Levels: levels, Variables: variables, Variant: WideMultivar}, nil
}

// =============================================================================
// BIT PACKING
// =============================================================================

func packBits(bits []uint8) []byte {
	n := (len(bits) + 7) / 8
	out := make([]byte, n)
	for i, b := range bits {
		if b != 0 {
			out[i/8] |= 1 << uint(7-(i%8))
		}
	}
	return out
}

func unpackBits(data []byte) []uint8 {
	bits := make([]uint8, 0, len(data)*8)
	for _, b := range data {
		for i := 7; i >= 0; i-- {
			bits = append(bits, uint8((b>>uint(i))&1))
		}
	}
	return bits
}

func pushByte(bits *[]uint8, b byte) {
	for i := 7; i >= 0; i-- {
		*bits = append(*bits, uint8((b>>uint(i))&1))
	}
}

// =============================================================================
// CORPUS — base restricted-chain structures (16-entry core corpus)
// =============================================================================

// BaseChainStructures gives the ordered (left, right) operand pairs for
// each base corpus entry. Order matches the Python reference.
var BaseChainStructures = [][2]interface{}{}

// BaseCorpusOrder is the canonical evaluation order for fingerprinting.
// Must match eml.py exactly.
var BaseCorpusOrder = []string{
	"exp(x)", "ln(x)", "identity", "zero",
	"exp(x)-ln(x)", "exp(x)-x", "e-x", "exp(exp(x))",
	"e-exp(x)", "1-ln(x)", "e/x", "exp(x)-1",
	"exp(x)-e", "e^e/x", "ln(ln(x))", "exp(exp(exp(x)))",
}

var baseChainPairs = map[string][][2]string{
	"exp(x)":           {{"x", "1"}},
	"ln(x)":            {{"1", "x"}, {"f", "1"}, {"1", "f"}},
	"identity":         {{"1", "x"}, {"f", "1"}, {"1", "f"}, {"f", "1"}},
	"zero":             {{"1", "1"}, {"f", "1"}, {"1", "f"}},
	"exp(x)-ln(x)":     {{"x", "x"}},
	"exp(x)-x":         {{"x", "1"}, {"x", "f"}},
	"e-x":              {{"x", "1"}, {"1", "f"}},
	"exp(exp(x))":      {{"x", "1"}, {"f", "1"}},
	"e-exp(x)":         {{"x", "1"}, {"f", "1"}, {"1", "f"}},
	"1-ln(x)":          {{"1", "1"}, {"f", "1"}, {"1", "f"}, {"f", "x"}},
	"e/x":              {{"1", "1"}, {"f", "1"}, {"1", "f"}, {"f", "x"}, {"f", "1"}},
	"exp(x)-1":         {{"1", "1"}, {"x", "f"}},
	"exp(x)-e":         {{"1", "1"}, {"f", "1"}, {"x", "f"}},
	"e^e/x":            {{"1", "x"}, {"f", "1"}},
	"ln(ln(x))":        {{"1", "x"}, {"f", "1"}, {"1", "f"}, {"1", "f"}, {"f", "1"}, {"1", "f"}},
	"exp(exp(exp(x)))": {{"x", "1"}, {"f", "1"}, {"f", "1"}},
}

// GetBaseChain constructs a restricted-variant Chain for a named base corpus entry.
func GetBaseChain(name string) (*Chain, error) {
	pairs, ok := baseChainPairs[name]
	if !ok {
		return nil, fmt.Errorf("unknown base corpus entry %q", name)
	}
	levels := make([]ChainLevel, len(pairs))
	for i, p := range pairs {
		levels[i] = ChainLevel{Left: p[0], Right: p[1]}
	}
	return &Chain{Levels: levels, Variables: []string{"x"}, Variant: Restricted}, nil
}

// =============================================================================
// COMPOUND PRIMITIVES
// =============================================================================

// Operand-pair sequences for the verified arithmetic compounds.
// Match eml.py exactly.

var compoundNegY = [][2]string{
	{"1", "1"}, {"f1", "1"}, {"1", "f2"},
	{"1", "f3"}, {"f4", "1"}, {"1", "f5"},
	{"y", "1"}, {"f6", "f7"},
}

var compoundXPlusY = [][2]string{
	{"1", "1"}, {"f1", "1"}, {"1", "f2"},
	{"1", "f3"}, {"f4", "1"}, {"1", "f5"},
	{"y", "1"}, {"f6", "f7"},
	{"1", "x"}, {"f9", "1"}, {"1", "f10"},
	{"f8", "1"},
	{"f11", "f12"},
}

var compoundXTimesY = [][2]string{
	{"1", "1"}, {"f1", "1"}, {"1", "f2"},
	{"1", "x"}, {"f4", "1"}, {"1", "f5"},
	{"1", "y"}, {"f7", "1"}, {"1", "f8"},
	{"1", "f3"}, {"f10", "1"}, {"1", "f11"},
	{"f12", "y"},
	{"1", "f6"}, {"f14", "1"}, {"1", "f15"},
	{"f13", "1"},
	{"f16", "f17"},
	{"f18", "1"},
}

var compoundLinearCal = [][2]string{
	{"1", "1"}, {"f1", "1"}, {"1", "f2"},
	{"1", "a"}, {"f4", "1"}, {"1", "f5"},
	{"1", "x"}, {"f7", "1"}, {"1", "f8"},
	{"1", "f3"}, {"f10", "1"}, {"1", "f11"},
	{"f12", "x"},
	{"1", "f6"}, {"f14", "1"}, {"1", "f15"},
	{"f13", "1"},
	{"f16", "f17"},
	{"f18", "1"},
	{"b", "1"},
	{"f12", "f20"},
	{"1", "f19"}, {"f22", "1"}, {"1", "f23"},
	{"f21", "1"},
	{"f24", "f25"},
}

// CompoundNegY returns the verified -y compound at L=8.
func CompoundNegY() *Chain {
	return buildChain(compoundNegY, []string{"y"})
}

// CompoundXPlusY returns the verified x+y compound at L=13.
func CompoundXPlusY() *Chain {
	return buildChain(compoundXPlusY, []string{"x", "y"})
}

// CompoundXTimesY returns the verified x·y compound at L=19.
func CompoundXTimesY() *Chain {
	return buildChain(compoundXTimesY, []string{"x", "y"})
}

// CompoundLinearCalibration returns the verified y=a·x+b compound at L≈26.
func CompoundLinearCalibration() *Chain {
	return buildChain(compoundLinearCal, []string{"a", "x", "b"})
}

func buildChain(pairs [][2]string, vars []string) *Chain {
	levels := make([]ChainLevel, len(pairs))
	for i, p := range pairs {
		levels[i] = ChainLevel{Left: p[0], Right: p[1]}
	}
	return &Chain{Levels: levels, Variables: vars, Variant: WideMultivar}
}

// =============================================================================
// TEST VECTORS & DETERMINISM FINGERPRINT
// =============================================================================

// CanonicalInputs are the test inputs used to cross-check against Python & TS.
// Must match eml.py exactly.
var CanonicalInputs = []float64{
	0.5, 1.0, 1.5, 2.0, math.E, math.Pi, 3.0, 5.0, 7.0, 10.0,
}

// EvaluateBaseCorpus returns the base-corpus output vectors at canonical inputs.
func EvaluateBaseCorpus() (map[string][]float64, error) {
	out := map[string][]float64{}
	for _, name := range BaseCorpusOrder {
		chain, err := GetBaseChain(name)
		if err != nil {
			return nil, err
		}
		ys := make([]float64, len(CanonicalInputs))
		for i, x := range CanonicalInputs {
			y, err := chain.Evaluate([]float64{x})
			if err != nil {
				return nil, err
			}
			ys[i] = y
		}
		out[name] = ys
	}
	return out, nil
}

// EvaluateCompounds returns compound-primitive output vectors at canonical inputs.
func EvaluateCompounds() (map[string][][]float64, error) {
	out := map[string][][]float64{}

	// neg_y: single variable
	negY := CompoundNegY()
	negYOut := make([][]float64, len(CanonicalInputs))
	for i, y := range CanonicalInputs {
		v, err := negY.Evaluate([]float64{y})
		if err != nil {
			return nil, err
		}
		negYOut[i] = []float64{v}
	}
	out["neg_y"] = negYOut

	// x+y and x·y: all pairs, lexicographic order
	plus := CompoundXPlusY()
	mul := CompoundXTimesY()
	plusOut := make([][]float64, 0, len(CanonicalInputs)*len(CanonicalInputs))
	mulOut := make([][]float64, 0, len(CanonicalInputs)*len(CanonicalInputs))
	for _, x := range CanonicalInputs {
		for _, y := range CanonicalInputs {
			vp, err := plus.Evaluate([]float64{x, y})
			if err != nil {
				return nil, err
			}
			vm, err := mul.Evaluate([]float64{x, y})
			if err != nil {
				return nil, err
			}
			plusOut = append(plusOut, []float64{vp})
			mulOut = append(mulOut, []float64{vm})
		}
	}
	out["x_plus_y"] = plusOut
	out["x_times_y"] = mulOut

	// linear_calibration: smaller grid
	aVals := []float64{0.5, 1.0, math.Pi}
	xVals := []float64{1.0, math.E}
	bVals := []float64{0.5, 1.0, math.E}
	lc := CompoundLinearCalibration()
	lcOut := make([][]float64, 0)
	for _, a := range aVals {
		for _, x := range xVals {
			for _, b := range bVals {
				v, err := lc.Evaluate([]float64{a, x, b})
				if err != nil {
					return nil, err
				}
				lcOut = append(lcOut, []float64{v})
			}
		}
	}
	out["linear_calibration"] = lcOut

	return out, nil
}

// CorpusFingerprint computes the SHA-256 determinism fingerprint.
// Must match eml.py output exactly when the math operations agree byte-for-byte.
func CorpusFingerprint() (string, error) {
	h := sha256.New()

	base, err := EvaluateBaseCorpus()
	if err != nil {
		return "", err
	}
	for _, name := range BaseCorpusOrder {
		h.Write([]byte(name))
		h.Write([]byte(":"))
		for _, y := range base[name] {
			binary.Write(h, binary.LittleEndian, y)
		}
	}

	compound, err := EvaluateCompounds()
	if err != nil {
		return "", err
	}
	for _, name := range []string{"neg_y", "x_plus_y", "x_times_y", "linear_calibration"} {
		h.Write([]byte(name))
		h.Write([]byte(":"))
		for _, row := range compound[name] {
			for _, y := range row {
				binary.Write(h, binary.LittleEndian, y)
			}
		}
	}
	return fmt.Sprintf("%x", h.Sum(nil)), nil
}

// =============================================================================
// SELF-TEST (package-level helpers for the cmd/selftest binary)
// =============================================================================

// SortedBaseNames returns BaseCorpusOrder (for diagnostic printing).
func SortedBaseNames() []string {
	out := make([]string, len(BaseCorpusOrder))
	copy(out, BaseCorpusOrder)
	sort.SliceStable(out, func(i, j int) bool { return i < j }) // preserve canonical order
	return out
}
