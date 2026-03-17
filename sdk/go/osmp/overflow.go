package osmp

import (
	"encoding/binary"
	"fmt"
	"strings"
)

const (
	FragmentHeaderBytes = 6
	LoRaFloorBytes      = 51
	LoRaStandardBytes   = 255
	FlagTerminal        = 0b00000001
	FlagCritical        = 0b00000010
	FlagNLPassthrough   = 0x04
)

type LossPolicy int
const (
	LossPolicyFailSafe            LossPolicy = iota
	LossPolicyGracefulDegradation
	LossPolicyAtomic
)

type Fragment struct {
	MsgID, FragIdx, FragCt, Flags, Dep uint8 // Flags/MsgID use proper sizes below
	MsgIDFull                          uint16
	Payload                            []byte
}

func (f *Fragment) IsTerminal() bool { return f.Flags&FlagTerminal != 0 }
func (f *Fragment) IsCritical() bool  { return f.Flags&FlagCritical != 0 }

func (f *Fragment) Pack() []byte {
	buf := make([]byte, FragmentHeaderBytes+len(f.Payload))
	binary.BigEndian.PutUint16(buf[0:2], f.MsgIDFull)
	buf[2] = f.FragIdx; buf[3] = f.FragCt; buf[4] = f.Flags; buf[5] = f.Dep
	copy(buf[FragmentHeaderBytes:], f.Payload)
	return buf
}

func UnpackFragment(data []byte) (*Fragment, error) {
	if len(data) < FragmentHeaderBytes {
		return nil, fmt.Errorf("fragment too short: %d bytes", len(data))
	}
	f := &Fragment{
		MsgIDFull: binary.BigEndian.Uint16(data[0:2]),
		FragIdx:   data[2], FragCt: data[3], Flags: data[4], Dep: data[5],
		Payload:   make([]byte, len(data)-FragmentHeaderBytes),
	}
	copy(f.Payload, data[FragmentHeaderBytes:])
	return f, nil
}

type OverflowProtocol struct {
	MTU     int
	Policy  LossPolicy
	counter uint16
	buf     map[uint16]map[uint8]*Fragment
}

func NewOverflowProtocol(mtu int, policy LossPolicy) *OverflowProtocol {
	if mtu <= 0 { mtu = LoRaStandardBytes }
	return &OverflowProtocol{MTU: mtu, Policy: policy, buf: make(map[uint16]map[uint8]*Fragment)}
}

func (op *OverflowProtocol) nextID() uint16 {
	op.counter++; return op.counter
}

func (op *OverflowProtocol) Fragment(payload []byte, critical bool) []*Fragment {
	avail := op.MTU - FragmentHeaderBytes
	cf := func(base uint8) uint8 {
		if critical { return base | FlagCritical }
		return base
	}
	if len(payload)+FragmentHeaderBytes <= op.MTU {
		id := op.nextID()
		return []*Fragment{{MsgIDFull: id, FragIdx: 0, FragCt: 1, Flags: cf(FlagTerminal), Dep: 0, Payload: payload}}
	}
	var chunks [][]byte
	for i := 0; i < len(payload); i += avail {
		end := i + avail; if end > len(payload) { end = len(payload) }
		c := make([]byte, end-i); copy(c, payload[i:end]); chunks = append(chunks, c)
	}
	id := op.nextID(); ct := uint8(len(chunks))
	result := make([]*Fragment, len(chunks))
	for i, ch := range chunks {
		flags := cf(0); if i == len(chunks)-1 { flags = cf(FlagTerminal) }
		result[i] = &Fragment{MsgIDFull: id, FragIdx: uint8(i), FragCt: ct, Flags: flags, Dep: 0, Payload: ch}
	}
	return result
}

func (op *OverflowProtocol) Receive(frag *Fragment) []byte {
	if strings.Contains(string(frag.Payload), "R:ESTOP") { return frag.Payload }
	id := frag.MsgIDFull
	if op.buf[id] == nil { op.buf[id] = make(map[uint8]*Fragment) }
	op.buf[id][frag.FragIdx] = frag
	rcv := op.buf[id]; exp := int(frag.FragCt)
	switch {
	case op.Policy == LossPolicyAtomic || frag.IsCritical():
		if len(rcv) == exp { return op.reassemble(rcv, exp) }
	case op.Policy == LossPolicyGracefulDegradation:
		if frag.IsTerminal() && len(rcv) == exp { return op.reassemble(rcv, exp) }
		if frag.IsTerminal() { return op.reassemblePartial(rcv, exp) }
	default:
		if len(rcv) == exp { return op.reassemble(rcv, exp) }
	}
	return nil
}

func (op *OverflowProtocol) reassemble(rcv map[uint8]*Fragment, exp int) []byte {
	var r []byte
	for i := 0; i < exp; i++ { r = append(r, rcv[uint8(i)].Payload...) }
	return r
}

func (op *OverflowProtocol) reassemblePartial(rcv map[uint8]*Fragment, exp int) []byte {
	var r []byte
	for i := 0; i < exp; i++ {
		f, ok := rcv[uint8(i)]; if !ok { break }
		r = append(r, f.Payload...)
	}
	return r
}

func (op *OverflowProtocol) NACK(msgID uint16, expCt int) string {
	rcv := op.buf[msgID]
	var missing []string
	for i := 0; i < expCt; i++ {
		if _, ok := rcv[uint8(i)]; !ok { missing = append(missing, fmt.Sprintf("%d", i)) }
	}
	return fmt.Sprintf("A:NACK[MSG:%d∖[%s]]", msgID, strings.Join(missing, ","))
}
