# MDR Handoff — MINING (Hard rock, rare earth, industrial rock) domain

**Status:** Ready for parallel build.
**Author:** CTO/CLC (Claude) — 2026-04-27
**Owner:** Whoever picks this up (or MDR-creation agent once built).

---

## Goal

Build a Mining MDR for OSMP covering hard-rock metal mines (gold, copper, lithium, rare earth), industrial rock and aggregate yards (limestone, granite, basalt, sand, gravel), surface and underground operations, mineral processing through to product handling, and the regulatory compliance reference data tied to each. Mining is a high-fit deployment domain for OSMP for the same substrate reason as oil and gas: remote sites with metered satellite uplinks, intermittent terrestrial 4G/5G in haul-road corridors, leaky-feeder or Wi-Fi mesh underground, weather-degraded connectivity (snow, lightning, dust storms), and a dense SCADA telemetry surface that benefits from compression-positive wire encoding.

This handoff is parallel to and independent of `HANDOFF-MDR-OILGAS.md`. Both are extractive-industry verticals but the equipment, hazards, regulatory frame, and value-stream are distinct enough to warrant separate namespaces and separate corpora.

---

## Scope

**In-scope** for MINING MDR:

**Surface mining (open pit, strip, quarry):**
- Drill rig telemetry: rotary speed, pulldown force, bit air pressure, water flow, hole depth, hole pattern
- Blast operations: blast number, hole count, charge mass, delay timing, exclusion zone state, post-blast clearance
- Loading: shovel/excavator state (swing, dipper full/empty, payload), front-end loader bucket weight
- Haulage: truck position, payload, fuel, gear, brake temperature, tire pressure (TPMS), driver fatigue indicators (where deployed)
- Crusher and screening: throughput (TPH), feed level, discharge size distribution, motor amps, vibration, choke alarm
- Conveyors: belt speed, motor load, belt slip, misalignment, fire suppression state
- Stockpile: pile mass, moisture, particle-size sample, contamination flags
- Water management: pit dewatering rate, sump level, settling pond level, discharge pH/turbidity
- Slope stability: prism (radar) displacement, piezometer water table, microseismic activity

**Underground mining (hard rock metal, REE):**
- Ventilation: airflow rate per drift, fan power, gas readings (CH4, CO, NOx, H2S, O2)
- Ground support: cable bolt tension, mesh integrity, shotcrete cure status, support pattern
- Refuge chamber: occupancy, air supply hours, comm link state
- Personnel tracking: tag positions, time-on-site, evacuation roster
- Drilling and blasting: face advance, ore grade-control sample, draw-point status
- LHD (load-haul-dump): position, payload, hours, hydraulic temp
- Hoisting: skip cycle time, rope tension, head sheave wear
- Pumping: dewatering pumps, sump levels, stage transitions (mine-water management)

**Mineral processing (mill / concentrator / hydromet / pyromet):**
- Comminution: SAG/ball mill power, feed rate, recycle load, grinding media draw
- Flotation: cell pH, reagent dosing, froth depth, bubble size, recovery rate
- Hydromet: leach tank pH, ORP, temperature, reagent inventory
- Pyromet: smelter temperatures (matte, slag), off-gas composition, oxygen lance flow
- REE-specific: solvent extraction (SX) train (organic/aqueous ratios, pH per stage), ion exchange (IX) column state, separation factor measurements
- Tailings: thickener torque, underflow density, paste plant feed, tailings dam piezometer / phreatic surface, freeboard
- Reagent inventory: cyanide (where used), xanthate, MIBC, frother, lime, flocculant

**Industrial rock / aggregate yards (limestone, granite, sand, gravel):**
- Quarry blast and bench operations (subset of surface mining above)
- Wash plants: water consumption, fines recovery, slurry density
- Sizing: screen deck health, bearing temperature, motor amps
- Product stockpile: mass per grade (1/4 minus, 3/4 minus, riprap, etc.), QC sample state
- Truck scale tickets: gross/tare/net, customer, lot, certificate

**Safety and emergency:**
- Gas alarms: CH4, CO, H2S, NOx (underground critical)
- Dust monitoring: respirable crystalline silica (RCS), respirable coal dust (where applicable), diesel particulate matter (DPM)
- Ground stability alarms: slope monitoring trip, microseismic event classification, subsidence
- Fire detection: belt fires, equipment fires, refuge chamber CO ingress
- Emergency response: muster, evacuation, mine rescue activation

