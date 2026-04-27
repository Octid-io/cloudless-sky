# MDR Handoff — AG (Agriculture) domain

**Status:** Ready for parallel build.
**Author:** CTO/CLC (Claude) — 2026-04-26
**Owner:** Whoever picks this up (or MDR-creation agent once built).

---

## Goal

Build an Ag MDR for OSMP covering field operations: irrigation control, soil sensing, livestock telemetry, crop monitoring, equipment dispatch. Closes the agricultural-IoT use case identified in the science MDR strategy doc as the **highest immediate commercial fit** ("agriculture hydrology MDR — existing LoRa deployment base, calibration is a real pain point, buyers are concentrated").

---

## Scope

**In-scope** for Ag MDR:
- Soil sensing (moisture, pH, NPK, electrical conductivity, temp)
- Irrigation control (valve state, flow rate, schedule, evapotranspiration)
- Livestock telemetry (collar position, temp, activity, gate state)
- Crop monitoring (canopy cover, NDVI, growth stage, pest pressure)
- Weather (extends existing W namespace; soil-specific micro-climate)
- Equipment dispatch (tractor, sprayer, drone, harvester)
- Pest/disease detection + alert
- Harvest tracking (yield, lot, field-of-origin)

**Out-of-scope** (defer):
- Subsidies/grants (regulatory, not protocol)
- Crop insurance (commerce, use K namespace)
- Land deeds (use I namespace)

---

## Namespace assignment

**Recommend new namespace `Α` (Alpha)** — Agriculture / Field Operations. Or extend `Ω` (Sovereign) if we want to keep new namespaces minimal.

Alternative: split across existing namespaces:
- E:* — soil sensors (env extension)
- W:* — weather (already exists)
- R:* — irrigation actuators (extend existing R)
- new namespace just for ag-specific ops (yield, pest, livestock)

Recommend: **single Α namespace for ag-specific opcodes**, plus reuse of E/W/R for crossover concepts. Keeps the dictionary clean.

---

## Authoritative reference lists

| Source | What it covers | URL |
|---|---|---|
| **USDA NRCS Soil Health** | Soil sensing standards | https://www.nrcs.usda.gov/conservation-basics/natural-resource-concerns/soils |
| **USDA NASS** | Crop reporting standards | https://www.nass.usda.gov/ |
| **FAO AQUASTAT** | Irrigation/water standards | http://www.fao.org/aquastat/ |
| **ASABE** (Am Society of Ag & Biological Engineers) | Equipment + sensor standards | https://asabe.org/ |
| **OECD/FAO Crop Production** | Yield + harvest standards | https://www.oecd-ilibrary.org/agriculture-and-food |
| **NIST USDA Soil Calibration** | Soil sensor calibration | https://www.nist.gov/ |
| **ISO 11783 (ISOBUS)** | Tractor-implement comms | https://www.iso.org/standard/57556.html |
| **NDVI / Sentinel-2 spec** | Crop satellite imagery | https://sentinel.esa.int/web/sentinel/missions/sentinel-2 |
| **EPA Pesticide Reg** | Pesticide application reporting | https://www.epa.gov/pesticides |

---

## Proposed opcode catalog

| Opcode | Definition | Source |
|---|---|---|
| Α:SOIL | soil_moisture_reading | USDA NRCS |
| Α:PH | soil_ph_reading | USDA NRCS |
| Α:NPK | nitrogen_phosphorus_potassium | USDA NRCS |
| Α:EC | electrical_conductivity | NIST |
| Α:IRR | irrigation_state | FAO AQUASTAT |
| Α:VLV | irrigation_valve_control | ASABE |
| Α:FLOW | water_flow_rate | ASABE |
| Α:ET | evapotranspiration | FAO Penman-Monteith |
| Α:NDVI | normalized_difference_vegetation_index | Sentinel-2 |
| Α:STG | crop_growth_stage | USDA NASS |
| Α:YLD | yield_estimate | OECD/FAO |
| Α:PEST | pest_pressure_observation | EPA |
| Α:DZ | disease_zone_alert | USDA APHIS |
| Α:LIV | livestock_telemetry | livestock-tracking standard |
| Α:HRD | herd_movement_event | livestock-tracking |
| Α:GATE | gate_state | ASABE |
| Α:HRVSTR | harvester_dispatch | ISOBUS |
| Α:SPRAY | sprayer_dispatch | EPA + ISOBUS |
| Α:LOT | field_or_pasture_lot_id | USDA |

~19 opcodes. Plus reuse of E:TH/HU (env), W:WIND/PRECIP (weather), R:RTH (drone return), G:POS (location).

---

## Cross-domain reuse

- E namespace (env sensor) — soil temp uses E:TH
- W namespace (weather) — atmospheric overlap
- R namespace (robotic) — harvester/sprayer/drone are R-namespace actuators
- T:SCHED — irrigation scheduling
- G:POS — field location anchor

---

## Wire format

Same as Food/existing MDRs. BLK compression. Output:
- `mdr/ag/MDR-AG-DEFINITIONS-v1.csv`
- `mdr/ag/MDR-AG-DEFINITIONS-v1.dpack`
- `mdr/ag/MDR-AG-blk.dpack`

---

## Brigade integration

1. Add `alpha_station.py` to brigade/stations/
2. Register in default_registry
3. Add 15-20 Ag chips to corpus
4. Re-run all 4 corpora — confirm 0 WRONG / 0 INVALID

---

## IP impact

- Α namespace is a sovereign extension — needs claim cluster review
- Hardware integration (LoRa-based soil sensors, ISOBUS bridge) creates licensing opportunity per the strategy doc
- Cross-vendor LoRa standardization potential (per DOE/NRCS programs)

---

## Definition of done

1. ✅ ~19 opcodes defined with ≥1 source per opcode
2. ✅ BLK-compressed .dpack
3. ✅ alpha_station.py in brigade
4. ✅ 15+ Ag chips in test corpus, all CORRECT
5. ✅ Existing 714-chip stress test still 100% SAFE / 0 WRONG / 0 INVALID
6. ✅ MCP data load
7. ✅ OSMP-SPEC entry for Α namespace
