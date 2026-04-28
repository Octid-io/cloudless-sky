# MDR Handoff — OILGAS (Oil & Gas / Energy / Pipeline) domain

**Status:** Ready for parallel build.
**Author:** CTO/CLC (Claude) — 2026-04-27
**Owner:** Whoever picks this up (or MDR-creation agent once built).

---

## Goal

Build an Oil & Gas MDR for OSMP covering offshore drilling operations, onshore production (Permian / Eagle Ford / South Texas / Bakken / Marcellus / etc.), midstream pipeline operations, valve control, custody transfer, flare/vent monitoring, and the compliance reference data tied to each. This is a high-fit deployment domain for OSMP because the substrate matches: rigs and remote production sites operate over satellite links (VSAT, Starlink, Inmarsat L-band fallback) where bandwidth is metered, latency varies, and weather degrades connectivity. SAL's compression-positive wire footprint and the Overflow Protocol's policy-aware fragmentation are direct value-adds over JSON/REST telemetry on those links.

---

## Scope

**In-scope** for OILGAS MDR:

**Upstream — drilling and well construction:**
- Rig telemetry: hook load, weight on bit (WOB), rotary RPM, surface torque, standpipe pressure, mud flow rate (in/out), mud weight, mud temperature, mud resistivity, gas in/out
- Wellbore state: hole depth, bit depth, hole angle, dogleg severity, pit volume totals, flow show, kick indicators
- BOP (Blowout Preventer): annular state, pipe ram state, blind shear ram state, accumulator pressure, choke/kill manifold positions
- Rig motion (offshore): heave, pitch, roll, draft, dynamic positioning thruster status
- Helideck: status (open/closed), wind limits, last landing/takeoff
- Crew safety: H2S detection, combustible gas (LEL%), muster station status, lifeboat readiness
- Power: generator status, fuel level, switchboard load

**Upstream — production:**
- Wellhead: tubing pressure (TP), casing pressure (CP), flowline temperature, choke setting, gas-oil ratio (GOR), water cut
- Artificial lift: rod pump (SPM/stroke length), ESP (pump speed/intake pressure/motor temp), gas lift (injection rate/pressure)
- Production accounting: barrels per day (BBL/d), MCF per day (gas), water cut, downtime events
- Tank battery: level (radar/ultrasonic), temperature, water-oil interface, vapor pressure
- LACT (Lease Automatic Custody Transfer): batch volume, gravity (API), BS&W (basic sediment & water), meter factor

**Midstream — pipeline operations:**
- Pipeline state: flow rate, pressure (suction/discharge/intermediate), temperature, density, viscosity
- Compressor station: stage suction/discharge pressure, stage temperatures, vibration, RPM, gas analyzer (BTU/CO2/H2S/H2O)
- Pump station: suction/discharge pressure, motor amps, pump RPM, vibration
- Pig operations: launcher state (loaded/launched), pig signals (passage events with timestamps), receiver state
- Leak detection: DAS (distributed acoustic sensing) anomaly, mass-balance imbalance, pressure-wave detection, OGI (optical gas imaging) reading
- Cathodic protection: pipe-to-soil potential, rectifier output, anode current
- Class location (PHMSA): class 1–4 designation, HCA (high consequence area) flag, MAOP (maximum allowable operating pressure)

**Valve control (across upstream and midstream):**
- Emergency Shutdown (ESD): trip cause, valve state per zone, time to safe state
- Surface Safety Valves (SSV) and Subsurface Safety Valves (SSSV)
- Motor-Operated Valves (MOV): position (open/close/intermediate), torque, motor current
- Choke valves: position percent, upstream/downstream pressure, calculated flow coefficient (Cv)
- Block-and-bleed: status of double-block-and-bleed configuration, leak indicator on bleed line
- Pressure Safety Valves (PSV) / Relief: lift events, set pressure, last bench test date

**Flare and vent:**
- Flare: pilot status, flame status, smokeless operation indicator, vent gas composition, mass flow to flare
- Vent stack: composition (methane fraction), volume, dispersion model state
- Combustor: temperature, residence time, destruction-removal efficiency (DRE)

