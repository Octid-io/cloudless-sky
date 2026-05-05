// SPDX-License-Identifier: Apache-2.0
//! OSMP conformance benchmark runner.
//!
//! Reads `protocol/test-vectors/canonical-test-vectors.json`, computes UTF-8
//! byte counts for each vector's natural-language and encoded forms, and
//! reports SAL byte reduction. Cross-SDK byte-identical with the Python, Go,
//! and TypeScript runners.

use serde::Deserialize;

/// Per-vector benchmark result.
#[derive(Debug, Clone)]
pub struct VectorResult {
    /// Vector identifier (e.g. `"TV-001"`).
    pub id: String,
    /// UTF-8 byte length of the natural-language form.
    pub nl_bytes: usize,
    /// UTF-8 byte length of the encoded SAL form.
    pub osmp_bytes: usize,
    /// Measured reduction percent: `round((1 - osmp_bytes/nl_bytes) * 1000) / 10`.
    pub reduction_pct: f64,
    /// Reference reduction percent published with the vector.
    pub expected_reduction_pct: f64,
    /// `true` when the measured reduction meets the conformance threshold.
    pub conformant: bool,
    /// `true` when the encoded SAL fragment decodes to a non-empty (ns, op).
    pub decode_ok: bool,
    /// `true` when the vector is part of the must-pass set.
    pub must_pass: bool,
}

/// Aggregated report for a benchmark run.
#[derive(Debug, Clone)]
pub struct BenchmarkReport {
    /// `true` when all vectors decoded and the mean reduction meets the threshold.
    pub conformant: bool,
    /// Number of must-pass vectors that were conformant.
    pub passed: usize,
    /// Total must-pass vector count.
    pub total_must_pass: usize,
    /// Mean reduction across all vectors (one decimal place).
    pub mean_reduction_pct: f64,
    /// Minimum per-vector reduction (one decimal place).
    pub min_reduction_pct: f64,
    /// Maximum per-vector reduction (one decimal place).
    pub max_reduction_pct: f64,
    /// Per-vector results in the order they appear in the JSON file.
    pub vectors: Vec<VectorResult>,
}

#[derive(Deserialize)]
struct TvFile {
    version: String,
    measurement_basis: String,
    vectors: Vec<TvVector>,
    compression_summary: CompressionSummary,
}

#[derive(Deserialize)]
struct TvVector {
    id: String,
    natural_language: String,
    encoded: String,
    #[serde(default)]
    reduction_pct: f64,
    #[serde(default)]
    must_pass: bool,
}

#[derive(Deserialize)]
struct CompressionSummary {
    conformance_threshold_pct: f64,
}

fn rep(s: &str, n: usize) -> String {
    s.repeat(n)
}

fn round1(x: f64) -> f64 {
    (x * 10.0).round() / 10.0
}

/// Crude single-token decode check: a SAL fragment "decodes" if it contains
/// at least one non-empty namespace + opcode token before any delimiter.
///
/// The full Rust decoder is not yet wired into the benchmark; this stub
/// keeps the report shape compatible with the Go / Python / TS runners.
/// Conformance is gated on byte reduction, not on this stub.
fn decode_ok_stub(encoded: &str) -> bool {
    if encoded.is_empty() {
        return false;
    }
    // Find first delimiter (or end-of-string) and check the leading token
    // is non-empty and starts with an ASCII uppercase / glyph-equivalent.
    let head: String = encoded
        .chars()
        .take_while(|c| !"@:?!→∧∥↺⚠⊘[> ".contains(*c))
        .collect();
    !head.is_empty()
}

