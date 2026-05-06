# Macros — Catalog

This page enumerates every macro shipping in the OSMP SDKs. The two corpora — Meshtastic (16) and EML (89) — register against the same macro architecture (`A:MACRO[name]` invocation, deterministic dictionary expansion at the receiver, slot-fill at composition time).

> See the [README Macros section](../README.md#macros) for the architectural overview, custom-registry pattern, and FNP basis-fingerprint compatibility.

---

## Meshtastic — 16 macros

Pre-validated SAL templates for [Meshtastic](https://meshtastic.org/) protobuf telemetry over LoRa. Bundled with `osmp-mcp` at `osmp_mcp/data/meshtastic-macros.json`.

| Macro | Description | Slots |
|---|---|---|
| `MESH:DEV` | Meshtastic DeviceMetrics telemetry (portnum 67) | `battery_level`, `voltage`, `channel_util`, `air_util`, `uptime` |
| `MESH:ENV` | Meshtastic EnvironmentMetrics basic (portnum 67) | `temperature`, `humidity`, `pressure` |
| `MESH:AQ` | Meshtastic AirQualityMetrics (portnum 67) | `pm25`, `pm10`, `co2` |
| `MESH:PWR` | Meshtastic PowerMetrics (portnum 67) | `ch1_v`, `ch2_v`, `ch3_v`, `ch1_a`, `ch2_a`, `ch3_a` |
| `MESH:HLTH` | Meshtastic HealthMetrics (portnum 67) | `heart_bpm`, `spO2`, `temperature` |
| `MESH:STAT` | Meshtastic LocalStats (portnum 67) | `packets_tx`, `packets_rx`, `rx_bad`, `online_nodes`, `total_nodes`, `noise_floor` |
| `MESH:POS` | Meshtastic Position (portnum 3) | `latitude`, `longitude`, `altitude`, `time` |
| `MESH:NODE` | Meshtastic NodeInfo (portnum 4) | `long_name`, `hw_model`, `firmware`, `role`, `has_wifi` |
| `MESH:ACK` | Meshtastic message acknowledgment (portnum 1) | `msg_id` |
| `MESH:ALRT` | Meshtastic Alert (portnum 11) | `alert_text`, `timestamp` |
| `MESH:TRACE` | Meshtastic Traceroute (portnum 70) | `route_nodes`, `hop_count` |
| `MESH:WPT` | Meshtastic Waypoint (portnum 8) | `lat`, `lon`, `name`, `expire` |
| `MESH:TALRT` | Temperature threshold alert rule | `threshold` |
| `MESH:BATLO` | Battery low threshold alert rule | `threshold` |
| `MESH:NOFF` | Node offline detection rule | `node_id` |
| `MEDEVAC` | Clinical MEDEVAC chain template — heart-rate threshold to casualty report to broadcast evacuation | `dx_code`, `target` |

### Example: MEDEVAC chain template

```
H:ICD[{dx_code}]→H:CASREP∧M:EVA@{target}
```

Slots: `?`, `?`

---

## EML MDR — 89 macros

Pre-built `eml(x, y) = exp(x) − ln(y)` chain templates for 89 specific functions across 9 function classes. Cross-SDK byte-identical across Python, TypeScript, Go, and Rust.

| Field | Meaning |
|---|---|
| **Shorthand ID** | 3-character ASCII identifier used in `A:MACRO[name]` invocation |
| **Function class** | Taxonomy bucket (compound_arithmetic, scientific, nn_activation, linalg, trigonometric, complex_arithmetic, nn_layer, numerical_method, special_function) |
| **Precision class** | `faithful_1ulp` (fast/fdlibm-derived, 1 ULP), `correctly_rounded_0ulp` (precision/crlibm, commercial), or `envelope_bounded` (verified within documented tolerance) |
| **Variant** | `single_output`, `multi_output`, `sender_preprocessed`, or `envelope_bounded` |
| **Fingerprint membership** | `in_bit_exact_corpus` (86 macros) or `separate_envelope_corpus` (3 macros) |

### Compound Arithmetic (35)

| ID | Description | Precision | Variant |
|---|---|---|---|
| `ABS` | \|x\| = sqrt(x^2) | fast (1 ULP) | single output |
| `ADD` | x + y | fast (1 ULP) | single output |
| `CBT` | cbrt(x) = x^(1/3) (sender provides third=1/3) | fast (1 ULP) | single output |
| `CSH` | cosh(x) | fast (1 ULP) | single output |
| `CUB` | x^3 | fast (1 ULP) | single output |
| `DIV` | x / y (= eml(ln(x), y)) | fast (1 ULP) | single output |
| `EE2` | exp(exp(x)) | fast (1 ULP) | single output |
| `EE3` | exp(exp(exp(x))) | fast (1 ULP) | single output |
| `EE4` | exp^4(x) | fast (1 ULP) | single output |
| `EE5` | exp^5(x) | fast (1 ULP) | single output |
| `EEM` | e - exp(x) | fast (1 ULP) | single output |
| `EEX` | e^e / x | fast (1 ULP) | single output |
| `ELN` | exp(x) - ln(x) | fast (1 ULP) | single output |
| `EM1` | exp(x) - 1 | fast (1 ULP) | single output |
| `EME` | exp(x) - e | fast (1 ULP) | single output |
| `EMX` | exp(x) - x | fast (1 ULP) | single output |
| `EOX` | e/x | fast (1 ULP) | single output |
| `ESX` | e - x | fast (1 ULP) | single output |
| `EXP` | exp(x) = eml(x, 1) | fast (1 ULP) | single output |
| `IDN` | identity(x) | fast (1 ULP) | single output |
| `LIN` | y = a*x + b (linear calibration) | fast (1 ULP) | single output |
| `LL2` | ln(ln(x)) | fast (1 ULP) | single output |
| `LL3` | ln^3(x) = ln(ln(ln(x))) | fast (1 ULP) | single output |
| `LOG` | ln(x) = eml(1, eml(eml(1,x), 1)) | fast (1 ULP) | single output |
| `MUL` | x * y | fast (1 ULP) | single output |
| `MXY` | max(x, y) via smooth-max | fast (1 ULP) | single output |
| `NEG` | negation -y | fast (1 ULP) | single output |
| `OML` | 1 - ln(x) | fast (1 ULP) | single output |
| `POW` | x^y = exp(y * ln(x)) | fast (1 ULP) | single output |
| `SNH` | sinh(x) | fast (1 ULP) | single output |
| `SQR` | x^2 | fast (1 ULP) | single output |
| `SQT` | sqrt(x) = x^0.5 (sender provides half=0.5) | fast (1 ULP) | single output |
| `SUB` | x - y | fast (1 ULP) | single output |
| `TNH` | tanh(x) | fast (1 ULP) | single output |
| `ZER` | zero (x-independent) | fast (1 ULP) | single output |

### Scientific (19)

| ID | Description | Precision | Variant |
|---|---|---|---|
| `BES` | Bose-Einstein 1/(exp((E-mu)/kT) - 1) | fast (1 ULP) | single output |
| `BOL` | Boltzmann factor exp(-E/kT) | fast (1 ULP) | single output |
| `BRN` | Bernoulli pressure (envelope-limited + M1 sender-preprocessed) | envelope-bounded | envelope bounded |
| `BWR` | Breit-Wigner resonance (sender-preprocessed delta_E) | fast (1 ULP) | single output |
| `CDP` | classical Doppler f * (v_wave + v_r)/(v_wave + v_s) | fast (1 ULP) | single output |
| `CLB` | Coulomb force k * q1 * q2 / r^2 | fast (1 ULP) | single output |
| `DOP` | Relativistic Doppler shift | fast (1 ULP) | single output |
| `FDR` | Fermi-Dirac 1/(exp((E-mu)/kT) + 1) | fast (1 ULP) | single output |
| `FRD` | Friedmann H^2(z) | fast (1 ULP) | single output |
| `HAD` | Hadamard quantum gate (envelope-bounded) | envelope-bounded | multi output |
| `LRZ` | Lorentz gamma 1/sqrt(1 - beta^2) | fast (1 ULP) | single output |
| `MXB` | Maxwell-Boltzmann speed distribution | fast (1 ULP) | single output |
| `ORV` | orbital velocity sqrt(GM/r) | fast (1 ULP) | single output |
| `PLK` | Planck blackbody (sender provides hnu/kT) | fast (1 ULP) | single output |
| `RCC` | RC charging V0*(1 - exp(-t/tau)) | fast (1 ULP) | single output |
| `REN` | relativistic energy gamma * m * c^2 | fast (1 ULP) | single output |
| `RLC` | RLC resonance frequency (envelope-limited; LC > 1) | envelope-bounded | envelope bounded |
| `SHR` | Sharpe ratio (R_p - R_f)/sigma | fast (1 ULP) | single output |
| `STB` | Stefan-Boltzmann scaled L/L_sun | fast (1 ULP) | single output |

### Nn Activation (10)

| ID | Description | Precision | Variant |
|---|---|---|---|
| `ELU` | ELU (smooth approx, k controls switch sharpness) | fast (1 ULP) | single output |
| `GLU` | GELU approx (x * sigmoid(coef*x)) | fast (1 ULP) | single output |
| `LRL` | Leaky ReLU | fast (1 ULP) | single output |
| `LSX` | log-softmax3 (3-class) | fast (1 ULP) | multi output |
| `MSH` | Mish = x * tanh(softplus(x)) | fast (1 ULP) | single output |
| `RLU` | ReLU(x) = (x+\|x\|)/2 | fast (1 ULP) | single output |
| `SIG` | sigmoid(x) = 1/(1+exp(-x)) | fast (1 ULP) | single output |
| `SPL` | softplus(x) = ln(1+exp(x)) | fast (1 ULP) | single output |
| `SWS` | Swish/SiLU = x * sigmoid(x) | fast (1 ULP) | single output |
| `SX3` | softmax3 (3-class) | fast (1 ULP) | multi output |

### Linalg (8)

| ID | Description | Precision | Variant |
|---|---|---|---|
| `CMP` | 2x2 characteristic polynomial (det, trace) | fast (1 ULP) | multi output |
| `CP3` | 3D cross product | fast (1 ULP) | multi output |
| `DT2` | 2x2 determinant ad - bc | fast (1 ULP) | single output |
| `INV` | 2x2 matrix inverse | fast (1 ULP) | multi output |
| `MMG` | 3x3 matrix multiplication (9 components) | fast (1 ULP) | multi output |
| `MMP` | 2x2 matrix multiplication | fast (1 ULP) | multi output |
| `QML` | quaternion multiplication | fast (1 ULP) | multi output |
| `TR3` | trace of 3x3 matrix | fast (1 ULP) | single output |

### Trigonometric (5)

| ID | Description | Precision | Variant |
|---|---|---|---|
| `ATA` | atan(x) Taylor (principal-domain) | fast (1 ULP) | sender preprocessed |
| `COS` | cos(x) Taylor (principal-domain) | fast (1 ULP) | sender preprocessed |
| `RRT` | range-reduced sin (K1 protocol; full-domain modulo 2pi at sender) | fast (1 ULP) | sender preprocessed |
| `SCH` | sin Chebyshev-equivalent (degree-11 polynomial; principal-domain after sender preproc) | fast (1 ULP) | sender preprocessed |
| `SIN` | sin(x) Taylor (principal-domain) | fast (1 ULP) | sender preprocessed |

### Complex Arithmetic (4)

| ID | Description | Precision | Variant |
|---|---|---|---|
| `CAB` | complex magnitude sqrt(a^2 + b^2) | fast (1 ULP) | single output |
| `CIM` | complex mul Im part: ad + bc | fast (1 ULP) | single output |
| `CMU` | complex multiplication (Re, Im) as multi-output pair | fast (1 ULP) | multi output |
| `CRE` | complex mul Re part: ac - bd | fast (1 ULP) | single output |

### Nn Layer (4)

| ID | Description | Precision | Variant |
|---|---|---|---|
| `ATM` | attention 2-head (score_head1, score_head2) | fast (1 ULP) | multi output |
| `ATN` | attention score = exp(q*k/sqrt(d)) | fast (1 ULP) | single output |
| `DEN` | dense forward scalar (no activation): w*x + b | fast (1 ULP) | single output |
| `LST` | LSTM cell scalar update (h_new, c_new) | fast (1 ULP) | multi output |

### Numerical Method (3)

| ID | Description | Precision | Variant |
|---|---|---|---|
| `LRP` | linear interpolation a + t*(b-a) | fast (1 ULP) | single output |
| `NEW` | Newton-Raphson step x - f(x)/f'(x) | fast (1 ULP) | single output |
| `SIM` | Simpson quadrature fragment | fast (1 ULP) | single output |

### Special Function (1)

| ID | Description | Precision | Variant |
|---|---|---|---|
| `ERF` | erf(x) Taylor (sender-bounded \|x\|<=1.5) | fast (1 ULP) | sender preprocessed |

---

## Custom registries

The macro architecture is open. Any operator can ship a custom corpus with the same `(shorthand_id, chain_template, function_class, precision_class)` shape. Register at runtime via the SDK's `MacroRegistry` (Python) / `MacroRegistry` (Go) / `MacroRegistry` (TypeScript) / equivalent Rust types.

Per-corpus fingerprints flow through the FNP handshake automatically. Two peers with equal basis fingerprints unlock SAIL binary mode and exchange macro-bound traffic byte-identically; peers with different bases fall back to SAL while preserving full semantic round-trip.

---

*Last regenerated from canonical Python `osmp.eml_mdr.REGISTRY` and `mdr/meshtastic/meshtastic-macros.json`. Updates to either source require a corresponding refresh of this catalog.*