**Regulatory and compliance reporting:**
- MSHA (US): part 50 reportable accidents/illnesses, citations, abatement, S&S violations
- BLM / state DEQ: surface disturbance, reclamation acreage, water permit
- ICMM members and IRMA-aligned operations: ESG telemetry, water stewardship metrics, biodiversity offsets
- TSF (Tailings Storage Facility): GISTM (Global Industry Standard on Tailings Management) conformance state, ITRB review state, EPRP activation
- Cyanide management (where applicable): ICMI Code certification status

**Out-of-scope** (defer or use other namespaces):
- Mineral marketing / commodity sales (use K namespace per ISO 20022)
- Title and surface rights (use I namespace; separate workstream)
- Geological modeling and resource estimation (massive datasets, wrong substrate for OSMP)
- Personnel HR data (privacy concerns, wrong namespace)
- Refining (downstream) — separate domain

---

## Substrate fit and connectivity considerations

Mining substrate considerations parallel oil and gas with three differentiators:

**Underground propagation.** Leaky feeder and Wi-Fi mesh dominate underground comms; LoRa operates poorly through rock but radio-over-fiber backhaul plus surface-mounted gateways covers most corridors. SAL's wire footprint matters more here than on satellite because the leaky-feeder bandwidth shared across hundreds of personnel and equipment is genuinely scarce.

**Dust and weather.** Surface mines experience whiteouts (Mongolian winter, Andean altiplano), dust storms (Western Australia, Atacama), lightning (Africa, Carolinas), monsoons (West Africa, Indonesia). VSAT and Starlink links degrade similarly to oil and gas operations; the same Overflow Protocol policy-graded delivery argument applies — TSF stability alarms ride Λ atomic policy and survive degradation, while production telemetry rides Γ graceful-degradation and drops cadence.

**Latency budgets.** Slope-stability and microseismic monitoring have hard latency budgets (alarms within seconds of detection). Production telemetry (truck cycle time, crusher throughput) has loose budgets (minutes). The protocol's per-frame consequence-class designators map directly to this latency budget partition: alarm frames carry ⚠ or ⊘ and inherit Λ atomic delivery; production frames carry ↺ and inherit Γ graceful-degradation.

**Per-vendor SCADA fragmentation.** Mining has more SCADA-vendor fragmentation than oil and gas (Caterpillar MineStar, Komatsu KOMTRAX, Sandvik OptiMine, Hexagon, Rockwell, Wenco, Modular Mining, plus the Modbus/OPC UA long tail). The Adaptive Shared Dictionary unifies the fragment vocabulary at the protocol layer; vendor-specific SCADA endpoints translate to/from the shared dictionary at the gateway.

---

## Namespace assignment

**Recommend new namespace `Ξ` (Xi, Greek)** — Mining / Extractive Industries (excluding hydrocarbons). Greek capital chosen to avoid visual collision with the Latin M (Municipal namespace) and N (Network namespace). Ξ is visually distinctive in mono and proportional fonts.

Greek-letter sovereign extensions per OSMP-SPEC §X-O are the established convention. Α (Alpha) is proposed for Agriculture, Π (Pi) for Petroleum / Oil & Gas, Ξ (Xi) for Mining. Future verticals can follow the same pattern (e.g., Σ for shipping/maritime, Θ for healthcare-operations distinct from H clinical sensing).

Alternative — extend existing namespaces: equipment under R, sensors under E, weather under W, etc. Same critique as OILGAS handoff: maximally distributed, worst discoverability, conflates extractive-industry-specific semantics with generic robotics.

**Recommend:** dedicated `Ξ` namespace for mining-specific opcodes (drill-and-blast, comminution, flotation, hydromet, pyromet, ventilation, hoisting, TSF). Reuse of existing namespaces for crossover concepts:
- E:* — generic environmental sensing (temp, pressure, humidity); reuse for crusher motor temp, mill bearing temp
- W:* — surface weather, lightning, snow
- R:* — generic actuators (belt stops, fire suppression activation, ventilation door)
- M:* — emergency response, evacuation
- L:* — compliance audit logging
- U:* — operator alerting
- T:* — shift scheduling, blast windows
- G:* — pit/face/level geolocation
- I:§ — authorization for blast detonation, cyanide system access, refuge chamber arm

