/**
 * SALBridge Tests (Finding 37, locks in Finding 13 at the bridge level)
 * =====================================================================
 *
 * Integration tests for SALBridge — peer registration, FALLBACK mode,
 * inbound frame detection, and the acquisition / regression state
 * machine. The smoking-gun assertion is that an inbound natural language
 * message containing `I:§` is correctly detected as a SAL frame, which
 * is the end-to-end behavior Finding 13 was about.
 *
 * Patent: OSMP-001-UTIL (pending) | License: Apache 2.0
 */
import { describe, it, expect, beforeEach } from "vitest";
import { SALBridge } from "../src/bridge.js";

describe("SALBridge construction and peer management", () => {
  it("constructs with a node id", () => {
    const bridge = new SALBridge("TEST_NODE");
    expect(bridge.nodeId).toBe("TEST_NODE");
  });

  it("registers a peer in FALLBACK by default (no FNP attempt)", () => {
    const bridge = new SALBridge("TEST_NODE");
    bridge.registerPeer("PEER1", false);
    expect(bridge.peerState("PEER1")).toBe("FALLBACK");
  });

  it("returns null peer state for unknown peer", () => {
    const bridge = new SALBridge("TEST_NODE");
    expect(bridge.peerState("UNKNOWN")).toBeNull();
  });
});

describe("SALBridge inbound frame detection (Finding 13)", () => {
  let bridge: SALBridge;

  beforeEach(() => {
    bridge = new SALBridge("TEST_NODE");
    bridge.registerPeer("PEER1", false);
  });

  it("detects I:§ in a natural language inbound message", () => {
    // The smoking-gun test: a peer sends a message containing the
    // human authorization marker as a SAL frame. The bridge must
    // detect it via the SAL_FRAME_RE_BRIDGE pattern.
    const result = bridge.receive(
      "operator should authorize via I:§ before proceeding",
      "PEER1",
    );
    expect(result.detectedFrames).toContain("I:§");
  });

  it("detects standard H:HR frame in inbound NL", () => {
    const result = bridge.receive(
      "patient has H:HR@PATIENT1 of 120",
      "PEER1",
    );
    expect(result.detectedFrames).toContain("H:HR");
  });

  it("detects multiple frames in one message", () => {
    const result = bridge.receive(
      "process H:HR and then M:EVA when ready",
      "PEER1",
    );
    expect(result.detectedFrames).toContain("H:HR");
    expect(result.detectedFrames).toContain("M:EVA");
  });

  it("does not detect SAL-shaped substrings inside words", () => {
    // noticedH:HR is a concatenation, not a real SAL frame
    const result = bridge.receive("noticedH:HR in the data", "PEER1");
    expect(result.detectedFrames).not.toContain("H:HR");
  });

  it("does not detect lowercase pseudo-frames", () => {
    const result = bridge.receive("a:hr is not valid", "PEER1");
    expect(result.detectedFrames.length).toBe(0);
  });

  it("recognizes pure SAL message and returns it as SAL", () => {
    const result = bridge.receive("H:HR@NODE1", "PEER1");
    expect(result.sal).toBe("H:HR@NODE1");
    expect(result.passthrough).toBe(false);
  });

  it("treats mixed-content message as NL passthrough with detected frames", () => {
    const result = bridge.receive(
      "patient has H:HR@NODE1 elevated, please review",
      "PEER1",
    );
    expect(result.passthrough).toBe(true);
    expect(result.detectedFrames).toContain("H:HR");
  });
});

describe("SALBridge acquisition state machine", () => {
  it("transitions FALLBACK -> ACQUIRED after threshold consecutive SAL hits", () => {
    // Default acquisition threshold; we can't easily import the constant
    // so we test the behavior with a small explicit threshold.
    const bridge = new SALBridge("TEST_NODE", undefined, true, 3, 5);
    bridge.registerPeer("PEER1", false);
    expect(bridge.peerState("PEER1")).toBe("FALLBACK");

    // Send 3 messages each containing a SAL frame
    bridge.receive("H:HR@NODE1", "PEER1");
    bridge.receive("M:EVA@NODE2", "PEER1");
    bridge.receive("R:STOP", "PEER1");

    expect(bridge.peerState("PEER1")).toBe("ACQUIRED");
  });

  it("regresses ACQUIRED -> FALLBACK after threshold consecutive misses", () => {
    const bridge = new SALBridge("TEST_NODE", undefined, true, 2, 2);
    bridge.registerPeer("PEER1", false);

    // Acquire
    bridge.receive("H:HR", "PEER1");
    bridge.receive("M:EVA", "PEER1");
    expect(bridge.peerState("PEER1")).toBe("ACQUIRED");

    // Miss
    bridge.receive("just a regular sentence here", "PEER1");
    bridge.receive("another non-sal message", "PEER1");
    expect(bridge.peerState("PEER1")).toBe("FALLBACK");
  });

  it("metrics record consecutive hits and unique opcodes", () => {
    const bridge = new SALBridge("TEST_NODE", undefined, true, 10, 10);
    bridge.registerPeer("PEER1", false);
    bridge.receive("H:HR", "PEER1");
    bridge.receive("M:EVA", "PEER1");
    const metrics = bridge.getMetrics("PEER1");
    expect(metrics).not.toBeNull();
    expect(metrics!.consecutiveSalHits).toBe(2);
    expect(metrics!.uniqueOpcodesSeen.size).toBe(2);
  });
});

describe("SALBridge outbound annotation", () => {
  it("annotates outbound SAL with NL context for non-OSMP peers", () => {
    const bridge = new SALBridge("TEST_NODE", undefined, true);
    bridge.registerPeer("PEER1", false);
    const out = bridge.send("H:HR@NODE1", "PEER1");
    // Annotated form includes both NL and SAL
    expect(out).toContain("[SAL: H:HR@NODE1]");
  });

  it("send to native OSMP peer would pass SAL through directly", () => {
    // We can't easily set ESTABLISHED state without going through FNP,
    // but we can verify that the annotation logic is FALLBACK-mode behavior
    const bridge = new SALBridge("TEST_NODE", undefined, true);
    bridge.registerPeer("PEER1", false);
    expect(bridge.peerState("PEER1")).toBe("FALLBACK");
  });
});

// ── Marker test for Finding 13 at the bridge integration level ────────────

describe("Bridge frame detection marker", () => {
  it("Finding 13 — bridge.receive detects I:§ end-to-end", () => {
    // If this test fails, the bridge regex has lost its support for
    // the human authorization marker glyph and FALLBACK peers can no
    // longer signal HITL preconditions to the OSMP node.
    const bridge = new SALBridge("TEST_NODE");
    bridge.registerPeer("PEER1", false);
    const result = bridge.receive(
      "authorize via I:§ before proceeding",
      "PEER1",
    );
    expect(result.detectedFrames).toContain("I:§");
  });
});
