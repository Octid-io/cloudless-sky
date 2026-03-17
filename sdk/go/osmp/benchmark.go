package osmp

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"runtime"
)

type VectorResult struct {
	ID                   string
	NLBytes, OSMPBytes   int
	ReductionPct         float64
	Conformant, DecodeOk bool
	MustPass             bool
}

type BenchmarkReport struct {
	Conformant                             bool
	Passed, TotalMustPass                  int
	MeanReductionPct, MinReductionPct, MaxReductionPct float64
	Vectors                                []VectorResult
}

type tvFile struct {
	Version string `json:"version"`
	MeasurementBasis string `json:"measurement_basis"`
	Vectors []struct {
		ID              string  `json:"id"`
		NaturalLanguage string  `json:"natural_language"`
		Encoded         string  `json:"encoded"`
		ReductionPct    float64 `json:"reduction_pct"`
		MustPass        bool    `json:"must_pass"`
	} `json:"vectors"`
	CompressionSummary struct {
		ConformanceThresholdPct float64 `json:"conformance_threshold_pct"`
	} `json:"compression_summary"`
}

func defaultVectorsPath() string {
	_, file, _, ok := runtime.Caller(0)
	if !ok { return "protocol/test-vectors/canonical-test-vectors.json" }
	return filepath.Join(filepath.Dir(file), "..", "..", "..", "protocol", "test-vectors", "canonical-test-vectors.json")
}

func rep(s string, n int) string {
	r := ""
	for i := 0; i < n; i++ { r += s }
	return r
}

func RunBenchmark(vectorsPath string) (BenchmarkReport, error) {
	if vectorsPath == "" { vectorsPath = defaultVectorsPath() }
	raw, err := os.ReadFile(vectorsPath)
	if err != nil { return BenchmarkReport{}, fmt.Errorf("reading vectors: %w", err) }
	var data tvFile
	if err := json.Unmarshal(raw, &data); err != nil { return BenchmarkReport{}, err }

	dec := NewDecoder(nil)
	threshold := data.CompressionSummary.ConformanceThresholdPct
	var results []VectorResult
	passed, totalMP := 0, 0

	fmt.Printf("\n%s\n  OSMP BENCHMARK — Cloudless Sky Protocol v%s\n  Measurement: %s\n  SDK: Go\n%s\n\n",
		rep("=",72), data.Version, data.MeasurementBasis, rep("=",72))
	fmt.Printf("  %-10s %8s %10s %10s  %s\n", "ID", "NL Bytes", "OSMP Bytes", "Reduction", "Status")
	fmt.Printf("  %s\n", rep("-",60))

	for _, v := range data.Vectors {
		nlB   := UTF8Bytes(v.NaturalLanguage)
		osmpB := UTF8Bytes(v.Encoded)
		red   := math.Round((1-float64(osmpB)/float64(nlB))*1000) / 10
		conf  := red >= threshold
		status := "PASS"; if !conf { status = "LOW" }
		if v.MustPass { totalMP++; if conf { passed++ } }
		decOk := false
		r, er := dec.DecodeFrame(v.Encoded)
		if er == nil && r.Namespace != "" && r.Opcode != "" { decOk = true } else if er != nil { status = "FAIL (decode error)" }
		mk := "✓"; if !conf || !decOk { mk = "✗" }
		fmt.Printf("  %s %-8s %8d %10d %9.1f%%  %s\n", mk, v.ID, nlB, osmpB, red, status)
		results = append(results, VectorResult{ID:v.ID, NLBytes:nlB, OSMPBytes:osmpB, ReductionPct:red, Conformant:conf, DecodeOk:decOk, MustPass:v.MustPass})
	}

	sum := 0.0; minR := math.MaxFloat64; maxR := -math.MaxFloat64
	for _, r := range results { sum += r.ReductionPct; if r.ReductionPct < minR { minR = r.ReductionPct }; if r.ReductionPct > maxR { maxR = r.ReductionPct } }
	mean := math.Round(sum/float64(len(results))*10) / 10
	decErr := 0; for _, r := range results { if !r.DecodeOk { decErr++ } }
	conformant := mean >= threshold && decErr == 0
	verdict := "CONFORMANT ✓"; if !conformant { verdict = "NON-CONFORMANT ✗" }

	fmt.Printf("\n%s\n  Vectors: %d\n  Must-pass: %d   Passed: %d\n  Mean: %.1f%%  Range: %.1f%% – %.1f%%\n  Threshold: %.0f%%  Decode errors: %d\n\n  %s  (mean %.1f%% vs %.0f%% threshold)\n%s\n\n",
		rep("─",72), len(results), totalMP, passed, mean, minR, maxR, threshold, decErr, verdict, mean, threshold, rep("=",72))

	return BenchmarkReport{Conformant:conformant, Passed:passed, TotalMustPass:totalMP,
		MeanReductionPct:mean, MinReductionPct:math.Round(minR*10)/10, MaxReductionPct:math.Round(maxR*10)/10,
		Vectors:results}, nil
}
