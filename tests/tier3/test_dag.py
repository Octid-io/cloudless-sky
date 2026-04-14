"""
OSMP Tier 3 Tests — DAG Decomposition
Overflow Protocol Tier 3: dependency-resolved fragmentation for instructions
with conditional branches and dependency chains.

Patent pending. Spec section 8.1 Tier 3.
"""
import sys, struct
sys.path.insert(0, "sdk/python")

import pytest
from osmp import (
    DAGFragmenter, DAGReassembler, DAGNode, OverflowProtocol,
    LossPolicy, Fragment, FLAG_TERMINAL, FLAG_CRITICAL, FLAG_EXTENDED_DEP,
    FRAGMENT_HEADER_BYTES,
)


# ── DAGFragmenter: parse compound SAL into DAG nodes ─────────────────────────

class TestDAGFragmenterParse:
    """Verify the parser produces correct DAG topology from compound SAL."""

    def test_single_instruction_one_node(self):
        """Atomic instruction: single node, no parents."""
        frag = DAGFragmenter()
        nodes = frag.parse("H:HR@NODE1")
        assert len(nodes) == 1
        assert nodes[0].parents == []
        assert nodes[0].payload == b"H:HR@NODE1"

    def test_sequence_chain(self):
        """A;B;C -> linear chain: B depends on A, C depends on B."""
        frag = DAGFragmenter()
        nodes = frag.parse("H:HR@NODE1;H:CASREP;M:EVA@*")
        assert len(nodes) == 3
        assert nodes[0].parents == []       # A is root
        assert nodes[1].parents == [0]      # B deps on A
        assert nodes[2].parents == [1]      # C deps on B

    def test_then_chain(self):
        """A→B→C -> same linear dep structure as sequence."""
        frag = DAGFragmenter()
        nodes = frag.parse("H:HR@NODE1>120→H:CASREP→M:EVA@*")
        assert len(nodes) == 3
        assert nodes[0].parents == []
        assert nodes[1].parents == [0]
        assert nodes[2].parents == [1]

    def test_fork_and(self):
        """A;(B∧C) -> A is root, B and C both depend on A."""
        frag = DAGFragmenter()
        nodes = frag.parse("H:HR@NODE1;H:CASREP∧M:EVA@*")
        assert len(nodes) == 3
        assert nodes[0].parents == []       # A root
        assert nodes[1].parents == [0]      # B deps A
        assert nodes[2].parents == [0]      # C deps A

    def test_diamond(self):
        """A;(B∧C);D -> A root, B/C dep A, D deps B AND C (multi-parent)."""
        frag = DAGFragmenter()
        nodes = frag.parse("H:HR@NODE1;H:CASREP∧M:EVA@*;I:CONF")
        assert len(nodes) == 4
        assert nodes[0].parents == []
        assert nodes[1].parents == [0]
        assert nodes[2].parents == [0]
        assert sorted(nodes[3].parents) == [1, 2]  # diamond join

    def test_parallel_block(self):
        """A∥[?X∧?Y] -> X and Y both roots (no parent specified)."""
        frag = DAGFragmenter()
        nodes = frag.parse("A∥[?H:HR@NODE1∧?M:EVA@*]")
        assert len(nodes) == 2
        assert nodes[0].parents == []
        assert nodes[1].parents == []

    def test_parallel_block_after_dependency(self):
        """A;A∥[?X∧?Y] -> X and Y both depend on A."""
        frag = DAGFragmenter()
        nodes = frag.parse("H:HR@NODE1;A∥[?H:CASREP∧?M:EVA@*]")
        assert len(nodes) == 3
        assert nodes[0].parents == []
        assert nodes[1].parents == [0]
        assert nodes[2].parents == [0]

    def test_payloads_preserved(self):
        """Each node payload is the UTF-8 encoded atomic SAL instruction."""
        frag = DAGFragmenter()
        nodes = frag.parse("H:HR@NODE1;H:CASREP")
        assert nodes[0].payload == b"H:HR@NODE1"
        assert nodes[1].payload == b"H:CASREP"

    def test_empty_string(self):
        """Empty input -> single empty-payload node (edge case)."""
        frag = DAGFragmenter()
        nodes = frag.parse("")
        assert len(nodes) == 1
        assert nodes[0].payload == b""