**Weather and environmental (operations-affecting):**
- Hurricane/cyclone: track, category, distance, ETA, evacuation trigger
- Sea state: significant wave height, peak period, wind speed (offshore)
- Lightning proximity (rig and tank battery shutdown trigger)
- Temperature (cold-weather operations: freeze protection, slug catcher heat tracing)
- Air permit envelope (NOx, VOC, methane caps under EPA OOOOa/b)

**Crew and ops:**
- Crew change events (helicopter manifest)
- Permit-to-work state (hot work, confined space, lockout-tagout)
- Incident logging (NPT, near-miss, recordable, lost-time)

**Out-of-scope** (defer or use other namespaces):
- Hydrocarbon trading and physical-financial reconciliation (use K namespace per ISO 20022)
- Land/lease/title (use I namespace; surface use agreements separate workstream)
- Detailed reservoir engineering (modeling and simulation are not protocol layer)
- Refinery downstream operations (separate domain — RFM MDR if/when warranted)
- Subsurface seismic acquisition (massive data volumes, wrong substrate for OSMP)

---

## Substrate fit and connectivity considerations

This is a domain where the substrate constraints argue for OSMP rather than against it. The handoff document captures the substrate fit explicitly because the deployment economics depend on it.

**VSAT (Ku/Ka band geostationary):** Standard rig comms link. Bandwidth metered (typical commitment 1–4 Mbps shared; bursting expensive). Rain fade on Ku band can drop link 4–10 dB during storms; Ka band more severe. SAL's 86.8% reduction vs JSON on equivalent payloads is direct cost reduction on metered link.

**Starlink (LEO Ku/Ka):** Increasing deployment offshore and at remote pads. Better latency than VSAT (~50 ms vs ~600 ms), less rain fade on most weather, but degrades during heavy precipitation and is sensitive to obstructed sky view (cargo, structure, helideck activity). SAL's policy-tagged fragments under OSMP Overflow Protocol let critical telemetry survive a Starlink degradation while non-critical drops to graceful-degradation policy.

**Inmarsat L-band (Fleet Xpress, BGAN):** Safety/regulatory fallback; very low bandwidth (kbps) but high availability (rain-tolerant). The 51-byte LoRa floor that OSMP's BAEL targets translates directly to L-band: a kick alert or ESD trigger can survive even when the high-bandwidth links are down.

**In-field SCADA over LoRa / ISA100 / WirelessHART:** Wellhead RTUs, valve actuators, leak detection sensors. SAL's frame-level grammar maps cleanly to SCADA poll/response patterns; the OSMP Adaptive Shared Dictionary versioning lets a fleet of RTUs share an evolving vocabulary without per-vendor schema rewrites.

**4G/5G in shale plays:** Permian, Eagle Ford, Bakken, Marcellus mostly have decent terrestrial coverage. SAL's compression still pays in volume (millions of polls/day across thousands of wellheads), but the bandwidth pressure is lower than offshore.

**The pitch in one line:** OSMP runs on the lowest link the rig has, with policy-graded delivery so that ESD trips and kick alerts get through even when the production telemetry has been throttled.

---

## Namespace assignment

**Recommend new namespace `Π` (Pi, Greek)** — Petroleum / Pipeline / Hydrocarbon Operations. Parallels the Α (Alpha) namespace proposed for Agriculture. Greek-letter sovereign extensions per OSMP-SPEC §X-O are the established convention for vertical-domain namespaces.

Alternative — extend existing `X` (Energy) namespace: X is currently grid-electrical (DR, CHG, FAULT, FREQ, GRD, ISLND, STORE, VOLT, WND, PROD). Folding hydrocarbon operations into X is mechanically possible but conflates electrical-energy-grid and hydrocarbon-production semantics. Disambiguating downstream (consumers asking "is this an electric grid frequency or a gas compressor frequency?") becomes a station-side problem.

