package osmp

import (
	"encoding/binary"
	"fmt"
	"sort"
	"strings"
)

// FlagExtendedDep signals that the first 4 bytes of payload are a u32
// dependency bitmap for multi-parent DAG nodes (Tier 3).
const FlagExtendedDep = 0b00001000

// DAGNode is a single executable unit in a Tier 3 DAG.
type DAGNode struct {
	Index   int
	Payload []byte
	Parents []int
}

// ── DAGFragmenter ────────────────────────────────────────────────────────────

// DAGFragmenter decomposes a compound SAL instruction into a DAG of fragments.
type DAGFragmenter struct {
	MTU int
}

// NewDAGFragmenter creates a fragmenter with the given MTU.
func NewDAGFragmenter(mtu int) *DAGFragmenter {
	if mtu <= 0 {
		mtu = LoRaStandardBytes
	}
	return &DAGFragmenter{MTU: mtu}
}

// Parse decomposes a compound SAL string into DAGNodes.
func (df *DAGFragmenter) Parse(compoundSAL string) []DAGNode {
	nodes := make([]DAGNode, 0)
	df.parseExpr(strings.TrimSpace(compoundSAL), &nodes, nil)
	return nodes
}

func (df *DAGFragmenter) parseExpr(expr string, nodes *[]DAGNode, parentIndices []int) []int {
	// ; (SEQUENCE) — lowest precedence
	parts := splitTopLevel(expr, ";")
	if len(parts) > 1 {
		tails := parentIndices
		for _, part := range parts {
			tails = df.parseExpr(strings.TrimSpace(part), nodes, tails)
		}
		return tails
	}

	// → (THEN)
	parts = splitTopLevel(expr, "→")
	if len(parts) > 1 {
		tails := parentIndices
		for _, part := range parts {
			tails = df.parseExpr(strings.TrimSpace(part), nodes, tails)
		}
		return tails
	}

	// ∧ (AND) — parallel fork
	parts = splitTopLevel(expr, "∧")
	if len(parts) > 1 {
		var allTails []int
		for _, part := range parts {
			branchTails := df.parseExpr(strings.TrimSpace(part), nodes, parentIndices)
			allTails = append(allTails, branchTails...)
		}
		return allTails
	}

	// A∥[...] — parallel execution block
	prefix := "A∥["
	if strings.HasPrefix(expr, prefix) && strings.HasSuffix(expr, "]") {
		inner := expr[len(prefix) : len(expr)-1]
		parts = splitTopLevel(inner, "∧")
		if len(parts) <= 1 {
			parts = []string{inner}
		}
		var allTails []int
		for _, part := range parts {
			clean := strings.TrimSpace(part)
			if strings.HasPrefix(clean, "?") {
				clean = clean[len("?"):]
			}
			branchTails := df.parseExpr(clean, nodes, parentIndices)
			allTails = append(allTails, branchTails...)
		}
		return allTails
	}

	// Atomic leaf node
	idx := len(*nodes)
	parents := make([]int, len(parentIndices))
	copy(parents, parentIndices)
	*nodes = append(*nodes, DAGNode{
		Index:   idx,
		Payload: []byte(expr),
		Parents: parents,
	})
	return []int{idx}
}

func splitTopLevel(expr, sep string) []string {
	var parts []string
	depth := 0
	var current strings.Builder
	runes := []rune(expr)
	sepRunes := []rune(sep)
	sepLen := len(sepRunes)
	i := 0

	for i < len(runes) {
		ch := runes[i]
		if ch == '[' || ch == '(' {
			depth++
			current.WriteRune(ch)
			i++
		} else if ch == ']' || ch == ')' {
			depth--
			current.WriteRune(ch)
			i++
		} else if depth == 0 && i+sepLen <= len(runes) && string(runes[i:i+sepLen]) == sep {
			parts = append(parts, current.String())
			current.Reset()
			i += sepLen
		} else {
			current.WriteRune(ch)
			i++
		}
	}
	if current.Len() > 0 {
		parts = append(parts, current.String())
	}
	return parts
}

// Fragmentize runs the full Tier 3 pipeline: parse → assign DEP → emit Fragments.
func (df *DAGFragmenter) Fragmentize(compoundSAL string, msgID uint16, critical bool) []*Fragment {
	nodes := df.Parse(compoundSAL)
	if len(nodes) == 0 {
		return nil
	}
	fragCt := uint8(len(nodes))
	frags := make([]*Fragment, len(nodes))

	for _, node := range nodes {
		isLast := node.Index == int(fragCt)-1
		flags := uint8(0)
		if isLast {
			flags |= FlagTerminal
		}
		if critical {
			flags |= FlagCritical
		}

		var dep uint8
		var payload []byte

		switch {
		case len(node.Parents) == 0:
			dep = uint8(node.Index) // self-reference = root
			payload = node.Payload
		case len(node.Parents) == 1:
			dep = uint8(node.Parents[0])
			payload = node.Payload
		default:
			flags |= FlagExtendedDep
			dep = uint8(node.Parents[0]) // primary dep for legacy readers
			var bitmap uint32
			for _, p := range node.Parents {
				bitmap |= 1 << uint(p)
			}
			bitmapBuf := make([]byte, 4)
			binary.BigEndian.PutUint32(bitmapBuf, bitmap)
			payload = append(bitmapBuf, node.Payload...)
		}

		frags[node.Index] = &Fragment{
			MsgIDFull: msgID,
			FragIdx:   uint8(node.Index),
			FragCt:    fragCt,
			Flags:     flags,
			Dep:       dep,
			Payload:   payload,
		}
	}
	return frags
}

// ── DAGReassembler ───────────────────────────────────────────────────────────

