"""
OSMP -- Octid Semantic Mesh Protocol
Tier 2 API: Class-based interface for advanced use.

    from osmp.core import OSMP

    o = OSMP()
    sal = o.encode(["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"])
    text = o.decode(sal)
    result = o.validate(sal)

For the two-function API, use Tier 1 instead:

    from osmp import encode, decode

Patent pending -- inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .protocol import (
        AdaptiveSharedDictionary,
        CompositionResult,
        DependencyRule,
        SALDecoder,
        SALEncoder,
    )


class OSMP:
    """Full-featured OSMP codec with configurable ASD and dependency rules.

    For zero-setup usage, prefer the module-level functions in ``osmp``.
    This class exposes configuration points (custom ASD floor version,
    pre-loaded dependency rules, direct ASD access) that the Tier 1
    functions intentionally hide.
    """

    def __init__(
        self,
        floor_version: str | None = None,
        dependency_rules: list[DependencyRule] | None = None,
    ):
        from .protocol import AdaptiveSharedDictionary, SALDecoder, SALEncoder

        if floor_version is not None:
            self._asd: AdaptiveSharedDictionary = AdaptiveSharedDictionary(floor_version)
        else:
            self._asd = AdaptiveSharedDictionary()

        self._encoder: SALEncoder = SALEncoder(self._asd)
        self._decoder: SALDecoder = SALDecoder(self._asd)
        self._dependency_rules: list[DependencyRule] | None = dependency_rules

    # -- Encoding --------------------------------------------------------

    def encode(self, instructions: list[str]) -> str:
        """Encode a list of opcode strings into a SAL instruction chain."""
        return self._encoder.encode_sequence(instructions)

    def encode_frame(
        self,
        namespace: str,
        opcode: str,
        target: str | None = None,
        query_slot: str | None = None,
        consequence_class: str | None = None,
    ) -> str:
        """Encode a single SAL frame from structured fields."""
        return self._encoder.encode_frame(
            namespace, opcode, target, query_slot,
            consequence_class=consequence_class,
        )

    # -- Decoding --------------------------------------------------------

    def decode(self, sal: str) -> str:
        """Decode a SAL string to natural language. Handles sequences."""
        frames = [f.strip() for f in sal.split(";") if f.strip()]
        if len(frames) <= 1:
            return self._decoder.decode_natural_language(sal)
        return "; ".join(self._decoder.decode_natural_language(f) for f in frames)

    def decode_frame(self, sal: str):
        """Decode a single SAL frame to a DecodedInstruction."""
        return self._decoder.decode_frame(sal)

    # -- Validation ------------------------------------------------------

    def validate(self, sal: str, nl: str = ""):
        """Validate a SAL instruction against all eight composition rules."""
        from .protocol import validate_composition
        return validate_composition(
            sal, nl, self._asd,
            dependency_rules=self._dependency_rules,
        )

    # -- Lookup ----------------------------------------------------------

    def lookup(self, namespace: str, opcode: str) -> str | None:
        """Look up an opcode definition in the ASD."""
        return self._asd.lookup(namespace, opcode)

    # -- Direct access ---------------------------------------------------

    @property
    def asd(self):
        """Direct access to the AdaptiveSharedDictionary instance."""
        return self._asd

    @property
    def encoder(self):
        """Direct access to the SALEncoder instance."""
        return self._encoder

    @property
    def decoder(self):
        """Direct access to the SALDecoder instance."""
        return self._decoder