Alternative — split across multiple existing namespaces: pipelines could go into a hypothetical pipeline namespace, valves into R, sensing into E, weather into W, etc. This is the maximally-distributed approach and produces the worst discoverability for an O&G operator browsing the dictionary.

**Recommend:** dedicated `Π` namespace for hydrocarbon-operations-specific opcodes (rig, well, pipeline, custody transfer, BOP, flare, ESD as O&G-specific). Reuse of existing namespaces for crossover concepts:
- E:* — sensor telemetry that's environmentally generic (temp, pressure) vs O&G-specific (mud weight, gas reading)
- W:* — weather, sea state, hurricane tracking
- R:* — physical actuators that are generic robotic (move, return) vs O&G-specific (BOP ram, choke valve, MOV)
- M:* — emergency response, evacuation routing
- L:* — compliance audit logging
- U:* — crew alerting

The cross-namespace pattern is the same as Agriculture (Α + reuse of E/W/R/T/G).

---

## Authoritative reference lists

### 1. Operational standards and protocols

| Source | What it covers | URL / Reference |
|---|---|---|
| **API 14C** | Offshore production safety systems (PSV, ESD, fire/gas) | API Recommended Practice 14C, 8th ed. |
| **API 510 / 570 / 653** | Pressure vessel / piping / tank inspection | API codes, ASME-aligned |
| **API 6A / 17D / 17F** | Wellhead, subsea wellhead, subsea production controls | API specs |
| **API RP 1167** | Pipeline control room management | API RP, PHMSA-incorporated |
| **API 5L / 5CT** | Line pipe / casing+tubing specs | API specs |
| **ISO 13628** | Subsea production systems | ISO/TS 13628 series |
| **ISO 10417** | Subsurface safety valves | ISO 10417:2004 |
| **ISO 15156 / NACE MR0175** | Sour service materials (H2S environments) | ISO/NACE joint |
| **NACE / AMPP CP standards** | Cathodic protection | NACE SP0169 (external), SP0285 (internal) |
| **IEC 61508 / 61511** | Functional safety / SIL-rated SIS | IEC standards |
| **PIDX** | Petroleum industry data exchange standards | PIDX International |
| **WITSML / PRODML / RESQML** | Energistics drilling/production/reservoir XML | Energistics standards |
| **OPC UA Companion for Oil & Gas** | OPC Foundation companion specs | OPC UA |

### 2. Regulatory references

| Jurisdiction | Source | Coverage |
|---|---|---|
| **US — pipelines** | PHMSA 49 CFR Part 192 (gas) / 195 (liquid) | Pipeline operations, integrity, reporting |
| **US — Texas** | Texas RRC Statewide Rules | Permitting, production reporting, plugging |
| **US — offshore** | BSEE 30 CFR Part 250 | Offshore drilling and production |
| **US — offshore** | BOEM Notices to Lessees (NTLs) | Lease compliance |
| **US — methane / VOC** | EPA 40 CFR Part 60 Subpart OOOO / OOOOa / OOOOb | New source performance standards |
| **US — GHG reporting** | EPA 40 CFR Part 98 Subpart W | Onshore production GHG |
| **US — OSHA** | 29 CFR 1910.119 (PSM) | Process Safety Management |
| **US — HCA mapping** | PHMSA HCA tool | High consequence area designation |
| **US — leak detection** | PHMSA Pipeline Safety Reform LDR | Mandatory leak detection on liquid lines |
| **UK** | HSE Offshore (PFEER, MAR) | Offshore safety |
| **AU** | NOPSEMA OPGGS regulations | Australian offshore |
| **NO** | PSA-NO regulations | Norwegian offshore |
| **CA** | CER (Canada Energy Regulator) | Pipeline + offshore |

### 3. Industry data dictionaries (for MDR cross-resolution)