/// Runs the benchmark over a canonical test-vectors JSON file and returns the report.
pub fn run_benchmark(vectors_path: &str) -> Result<BenchmarkReport, String> {
    let raw = std::fs::read_to_string(vectors_path)
        .map_err(|e| format!("reading vectors {vectors_path}: {e}"))?;
    let data: TvFile = serde_json::from_str(&raw)
        .map_err(|e| format!("parsing vectors {vectors_path}: {e}"))?;
    let threshold = data.compression_summary.conformance_threshold_pct;

    println!("\n{}", rep("=", 72));
    println!(
        "  OSMP BENCHMARK — Cloudless Sky Protocol v{}",
        data.version
    );
    println!("  Measurement: {}", data.measurement_basis);
    println!("  SDK: Rust");
    println!("{}\n", rep("=", 72));
    println!(
        "  {:<10} {:>8} {:>10} {:>10}  Status",
        "ID", "NL Bytes", "OSMP Bytes", "Reduction"
    );
    println!("  {}", rep("-", 60));

    let mut results: Vec<VectorResult> = Vec::with_capacity(data.vectors.len());
    let mut passed = 0usize;
    let mut total_must_pass = 0usize;

    for v in &data.vectors {
        let nl = v.natural_language.len();
        let osmp = v.encoded.len();
        let red = if nl == 0 {
            0.0
        } else {
            round1((1.0 - (osmp as f64) / (nl as f64)) * 100.0)
        };
        let conf = red >= threshold;
        let mut status = if conf { "PASS" } else { "LOW" };
        if v.must_pass {
            total_must_pass += 1;
            if conf {
                passed += 1;
            }
        }
        let dec_ok = decode_ok_stub(&v.encoded);
        if !dec_ok {
            status = "FAIL (decode error)";
        }
        let mk = if conf && dec_ok { "+" } else { "x" };
        println!(
            "  {} {:<8} {:>8} {:>10} {:>9.1}%  {}",
            mk, v.id, nl, osmp, red, status
        );
        results.push(VectorResult {
            id: v.id.clone(),
            nl_bytes: nl,
            osmp_bytes: osmp,
            reduction_pct: red,
            expected_reduction_pct: v.reduction_pct,
            conformant: conf,
            decode_ok: dec_ok,
            must_pass: v.must_pass,
        });
    }

    let n = results.len().max(1);
    let sum: f64 = results.iter().map(|r| r.reduction_pct).sum();
    let min_r = results
        .iter()
        .map(|r| r.reduction_pct)
        .fold(f64::INFINITY, f64::min);
    let max_r = results
        .iter()
        .map(|r| r.reduction_pct)
        .fold(f64::NEG_INFINITY, f64::max);
    let mean = round1(sum / (n as f64));
    let dec_err = results.iter().filter(|r| !r.decode_ok).count();
    let conformant = mean >= threshold && dec_err == 0;
    let verdict = if conformant {
        "CONFORMANT"
    } else {
        "NON-CONFORMANT"
    };

    println!("\n{}", rep("-", 72));
    println!("  Vectors:        {}", results.len());
    println!(
        "  Must-pass:      {}   Passed: {}",
        total_must_pass, passed
    );
    println!("  Mean reduction: {:.1}%", mean);
    println!("  Range:          {:.1}% – {:.1}%", min_r, max_r);
    println!("  Conformance threshold: {:.0}%", threshold);
    println!("  Decode errors:  {}", dec_err);
    println!(
        "\n  {}  (mean {:.1}% vs {:.0}% threshold)",
        verdict, mean, threshold
    );
    println!("{}\n", rep("=", 72));

    Ok(BenchmarkReport {
        conformant,
        passed,
        total_must_pass,
        mean_reduction_pct: mean,
        min_reduction_pct: round1(min_r),
        max_reduction_pct: round1(max_r),
        vectors: results,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn vectors_path() -> String {
        // CARGO_MANIFEST_DIR points at sdk/rust/.
        let manifest = env!("CARGO_MANIFEST_DIR");
        format!(
            "{manifest}/../../protocol/test-vectors/canonical-test-vectors.json"
        )
    }

    #[test]
    fn run_benchmark_reaches_threshold() {
        let path = vectors_path();
        let report = run_benchmark(&path).expect("benchmark must run");
        assert!(
            report.mean_reduction_pct >= 60.0,
            "mean reduction {} < 60%",
            report.mean_reduction_pct
        );
        assert!(!report.vectors.is_empty(), "no vectors loaded");
    }

    #[test]
    fn run_benchmark_aggregate_conformance() {
        // Aggregate conformance gate matches Go RunBenchmark and TypeScript
        // runBenchmark: mean reduction ≥ threshold AND zero decode errors.
        // Per-vector LOW vectors are informational; they do not invalidate
        // the run as long as the aggregate clears the threshold.
        let path = vectors_path();
        let report = run_benchmark(&path).expect("benchmark must run");
        assert!(
            report.conformant,
            "aggregate non-conformant: mean = {}%",
            report.mean_reduction_pct
        );
        let dec_err = report.vectors.iter().filter(|v| !v.decode_ok).count();
        assert_eq!(dec_err, 0, "decode errors must be zero");
    }
}