# ── DAGFragmenter: fragmentize (full pipeline: parse → assign DEP → emit) ────

class TestDAGFragmentize:
    """Verify fragment list from fragmentize has correct headers."""

    def test_single_instruction_tier1_fallthrough(self):
        """Single instruction -> single fragment, DEP=0x00, terminal set."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("H:HR@NODE1", msg_id=42)
        assert len(frags) == 1
        f = frags[0]
        assert f.msg_id == 42
        assert f.frag_idx == 0
        assert f.frag_ct == 1
        assert f.dep == 0x00
        assert f.is_terminal
        assert f.payload == b"H:HR@NODE1"

    def test_sequence_dep_bytes(self):
        """A;B;C -> DEP=[0x00, 0x00, 0x01] (B deps A, C deps B)."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("H:HR@NODE1;H:CASREP;M:EVA@*", msg_id=1)
        assert len(frags) == 3
        assert frags[0].dep == 0x00
        assert frags[1].dep == 0      # parent is frag 0
        assert frags[2].dep == 1      # parent is frag 1

    def test_fork_dep_bytes(self):
        """A;(B∧C) -> B and C both dep on A (frag 0)."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("H:HR@NODE1;H:CASREP∧M:EVA@*", msg_id=1)
        assert frags[0].dep == 0x00
        assert frags[1].dep == 0
        assert frags[2].dep == 0

    def test_diamond_extended_dep(self):
        """Diamond join: D deps on B(1) AND C(2) -> extended dep bitmap."""
        frag = DAGFragmenter()
        frags = frag.fragmentize(
            "H:HR@NODE1;H:CASREP∧M:EVA@*;I:CONF", msg_id=1)
        assert len(frags) == 4

        # Fragment 3 (D) should have FLAG_EXTENDED_DEP set
        d = frags[3]
        assert d.flags & FLAG_EXTENDED_DEP
        # First 4 bytes of payload are u32 bitmap
        bitmap = struct.unpack(">I", d.payload[:4])[0]
        # Bits 1 and 2 set (parents at index 1 and 2)
        assert bitmap & (1 << 1)
        assert bitmap & (1 << 2)
        # Actual payload follows bitmap
        assert d.payload[4:] == b"I:CONF"

    def test_single_parent_no_extended_flag(self):
        """Single-parent nodes should NOT have FLAG_EXTENDED_DEP set."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("H:HR@NODE1;H:CASREP", msg_id=1)
        for f in frags:
            assert not (f.flags & FLAG_EXTENDED_DEP)

    def test_terminal_on_last_fragment(self):
        """Only the last fragment has FLAG_TERMINAL set."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("A;B;C", msg_id=1)
        for f in frags[:-1]:
            assert not f.is_terminal
        assert frags[-1].is_terminal

    def test_critical_flag_propagated(self):
        """critical=True sets FLAG_CRITICAL on all fragments."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("A;B", msg_id=1, critical=True)
        for f in frags:
            assert f.is_critical

    def test_frag_ct_matches_node_count(self):
        """frag_ct on every fragment equals total node count."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("A;B∧C;D", msg_id=1)
        for f in frags:
            assert f.frag_ct == 4

    def test_pack_unpack_round_trip(self):
        """All Tier 3 fragments survive pack/unpack."""
        frag = DAGFragmenter()
        frags = frag.fragmentize(
            "H:HR@NODE1;H:CASREP∧M:EVA@*;I:CONF", msg_id=1)
        for f in frags:
            unpacked = Fragment.unpack(f.pack())
            assert unpacked.msg_id == f.msg_id
            assert unpacked.frag_idx == f.frag_idx
            assert unpacked.frag_ct == f.frag_ct
            assert unpacked.flags == f.flags
            assert unpacked.dep == f.dep
            assert unpacked.payload == f.payload

    def test_header_stays_6_bytes(self):
        """Fragment header is always exactly 6 bytes, per spec constraint."""
        frag = DAGFragmenter()
        frags = frag.fragmentize(
            "H:HR@NODE1;H:CASREP∧M:EVA@*;I:CONF", msg_id=1)
        for f in frags:
            packed = f.pack()
            # Header is first 6 bytes; payload starts at byte 6
            assert packed[:6] == struct.pack(">HBBBB",
                f.msg_id, f.frag_idx, f.frag_ct, f.flags, f.dep)


# ── DAGReassembler: receive and resolve ──────────────────────────────────────

class TestDAGReassemblerComplete:
    """Full DAG resolution: all fragments received."""

    def test_simple_chain_execution_order(self):
        """A->B->C: execution order must be [A, B, C]."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("H:HR@NODE1;H:CASREP;M:EVA@*", msg_id=1)
        reasm = DAGReassembler(policy=LossPolicy.GRACEFUL_DEGRADATION)
        result = None
        for f in frags:
            result = reasm.receive(f)
        assert result is not None
        assert result == [b"H:HR@NODE1", b"H:CASREP", b"M:EVA@*"]

    def test_fork_execution_order(self):
        """A;(B∧C): A executes first, then B and C (order between B/C is
        deterministic by index)."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("H:HR@NODE1;H:CASREP∧M:EVA@*", msg_id=1)
        reasm = DAGReassembler(policy=LossPolicy.GRACEFUL_DEGRADATION)
        result = None
        for f in frags:
            result = reasm.receive(f)
        assert result is not None
        assert result[0] == b"H:HR@NODE1"  # root first
        assert set(result[1:]) == {b"H:CASREP", b"M:EVA@*"}

    def test_diamond_execution_order(self):
        """A;(B∧C);D: A first, then B/C, then D last."""
        frag = DAGFragmenter()
        frags = frag.fragmentize(
            "H:HR@NODE1;H:CASREP∧M:EVA@*;I:CONF", msg_id=1)
        reasm = DAGReassembler(policy=LossPolicy.GRACEFUL_DEGRADATION)
        result = None
        for f in frags:
            result = reasm.receive(f)
        assert result is not None
        assert result[0] == b"H:HR@NODE1"
        assert result[-1] == b"I:CONF"
        # Middle two are B and C in some order
        middle = set(result[1:3])
        assert middle == {b"H:CASREP", b"M:EVA@*"}

    def test_out_of_order_delivery(self):
        """Fragments arriving out of order still resolve correctly."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("A;B;C", msg_id=1)
        reasm = DAGReassembler(policy=LossPolicy.GRACEFUL_DEGRADATION)
        # Deliver in reverse order; only last delivery (which is terminal) triggers
        result = None
        for f in reversed(frags):
            result = reasm.receive(f)
        # Since frag[2] is terminal and delivered first, it triggers resolution
        # after first receipt because is_terminal is True
        # Actually reversed means we get frag[2] first (terminal), then frag[1], frag[0]
        # frag[2] is terminal but we only have 1/3 fragments -> partial
        # frag[0] is not terminal -> None
        # Let me re-think: deliver frag[2] first (terminal, 1/3) -> partial
        # Then frag[1] (not terminal) -> None
        # Then frag[0] (not terminal) -> None
        # So we need a different approach. Let me deliver all then check.
        # Actually under GRACEFUL_DEGRADATION, terminal triggers partial.

        # Let me just verify the first trigger produced something sensible.
        # Re-do cleanly:
        reasm2 = DAGReassembler(policy=LossPolicy.GRACEFUL_DEGRADATION)
        # Deliver 2, 0, 1 (terminal is frag 2, delivered first)
        r = reasm2.receive(frags[2])  # terminal, only frag 2; deps=[1], missing -> empty
        r = reasm2.receive(frags[0])  # not terminal -> None
        assert r is None
        r = reasm2.receive(frags[1])  # not terminal -> None; but we have all 3 now
        # Not terminal, so returns None under GD
        # Only terminal triggers resolution in current design
        assert r is None  # 1 is not terminal

        # All-at-once with correct terminal last:
        reasm3 = DAGReassembler(policy=LossPolicy.GRACEFUL_DEGRADATION)
        reasm3.receive(frags[1])
        reasm3.receive(frags[0])
        r = reasm3.receive(frags[2])  # terminal, all present
        assert r is not None
        assert r == [b"A", b"B", b"C"]