---

## Authoritative reference lists

### 1. Operational standards and protocols

| Source | What it covers | Reference |
|---|---|---|
| **GMSG / ICMM Open Mining Format** | Open mining data exchange | GMSG specifications |
| **ISO 19296** | Mining — Mobile machines — Object detection | ISO 19296:2018 |
| **ISO 14310** | Petroleum — packers and bridge plugs (mining-shared) | ISO 14310 |
| **GISTM** | Global Industry Standard on Tailings Management | ICMM/UNEP/PRI joint |
| **CIM Best Practice Guidelines** | Canadian Institute of Mining standards | CIM |
| **JORC / NI 43-101 / SAMREC / PERC** | Resource and reserve reporting codes | International alignment |
| **API / NACE** (process side) | Pipeline and CP standards (water, slurry) | Shared with O&G |
| **ASTM aggregates** | Aggregate testing (D75, C29, C136, etc.) | ASTM International |
| **AGI gas detection** | Workplace gas monitoring | ANSI/ISA / IEC 60079 |
| **IEC 61508 / 61511** | Functional safety / SIL-rated SIS | Shared with O&G |
| **MEMS-mining** | Wireless underground sensor standards | Industry working groups |

### 2. Regulatory references

| Jurisdiction | Source | Coverage |
|---|---|---|
| **US — federal** | MSHA 30 CFR Parts 50, 56, 57, 75, 77 | Federal mine safety; surface (56), underground M/NM (57), underground coal (75), surface coal (77) |
| **US — state** | State DEQ / Mining Bureau (varies) | Reclamation, water |
| **US — federal land** | BLM Mining Law / Mining Act | Federal lands operations |
| **US — environmental** | EPA NPDES, RCRA, CERCLA | Discharge, waste, legacy contamination |
| **CA** | Provincial Mines Acts (BC, ON, QC, SK) | Provincial-led; federal CER for some projects |
| **AU** | DMIRS (WA), DRDMW (QLD), state mines departments | State-led |
| **CL** | SERNAGEOMIN | Chile mining regulator |
| **PE** | OSINERGMIN | Peru mining + energy |
| **ZA** | DMR (South Africa) | Mineral and Petroleum Resources |
| **EU** | Critical Raw Materials Act + national | REE-relevant; supply chain due diligence |

### 3. Industry data dictionaries (for MDR cross-resolution)

| Source | What it provides | Notes |
|---|---|---|
| **OMF (Open Mining Format)** | Geometry, geology, sampling | GMSG / Seequent + others |
| **Industrial Minerals taxonomy** | Industrial rock classifications | IMA |
| **REE oxide spec** | Lanthanide oxide product specs | Industry data |
| **MSHA accident/citation codes** | Reportable event categorization | MSHA Part 50 |
| **GISTM tailings classification** | Consequence categories, ESCM | ICMM/UNEP/PRI |
| **ASTM aggregate gradations** | 1/4 minus, 3/4 minus, etc. | ASTM C33, etc. |

These dictionaries are candidates for downstream MDR `.dpack` builds. First candidates:

1. **`MDR-MSHA-CFR`** — 30 CFR Parts 50/56/57/75/77 citations (300–500 entries). For US compliance audit chains.
2. **`MDR-GISTM-CONSEQ`** — GISTM consequence categories and ESCM definitions (50–100 entries). For TSF compliance frames.
3. **`MDR-ASTM-AGG`** — ASTM aggregate specifications (100–200 entries). For industrial-rock product certification.
4. **`MDR-REE-PRODUCTS`** — Rare earth oxide product specs (50–100 entries). For REE supply chain.

MSHA-CFR first; the rest demand-driven.

---

## Proposed opcode catalog

Approximately 40 opcodes split across surface, underground, processing, TSF, safety, and compliance. Plus reuse of existing namespaces for crossover.

### Surface mining and quarrying

| Opcode | Definition | Source |
|---|---|---|
| Ξ:DRL | drill_rig_state | GMSG |
| Ξ:BLST | blast_event_or_state | MSHA / blasting standard |
| Ξ:SHVL | shovel_or_excavator_state | OEM standards |
| Ξ:LDR | front_end_loader_state | OEM standards |
| Ξ:HAUL | haul_truck_state | ISO 19296 |
| Ξ:DSPC | dispatch_event | GMSG dispatch model |
| Ξ:SLOPE | slope_stability_reading | radar / piezo / microseismic |