// DAGReassembler buffers fragments and resolves the dependency DAG under
// loss tolerance policy.
type DAGReassembler struct {
	Policy LossPolicy
	buf    map[uint16]map[uint8]*Fragment
}

// NewDAGReassembler creates a reassembler with the given policy.
func NewDAGReassembler(policy LossPolicy) *DAGReassembler {
	return &DAGReassembler{
		Policy: policy,
		buf:    make(map[uint16]map[uint8]*Fragment),
	}
}

// Receive buffers a fragment and attempts DAG resolution.
// Returns ordered payloads in execution order, or nil if not yet resolvable.
func (dr *DAGReassembler) Receive(frag *Fragment) [][]byte {
	// R:ESTOP hard exception
	if strings.Contains(string(frag.Payload), "R:ESTOP") {
		return [][]byte{frag.Payload}
	}

	mid := frag.MsgIDFull
	if dr.buf[mid] == nil {
		dr.buf[mid] = make(map[uint8]*Fragment)
	}
	dr.buf[mid][frag.FragIdx] = frag
	rcv := dr.buf[mid]
	exp := int(frag.FragCt)

	switch dr.Policy {
	case LossPolicyFailSafe:
		if len(rcv) == exp {
			return dr.resolveDAG(rcv)
		}
	case LossPolicyAtomic:
		if len(rcv) == exp {
			return dr.resolveDAG(rcv)
		}
	default: // GracefulDegradation
		if frag.IsTerminal() && len(rcv) == exp {
			return dr.resolveDAG(rcv)
		}
		if frag.IsTerminal() {
			return dr.resolveDAGPartial(rcv)
		}
	}
	return nil
}

func (dr *DAGReassembler) getParents(frag *Fragment) []int {
	if frag.Flags&FlagExtendedDep != 0 {
		if len(frag.Payload) < 4 {
			return nil
		}
		bitmap := binary.BigEndian.Uint32(frag.Payload[:4])
		var parents []int
		for i := 0; i < 32; i++ {
			if bitmap&(1<<uint(i)) != 0 {
				parents = append(parents, i)
			}
		}
		return parents
	}
	// Self-reference = root
	if frag.Dep == frag.FragIdx {
		return nil
	}
	return []int{int(frag.Dep)}
}

func (dr *DAGReassembler) getPayload(frag *Fragment) []byte {
	if frag.Flags&FlagExtendedDep != 0 && len(frag.Payload) >= 4 {
		return frag.Payload[4:]
	}
	return frag.Payload
}

func (dr *DAGReassembler) resolveDAG(rcv map[uint8]*Fragment) [][]byte {
	nodeSet := make(map[int]bool)
	for k := range rcv {
		nodeSet[int(k)] = true
	}
	order := dr.topoSort(rcv, nodeSet)
	result := make([][]byte, len(order))
	for i, idx := range order {
		result[i] = dr.getPayload(rcv[uint8(idx)])
	}
	return result
}

func (dr *DAGReassembler) resolveDAGPartial(rcv map[uint8]*Fragment) [][]byte {
	present := make(map[int]bool)
	for k := range rcv {
		present[int(k)] = true
	}
	executable := make(map[int]bool)
	for idx := range present {
		if dr.ancestorsSatisfied(rcv, idx, present) {
			executable[idx] = true
		}
	}
	if len(executable) == 0 {
		return [][]byte{}
	}
	order := dr.topoSort(rcv, executable)
	result := make([][]byte, len(order))
	for i, idx := range order {
		result[i] = dr.getPayload(rcv[uint8(idx)])
	}
	return result
}

func (dr *DAGReassembler) ancestorsSatisfied(rcv map[uint8]*Fragment, idx int, present map[int]bool) bool {
	visited := make(map[int]bool)
	stack := []int{idx}
	for len(stack) > 0 {
		current := stack[len(stack)-1]
		stack = stack[:len(stack)-1]
		if visited[current] {
			continue
		}
		visited[current] = true
		if !present[current] {
			return false
		}
		if frag, ok := rcv[uint8(current)]; ok {
			for _, p := range dr.getParents(frag) {
				if !visited[p] {
					stack = append(stack, p)
				}
			}
		}
	}
	return true
}

func (dr *DAGReassembler) topoSort(rcv map[uint8]*Fragment, nodeSet map[int]bool) []int {
	inDeg := make(map[int]int)
	children := make(map[int][]int)
	for i := range nodeSet {
		inDeg[i] = 0
		children[i] = nil
	}

	for idx := range nodeSet {
		parents := dr.getParents(rcv[uint8(idx)])
		for _, p := range parents {
			if nodeSet[p] {
				inDeg[idx]++
				children[p] = append(children[p], idx)
			}
		}
	}

	var queue []int
	for i := range nodeSet {
		if inDeg[i] == 0 {
			queue = append(queue, i)
		}
	}
	sort.Ints(queue)

	var order []int
	for len(queue) > 0 {
		node := queue[0]
		queue = queue[1:]
		order = append(order, node)
		ch := children[node]
		sort.Ints(ch)
		for _, c := range ch {
			inDeg[c]--
			if inDeg[c] == 0 {
				queue = append(queue, c)
			}
		}
	}
	return order
}

// NACK generates a NACK for missing fragments in a DAG message.
func (dr *DAGReassembler) NACK(msgID uint16, expCt int) string {
	rcv := dr.buf[msgID]
	var missing []string
	for i := 0; i < expCt; i++ {
		if _, ok := rcv[uint8(i)]; !ok {
			missing = append(missing, fmt.Sprintf("%d", i))
		}
	}
	return fmt.Sprintf("A:NACK[MSG:%d∖[%s]]", msgID, strings.Join(missing, ","))
}
