// Brigade base helpers — opcode-existence check via active ASD.
//
// Faithful Go port of sdk/python/osmp/brigade/base_helpers.py.
package brigade

import "github.com/octid-io/cloudless-sky/sdk/go/osmp"

// OpcodeExists checks whether namespace:opcode is in the active ASD.
// Stations should consult this before proposing — emitting SAL with an
// opcode that doesn't exist in the loaded dictionary will fail validation
// AND signals to the receiver an action it cannot dispatch.
func OpcodeExists(namespace, opcode string) bool {
	ops, ok := osmp.ASDFloorBasis[namespace]
	if !ok {
		return false
	}
	_, exists := ops[opcode]
	return exists
}

// AllOpcodes returns all opcodes in a namespace from the active ASD.
func AllOpcodes(namespace string) []string {
	ops, ok := osmp.ASDFloorBasis[namespace]
	if !ok {
		return nil
	}
	out := make([]string, 0, len(ops))
	for op := range ops {
		out = append(out, op)
	}
	return out
}