### Crushing, screening, conveying

| Opcode | Definition | Source |
|---|---|---|
| Ξ:CRSH | crusher_state | OEM / mineral processing |
| Ξ:SCRN | screen_state | OEM |
| Ξ:CONV | conveyor_state | CEMA / OEM |
| Ξ:PILE | stockpile_state_or_sample | mining QC |

### Underground

| Opcode | Definition | Source |
|---|---|---|
| Ξ:VENT | ventilation_state | MSHA Part 75 |
| Ξ:GAS | underground_gas_reading | IEC 60079 |
| Ξ:GRD | ground_support_state | rock mechanics standard |
| Ξ:RFG | refuge_chamber_state | MSHA / GMSG |
| Ξ:LHD | load_haul_dump_state | OEM |
| Ξ:HOIST | hoist_skip_or_cage_state | mining hoisting standard |
| Ξ:DEW | dewatering_pump_state | mining-water mgmt |

### Mineral processing

| Opcode | Definition | Source |
|---|---|---|
| Ξ:SAG | sag_or_ball_mill_state | mineral processing |
| Ξ:FLOT | flotation_cell_state | mineral processing |
| Ξ:LCH | leach_tank_state | hydromet |
| Ξ:SX | solvent_extraction_stage_state | hydromet (REE) |
| Ξ:IX | ion_exchange_column_state | hydromet (REE) |
| Ξ:SMLT | smelter_state | pyromet |
| Ξ:THK | thickener_state | mineral processing |
| Ξ:RGT | reagent_inventory_or_dose | mineral processing |

### Tailings storage facility (TSF)

| Opcode | Definition | Source |
|---|---|---|
| Ξ:TSF | tsf_state_summary | GISTM |
| Ξ:PHRE | phreatic_surface_reading | GISTM |
| Ξ:FBRD | freeboard_reading | GISTM |
| Ξ:PASTE | paste_plant_state | tailings paste fill |

### Safety, alarm, compliance

| Opcode | Definition | Source |
|---|---|---|
| Ξ:DST | dust_reading_RCS_or_DPM | MSHA / OSHA PEL |
| Ξ:GRDA | ground_stability_alarm | rock mechanics |
| Ξ:SEISM | microseismic_event | mine geophysics |
| Ξ:FIRE | mine_fire_event | MSHA |
| Ξ:RESC | mine_rescue_activation | MSHA |
| Ξ:CTNS | cyanide_management_state | ICMI Cyanide Code |
| Ξ:RPT | regulatory_report_event | MSHA Part 50 / equiv |

### Personnel and operations

| Opcode | Definition | Source |
|---|---|---|
| Ξ:TAG | personnel_tag_position | mining tag-and-track |
| Ξ:SHFT | shift_change_or_muster_event | mining ops |
| Ξ:PTW | permit_to_work_state | shared with O&G |
| Ξ:BLAS | blast_authorization_state | MSHA / state |

~40 Ξ opcodes. Plus reuse:
- E:TH/HU/PU — environmental temp/humidity/pressure (motor temps, ambient)
- W:WIND/PRECIP/STORM — surface weather
- R:STOP/MOV/RTH — physical actuators (belt stops, ventilation doors, drone inspection)
- M:EVA/RTE — evacuation, emergency routing
- L:LOG — compliance audit logging
- U:NOTIFY/ALERT — operator alerting
- T:SCHED/EXP — blast windows, permit expiration
- G:POS — pit/face/level geolocation
- I:§ — authorization for blast detonation, cyanide access, refuge arm

---

## Cross-domain reuse and `.dpack` candidates

Reference-dictionary candidates following the ICD-10-CM / ISO 20022 pattern:

1. **`MDR-MSHA-CFR`** (300–500 entries) — first build, US compliance.
2. **`MDR-GISTM-CONSEQ`** (50–100 entries) — TSF compliance, GISTM-aligned operators.
3. **`MDR-ASTM-AGG`** (100–200 entries) — industrial-rock products.
4. **`MDR-REE-PRODUCTS`** (50–100 entries) — rare earth oxide specs.
5. **`MDR-OMF-GEOM`** (variable, large) — open mining format geometry; lower priority, large payload.

---

## Wire format

