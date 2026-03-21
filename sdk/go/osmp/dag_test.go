package osmp

import (
	"bytes"
	"encoding/binary"
	"testing"
)

func TestDAGParseSequence(t *testing.T) {
	df := NewDAGFragmenter(255)
	nodes := df.Parse("H:HR@NODE1;H:CASREP;M:EVA@*")
	if len(nodes) != 3 {
		t.Fatalf("expected 3 nodes, got %d", len(nodes))
	}
	if len(nodes[0].Parents) != 0 {
		t.Error("node 0 should be root")
	}
	if len(nodes[1].Parents) != 1 || nodes[1].Parents[0] != 0 {
		t.Error("node 1 should depend on 0")
	}
	if len(nodes[2].Parents) != 1 || nodes[2].Parents[0] != 1 {
		t.Error("node 2 should depend on 1")
	}
}

func TestDAGParseFork(t *testing.T) {
	df := NewDAGFragmenter(255)
	nodes := df.Parse("H:HR@NODE1;H:CASREP∧M:EVA@*")
	if len(nodes) != 3 {
		t.Fatalf("expected 3 nodes, got %d", len(nodes))
	}
	if len(nodes[1].Parents) != 1 || nodes[1].Parents[0] != 0 {
		t.Error("node 1 should depend on 0")
	}
	if len(nodes[2].Parents) != 1 || nodes[2].Parents[0] != 0 {
		t.Error("node 2 should depend on 0")
	}
}

func TestDAGParseDiamond(t *testing.T) {
	df := NewDAGFragmenter(255)
	nodes := df.Parse("A;B∧C;D")
	if len(nodes) != 4 {
		t.Fatalf("expected 4, got %d", len(nodes))
	}
	if len(nodes[3].Parents) != 2 {
		t.Fatalf("node 3 should have 2 parents, got %d", len(nodes[3].Parents))
	}
}

func TestDAGFragmentizeDiamondExtendedDep(t *testing.T) {
	df := NewDAGFragmenter(255)
	frags := df.Fragmentize("A;B∧C;D", 1, false)
	if len(frags) != 4 {
		t.Fatalf("expected 4 fragments, got %d", len(frags))
	}
	d := frags[3]
	if d.Flags&FlagExtendedDep == 0 {
		t.Fatal("fragment 3 should have extended dep flag")
	}
	if len(d.Payload) < 4 {
		t.Fatal("payload too short for bitmap")
	}
	bitmap := binary.BigEndian.Uint32(d.Payload[:4])
	if bitmap&(1<<1) == 0 || bitmap&(1<<2) == 0 {
		t.Errorf("bitmap should have bits 1 and 2 set, got %032b", bitmap)
	}
	if string(d.Payload[4:]) != "D" {
		t.Errorf("payload after bitmap should be 'D', got %q", d.Payload[4:])
	}
}

func TestDAGFragmentizeSelfRefRoot(t *testing.T) {
	df := NewDAGFragmenter(255)
	frags := df.Fragmentize("A;B", 1, false)
	if frags[0].Dep != 0 {
		t.Errorf("root frag 0 dep should be 0 (self-ref), got %d", frags[0].Dep)
	}
	if frags[1].Dep != 0 {
		t.Errorf("frag 1 dep should be 0, got %d", frags[1].Dep)
	}
}

func TestDAGReassemblerChain(t *testing.T) {
	df := NewDAGFragmenter(255)
	frags := df.Fragmentize("A;B;C", 1, false)
	dr := NewDAGReassembler(LossPolicyGracefulDegradation)
	var result [][]byte
	for _, f := range frags {
		result = dr.Receive(f)
	}
	if result == nil || len(result) != 3 {
		t.Fatalf("expected 3 payloads, got %v", result)
	}
	if string(result[0]) != "A" || string(result[1]) != "B" || string(result[2]) != "C" {
		t.Errorf("wrong order: %v", result)
	}
}

func TestDAGReassemblerDiamond(t *testing.T) {
	df := NewDAGFragmenter(255)
	frags := df.Fragmentize("A;B∧C;D", 1, false)
	dr := NewDAGReassembler(LossPolicyGracefulDegradation)
	var result [][]byte
	for _, f := range frags {
		result = dr.Receive(f)
	}
	if result == nil || len(result) != 4 {
		t.Fatalf("expected 4 payloads, got %v", result)
	}
	if string(result[0]) != "A" {
		t.Error("first should be A")
	}
	if string(result[3]) != "D" {
		t.Error("last should be D")
	}
}

func TestDAGGracefulDegradationMissingRoot(t *testing.T) {
	df := NewDAGFragmenter(255)
	frags := df.Fragmentize("A;B∧C", 1, false)
	dr := NewDAGReassembler(LossPolicyGracefulDegradation)
	dr.Receive(frags[1])             // B
	result := dr.Receive(frags[2])   // C (terminal), A missing
	if len(result) != 0 {
		t.Errorf("expected empty (no root), got %d payloads", len(result))
	}
}

func TestDAGGracefulDegradationMissingMiddle(t *testing.T) {
	df := NewDAGFragmenter(255)
	frags := df.Fragmentize("A;B;C", 1, false)
	dr := NewDAGReassembler(LossPolicyGracefulDegradation)
	dr.Receive(frags[0])             // A
	result := dr.Receive(frags[2])   // C (terminal), B missing
	if result == nil || len(result) != 1 || string(result[0]) != "A" {
		t.Errorf("expected [A], got %v", result)
	}
}

func TestDAGAtomicPartialNil(t *testing.T) {
	df := NewDAGFragmenter(255)
	frags := df.Fragmentize("A;B;C", 1, false)
	dr := NewDAGReassembler(LossPolicyAtomic)
	dr.Receive(frags[0])
	result := dr.Receive(frags[2]) // skip B
	if result != nil {
		t.Error("atomic should return nil on partial")
	}
}

func TestDAGEstopImmediate(t *testing.T) {
	dr := NewDAGReassembler(LossPolicyAtomic)
	f := &Fragment{MsgIDFull: 1, FragIdx: 2, FragCt: 5, Flags: 0, Dep: 1, Payload: []byte("R:ESTOP@BOT1")}
	result := dr.Receive(f)
	if result == nil || len(result) != 1 {
		t.Fatal("ESTOP should fire immediately")
	}
	if !bytes.Contains(result[0], []byte("R:ESTOP")) {
		t.Error("payload should contain R:ESTOP")
	}
}

func TestDAGPackUnpackRoundTrip(t *testing.T) {
	df := NewDAGFragmenter(255)
	frags := df.Fragmentize("A;B∧C;D", 1, false)
	for _, f := range frags {
		packed := f.Pack()
		if len(packed) < FragmentHeaderBytes {
			t.Fatal("packed too short")
		}
		unpacked, err := UnpackFragment(packed)
		if err != nil {
			t.Fatal(err)
		}
		if unpacked.MsgIDFull != f.MsgIDFull || unpacked.FragIdx != f.FragIdx ||
			unpacked.FragCt != f.FragCt || unpacked.Flags != f.Flags || unpacked.Dep != f.Dep {
			t.Errorf("header mismatch on frag %d", f.FragIdx)
		}
		if !bytes.Equal(unpacked.Payload, f.Payload) {
			t.Errorf("payload mismatch on frag %d", f.FragIdx)
		}
	}
}
