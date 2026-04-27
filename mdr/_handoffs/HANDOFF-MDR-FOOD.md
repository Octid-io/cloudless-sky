# MDR Handoff — FOOD domain

**Status:** Ready for parallel build.
**Author:** CTO/CLC (Claude) — 2026-04-26
**Owner:** Whoever picks this up (or MDR-creation agent once built).

---

## Goal

Build a Food MDR for OSMP that turns currently-passthrough inputs like "order me a pepperoni pizza", "two tacos al pastor", "deliver pizza to 123 Main", "what's the special tonight" into wire-grade SAL.

Closes the largest known gap in the brigade's adversarial corpus (10/60 ADV-FOOD chips currently passthrough — correct outcome today; CORRECT outcome once vocab ships).

---

## Scope

**In-scope** for Food MDR:
- Restaurant operations (order, menu, reservation, table, bill)
- Food traceability (lot, batch, supplier, source, expiration)
- Allergen / dietary tagging (gluten, dairy, nut, kosher, halal, vegan)
- Food safety (temperature, expiration, contamination, recall)
- Delivery / logistics (route, ETA, courier, address)
- Inventory (stock level, reorder point, par, depletion)

**Out-of-scope** (defer to other MDRs or never):
- Recipe authoring (creative work, not protocol)
- Marketing / promotion (not actuation)
- POS payment (use existing K namespace + new K opcodes only if needed)

---

## Namespace assignment

**Recommend new namespace `Φ` (Phi)** — Food / Provenance.

Rationale: F is taken (Flow), P is taken (Procedure), and the existing 26 Latin letters are full. The Greek extension pattern is established (Ω is Sovereign). Phi is structurally clean, visually distinct, no namespace collision.

Alternative: extend existing K (Commerce) with K:ORD-style opcodes for food-specific orders. CTO call needed — recommend Φ for separation, K extension if minimal.

---

## Authoritative reference lists

Every Food MDR opcode definition cites at least one authoritative source. Required references:

| Source | What it covers | URL |
|---|---|---|
| **FDA Food Code** | Safety + temperature requirements | https://www.fda.gov/food/retail-food-protection/fda-food-code |
| **USDA FSIS** | Inspection, traceability | https://www.fsis.usda.gov/ |
| **Codex Alimentarius** | International food standards | https://www.fao.org/fao-who-codexalimentarius/ |
| **GS1 Food Traceability** | Lot/batch identifier standards | https://www.gs1.org/standards/traceability |
| **HACCP** | Hazard analysis critical control points | https://www.fda.gov/food/hazard-analysis-critical-control-point-haccp |
| **Big-8 allergens** | FDA-required allergen list | https://www.fda.gov/food/food-labeling-nutrition/food-allergies |

---

## Proposed opcode catalog

| Opcode | Definition | Source |
|---|---|---|
| Φ:ORD | place_order | restaurant POS standard |
| Φ:ITEM | menu_item_reference | GS1 |
| Φ:LOT | lot_batch_identifier | GS1 |
| Φ:EXP | expiration_date_check | FDA Food Code |
| Φ:TEMP | food_temperature_reading | HACCP |
| Φ:ALRG | allergen_tag | FDA Big-8 |
| Φ:DIET | dietary_classification | Codex |
| Φ:RECALL | recall_event | USDA FSIS |
| Φ:DLVR | delivery_dispatch | logistics standard |
| Φ:STK | inventory_stock_level | restaurant ops |
| Φ:RSRV | reservation_create | OpenTable schema |
| Φ:MENU | menu_inquiry | restaurant POS |
| Φ:KIT | kitchen_ticket_dispatch | restaurant ops |
| Φ:BILL | check_bill_request | restaurant POS |
| Φ:VOID | order_void | POS standard |

~15 opcodes. Add slot definitions per opcode (e.g., Φ:ORD takes [item_id, qty, modifiers]; Φ:TEMP takes [F or C value]).

---

## Cross-domain reuse

- **E:TH** (env temp) — reuse for refrigeration/cooler/freezer monitoring (no new opcode)
- **T:EXP** (existing) — reuse for general expiration; Φ:EXP for food-specific compliance check
- **K:PAY** (existing) — reuse for restaurant payment; no new K opcode needed
- **G:POS** (existing) — reuse for delivery target location

This means Food MDR adds ~15 opcodes, not 30. Existing infra carries half.

---

## Wire format

Same as existing MDRs: BLK compression to `MDR-FOOD-FY2026-blk.dpack`. Standard format already used by ICD10CM, ISO20022, Meshtastic, MITRE-ATTACK.

Output files:
- `mdr/food/MDR-FOOD-DEFINITIONS-v1.csv` — full opcode + definition + source
- `mdr/food/MDR-FOOD-DEFINITIONS-v1.dpack` — block-compressed wire form
- `mdr/food/MDR-FOOD-blk.dpack` — load-once at SDK startup
- Update `osmp_mcp/data/` symlink for MCP access

---

## Brigade integration (after MDR ships)

1. Add `phi_station.py` to `sdk/python/osmp/brigade/stations/` — proposes Φ frames
2. Register in `default_registry()`
3. Add to corpus: 5-10 Food chips with Φ-namespace expected_sal
4. Re-run `phase1_brigade.py` against corpus + adversarial — confirm food chips now CORRECT, no regression on existing chips

---

## IP / patent impact

- Φ namespace is a new sovereign extension — confirm with CIP-v16 strategy whether it needs its own claim cluster or amends existing 14/15 (sensor namespaces).
- Big-8 allergen tagging is a regulatory requirement — could be claim of art around protocol-level allergen exposure for downstream agents. Worth flagging to IP review.

---

## Definition of done

1. ✅ All ~15 opcodes defined in CSV with definitions + ≥1 authoritative source per opcode
2. ✅ BLK-compressed .dpack file generated
3. ✅ phi_station.py wired into brigade
4. ✅ 10+ Food chips added to test corpus, all CORRECT
5. ✅ Existing 714-chip stress test still 100% SAFE / 0 WRONG / 0 INVALID
6. ✅ Loaded into MCP server's data dir
7. ✅ Doc entry in OSMP-SPEC about Φ namespace