Same as Ag / OilGas / existing MDRs. BLK compression. Output:
- `mdr/mining/MDR-MINING-DEFINITIONS-v1.csv`
- `mdr/mining/MDR-MINING-DEFINITIONS-v1.dpack`
- `mdr/mining/MDR-MINING-blk.dpack`

Plus the reference-dictionary `.dpack` artifacts above (MSHA-CFR first).

---

## Brigade integration

1. Add `xi_station.py` to `sdk/python/osmp/brigade/stations/`.
2. Register in `default_registry`.
3. Verb-lexicon additions: blast (vs explode), muck, draw, hoist, cycle, mill, leach, float, smelt, panel, stope.
4. Phrase-lexicon additions: "pit slope", "face advance", "ventilation airflow", "ground support", "refuge chamber", "tailings facility", "haul truck cycle", "crusher feed", "ball mill power", "flotation recovery", "leach pH", "solvent extraction", "tailings phreatic surface", "freeboard reading", "permit to blast", "muster the crew".
5. Disambiguation rules:
   - "Mill" — Ξ:SAG (mineral processing) vs. industrial mill (ag) vs. wood mill (foreign domain). Mining context inferred from surrounding tokens (ore, grade, tonnage, recovery).
   - "Blast" — Ξ:BLST (mining blast) vs B namespace alarms vs metaphorical "blast email". Mining context required.
   - "Tag" — Ξ:TAG (personnel tracking) vs. generic tagging. Underground or "personnel" context required.
6. Add 30+ MINING chips to corpus (surface, underground, processing, TSF, safety).
7. Re-run all corpora — confirm 0 WRONG / 0 INVALID.

---

## Macro candidates

| Macro ID | Chain template | Triggers |
|---|---|---|
| `MIN:HAUL_CYC` | `Ξ:HAUL[truck:{id},load:{tons},dest:{dest}]∧T:NOW[t:{ts}]` | "haul cycle", "truck cycle", "haul truck dispatched" |
| `MIN:BLAST_CLR` | `Ξ:BLAS[id:{blastid},state:CLEAR]→Ξ:BLST[holes:{n},mass:{kg}]→U:NOTIFY@*` | "blast clearance", "blast all clear", "blast complete" |
| `MIN:VENT` | `Ξ:VENT[area:{drift},flow:{cfm}]∧Ξ:GAS[ch4:{ch4},co:{co},o2:{o2}]` | "ventilation reading", "underground air", "drift airflow" |
| `MIN:SLOPE` | `Ξ:SLOPE[radar:{mm},piezo:{m},seism:{evt}]∧L:LOG@SLOPE` | "slope stability", "pit wall reading", "slope monitoring" |
| `MIN:TSF_DAILY` | `Ξ:TSF[state:{state}]∧Ξ:PHRE[m:{m}]∧Ξ:FBRD[m:{m}]∧L:LOG@TSF` | "tailings daily", "tsf check", "tailings dam reading" |
| `MIN:MILL_PWR` | `Ξ:SAG[kw:{kw},rpm:{rpm},load:{load}]∧E:TH[brg:{brgT}]` | "mill power", "sag mill status", "ball mill load" |
| `MIN:FLOT_REC` | `Ξ:FLOT[ph:{ph},frgth:{frgth},rec:{rec}]∧Ξ:RGT[mibc:{mibc},xanthate:{xan}]` | "flotation recovery", "flotation reading", "flot cell status" |
| `MIN:DUST` | `Ξ:DST[rcs:{rcs},dpm:{dpm},loc:{loc}]∧L:LOG@DUST` | "dust reading", "respirable silica", "DPM exposure" |
| `MIN:RESCUE` | `Ξ:RESC[event:{evt}]→Ξ:RFG[occ:{n}]→M:EVA@*→U:NOTIFY@RESCUE` | "mine rescue", "evacuate underground", "refuge activation" |
| `MIN:GISTM_RPT` | `Ξ:TSF[gistm:{class}]∧Ξ:PHRE[m:{m}]∧L:LOG@GISTM` | "GISTM report", "tailings consequence class", "ITRB review" |
| `MIN:LACT_AGG` | `Ξ:PILE[grade:{grade},tons:{tons},lot:{lot}]∧L:LOG@SCALE` | "scale ticket", "stockpile reading", "aggregate lot" |