| Source | What it provides | Notes |
|---|---|---|
| **PPDM** (Professional Petroleum Data Management) | Master well/license/agreement data model | Industry standard upstream |
| **PIDX Codes** | Trading partner codes, service codes | E-commerce in oilfield |
| **Energistics WITSML log curves** | Standardized drilling channel names | Curve mnemonics like SPP, ROP, WOB |
| **API RP 4G** | Mast and substructure inspection | Reference codes |
| **OGUK Process Safety KPIs** | UK upstream lagging/leading indicators | Tier 1/2/3/4 events |

These dictionaries are candidates for downstream MDR `.dpack` builds (parallel to ICD-10-CM and ISO 20022). The first such candidate is **WITSML log curves** because the curve mnemonics (SPP, WOB, RPM, MWT, MFI, MFO, MD, BD, HKLD, GASIN, GASOUT, etc.) are widely standardized and a 200–500-entry MDR would resolve a large fraction of drilling-floor telemetry.

---

## Proposed opcode catalog

Approximately 40 opcodes split across drilling, production, midstream, valve control, flare/vent, and incident. Plus reuse of existing namespaces for crossover concepts.

### Drilling (rig and well construction)

| Opcode | Definition | Source |
|---|---|---|
| Π:RIG | rig_state_summary | API 14C |
| Π:WOB | weight_on_bit | WITSML |
| Π:HKLD | hook_load | WITSML |
| Π:RPM | rotary_RPM | WITSML |
| Π:TRQ | surface_torque | WITSML |
| Π:SPP | standpipe_pressure | WITSML |
| Π:MWT | mud_weight | WITSML |
| Π:MFI | mud_flow_in | WITSML |
| Π:MFO | mud_flow_out | WITSML |
| Π:PIT | pit_volume_total | WITSML |
| Π:GAS | gas_reading_in_or_out | WITSML / API |
| Π:KICK | kick_alert | API RP 53 (BOP) |
| Π:BOP | bop_state_summary | API 53 / Spec 16A |
| Π:RAM | bop_ram_state | API Spec 16A |
| Π:HEAVE | rig_heave_motion | DP standard |
| Π:HELI | helideck_state | CAP 437 / OGUK |

### Production (wellhead and surface facilities)

| Opcode | Definition | Source |
|---|---|---|
| Π:WHD | wellhead_state_summary | API 6A |
| Π:TP | tubing_pressure | API 6A |
| Π:CP | casing_pressure | API 6A |
| Π:CHK | choke_position | API |
| Π:GOR | gas_oil_ratio | SPE |
| Π:WC | water_cut | SPE |
| Π:LIFT | artificial_lift_state | SPE |
| Π:PROD | production_rate_BBL_or_MCF | TRRC / EIA |
| Π:TANK | tank_level_and_temp | API 2350 / 653 |
| Π:LACT | lact_meter_batch | API MPMS Ch. 6 |

### Midstream (pipeline and compressor)

| Opcode | Definition | Source |
|---|---|---|
| Π:PIPE | pipeline_segment_state | PHMSA 192/195 |
| Π:CMP | compressor_state | API 618 / 11P |
| Π:PUMP | pump_state | API 610 |
| Π:PIG | pigging_event | API RP 1130 |
| Π:LEAK | leak_detection_event | PHMSA / API 1130 |
| Π:CP_E | cathodic_protection_reading | NACE SP0169 |
| Π:HCA | hca_class_designation | PHMSA HCA tool |
| Π:MAOP | maximum_allowable_operating_pressure | PHMSA 192/195 |

### Valve control (cross-cutting)

| Opcode | Definition | Source |
|---|---|---|
| Π:ESD | emergency_shutdown_event_or_state | API 14C |
| Π:SSV | surface_safety_valve_state | API 6A / 14A |
| Π:SSSV | subsurface_safety_valve_state | API 14A / ISO 10417 |
| Π:MOV | motor_operated_valve_state | IEEE / API |
| Π:PSV | pressure_safety_valve_event | API 520/521/526 |
| Π:BBV | block_and_bleed_state | API 6D |

### Flare, vent, emissions

