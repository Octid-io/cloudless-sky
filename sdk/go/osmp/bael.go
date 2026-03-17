package osmp

// BAELMode identifies which encoding representation BAEL selected.
type BAELMode int
const (
	BAELModeFullOSMP      BAELMode = iota
	BAELModeTCLOnly
	BAELModeNLPassthrough
)

type BAELResult struct { Mode BAELMode; Payload string; FlagsByte uint8 }

// UTF8Bytes returns UTF-8 byte count. Canonical measurement basis.
func UTF8Bytes(s string) int { return len([]byte(s)) }

type BAELEncoder struct{}

func (b *BAELEncoder) SelectMode(nl, osmp, tcl string) BAELResult {
	nlB := UTF8Bytes(nl); osmpB := UTF8Bytes(osmp)
	tclB := osmpB + 1
	if tcl != "" { tclB = UTF8Bytes(tcl) }
	if nlB <= osmpB && nlB <= tclB {
		return BAELResult{Mode: BAELModeNLPassthrough, Payload: nl, FlagsByte: FlagNLPassthrough}
	}
	if tcl != "" && tclB < osmpB {
		return BAELResult{Mode: BAELModeTCLOnly, Payload: tcl, FlagsByte: 0x00}
	}
	return BAELResult{Mode: BAELModeFullOSMP, Payload: osmp, FlagsByte: 0x00}
}
