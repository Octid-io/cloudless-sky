"""S-station — Crypto / Security."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class SStation(Station):
    namespace = "S"

    VERB_TO_OPCODE = {
        "encrypt":  "ENC",
        "decrypt":  "DEC",
        "sign":     "SIGN",
        "hash":     "HASH",
        "verify":   "VFY",
    }

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()

        if req.verb_lemma in self.VERB_TO_OPCODE:
            out.append(FrameProposal(
                namespace="S", opcode=self.VERB_TO_OPCODE[req.verb_lemma],
                rationale=f"verb '{req.verb_lemma}' -> S:{self.VERB_TO_OPCODE[req.verb_lemma]}",
            ))

        # KEYGEN — generate a key/keypair
        if (("key pair" in raw_low or "keypair" in raw_low or "key" in raw_low and "generate" in raw_low)
            and not any(p.opcode == "KEYGEN" for p in out)):
            out.append(FrameProposal(
                namespace="S", opcode="KEYGEN",
                rationale="keypair generation",
            ))

        # ROTATE — key rotation
        if "rotate" in raw_low and ("key" in raw_low or "credentials" in raw_low):
            out.append(FrameProposal(
                namespace="S", opcode="ROTATE",
                rationale="key rotation",
            ))

        return out
