package main

import (
	"fmt"
	"os"
	"github.com/octid/cloudless-sky/sdk/go/osmp"
)

func main() {
	path := ""
	if len(os.Args) > 1 { path = os.Args[1] }
	r, err := osmp.RunBenchmark(path)
	if err != nil { fmt.Fprintln(os.Stderr, err); os.Exit(2) }
	if r.Conformant { os.Exit(0) }
	os.Exit(1)
}
