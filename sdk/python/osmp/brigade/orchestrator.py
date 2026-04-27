"""Orchestrator — the head chef. Plans the dish, calls stations, assembles, validates.

Deterministic v1: rule-based selection of station outputs. Future v2 will use
an LLM as the orchestrator with tool-call access to stations.
"""
from __future__ import annotations

import re

from ..protocol import validate_composition
from .request import ParsedRequest, FrameProposal
from .parser import (
    parse, MODIFIER_MARKERS_PATTERN, BRIDGE_ALLOWED_NAMESPACES,
    BRIDGE_FORBIDDEN_FRAMES,
)
from .stations import default_registry, BrigadeRegistry


from dataclasses import dataclass


@dataclass
class ComposeResult:
    """Structured composition result. The hint field is the teaching signal —
    when the composer can't fully compose, the hint explains why so the
    consumer (developer, LLM, or user) can adjust their input or extend vocab.
    """
    sal: str | None              # SAL string (None if passthrough)
    mode: str                    # 'sal' | 'bridge' | 'passthrough' | 'refused'
    hint: str | None = None      # Teaching message — why we made this decision
    residue: str | None = None   # NL residue (only set when mode='bridge')
    reason_code: str | None = None  # Machine-readable reason (NEGATION, INJECTION, NO_OPCODE, etc.)