| Opcode | Definition | Source |
|---|---|---|
| Π:FLR | flare_state | API 521 / EPA |
| Π:VNT | vent_state | EPA OOOOa |
| Π:OGI | optical_gas_imaging_reading | EPA Method 21 / OOOOa |
| Π:CO2E | co2_equivalent_estimate | EPA Subpart W |

### Compliance and operations

| Opcode | Definition | Source |
|---|---|---|
| Π:PTW | permit_to_work_state | OGUK / OSHA |
| Π:NPT | non_productive_time_event | IADC |
| Π:INC | incident_classification | API 754 / OGP 456 |
| Π:CREW | crew_manifest_or_change | OIM / OSHA |

~40 Π opcodes. Plus reuse:
- E:TH/HU/PU — environmental temp/humidity/pressure (cross-domain)
- W:WIND/WAVE/RAIN/STORM — weather (sea state extends W with wave-period if needed)
- R:STOP/MOV/RTH — physical actuators where existing R semantics apply (drone inspection RTH, generic stop)
- M:EVA/RTE — evacuation, emergency routing (storm evacuation, kick → RTH for personnel)
- L:LOG — compliance logging
- U:NOTIFY/ALERT — crew alerting
- T:SCHED/EXP — operational scheduling, permit expiration
- G:POS — wellhead/rig/pipeline-segment geolocation
- I:§ — authorization precondition for ESD test, MOV manual operation, hot work permits

---

## Cross-domain reuse and MDR `.dpack` candidates

Following the pattern of ICD-10-CM and ISO 20022, the OILGAS MDR has natural reference-dictionary candidates that should be built as separate `.dpack` artifacts with cross-resolution:

1. **`MDR-WITSML-CURVES`** — log curve mnemonics (200–500 entries). Resolves drilling-floor telemetry channel names to standardized definitions. Highest-value first build.

2. **`MDR-API-SPECS`** — API specification numbers and titles (100–200 entries). Resolves regulatory / standards references in compliance frames.

3. **`MDR-PHMSA-CFR`** — 49 CFR Part 192 / 195 regulatory citations (200–400 entries). For pipeline compliance audit chains.

4. **`MDR-TRRC-RULES`** — Texas Statewide Rules (50–100 entries). For Texas-specific reporting frames.

5. **`MDR-EPA-SUBPART`** — EPA OOOO/OOOOa/OOOOb/Subpart W methane and GHG codes (50–100 entries).

6. **`MDR-NACE-SP`** — NACE / AMPP cathodic protection standards (50 entries).

7. **`MDR-PIDX-CODES`** — Petroleum industry data exchange trading partner codes (1000+ entries; lower priority).

WITSML curves first; the rest as demand-driven follow-ons.

---

## Wire format

Same as Food / Ag / existing MDRs. BLK compression. Output:
- `mdr/oilgas/MDR-OILGAS-DEFINITIONS-v1.csv`
- `mdr/oilgas/MDR-OILGAS-DEFINITIONS-v1.dpack`
- `mdr/oilgas/MDR-OILGAS-blk.dpack`

Plus reference-dictionary `.dpack` artifacts for the MDR candidates listed above (WITSML curves first).

---

## Brigade integration

1. Add `pi_station.py` to `sdk/python/osmp/brigade/stations/` (Greek-namespace station file naming convention; mirror what AG `alpha_station.py` will look like).
2. Register in `default_registry`.
3. Verb-lexicon additions: shut-in, kick, bleed, flare, pig, sour, dry-tree, wet-tree, blowdown, kill (well kill, distinct from C:KILL compute-kill).
4. Phrase-lexicon additions: "weight on bit", "standpipe pressure", "gas-oil ratio", "blowout preventer", "emergency shutdown", "lact meter", "pig launcher", "cathodic protection", "wellhead pressure", "tubing pressure", "casing pressure".
5. Disambiguation rule: a "kill" verb in the presence of a "well" or rig context maps to Π:WHD/Π:KILL (well kill); in the presence of a "process" or compute context maps to C:KILL. Brigade verb lexicon needs an O&G-context flag.
6. Add 30+ OILGAS chips to corpus (drilling, production, pipeline, valve, flare, emergency).
7. Re-run all corpora — confirm 0 WRONG / 0 INVALID.

