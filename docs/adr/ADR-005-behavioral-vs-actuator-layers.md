# ADR-005: Behavioral Command Layer vs Actuator Command Layer in R Namespace

Status: Accepted
Date: April 8, 2026
Priority: v15 dictionary refinement
Related: OSMP-SPEC-v1.0.2.md, OSMP-semantic-dictionary-v15.csv

## Context

The OSMP R namespace (Robotic / Physical Agent) carries opcodes that command physical actions on robotic and autonomous vehicle systems. During the v14 to v15 dictionary refinement, a structural distinction was identified in how physical motion commands operate across autonomous system architectures. This ADR captures that distinction as a formal namespace design pattern and explains why v15 adds paired command entries rather than single unified entries for acceleration and deceleration semantics.

## Problem

Physical motion commands in autonomous systems operate at two distinct abstraction layers. A planning layer emits behavioral targets such as "reduce speed to 15 mph in the next 50 meters" without specifying the means. A control layer translates those targets into actuator commands such as "brake pressure 0.3, throttle 0.0, steering angle 0.02" that act directly on physical systems. Every production autonomous vehicle stack maintains this separation: Waymo, Cruise, Tesla FSD, Zoox, and Zoox-derived platforms all emit behavioral targets at the planning layer and translate to actuator commands at the control layer. ROS2 maintains the same separation through nav_msgs versus control_msgs. SAE J3016 OEDR (Object Event Detection Response) formalizes the planning-versus-control distinction in the DDT fallback taxonomy.

The v14 R namespace included R:STOP for "come to a halt" and R:ESTOP for "engage emergency stop immediately" which implicitly captured the abstraction layers for stopping commands. But v14 did not include corresponding paired entries for acceleration and deceleration. Agents emitting motion commands had to either force a behavioral target into a control-layer mnemonic or force an actuator command into a behavioral mnemonic, losing the abstraction layer distinction at the wire format.

## Decision

Adopt paired abstraction-layer entries in the R namespace for motion commands that span the behavioral/actuator distinction. For each motion concept that operates at both layers in real-world autonomous systems, the v15 dictionary adds two entries: one carrying the behavioral semantic (target state, means unspecified) and one carrying the actuator semantic (direct mechanism engagement).

The acceleration/deceleration pair becomes:

- R:ACC — accelerate_behavioral (target state: speed increase; means selected by receiving system)
- R:THR — throttle_actuator (direct throttle mechanism engagement command)
- R:DECEL — decelerate_behavioral (target state: speed decrease; means selected by receiving system)
- R:BRK — brake_actuator (direct brake mechanism engagement command)

Four entries, four distinct semantics, total byte count 22 bytes for the complete motion vocabulary across both abstraction layers.

The existing v14 entries R:STOP and R:ESTOP continue to cover the stopping pair and do not require renaming or supplementing under this pattern. R:STOP is the behavioral "come to a halt" command. R:ESTOP is the actuator-layer emergency stop engagement. The two entries already match the pattern; v15 validates and formalizes the pattern rather than introducing it.

The existing v14 entry R:YIELD (yield_right_of_way, COLREGs Rule 16/17 give-way craft) is classified as a behavioral command under this pattern. It has no paired actuator entry because yielding is inherently a behavioral outcome, not a single actuator engagement. No v15 addition is proposed.

## Consequences

### Positive

The R namespace now carries an abstraction-layer pattern grounded in established autonomous systems architecture that agents can rely on. An agent issuing a planning-layer command uses R:DECEL and the receiving system's controller selects the means. An agent issuing a control-layer command uses R:BRK and the receiving actuator engages the brake directly. The two commands are not interchangeable, and the distinction is preserved at the wire format layer without additional slot values or frame metadata.

The pattern is extensible. Future refinement rounds that surface similar abstraction-layer distinctions in the R namespace can add paired entries following this ADR as the reference precedent. Candidates to watch include steering (behavioral heading target vs actuator steering angle command), speed maintenance (behavioral cruise target vs actuator throttle/brake modulation), lane keeping (behavioral lane center target vs actuator steering correction), and landing (behavioral landing command vs actuator gear/flap engagement).

### Negative

The R namespace gains 4 new entries where a simpler design would have used 1 or 2. Agents composing motion commands now need to know which abstraction layer their receiving system operates at. This is a real complexity cost for SDK authors writing composition helpers.

The 7-byte R:DECEL entry is the longest new addition in the v15 delta. It sits at the boundary of acceptable brevity for constrained channels.

The behavioral/actuator distinction is not universally recognized across all autonomous system architectures. Some simpler platforms (agricultural autosteer, warehouse AGV, delivery drone) do not maintain a two-layer separation because their planning and control are fused in a single decision loop. For these platforms, the sibling entries are redundant.

### Neutral

The ADR does not prescribe slot value conventions for the new entries. Slot value schemas are orthogonal to the behavioral/actuator layer distinction and are addressed in separate specification sections.

The ADR does not affect existing v14 scope. R:ACCEL remains as accelerometer_data_stream. R:ACC is the new verb and occupies a different mnemonic slot. The two entries coexist in the R namespace without dictionary-level conflict.

## Cross-References

### Related v15 delta entries

- The v15 dictionary contains the four R-namespace motion entries introduced by this ADR: R:ACC, R:THR, R:DECEL, R:BRK.
- The v15 dictionary also contains four multi-namespace ADJ entries (R:ADJ, O:ADJ, Z:ADJ, A:ADJ) which follow a separate namespace-portable semantic pattern.

### Authoritative sources

- SAE J3016: Taxonomy and definitions for terms related to driving automation systems for on-road motor vehicles (DDT fallback, OEDR, behavioral competence hierarchy)
- ISO 22736: Road vehicles — Taxonomy for automated driving systems
- ROS2 nav_msgs vs control_msgs package separation
- IEC 61131-3 (industrial control system command hierarchy) as a parallel precedent for the behavioral/actuator distinction in non-autonomous-vehicle control contexts

## Decision Record

Decision: Adopt paired behavioral/actuator entries for motion commands in R namespace starting with v15.
Approved by: Clay Holberg (inventor).
Implementation: v15 dictionary contains the four new R-namespace entries.
Supersedes: None (new pattern).
Superseded by: None.
