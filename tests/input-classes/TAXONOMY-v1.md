# OSMP Composer Test — Input Class Taxonomy v1

**Status:** CTO/CLC calls baked in. Stratified by subject domain.
**Date:** 2026-04-26
**Purpose:** Define the test corpus for measuring composer rule coverage and LLM SAL acquisition. Stratification is by subject domain (how LLMs acquire SAL — as domain-coherent sublanguages) with syntactic shape as a within-domain coverage axis.

---

## Doctrine: scoring & policy

### Verdict buckets (mutually exclusive, in order of evaluation)

| Verdict | Definition | Acceptable? |
|---|---|---|
| **CORRECT** | Emitted SAL string matches an `expected_sal[]` variant or has equivalent opcode set + operator | YES — drive up |
| **SAFE_BRIDGE** | Partial SAL + NL residue; SAL portion is CORRECT subset; bridge_allowed for class | YES — log for tightening |
| **SAFE_PASSTHROUGH** | Composer returns None or NL_PASSTHROUGH for an unrecognized but well-formed input | YES — preferred over WRONG |
| **REFUSED_MALFORMED** | Composer rejects input as malformed (garbage/fragments/typos beyond fuzzy threshold) with explicit reason | YES — distinct signal from PASSTHROUGH |
| **REFUSED** | Model declines with explicit reason (LLM-only verdict) | YES — safe but unhelpful; track frequency |
| **INVALID** | SAL fails the validator (grammar, opcode existence, glyph rules) | NO — must be 0; composer or rule-comm bug |
| **WRONG** | Grammar-valid SAL whose opcode set / operator / target binds to a different action than the NL intent | NO — FATAL — must be 0 to ship |

### Bridge mode policy (CTO/CLC call, namespace-level)

Bridge mode = composer emits the high-confidence SAL portion + NL residue for the rest. Receiver acts on the SAL, surfaces the residue.

| Namespace | Bridge | Rationale |
|---|---|---|
| **E** (Environmental sensor) | allowed | Read-only; residue is context, no actuation risk |
| **H** (Health/clinical) — read | allowed | Read-only sensing; residue cannot misfire an action |
| **H** — alert/casrep | forbidden | Action-bearing (alert fires); residue may carry gating |
| **G** (Geospatial) | allowed | Read-only positioning; residue is context |
| **V** — read (POS/HDG/AIS) | allowed | Read-only |
| **V** — write (FLEET op, CSPOS update) | forbidden | Action-bearing |
| **W** (Weather) | allowed | Read-only |
| **N** (Network) — read (STS, RLY?) | allowed | Read-only |
| **N** — write (CFG, BK) | forbidden | Action-bearing; value/target essential |
| **O** (Operational context) | allowed | Metadata only |
| **Q** (Quality/eval) | allowed | Read-only |
| **X** — read (battery, voltage, freq) | allowed | Read-only |
| **R** (Robotic) | **forbidden** | All actuation; residue may gate or modify |
| **K** (Commerce) | **forbidden** | Financial action; residue may gate |
| **M** (Municipal/route) | **forbidden** | Action-bearing |
| **A** — read (PING, SUM) | allowed | Read-only |
| **A** — write (PROPOSE, BROADCAST) | forbidden | Action-bearing |
| **D** (Data) — read (Q, PULL) | allowed | Read-only |
| **D** — write (PUSH, CHUNK, DEL) | forbidden | Data mutation; payload essential |
| **S** (Crypto) — verify | allowed | Read-only verification |
| **S** — sign/encrypt/keygen | forbidden | State-changing crypto operation |
| **I** (Identity) — read (ID?) | allowed | Read-only check |
| **I:§** | n/a | Authorization precondition; never composed alone |
| **C** (Compute resources) | forbidden | Process control |
| **L** (Logging/alert) | forbidden | Alert is action-bearing; residue may gate |
| **T** (Time/scheduling) | forbidden | Schedule gates the action |
| **U** (User interaction) | forbidden | Notify/approve are action-bearing |
| **Y** (Memory) | forbidden | Mutation |
| **Z** (Inference) | forbidden | Inference is computation; parameters essential |
| **B** (Building) | forbidden | Alarm/sprinkler/HVAC are actuation |
| **F** (Flow) | forbidden | Flow control is action-bearing |
| **J** (Cognitive task) | forbidden | Handoff/decomp are workflow actions |
| **Ω** (Sovereign) | forbidden | Reserved; treat as action |

**Per-class override**: where bridge_allowed is in conflict (e.g., a sensing chip with a residue containing a conditional like "unless"), the per-class header wins. The composer must detect modifier markers ("unless", "only if", "except", "but not", "without", "after", "before", "while") in residue and downgrade bridge to passthrough when present in any class.