---

## Macro candidates

Pre-validated multi-frame chain templates (parallel to the Meshtastic macro corpus). These are the highest-value composition shortcuts for O&G operators.

| Macro ID | Chain template | Triggers |
|---|---|---|
| `OG:RIG_TEL` | `Π:WOB[wob:{wob}]∧Π:HKLD[hkld:{hkld}]∧Π:RPM[rpm:{rpm}]∧Π:SPP[spp:{spp}]∧Π:MFI[in:{mfi}]∧Π:MFO[out:{mfo}]∧Π:MWT[mw:{mwt}]` | "rig telemetry", "drilling parameters", "rig status" |
| `OG:KICK` | `Π:KICK→Π:BOP→Π:ESD→U:ALERT@*` | "kick", "well kick", "gas kick" |
| `OG:WELL` | `Π:TP[tp:{tp}]∧Π:CP[cp:{cp}]∧Π:CHK[chk:{chk}]∧Π:GOR[gor:{gor}]∧Π:WC[wc:{wc}]∧Π:PROD[bbl:{bbl},mcf:{mcf}]` | "wellhead status", "well telemetry", "production status" |
| `OG:PIPE` | `Π:PIPE[seg:{seg}]∧Π:PIPE[suction:{ps}]∧Π:PIPE[discharge:{pd}]∧Π:LEAK[bal:{imbal}]` | "pipeline status", "pipeline pressures", "pipeline flow" |
| `OG:LACT` | `Π:LACT[bbl:{bbl},api:{api},bsw:{bsw},mf:{mf}]∧L:LOG@CUSTODY` | "lact batch", "custody transfer", "lact meter reading" |
| `OG:ESD_TRIP` | `Π:ESD@{zone}→Π:SSV@CLOSE→Π:MOV@CLOSE→U:ALERT@*` | "ESD trip", "emergency shutdown", "shut in" |
| `OG:PIG_RUN` | `Π:PIG[stage:LAUNCH,id:{pigid}]→Π:PIG[stage:TRACK]→Π:PIG[stage:RECEIVE]` | "pig run", "pig in transit", "pigging event" |
| `OG:CMP_HEALTH` | `Π:CMP[rpm:{rpm}]∧Π:CMP[suct:{ps}]∧Π:CMP[disch:{pd}]∧Π:CMP[vib:{vib}]` | "compressor status", "compressor health" |
| `OG:TANK` | `Π:TANK[lvl:{lvl},t:{t},h2o:{water}]∧L:LOG@TANK` | "tank gauge", "tank level", "tank reading" |
| `OG:FLARE` | `Π:FLR[flame:{flame},smoke:{smoke}]∧Π:OGI[ppm:{ppm}]∧Π:CO2E[t:{co2e}]` | "flare status", "flare reading", "flare check" |
| `OG:CP_SURVEY` | `Π:CP_E[mv:{mv},loc:{loc}]∧L:LOG@CP_SURVEY` | "cathodic protection reading", "cp survey" |
| `OG:STORM_EVAC` | `W:ALERT@HURRICANE→M:EVA@*→Π:ESD@PLATFORM→U:NOTIFY@CREW` | "storm evacuation", "hurricane procedure", "platform evac" |

Macro corpus location: `mdr/oilgas/oilgas-macros.json`. Format identical to `mdr/meshtastic/meshtastic-macros.json`.

---

## IP impact

**Sovereign extension.** The Π namespace is a sovereign extension under OSMP-001's namespace architecture. Per the third-party-extension licensing pattern in PATENT-NOTICE.md, third-party operators (oil majors, SCADA vendors) deploying their own Π:* opcodes for proprietary equipment retain their own intellectual property in those extensions while inheriting wire-level compatibility with the public grammar.