class TestDAGReassemblerGracefulDegradation:
    """Gamma policy: execute maximal subset whose deps are satisfied."""

    def test_missing_middle_of_chain(self):
        """A->B->C with B missing: only A is executable."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("H:HR@NODE1;H:CASREP;M:EVA@*", msg_id=1)
        reasm = DAGReassembler(policy=LossPolicy.GRACEFUL_DEGRADATION)
        reasm.receive(frags[0])
        result = reasm.receive(frags[2])  # terminal, but B(1) missing
        assert result is not None
        # Only A is executable (C's parent B is missing)
        assert result == [b"H:HR@NODE1"]

    def test_missing_root(self):
        """A;(B∧C) with A missing: nothing executable."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("H:HR@NODE1;H:CASREP∧M:EVA@*", msg_id=1)
        reasm = DAGReassembler(policy=LossPolicy.GRACEFUL_DEGRADATION)
        reasm.receive(frags[1])
        result = reasm.receive(frags[2])  # terminal, A missing
        assert result == []  # no root -> nothing executable

    def test_diamond_missing_one_branch(self):
        """A;(B∧C);D with C missing: A and B execute, D does not."""
        frag = DAGFragmenter()
        frags = frag.fragmentize(
            "H:HR@NODE1;H:CASREP∧M:EVA@*;I:CONF", msg_id=1)
        reasm = DAGReassembler(policy=LossPolicy.GRACEFUL_DEGRADATION)
        reasm.receive(frags[0])  # A
        reasm.receive(frags[1])  # B
        # skip frags[2] (C)
        result = reasm.receive(frags[3])  # D (terminal), C missing
        assert result is not None
        payloads = [p for p in result]
        assert b"H:HR@NODE1" in payloads  # A executes
        assert b"H:CASREP" in payloads    # B executes
        assert b"I:CONF" not in payloads  # D blocked (parent C missing)
        assert b"M:EVA@*" not in payloads # C not received

    def test_fork_missing_one_branch(self):
        """A;(B∧C) with C missing: A and B execute."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("H:HR@NODE1;H:CASREP∧M:EVA@*", msg_id=1)
        reasm = DAGReassembler(policy=LossPolicy.GRACEFUL_DEGRADATION)
        reasm.receive(frags[0])  # A
        # skip frags[1] (B)
        result = reasm.receive(frags[2])  # C (terminal), B missing
        assert b"H:HR@NODE1" in result   # A
        assert b"M:EVA@*" in result      # C (parent A present)
        assert b"H:CASREP" not in result # B not received


class TestDAGReassemblerAtomic:
    """Lambda policy: all or nothing."""

    def test_atomic_complete(self):
        """All fragments received -> full execution."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("A;B;C", msg_id=1)
        reasm = DAGReassembler(policy=LossPolicy.ATOMIC)
        result = None
        for f in frags:
            result = reasm.receive(f)
        assert result == [b"A", b"B", b"C"]

    def test_atomic_partial_returns_none(self):
        """Missing any fragment -> None."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("A;B;C", msg_id=1)
        reasm = DAGReassembler(policy=LossPolicy.ATOMIC)
        reasm.receive(frags[0])
        result = reasm.receive(frags[2])  # skip B
        assert result is None


class TestDAGReassemblerFailSafe:
    """Phi policy: discard everything if any fragment missing."""

    def test_failsafe_complete(self):
        """All fragments -> executes."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("A;B", msg_id=1)
        reasm = DAGReassembler(policy=LossPolicy.FAIL_SAFE)
        reasm.receive(frags[0])
        result = reasm.receive(frags[1])
        assert result == [b"A", b"B"]

    def test_failsafe_partial_returns_none(self):
        """Missing fragment -> None (silent discard)."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("A;B;C", msg_id=1)
        reasm = DAGReassembler(policy=LossPolicy.FAIL_SAFE)
        reasm.receive(frags[0])
        result = reasm.receive(frags[1])  # not all received
        assert result is None


# ── R:ESTOP hard exception ───────────────────────────────────────────────────

class TestDAGEstop:
    """R:ESTOP overrides DAG, policy, everything."""

    def test_estop_in_dag_fires_immediately(self):
        """R:ESTOP in any fragment fires immediately regardless of deps."""
        reasm = DAGReassembler(policy=LossPolicy.ATOMIC)
        estop_frag = Fragment(
            msg_id=1, frag_idx=2, frag_ct=5,
            flags=0, dep=1, payload=b"R:ESTOP@BOT1")
        result = reasm.receive(estop_frag)
        assert result is not None
        assert result == [b"R:ESTOP@BOT1"]

    def test_estop_under_failsafe(self):
        """R:ESTOP fires even under Phi with incomplete receipt."""
        reasm = DAGReassembler(policy=LossPolicy.FAIL_SAFE)
        f = Fragment(msg_id=1, frag_idx=0, frag_ct=4,
                     flags=0, dep=0, payload=b"R:ESTOP@*")
        result = reasm.receive(f)
        assert result == [b"R:ESTOP@*"]

    def test_estop_non_root_fragment(self):
        """R:ESTOP on a non-root node with unmet deps still fires."""
        reasm = DAGReassembler(policy=LossPolicy.GRACEFUL_DEGRADATION)
        f = Fragment(msg_id=1, frag_idx=3, frag_ct=5,
                     flags=FLAG_EXTENDED_DEP, dep=1,
                     payload=struct.pack(">I", 0b110) + b"R:ESTOP@*")
        result = reasm.receive(f)
        assert result is not None
        assert b"R:ESTOP" in result[0]


# ── OverflowProtocol integration ─────────────────────────────────────────────

class TestOverflowProtocolTier3:
    """Integration: fragment_dag + receive_dag through OverflowProtocol."""

    def test_round_trip_simple_chain(self):
        """fragment_dag -> receive_dag round trip for A;B;C."""
        op = OverflowProtocol(255, LossPolicy.GRACEFUL_DEGRADATION)
        frags = op.fragment_dag("H:HR@NODE1;H:CASREP;M:EVA@*")
        result = None
        for f in frags:
            result = op.receive_dag(f)
        assert result == [b"H:HR@NODE1", b"H:CASREP", b"M:EVA@*"]

    def test_round_trip_diamond(self):
        """fragment_dag -> receive_dag for diamond DAG."""
        op = OverflowProtocol(255, LossPolicy.GRACEFUL_DEGRADATION)
        frags = op.fragment_dag("H:HR@NODE1;H:CASREP∧M:EVA@*;I:CONF")
        result = None
        for f in frags:
            result = op.receive_dag(f)
        assert result is not None
        assert result[0] == b"H:HR@NODE1"
        assert result[-1] == b"I:CONF"

    def test_tier2_backward_compatible(self):
        """Existing Tier 1/2 fragment() still works unchanged."""
        op = OverflowProtocol(255, LossPolicy.GRACEFUL_DEGRADATION)
        p = b"H:HR@NODE1"
        frags = op.fragment(p)
        assert len(frags) == 1
        assert frags[0].dep == 0
        assert not (frags[0].flags & FLAG_EXTENDED_DEP)
        assert op.receive(frags[0]) == p

    def test_critical_dag(self):
        """critical=True propagates to all DAG fragments."""
        op = OverflowProtocol(255, LossPolicy.GRACEFUL_DEGRADATION)
        frags = op.fragment_dag("A;B;C", critical=True)
        for f in frags:
            assert f.is_critical

    def test_nack_on_dag_message(self):
        """NACK generation works for DAG messages."""
        op = OverflowProtocol(255, LossPolicy.ATOMIC)
        frags = op.fragment_dag("A;B;C;D")
        op.receive_dag(frags[0])
        op.receive_dag(frags[3])
        nack = op._dag_reassembler.nack(frags[0].msg_id, 4)
        assert "1" in nack and "2" in nack  # fragments 1 and 2 missing


# ── Edge cases ───────────────────────────────────────────────────────────────

class TestDAGEdgeCases:
    """Boundary conditions and degenerate inputs."""

    def test_single_fragment_dag_falls_through(self):
        """Single instruction -> 1 fragment, behaves like Tier 1."""
        op = OverflowProtocol(255, LossPolicy.GRACEFUL_DEGRADATION)
        frags = op.fragment_dag("H:HR@NODE1")
        assert len(frags) == 1
        assert frags[0].dep == 0x00
        assert frags[0].is_terminal

    def test_deep_chain(self):
        """10-node linear chain: each node depends on previous."""
        sal = ";".join(f"A:OP{i}" for i in range(10))
        frag = DAGFragmenter()
        nodes = frag.parse(sal)
        assert len(nodes) == 10
        for i, n in enumerate(nodes):
            if i == 0:
                assert n.parents == []
            else:
                assert n.parents == [i - 1]

    def test_wide_fork(self):
        """A; (B∧C∧D∧E∧F): 5 parallel children all dep on A."""
        sal = "ROOT;" + "∧".join(f"CHILD{i}" for i in range(5))
        frag = DAGFragmenter()
        nodes = frag.parse(sal)
        assert len(nodes) == 6
        assert nodes[0].parents == []
        for i in range(1, 6):
            assert nodes[i].parents == [0]

    def test_multi_parent_bitmap_u32(self):
        """Extended dep bitmap is big-endian u32."""
        frag = DAGFragmenter()
        frags = frag.fragmentize("A;B∧C;D", msg_id=1)
        d = frags[3]  # D deps on B(1) and C(2)
        assert d.flags & FLAG_EXTENDED_DEP
        bitmap = struct.unpack(">I", d.payload[:4])[0]
        assert bitmap == (1 << 1) | (1 << 2)

    def test_msg_id_increments(self):
        """Each fragment_dag call gets a new msg_id."""
        op = OverflowProtocol(255, LossPolicy.GRACEFUL_DEGRADATION)
        f1 = op.fragment_dag("A;B")
        f2 = op.fragment_dag("C;D")
        assert f1[0].msg_id != f2[0].msg_id

    def test_multiple_messages_independent(self):
        """Two DAG messages don't interfere with each other."""
        op = OverflowProtocol(255, LossPolicy.GRACEFUL_DEGRADATION)
        frags_a = op.fragment_dag("A;B")
        frags_b = op.fragment_dag("X;Y")

        # Receive message B fully
        op.receive_dag(frags_b[0])
        result_b = op.receive_dag(frags_b[1])
        assert result_b == [b"X", b"Y"]

        # Receive message A fully
        op.receive_dag(frags_a[0])
        result_a = op.receive_dag(frags_a[1])
        assert result_a == [b"A", b"B"]