class Orchestrator:
    """Coordinates the brigade. Takes NL, returns SAL or None (passthrough)."""

    def __init__(self, registry: BrigadeRegistry | None = None):
        self.registry = registry or default_registry()

    def compose(self, nl: str) -> str | None:
        """Top-level entry point. NL → SAL or None.

        Backward-compatible API — discards the hint. For teaching/diagnostic
        contexts, use compose_with_hint() instead.
        """
        result = self.compose_with_hint(nl)
        return result.sal

    def compose_with_hint(self, nl: str) -> ComposeResult:
        """Compose NL → ComposeResult including teaching hint.

        Hint is set whenever:
          - mode='passthrough' (why we couldn't compose)
          - mode='refused' (safety gate fired — explains which one)
          - mode='bridge' (what part stayed as NL residue)

        Mode='sal' results have hint=None (no teaching needed; success).
        """
        req = parse(nl)
        return self._compose_request_with_hint(req, nl)

    def _compose_request_with_hint(self, req: ParsedRequest, raw: str) -> ComposeResult:
        """Same as _compose_request but returns ComposeResult with teaching hint."""
        # Min byte threshold
        if len(raw.encode("utf-8")) < 5:
            return ComposeResult(sal=None, mode='refused',
                                  reason_code='INPUT_TOO_SHORT',
                                  hint=f"Input too short ({len(raw.encode('utf-8'))}B); minimum 5B for any compose attempt.")
        # Negation
        if req.is_negated:
            return ComposeResult(sal=None, mode='refused',
                                  reason_code='NEGATION',
                                  hint="Input contains negation marker (don't / do not / never / cancel / abort). Refused per safety doctrine — emitting affirmative SAL would fire the wrong action.")
        # Glyph injection / code injection / email / idiom
        if req.has_glyph_injection:
            return ComposeResult(sal=None, mode='refused',
                                  reason_code='UNSAFE_INPUT',
                                  hint="Input contains SAL-like syntax, code-injection patterns, email addresses, or known verb idioms. Refused per safety doctrine.")
        # Pronoun-object
        PRONOUN_OBJECTS = {"that", "it", "this", "them", "these", "those", "everything"}
        if req.verb_lemma and req.direct_object:
            dobj_first = req.direct_object.lower().strip().split()[0]
            if dobj_first in PRONOUN_OBJECTS and not req.targets:
                return ComposeResult(sal=None, mode='refused',
                                      reason_code='UNRESOLVED_PRONOUN',
                                      hint=f"Verb '{req.verb_lemma}' followed by pronoun '{dobj_first}' with no antecedent. Refused — receiver cannot resolve the target.")

        # Action verb + non-actuator object check
        from .parser import ACTUATOR_OBJECT_NOUNS
        ACTION_VERBS_NEEDING_VALID_OBJECT = {"stop", "halt", "cease", "block",
                                               "close", "lock", "open", "unlock",
                                               "start", "kill", "shutdown", "shut",
                                               "reboot", "restart"}
        if (req.verb_lemma in ACTION_VERBS_NEEDING_VALID_OBJECT
            and req.direct_object):
            obj_first = req.direct_object.lower().strip().split()[0]
            if (obj_first not in ACTUATOR_OBJECT_NOUNS
                and not any(t.source == "entity" for t in req.targets)):
                return ComposeResult(sal=None, mode='refused',
                                      reason_code='NON_ACTUATOR_OBJECT',
                                      hint=f"Verb '{req.verb_lemma}' applied to '{obj_first}' — not a known actuator. The object isn't in the protocol's device/system whitelist. Either rephrase with a structured target ID (e.g., 'stop conveyor 3') or extend ACTUATOR_OBJECT_NOUNS.")

        # Chain handling
        if req.has_chain():
            sal = self._compose_chain(req, raw)
            if sal:
                return ComposeResult(sal=sal, mode='sal')
            return ComposeResult(sal=None, mode='passthrough',
                                  reason_code='CHAIN_INCOMPLETE',
                                  hint="Input has chain markers (then/and) but at least one segment couldn't be composed. Refusing chain to avoid partial-action emission.")

        # Single-frame composition
        sal = self._compose_single_frame(req, raw)
        if sal:
            return ComposeResult(sal=sal, mode='sal')

        # Try bridge mode
        proposals_by_ns = self.registry.propose_all(req)
        bridge = self._try_bridge_mode(req, proposals_by_ns, raw)
        if bridge:
            # Split SAL and residue from bridge format "SAL::residue"
            if "::" in bridge:
                sal_part, residue = bridge.split("::", 1)
                return ComposeResult(sal=sal_part, mode='bridge',
                                      residue=residue, reason_code='PARTIAL_COMPOSE',
                                      hint=f"Composed primary intent as SAL; residue '{residue.strip()}' carried as NL context for the receiver.")
            return ComposeResult(sal=bridge, mode='sal')

        # Final passthrough — diagnose why
        if not req.namespace_hints and not req.targets and not req.slot_values:
            return ComposeResult(sal=None, mode='passthrough',
                                  reason_code='NO_PROTOCOL_CONTENT',
                                  hint="Input doesn't contain protocol-recognizable content (no verb in lexicon, no entity targets, no slot values). Likely conversational or out-of-scope.")

        # Has some signal but no proposal qualified
        signals = []
        if req.verb_lemma: signals.append(f"verb='{req.verb_lemma}'")
        if req.targets: signals.append(f"targets={[t.id for t in req.targets]}")
        if req.namespace_hints: signals.append(f"namespaces={list(req.namespace_hints)}")
        return ComposeResult(sal=None, mode='passthrough',
                              reason_code='NO_OPCODE_MATCH',
                              hint=f"Parsed signals ({', '.join(signals)}) but no station produced a valid frame. Likely a vocab gap — opcode for this concept may not exist in current ASD, or station rules need extension.")

    def _compose_request(self, req: ParsedRequest, raw: str) -> str | None:
        # Min byte threshold (very short inputs can't compress and very-short
        # inputs like "go", "stop", "ping" alone are too ambiguous)
        if len(raw.encode("utf-8")) < 5:
            return None
        # SAFETY: refuse to compose negated inputs.
        # "don't stop" must NOT compose to R:STOP — that would fire the action.
        # Per asymmetric-failure doctrine: passthrough is safe; wrong-action is fatal.
        if req.is_negated:
            return None
        # SAFETY: refuse glyph-injection inputs. User typed SAL syntax in NL —
        # could be adversarial probing or confused user. Either way, refuse.
        if req.has_glyph_injection:
            return None
        # SAFETY: refuse pronoun-object inputs ("stop that", "do it", "send this").
        # Without an antecedent the receiver cannot resolve the object.
        PRONOUN_OBJECTS = {"that", "it", "this", "them", "these", "those", "everything"}
        if req.verb_lemma and req.direct_object:
            dobj_first = req.direct_object.lower().strip().split()[0]
            if dobj_first in PRONOUN_OBJECTS and not req.targets:
                return None

        # SAFETY: refuse action verb + abstract / non-actuator object.
        # "stop bothering" → bothering isn't a real actuator target.
        # "stop ordering pizza" → ordering isn't an actuator.
        # The actuator-verb's object must be in the actuator-noun whitelist
        # OR be a structured target ID.
        from .parser import ACTUATOR_OBJECT_NOUNS
        ACTION_VERBS_NEEDING_VALID_OBJECT = {"stop", "halt", "cease", "block",
                                               "close", "lock", "open", "unlock",
                                               "start", "kill", "shutdown", "shut",
                                               "reboot", "restart"}
        if (req.verb_lemma in ACTION_VERBS_NEEDING_VALID_OBJECT
            and req.direct_object):
            obj_first = req.direct_object.lower().strip().split()[0]
            if (obj_first not in ACTUATOR_OBJECT_NOUNS
                and not any(t.source == "entity" for t in req.targets)):
                # Object isn't a known actuator AND no structured entity target.
                # Refuse rather than emit "R:STOP@ORDERING" which makes no sense.
                return None
        # (removed bare-noun gate — too aggressive; broke valid 2-word inputs
        # like "wind speed", "uptime", "battery level". Stations + validator
        # gate emission. Truly ambiguous bare nouns are caught by the
        # confidence-priority logic in _build_single_best.)
        # Note: we let stations propose regardless of ns_hints — passthrough
        # falls out naturally if no station proposes anything.

        # Chain handling: each segment composes independently, then joined with chain operator
        if req.has_chain():
            return self._compose_chain(req, raw)

        # Single-frame composition
        return self._compose_single_frame(req, raw)

    def _compose_chain(self, req: ParsedRequest, raw: str) -> str | None:
        # For chain segments, BAEL is enforced at the WHOLE-chain level against
        # the parent NL — not per segment. So compose each segment using the
        # PARENT raw as the NL context, allowing segments that would bust
        # BAEL alone to still contribute to a chain that fits BAEL overall.
        sub_sals: list[str] = []
        for seg in req.chain_segments:
            sub = self._compose_request(seg, raw)  # use parent raw, not seg.raw
            if sub is None:
                # Try with the segment's own raw as a fallback
                sub = self._compose_request(seg, seg.raw)
            if sub is None:
                return None
            sub_sals.append(sub)
        if len(sub_sals) < 2:
            return None
        joined = (req.chain_operator or "\u2227").join(sub_sals)
        result = validate_composition(joined, nl=raw)
        if result.valid:
            return joined
        return None

    def _compose_single_frame(self, req: ParsedRequest, raw: str) -> str | None:
        # Run all stations
        proposals_by_ns = self.registry.propose_all(req)

        if not proposals_by_ns:
            return None

        # Selection rules (in priority order):
        # 1. EMERGENCY: R:ESTOP wins over everything
        # 2. AUTHORIZATION_REQUIRED: prepend I:§→ to the action frame
        # 3. CONDITIONS present: condition-bearing chain (sense → alert)
        # 4. SCHEDULE present: T:SCHED prepended
        # 5. Single best frame: pick the highest-confidence non-wrapper proposal
        # 6. Multi-frame: combine sensing + auxiliary frames if needed

        # Rule 1: emergency
        for p in proposals_by_ns.get("R", []):
            if p.opcode == "ESTOP":
                sal = p.assemble()
                if validate_composition(sal, nl=raw).valid:
                    return sal

        # Rule 3: conditions present (X<N → ALERT chain)
        if req.conditions:
            sal = self._build_conditional_chain(req, proposals_by_ns, raw)
            if sal:
                return sal

        # Rule 4: schedule present (T:SCHED → action chain)
        if req.schedule and req.verb_lemma:
            sal = self._build_scheduled_chain(req, proposals_by_ns, raw)
            if sal:
                return sal

        # Rule 5: single frame — pick best
        sal = self._build_single_best(req, proposals_by_ns, raw)
        # Rule 5b: if no single-frame composition, try bridge mode
        # Bridge returns "SAL::residue" — split, return only the SAL part
        # via compose() (residue surfaces via compose_with_hint()).
        if not sal:
            bridge = self._try_bridge_mode(req, proposals_by_ns, raw)
            if bridge:
                if "::" in bridge:
                    sal_part, _residue = bridge.split("::", 1)
                    # Validate SAL part standalone
                    v = validate_composition(sal_part, nl=raw)
                    if v.valid:
                        return sal_part
                else:
                    return bridge
        if sal:
            # Apply authorization precondition if needed
            if req.authorization_required:
                # SAFETY: don't apply I:§→ to non-action frames (U:APPROVE, etc.)
                # I:§→U:APPROVE is meaningless — auth gate to an approval signal.
                # Only prepend I:§→ to action frames (R, K, M, C, D-write, S-write).
                action_namespaces = {"R", "K", "M", "C", "S"}
                # Extract the namespace of the primary frame (first opcode in sal)
                import re as _re_ns
                m = _re_ns.match(r'([A-Z\u03a9]):', sal)
                primary_ns = m.group(1) if m else None
                if primary_ns in action_namespaces:
                    sal = self._apply_auth_precondition(sal, proposals_by_ns)
                else:
                    # Auth required but no action frame — refuse to emit a meaningless
                    # I:§→<non-action> chain. Passthrough is safer.
                    return None
            result = validate_composition(sal, nl=raw)
            if result.valid:
                return sal

        return None

    def _pick_namespace_priority(self, req: ParsedRequest, proposals_by_ns: dict) -> list[str]:
        """Order namespaces by relevance to this request."""
        order = []
        # Domain hint takes priority
        if req.domain_hint:
            DOMAIN_PRIORITY = {
                "medical":        ["H", "I", "U", "L"],
                "uav":            ["V", "R", "G", "I"],
                "weather":        ["W", "E"],
                "device_control": ["R", "C"],
                "meshtastic":     ["A", "N", "G", "O"],
                "crypto":         ["S", "I"],
                "config":         ["N", "T"],
                "vehicle":        ["V", "G"],
                "sensor":         ["E"],
            }
            order.extend(DOMAIN_PRIORITY.get(req.domain_hint, []))
        # Then namespace hints from parser
        for ns in req.namespace_hints:
            if ns not in order:
                order.append(ns)
        # Then anything else that proposed
        for ns in proposals_by_ns:
            if ns not in order:
                order.append(ns)
        return order

    def _build_single_best(self, req: ParsedRequest, proposals_by_ns: dict, raw: str) -> str | None:
        """Pick the single best frame proposal.

        Strategy:
          1. Try high-confidence proposals (>=2.0) FIRST regardless of namespace.
             Stations use confidence to flag explicit overrides (I:ID for
             "verify identity" overrides S:VFY).
          2. Within normal-confidence proposals, prefer by namespace priority
             (domain hint + ns_hints from parser).
          3. Try also-without-target variant of each proposal (e.g., R:STOP↺
             alone might validate even if R:STOP↺@CONVEYOR busts BAEL).
          4. As a last resort, try 2-frame conjunctive combinations.
        """
        order = self._pick_namespace_priority(req, proposals_by_ns)

        # Phase 1: high-confidence overrides (across all namespaces)
        all_props: list[FrameProposal] = []
        for ns in proposals_by_ns:
            all_props.extend(proposals_by_ns[ns])
        high_conf = [p for p in all_props if p.confidence >= 2.0]
        for p in sorted(high_conf, key=lambda p: (-p.confidence, len(p.assemble().encode("utf-8")))):
            for variant in self._frame_variants(p):
                v = validate_composition(variant, nl=raw)
                if v.valid:
                    return variant

        # Phase 2: namespace-priority order
        for ns in order:
            props = proposals_by_ns.get(ns, [])
            if not props:
                continue
            # Skip already-handled high-conf (they failed validation above)
            normal = [p for p in props if p.confidence < 2.0]
            if not normal:
                continue
            sorted_props = sorted(normal, key=lambda p: (-p.confidence, len(p.assemble().encode("utf-8"))))
            for p in sorted_props:
                for variant in self._frame_variants(p):
                    v = validate_composition(variant, nl=raw)
                    if v.valid:
                        return variant

        # Phase 3: 2-frame conjunctive combinations
        if len(all_props) >= 2:
            for i, p1 in enumerate(all_props):
                for p2 in all_props[i + 1:]:
                    if p1.namespace == p2.namespace and p1.opcode == p2.opcode:
                        continue
                    sal = p1.assemble() + "\u2227" + p2.assemble()
                    if validate_composition(sal, nl=raw).valid:
                        return sal
        return None

    def _frame_variants(self, p: FrameProposal) -> list[str]:
        """Return progressively-shorter variants of a frame proposal.

        Try with all decorations first, then strip target, then strip query
        marker. Each step makes the SAL shorter, which helps fit BAEL when
        the input is itself short.
        """
        variants = [p.assemble()]
        # Without target
        if p.target:
            stripped = FrameProposal(
                namespace=p.namespace, opcode=p.opcode,
                target=None,
                slot_values=p.slot_values,
                consequence_class=p.consequence_class,
                is_query=p.is_query,
            )
            variants.append(stripped.assemble())
        # Without query marker
        if p.is_query:
            no_q = FrameProposal(
                namespace=p.namespace, opcode=p.opcode,
                target=p.target,
                slot_values=p.slot_values,
                consequence_class=p.consequence_class,
                is_query=False,
            )
            variants.append(no_q.assemble())
        # Without target AND without query
        if p.target and p.is_query:
            bare = FrameProposal(
                namespace=p.namespace, opcode=p.opcode,
                slot_values=p.slot_values,
                consequence_class=p.consequence_class,
            )
            variants.append(bare.assemble())
        # Dedupe preserving order
        seen = set()
        out = []
        for v in variants:
            if v not in seen:
                out.append(v)
                seen.add(v)
        return out

    def _build_conditional_chain(self, req: ParsedRequest, proposals_by_ns: dict, raw: str) -> str | None:
        """Build a sensing→alert chain when conditions are present."""
        # Find sensing proposal (E, H, W namespaces)
        sensing = None
        for ns in ("H", "E", "W", "V"):
            for p in proposals_by_ns.get(ns, []):
                if p.opcode in ("HR", "BP", "TH", "HU", "PU", "WIND", "SPO2", "TEMP", "HDG", "POS"):
                    sensing = p
                    break
            if sensing:
                break

        if not sensing:
            return None

        # Find alert proposal — prefer same-namespace alert (H:ALERT for H sensing, W:ALERT for W)
        alert = None
        if sensing.namespace == "H":
            for p in proposals_by_ns.get("H", []):
                if p.opcode in ("ALERT", "CASREP"):
                    alert = p
                    break
        if not alert and sensing.namespace == "W":
            for p in proposals_by_ns.get("W", []):
                if p.opcode == "ALERT":
                    alert = p
                    break
        # Fallbacks: U:NOTIFY > U:ALERT > L:ALERT
        if not alert:
            for ns in ("U", "L"):
                for p in proposals_by_ns.get(ns, []):
                    if p.opcode in ("NOTIFY", "ALERT"):
                        alert = p
                        break
                if alert:
                    break

        if not alert:
            return None

        # Build sensing<COND→alert
        cond = req.conditions[0]
        sensing_sal = sensing.assemble() + cond.operator + cond.value
        alert_sal = alert.assemble()
        sal = sensing_sal + "\u2192" + alert_sal
        if validate_composition(sal, nl=raw).valid:
            return sal
        return None

    def _build_scheduled_chain(self, req: ParsedRequest, proposals_by_ns: dict, raw: str) -> str | None:
        """Build T:SCHED→action chain."""
        # Find action proposal across many namespaces — schedule can drive any action
        action = None
        # Broaden the action set so U:NOTIFY, H:ALERT, etc. count as scheduled-action targets
        SCHEDULABLE_OPCODES = {"PING", "STOP", "BK", "CFG", "RSTRT", "ENC", "SIGN",
                                "ALERT", "NOTIFY", "PUSH", "FETCH", "STORE", "BACKUP",
                                "Q", "MOV", "CAM", "MIC", "TORCH", "HAPTIC", "REPORT",
                                "AUDIT", "LOG", "VFY", "ID"}
        for ns in ("A", "R", "N", "C", "S", "L", "U", "H", "W", "I"):
            for p in proposals_by_ns.get(ns, []):
                if p.opcode in SCHEDULABLE_OPCODES:
                    action = p
                    break
            if action:
                break
        if not action:
            return None

        sched_sal = f"T:SCHED[{req.schedule}]"
        # Try → (3 bytes) first; if BAEL fails, try ; (1 byte) as semantic equivalent
        for op in ("\u2192", ";"):
            sal = sched_sal + op + action.assemble()
            if validate_composition(sal, nl=raw).valid:
                return sal
        return None

    def _try_bridge_mode(self, req: ParsedRequest, proposals_by_ns: dict, raw: str) -> str | None:
        """Bridge mode: emit partial SAL + NL residue when single-frame composition fails.

        Allowed only for sensing-namespace proposals where:
          1. Frame namespace is in BRIDGE_ALLOWED_NAMESPACES
          2. Frame (namespace, opcode) NOT in BRIDGE_FORBIDDEN_FRAMES
          3. Residue NL contains no modifier markers (unless/only if/except/etc.)
          4. SAL part validates standalone
          5. Composite (SAL :: residue) byte length is < NL bytes (BAEL still rules)

        Returns: "FRAME :: residue" if all conditions met, else None.

        The receiver (per protocol decode) actuates on FRAME and surfaces the
        residue as additional context. This is doctrine-grade fail-soft for
        sensing inputs that can't fully encode.
        """
        # Pick the best sensing-namespace proposal
        bridge_candidate: FrameProposal | None = None
        for ns in proposals_by_ns:
            if ns not in BRIDGE_ALLOWED_NAMESPACES:
                continue
            for p in proposals_by_ns[ns]:
                if (p.namespace, p.opcode) in BRIDGE_FORBIDDEN_FRAMES:
                    continue
                # Per-frame: ALERT/CASREP etc. excluded
                if p.opcode in ("ALERT", "CASREP", "ESTOP", "STOP", "MOV", "RTH",
                                  "CFG", "BK", "KILL", "RSTRT", "ENC", "DEC",
                                  "SIGN", "KEYGEN", "PUSH", "DEL", "FORM",
                                  "CAM", "MIC", "SPKR", "TORCH", "HAPTIC", "VIBE",
                                  "BT", "WIFI", "DISP", "RTH", "SCRN"):
                    continue
                if bridge_candidate is None or p.confidence > bridge_candidate.confidence:
                    bridge_candidate = p

        if not bridge_candidate:
            return None

        # Build the bare frame string
        sal_part = bridge_candidate.assemble()
        v = validate_composition(sal_part, nl=raw)
        if not v.valid:
            # Can't bridge with an invalid SAL part
            return None

        # Compute residue: the input NL with the matched opcode-related words removed
        # Simple heuristic: residue is everything except the captured intent.
        # For now: residue is the full NL minus stopwords + the verb (rough approximation).
        residue = self._compute_residue(req, bridge_candidate)
        if not residue.strip():
            # No real residue — the SAL fully captures intent, just return it
            return sal_part

        # Modifier-marker check: if residue contains "unless"/"only if"/"except", etc.,
        # it might gate the SAL action. Forbid bridge — passthrough is safer.
        if MODIFIER_MARKERS_PATTERN.search(residue):
            return None

        # Compose with bridge separator. Wire form: "<SAL>::<NL_RESIDUE>"
        # The "::" separator is bijective with NL since "::" is reserved in SAL grammar.
        composite = f"{sal_part}::{residue}"

        # BAEL: composite must still be smaller than original NL
        if len(composite.encode("utf-8")) >= len(raw.encode("utf-8")):
            return None

        return composite

    def _compute_residue(self, req: ParsedRequest, proposal: FrameProposal) -> str:
        """Compute the NL residue after extracting what the proposal captures.

        Heuristic: strip the verb, the matched opcode keywords, and stopwords.
        What's left is residue. Simple but functional for v1.
        """
        # Extract opcode-related words from the proposal's rationale and definition
        # (rationale is "phrase 'X' -> Y:Z" form, X is the matched phrase)
        consumed_words: set[str] = set()
        if req.verb:
            consumed_words.add(req.verb.lower())
        if req.verb_lemma and req.verb_lemma != req.verb:
            consumed_words.add(req.verb_lemma.lower())
        if req.direct_object:
            for w in req.direct_object.lower().split():
                consumed_words.add(w)
        # Add target words to consumed (already in the @binding)
        for t in req.targets:
            consumed_words.add(t.id.lower())
        # Add slot-value words to consumed
        for sv in req.slot_values:
            consumed_words.add(sv.value.lower())

        # Filter input tokens
        STOPWORDS = {"the", "a", "an", "to", "of", "for", "from", "with",
                     "and", "or", "is", "are", "be", "been", "this", "that",
                     "please", "could", "you", "i", "me", "my"}
        residue_tokens = []
        for tok in req.raw.split():
            clean = tok.lower().strip(".,!?;:'\"")
            if clean in consumed_words or clean in STOPWORDS:
                continue
            residue_tokens.append(tok)
        return " ".join(residue_tokens)

    def _apply_auth_precondition(self, sal: str, proposals_by_ns: dict) -> str:
        """Prepend I:§→ to enforce authorization."""
        # Use I:§ if I-station proposed it
        i_props = proposals_by_ns.get("I", [])
        for p in i_props:
            if p.opcode == "\u00a7":
                return f"I:\u00a7\u2192{sal}"
        # Default: still prepend I:§
        return f"I:\u00a7\u2192{sal}"