**Hardware integration claims.** Wellhead RTU and pipeline SCADA gateway integrations create field-installable embodiments that strengthen system-level claims. A Π-namespace wellhead RTU running OSMP brigade and emitting policy-graded SAL over VSAT/Starlink/L-band is a concrete reduction-to-practice for the runtime environment claim cluster (v22 Claim 49).

**Compliance audit chain.** The combination of Π:* operational opcodes plus L:LOG plus I:§ authorization preconditions plus the regulatory MDR `.dpack` artifacts (PHMSA-CFR, TRRC-RULES, EPA-SUBPART) produces a verifiable compliance audit chain on the wire. This pattern is a candidate independent claim ("regulatory compliance audit chain composed of structured-instruction frames carrying authoritative-source reference identifiers, validated against a managed dictionary registry") in a future filing.

**Connectivity-degradation policy claim.** OSMP's Overflow Protocol policies (Φ fail-safe, Γ graceful-degradation, Λ atomic) applied to satellite-degraded operations produce a domain-specific use case that strengthens the existing Overflow Protocol claims in OSMP-001. The evidence pattern: ESD trips and kick alerts emit under Λ atomic policy and survive a Starlink rain-fade event; production telemetry emits under Γ graceful-degradation and drops to a reduced cadence; non-critical logging emits under Φ fail-safe and tolerates packet loss without retransmission. This is filing-strength evidence for the Overflow Protocol's domain applicability, not a new claim.

---

## Definition of done

1. ✅ ~40 Π opcodes defined with ≥1 source per opcode (table above is the spec; verify each citation)
2. ✅ Authoritative reference dictionary builds (WITSML curves first, then API specs, PHMSA CFR, TRRC, EPA Subpart, NACE)
3. ✅ BLK-compressed `.dpack` for the OILGAS opcode definitions
4. ✅ `pi_station.py` in brigade with verb-lexicon and phrase-lexicon additions
5. ✅ `mdr/oilgas/oilgas-macros.json` with the ~12 macros above (or the inventor's curated list)
6. ✅ 30+ OILGAS chips in test corpus, all CORRECT
7. ✅ Existing corpus stress test still 100% SAFE / 0 WRONG / 0 INVALID
8. ✅ MCP data load (osmp://dictionary surfaces Π namespace; osmp://corpora lists OILGAS)
9. ✅ OSMP-SPEC entry for Π namespace (mirroring the Α namespace entry pattern from Ag)
10. ✅ Cross-resolution test: a frame referencing an API spec number resolves through MDR-API-SPECS to the standard's title

---

## Open questions for the inventor

1. **Π or different glyph?** Greek letter for petroleum is the natural choice but the Α/Π pairing (Agriculture / Petroleum) is just two of the 24 Greek letters. If the inventor wants a more deliberate mapping (e.g., "industry verticals always get Greek capitals; sciences always get Greek lowercase"), that should be set as policy before more domain MDRs land.

2. **Disambiguation strategy for shared verbs.** "Kill" in O&G means well kill (mud weight increase to overbalance reservoir pressure). C:KILL means terminate compute process. The brigade verb-lexicon-plus-context-flag pattern handles this, but the policy needs to be set: do we accept ambiguity at the verb-lexicon layer and resolve at the station layer (current pattern), or do we promote namespace-disambiguation tokens to the parser layer?

3. **MDR build sequencing.** WITSML curves (200–500 entries) is the highest-leverage first build, but the inventor may have a different priority based on customer conversations. Permian operator wants TRRC rules first? Offshore operator wants API specs first? Confirm before starting a `.dpack` build.

4. **Compliance MDR scope.** PHMSA 192/195 is large (each part is hundreds of pages). The MDR should resolve common citations at the section/subsection level (e.g., "192.605", "192.610") not full prose. Confirm the granularity target before building.

5. **Unit-system policy.** Onshore US is field units (psi, bbl, MCF, °F). Offshore frequently SI (bar, m³, kg, °C). LACT is BBL custody-of-record. Slot-value grammar accommodates either, but the corpus chips need a deliberate mix to ensure stations resolve both systems.