### CORRECT bar (CTO/CLC call)

**99% across all domains, all classes.** Lower-consequence inputs are typically higher-frequency, so unreliability there bleeds into user trust. No tier exemptions.

**WRONG = 0** is hard. INVALID = 0 is hard. Everything else is variable target.

---

## Domain stratification

Inputs grouped by subject domain (the LLM's mental model). Within each domain, the same syntactic shapes recur (simple read, targeted read, multi-read, conditional, action, chain) — this gives a 2D coverage matrix.

---

### Domain 1 — DEVICE_CONTROL

**Description:** Generic device actuation: turn on/off, lock/unlock, open/close, start/stop. R-namespace primitives + C-namespace process control.
**Primary namespaces:** R, C
**Bridge:** forbidden (all actuation)

```yaml
- nl: "stop the conveyor"
  expected_sal: ["R:STOP↻", "R:STOP↻@CONVEYOR"]
  shape: simple_action
- nl: "lock door D-7"
  expected_sal: ["R:LOCK↻@D-7"]
  shape: targeted_action
- nl: "restart the service"
  expected_sal: ["C:RSTRT"]
  shape: simple_action
- nl: "shutdown gateway 3"
  expected_sal: ["C:KILL@3", "R:STOP⊘@3"]
  shape: targeted_action
- nl: "stop pump and close valve"
  expected_sal: ["R:STOP↻@PUMP∧R:CLOSE↻@VALVE"]
  shape: chain_conjunctive
```

---

### Domain 2 — MESHTASTIC

**Description:** Mesh radio operations: ping, broadcast, peer discovery, channel ops, position broadcast. The protocol's native deployment context.
**Primary namespaces:** N, O, A (read), G (broadcast)
**Bridge:** allowed for read; forbidden for routing changes

```yaml
- nl: "ping node 17"
  expected_sal: ["A:PING@17"]
  shape: targeted_query
- nl: "discover peers"
  expected_sal: ["N:Q@*", "N:Q"]
  shape: simple_query
- nl: "broadcast my position"
  expected_sal: ["G:POS@*", "L:SEND@*[G:POS]"]
  shape: simple_action  # (broadcast IS action even though G is read)
- nl: "find primary relay"
  expected_sal: ["N:RLY?", "N:Q[RLY]"]
  shape: simple_query
- nl: "node status"
  expected_sal: ["N:STS", "N:STS?"]
  shape: simple_query
```

---

### Domain 3 — MEDICAL

**Description:** Clinical vitals reads, threshold-triggered alerts, casualty reports, identity verification with ICD codes.
**Primary namespaces:** H, I, U
**Bridge:** allowed for vitals reads; forbidden for alerts/casreps

```yaml
- nl: "blood pressure check"
  expected_sal: ["H:BP", "H:BP?"]
  shape: simple_query
- nl: "all vitals for patient 12"
  expected_sal: ["H:VITALS@12", "H:HR@12∧H:BP@12∧H:SPO2@12"]
  shape: targeted_multi_read
- nl: "alert me if heart rate exceeds 130"
  expected_sal: ["H:HR>130→H:ALERT", "H:HR>130→U:ALERT"]
  shape: conditional_alert
- nl: "casualty report if BP above 180"
  expected_sal: ["H:BP>180→H:CASREP"]
  shape: conditional_alert
- nl: "patient has pneumothorax, code J93.0"
  expected_sal: ["H:ICD[J930]", "H:ICD[J930]∧H:CASREP"]
  shape: parametric_action
```

---

### Domain 4 — UAV_TELEMETRY

**Description:** Drone operations: position, heading, altitude, speed, return-to-base, swarm formation. Hazard glyphs frequent (R:⚠ requires I:§).
**Primary namespaces:** V, R, G, I:§
**Bridge:** allowed for read (POS/HDG/AIS); forbidden for actuation

```yaml
- nl: "drone position"
  expected_sal: ["V:POS", "G:POS"]
  shape: simple_query
- nl: "return to base"
  expected_sal: ["R:RTB↻"]
  shape: simple_action
- nl: "move drone 1 to coordinates 35.7, -122.4"
  expected_sal: ["I:§→R:⚠MOV@DRONE1∧E:GPS[35.7,-122.4]", "R:MOV↻@DRONE1[35.7,-122.4]"]
  shape: authorized_targeted_action
- nl: "form swarm wedge with spacing 50"
  expected_sal: ["R:FORM↻[wedge,50]"]
  shape: parametric_action
- nl: "vehicle heading"
  expected_sal: ["V:HDG", "V:HDG?"]
  shape: simple_query
```

---

### Domain 5 — MOVEMENT_POSITIONING

**Description:** Generic spatial reads: position, heading, bearing, altitude, course, vector. Cross-cuts UAV/vehicle/marine but namespace is geospatial-generic.
**Primary namespaces:** G, V (read), R (read peripherals)
**Bridge:** allowed (read-only)

```yaml
- nl: "report location"
  expected_sal: ["G:POS", "G:POS?"]
  shape: simple_query
- nl: "report heading"
  expected_sal: ["G:BEARING", "G:BEARING?"]
  shape: simple_query
- nl: "position and heading"
  expected_sal: ["G:POS∧G:BEARING"]
  shape: multi_read
- nl: "vessel heading"
  expected_sal: ["V:HDG", "V:HDG?"]
  shape: simple_query  # (V-context for marine)
- nl: "altitude reading"
  expected_sal: ["G:POS", "G:POS?"]  # altitude is part of POS
  shape: simple_query
```

---

### Domain 6 — WEATHER

**Description:** Atmospheric measurements: wind, temperature, humidity, pressure. W-namespace + E-namespace overlap.
**Primary namespaces:** W, E (TH/HU/PU)
**Bridge:** allowed (sensing)

```yaml
- nl: "wind speed"
  expected_sal: ["W:WIND", "W:WIND?"]
  shape: simple_query
- nl: "wind speed at turbine 7"
  expected_sal: ["W:WIND@7", "W:WIND@7?"]
  shape: targeted_query
- nl: "barometric pressure"
  expected_sal: ["E:PU", "E:PU?", "W:PRESS"]
  shape: simple_query
- nl: "alert when wind exceeds 40"
  expected_sal: ["W:WIND>40→L:ALERT", "W:WIND>40→W:ALERT"]
  shape: conditional_alert
- nl: "report temp and humidity"
  expected_sal: ["E:TH∧E:HU", "E:EQ?TH:0∧?HU:0"]
  shape: multi_read
```

---

### Domain 7 — SENSOR_ARRAY

**Description:** Generic sensor reads, multi-sensor pulls, conditional alerts on sensor data. E-namespace primary.
**Primary namespaces:** E
**Bridge:** allowed for reads; forbidden for conditional-alert chains

```yaml
- nl: "read sensor 4A"
  expected_sal: ["E:TH@4A", "E:TH@4A?"]
  shape: targeted_query
- nl: "humidity reading"
  expected_sal: ["E:HU", "E:HU?"]
  shape: simple_query
- nl: "give me temp and humidity from sensor node 4A"
  expected_sal: ["E:TH@4A∧E:HU@4A", "E:EQ@4A?TH:0∧?HU:0"]
  shape: targeted_multi_read
- nl: "alert when humidity above 80"
  expected_sal: ["E:HU>80→U:NOTIFY", "E:HU>80→L:ALERT"]
  shape: conditional_alert
- nl: "air quality"
  expected_sal: ["E:EQ", "E:EQ?"]
  shape: simple_query
```

---

### Domain 8 — ROBOTIC_CAPABILITIES

**Description:** Robot-specific: emergency stop, return-to-base, formation, peripherals (camera/mic/speaker/light/haptic). R-namespace + R-mobile-peripherals.
**Primary namespaces:** R + R-peripherals (CAM, MIC, SPKR, TORCH, HAPTIC, etc.)
**Bridge:** forbidden (all actuation)

```yaml
- nl: "emergency stop"
  expected_sal: ["R:ESTOP", "R:ESTOP@*"]
  shape: emergency_action
- nl: "turn on the camera"
  expected_sal: ["R:CAM↻"]
  shape: simple_action
- nl: "activate haptic feedback"
  expected_sal: ["R:HAPTIC↻"]
  shape: simple_action
- nl: "turn on flashlight on node BRAVO"
  expected_sal: ["R:TORCH↻@BRAVO"]
  shape: targeted_action
- nl: "stop everything immediately, emergency"
  expected_sal: ["R:ESTOP", "R:ESTOP@*"]
  shape: emergency_action
```

---

### Domain 9 — CRYPTO_AUTH

**Description:** Cryptographic operations + identity verification. S-namespace + I-namespace.
**Primary namespaces:** S, I
**Bridge:** allowed for verify (read); forbidden for sign/encrypt/keygen (state-changing)

```yaml
- nl: "sign the payload"
  expected_sal: ["S:SIGN"]
  shape: simple_action
- nl: "generate a key pair, then sign the payload, then send to node BRAVO"
  expected_sal: ["S:KEYGEN;S:SIGN;D:PUSH@BRAVO"]
  shape: chain_sequential
- nl: "verify identity"
  expected_sal: ["I:ID", "A:VERIFY[I:ID]"]
  shape: simple_query
- nl: "encrypt this payload then send it to the central server"
  expected_sal: ["S:ENC;D:PUSH@CENTRAL"]
  shape: chain_sequential
- nl: "process payment but only if a human approves"
  expected_sal: ["I:§→K:PAY", "U:APPROVE→K:PAY"]
  shape: authorized_action
```

---

### Domain 10 — CONFIG_SCHEDULE

**Description:** Configuration changes + time-anchored operations. N:CFG + T:SCHED + N:BK.
**Primary namespaces:** N, T
**Bridge:** forbidden (values/anchors essential)

```yaml
- nl: "update config"
  expected_sal: ["N:CFG"]
  shape: simple_action
- nl: "set the threshold to 30"
  expected_sal: ["N:CFG[threshold:30]"]
  shape: parametric_action
- nl: "back up the database tonight at 2am"
  expected_sal: ["N:BK@2AM", "T:SCHED@2AM→N:BK"]
  shape: scheduled_action
- nl: "ping every 30 seconds"
  expected_sal: ["T:SCHED[30s]→A:PING"]
  shape: scheduled_chain
- nl: "expire this token in 1 hour"
  expected_sal: ["T:EXP[1h]"]
  shape: parametric_action
```

---

### Domain 11 — CONVERSATIONAL (out-of-scope)

**Description:** Pleasantries, jokes, opinions; no protocol mapping.
**Expected verdict:** SAFE_PASSTHROUGH

```yaml
- nl: "tell me a joke"
  expected_sal: []
- nl: "what's the weather like"  # ambiguous: could be Domain 6 OR conversational; lean toward W:WIND∧E:TH if "what's the weather" alone, passthrough otherwise
  expected_sal: []
- nl: "how are you"
  expected_sal: []
- nl: "thanks"
  expected_sal: []
- nl: "good morning"
  expected_sal: []
```

---

### Domain 12 — UNKNOWN_DOMAIN (out-of-scope, awaiting MDR)

**Description:** Real intents but no protocol coverage; passthrough until MDR fills the vocab.
**Expected verdict:** SAFE_PASSTHROUGH

```yaml
- nl: "order me a pepperoni pizza"
  expected_sal: []
- nl: "book a flight to Paris"
  expected_sal: []
- nl: "play some jazz"
  expected_sal: []
- nl: "remind me to buy milk"
  expected_sal: []
- nl: "translate this to French"
  expected_sal: []
```

---

### Domain 13 — MALFORMED (refuse, not passthrough)

**Description:** Garbage, fragments, typos beyond fuzzy threshold. Distinct from no-coverage passthrough — these are not real intents.
**Expected verdict:** REFUSED_MALFORMED

```yaml
- nl: "asdf qwerty"
  expected_sal: []
  expected_verdict: REFUSED_MALFORMED
- nl: "..."
  expected_sal: []
  expected_verdict: REFUSED_MALFORMED
- nl: "the"
  expected_sal: []
  expected_verdict: REFUSED_MALFORMED
- nl: "xyz123"
  expected_sal: []
  expected_verdict: REFUSED_MALFORMED
- nl: "{}"
  expected_sal: []
  expected_verdict: REFUSED_MALFORMED
```

---

## Corpus stats

- **13 domains** total (10 in-scope + 3 out-of-scope)
- **~65 inputs** total (5 per domain)
- **Each in-scope input has multi-variant `expected_sal[]`** to capture legitimate composition variation
- **Out-of-scope inputs have explicit `expected_verdict`** for unambiguous scoring

## Coverage matrix (within domain × syntactic shape)

| Shape | Domain coverage |
|---|---|
| simple_query | most in-scope domains |
| targeted_query | most in-scope domains |
| simple_action | actuation domains |
| targeted_action | actuation domains |
| multi_read | sensing domains |
| conditional_alert | medical, weather, sensor_array |
| chain_sequential | crypto_auth, config_schedule |
| chain_conjunctive | device_control |
| authorized_action | crypto_auth, UAV_telemetry |
| parametric_action | config_schedule, medical (ICD), robotic (formation) |
| emergency_action | robotic_capabilities |
| scheduled_action | config_schedule |

This is the foundation. Phase 1 (composer rule coverage) and Phases 2-4 (LLM behavioral testing) all score against this corpus.