Macro corpus location: `mdr/mining/mining-macros.json`. Format identical to `mdr/meshtastic/meshtastic-macros.json`.

---

## IP impact

**Sovereign extension.** Ξ namespace is a sovereign extension under OSMP-001's namespace architecture. Same third-party-extension licensing pattern as Π (oil & gas) — vendor-specific SCADA gateway extensions retain their own IP while inheriting wire-level compatibility.

**TSF compliance audit chain.** GISTM-aligned operators and ICMM members have ESG reporting obligations that map onto OSMP's audit-chain pattern (Ξ:TSF + Ξ:PHRE + Ξ:FBRD + L:LOG@GISTM). The reduction-to-practice is straightforward: a mine site emitting daily SAL chains that resolve through `MDR-GISTM-CONSEQ` produces a verifiable ESG telemetry record. This is candidate evidence for the regulatory-compliance-audit-chain claim opportunity flagged in the OILGAS handoff.

**Underground propagation evidence.** A mining site's leaky-feeder-plus-mesh deployment, when run on OSMP, produces a domain-distinct test case for the Overflow Protocol's policy-graded delivery (parallel to satellite-degraded delivery in O&G). Two independent extractive verticals demonstrating the same Overflow Protocol property is stronger evidence than one.

**Critical Minerals Act / REE supply chain.** EU Critical Raw Materials Act and US Defense Production Act REE provisions create regulatory tail-wind for traceable supply-chain telemetry. SAL-encoded REE oxide product certifications (Ξ:RGT + L:LOG@CERT cross-resolved through `MDR-REE-PRODUCTS`) is a fit-for-regulation use case worth surfacing in commercial conversations.

---

## Definition of done

1. ✅ ~40 Ξ opcodes defined with ≥1 source per opcode (table above is the spec; verify each citation)
2. ✅ Authoritative reference dictionary builds (MSHA-CFR first, then GISTM, ASTM aggregates, REE products)
3. ✅ BLK-compressed `.dpack` for the MINING opcode definitions
4. ✅ `xi_station.py` in brigade with verb-lexicon and phrase-lexicon additions
5. ✅ `mdr/mining/mining-macros.json` with the ~11 macros above (or the inventor's curated list)
6. ✅ 30+ MINING chips in test corpus, all CORRECT
7. ✅ Existing corpus stress test still 100% SAFE / 0 WRONG / 0 INVALID
8. ✅ MCP data load (osmp://dictionary surfaces Ξ namespace; osmp://corpora lists MINING)
9. ✅ OSMP-SPEC entry for Ξ namespace
10. ✅ Cross-resolution test: a frame referencing an MSHA citation resolves through MDR-MSHA-CFR to the regulation text

---

## Open questions for the inventor

1. **Greek namespace policy.** Α / Π / Ξ are three vertical-domain proposals. If the policy is "industry verticals always get Greek capitals," the alphabet supports about 18 distinct verticals before collisions force a different scheme. Set the policy explicitly before more domain MDRs land.

2. **REE-specific carve-out.** Rare earth element processing (SX trains, IX columns, separation factors) is mechanically distinct from base/precious metal hydromet. The handoff folds REE into Mining (Ξ:SX, Ξ:IX) but a dedicated REE namespace could be argued. Recommend keeping under Ξ unless and until REE deployment volume warrants separation.

3. **TSF priority.** GISTM compliance is a high-visibility regulatory pressure point post-Brumadinho (2019) and Mariana (2015). MDR-GISTM-CONSEQ may warrant building before MDR-MSHA-CFR if the first commercial conversation is with a multi-national operator. Confirm with the inventor before sequencing.

4. **Industrial rock vs metals.** Aggregate quarries (limestone, granite, sand, gravel) have a smaller telemetry surface than metal mines and a different regulatory frame (state-led, less MSHA-intensive). The handoff currently combines them. If commercial focus is metals, the aggregate-specific opcodes (Ξ:PILE grade variants, scale tickets, ASTM specs) can be deferred to a v2 build.

5. **Underground gas profile.** Coal underground operations require methane focus (MSHA Part 75 ventilation plans). Hard-rock metal mines have different gas profiles (radon, NOx from blasting). REE-bearing carbonatites can have radiogenic concerns. The Ξ:GAS opcode's slot-value vocabulary needs to accommodate all three; spec it explicitly in the opcode table.
